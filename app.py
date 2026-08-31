import base64
import io
import json
import os
import secrets
import sqlite3
import uuid

import requests
from authlib.integrations.flask_client import OAuth
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import (
    LoginManager, current_user, login_required, login_user, logout_user,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_wtf.csrf import CSRFProtect
from PIL import Image, ImageOps
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

from models import Artwork, Follow, User, db
from pixelate import build_grid, render_pattern, render_preview, to_base64_png
from pixelated import convert_pixelated_photo

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
# Pin instance_path to the script's own directory instead of Flask's default resolution,
# which falls back to the current working directory when run as `python app.py` — that
# would silently create a fresh empty database if this is ever launched from elsewhere.
app = Flask(__name__, instance_relative_config=True, instance_path=os.path.join(APP_ROOT, "instance"))
os.makedirs(app.instance_path, exist_ok=True)

# Trust exactly one reverse proxy hop (e.g. nginx) for the client's real IP/scheme/host.
# Only safe once a real reverse proxy sits in front and overwrites these headers itself —
# see the deployment notes before putting this app directly on the public internet.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

SECRET_KEY_PATH = os.path.join(app.instance_path, "secret_key")
if not os.path.exists(SECRET_KEY_PATH):
    with open(SECRET_KEY_PATH, "wb") as f:
        f.write(os.urandom(32))
os.chmod(SECRET_KEY_PATH, 0o600)  # owner read/write only — this file signs sessions and CSRF tokens
with open(SECRET_KEY_PATH, "rb") as f:
    app.secret_key = f.read()

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(app.instance_path, "app.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB — a generous cap for phone photos

# SESSION_COOKIE_SECURE requires HTTPS to even send the cookie back — keep it off for local
# http://127.0.0.1 development and turn it on via PRODUCTION=true once deployed behind HTTPS.
IS_PRODUCTION = os.environ.get("PRODUCTION", "false").lower() == "true"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = IS_PRODUCTION

CONTENT_SECURITY_POLICY = {
    "default-src": "'self'",
    "object-src": "'none'",
    # Google Fonts stylesheet, plus inline style="background:..." on the color swatches
    "style-src": ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
    "font-src": ["'self'", "https://fonts.gstatic.com"],
    # generated pattern/preview images are shown via data: URIs by static/app.js
    "img-src": ["'self'", "data:"],
}
talisman = Talisman(
    app,
    content_security_policy=CONTENT_SECURITY_POLICY,
    force_https=IS_PRODUCTION,
    strict_transport_security=IS_PRODUCTION,
    session_cookie_secure=IS_PRODUCTION,
)

csrf = CSRFProtect(app)

# In-memory storage is fine for a single process, but resets on every restart and
# won't be shared across multiple instances. Set RATE_LIMIT_STORAGE_URI (e.g.
# redis://localhost:6379) once you deploy more than one instance behind a load
# balancer, or want limits to survive restarts.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per hour"],
    storage_uri=os.environ.get("RATE_LIMIT_STORAGE_URI", "memory://"),
)

db.init_app(app)


# With multiple Gunicorn workers, several processes write to the same SQLite file.
# SQLite's default rollback journal locks the whole database for every write, so a
# concurrent writer fails immediately with "database is locked". WAL lets readers
# keep reading while one writer works, and busy_timeout makes a blocked writer wait
# and retry for up to 5s instead of erroring out straight away.
@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Παρακαλώ συνδεθείτε για να συνεχίσετε."
login_manager.login_message_category = "error"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def _migrate_sqlite_schema():
    """Add columns introduced after the initial schema to an existing db file."""
    db_path = os.path.join(app.instance_path, "app.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user'")
    if cur.fetchone() is None:
        conn.close()
        return
    cur.execute("PRAGMA table_info(user)")
    existing_cols = {row[1] for row in cur.fetchall()}
    if "email" not in existing_cols:
        cur.execute("ALTER TABLE user ADD COLUMN email VARCHAR(255)")
    if "google_id" not in existing_cols:
        cur.execute("ALTER TABLE user ADD COLUMN google_id VARCHAR(255)")
    conn.commit()
    conn.close()


with app.app_context():
    _migrate_sqlite_schema()
    db.create_all()

# Google OAuth is optional: the app works fully without it, the "Continue
# with Google" button just stays hidden until credentials are configured.
# Create a Google Cloud OAuth 2.0 Client ID (Web application), add
# http://<your-host>/login/google/callback as an authorized redirect URI,
# then save the credentials to instance/google_oauth.json as:
#   {"client_id": "...", "client_secret": "..."}
GOOGLE_OAUTH_PATH = os.path.join(app.instance_path, "google_oauth.json")
GOOGLE_OAUTH_CONFIG = None
if os.path.exists(GOOGLE_OAUTH_PATH):
    with open(GOOGLE_OAUTH_PATH) as f:
        GOOGLE_OAUTH_CONFIG = json.load(f)

oauth = OAuth(app)
if GOOGLE_OAUTH_CONFIG:
    oauth.register(
        name="google",
        client_id=GOOGLE_OAUTH_CONFIG["client_id"],
        client_secret=GOOGLE_OAUTH_CONFIG["client_secret"],
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

UPLOAD_ROOT = os.path.join(app.static_folder, "uploads")


def user_upload_dir(user_id):
    path = os.path.join(UPLOAD_ROOT, str(user_id))
    os.makedirs(path, exist_ok=True)
    return path


@app.errorhandler(RequestEntityTooLarge)
def handle_upload_too_large(e):
    message = "Το αρχείο είναι πολύ μεγάλο (μέγιστο 20MB)."
    if request.path in ("/process", "/process_pixelated", "/save"):
        return jsonify({"error": message}), 413
    flash(message, "error")
    return redirect(request.referrer or url_for("index")), 413


SYMBOL_MAX_GRID = 200  # above this, numbered stitch charts aren't practical to read or draw quickly


EXAMPLE_ARTWORKS = [
    {"title": "Αστέρι", "preview": "examples/star_preview.png", "pattern": "examples/star_pattern.png", "difficulty": "easy"},
    {"title": "Καρδιά", "preview": "examples/heart_preview.png", "pattern": "examples/heart_pattern.png", "difficulty": "easy"},
    {"title": "Ήλιος", "preview": "examples/sun_preview.png", "pattern": "examples/sun_pattern.png", "difficulty": "easy"},
    {"title": "Λουλούδι", "preview": "examples/flower_preview.png", "pattern": "examples/flower_pattern.png", "difficulty": "easy"},
    {"title": "Σπίτι", "preview": "examples/house_preview.png", "pattern": "examples/house_pattern.png", "difficulty": "easy"},
    {"title": "Παιδιά που παίζουν", "preview": "examples/kids_preview.png", "pattern": "examples/kids_pattern.png", "difficulty": "easy"},
    {"title": "Γάτα", "preview": "examples/cat_preview.png", "pattern": "examples/cat_pattern.png", "difficulty": "medium"},
    {"title": "Βουνό", "preview": "examples/mountain_preview.png", "pattern": "examples/mountain_pattern.png", "difficulty": "medium"},
    {"title": "Ιστιοφόρο", "preview": "examples/sailboat_preview.png", "pattern": "examples/sailboat_pattern.png", "difficulty": "medium"},
    {"title": "Παπαγάλος", "preview": "examples/parrot_preview.png", "pattern": "examples/parrot_pattern.png", "difficulty": "medium"},
    {"title": "Κάστρο", "preview": "examples/castle_preview.png", "pattern": "examples/castle_pattern.png", "difficulty": "medium"},
    {"title": "Πεταλούδα", "preview": "examples/butterfly_preview.png", "pattern": "examples/butterfly_pattern.png", "difficulty": "hard"},
    {"title": "Ηλιοβασίλεμα", "preview": "examples/sunset_preview.png", "pattern": "examples/sunset_pattern.png", "difficulty": "hard"},
    {"title": "Παγώνι", "preview": "examples/peacock_preview.png", "pattern": "examples/peacock_pattern.png", "difficulty": "hard"},
    {"title": "Λιοντάρι", "preview": "examples/lion_preview.png", "pattern": "examples/lion_pattern.png", "difficulty": "hard"},
]

EXAMPLES_BY_DIFFICULTY = {
    "easy": [e for e in EXAMPLE_ARTWORKS if e["difficulty"] == "easy"],
    "medium": [e for e in EXAMPLE_ARTWORKS if e["difficulty"] == "medium"],
    "hard": [e for e in EXAMPLE_ARTWORKS if e["difficulty"] == "hard"],
}


def _is_valid_email(value):
    return "@" in value and "." in value.split("@")[-1] and " " not in value


@app.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("explore"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not username or not email or not password:
            flash("Συμπληρώστε όνομα χρήστη, email και κωδικό.", "error")
        elif not _is_valid_email(email):
            flash("Το email δεν είναι έγκυρο.", "error")
        elif password != confirm:
            flash("Οι κωδικοί δεν ταιριάζουν.", "error")
        elif len(password) < 8:
            flash("Ο κωδικός πρέπει να έχει τουλάχιστον 8 χαρακτήρες.", "error")
        elif User.query.filter_by(username=username).first():
            flash("Αυτό το όνομα χρήστη υπάρχει ήδη.", "error")
        elif User.query.filter_by(email=email).first():
            flash("Υπάρχει ήδη λογαριασμός με αυτό το email.", "error")
        else:
            user = User(username=username, email=email, password_hash=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("explore"))

    return render_template("register.html", google_configured=bool(GOOGLE_OAUTH_CONFIG))


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("explore"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        identifier_lower = identifier.lower()
        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier_lower)
        ).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("explore"))
        flash("Λάθος στοιχεία σύνδεσης.", "error")

    return render_template("login.html", google_configured=bool(GOOGLE_OAUTH_CONFIG))


@app.route("/login/google")
def login_google():
    if not GOOGLE_OAUTH_CONFIG:
        abort(404)
    redirect_uri = url_for("login_google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@app.route("/login/google/callback")
def login_google_callback():
    if not GOOGLE_OAUTH_CONFIG:
        abort(404)

    token = oauth.google.authorize_access_token()
    userinfo = token.get("userinfo") or oauth.google.userinfo()
    google_id = userinfo["sub"]
    email = userinfo.get("email", "").strip().lower()
    picture_url = userinfo.get("picture")

    user = User.query.filter_by(google_id=google_id).first()
    if user is None and email:
        user = User.query.filter_by(email=email).first()

    if user is None:
        base_username = (email.split("@")[0] if email else "user").lower()
        base_username = "".join(c for c in base_username if c.isalnum()) or "user"
        username = base_username
        suffix = 1
        while User.query.filter_by(username=username).first() is not None:
            suffix += 1
            username = f"{base_username}{suffix}"

        user = User(
            username=username,
            email=email or None,
            google_id=google_id,
            password_hash=generate_password_hash(secrets.token_urlsafe(32)),
        )
        db.session.add(user)
        db.session.commit()  # assign a real id before we might save an avatar file below
    elif user.google_id is None:
        user.google_id = google_id
        db.session.commit()

    if user.avatar_path is None and picture_url:
        try:
            resp = requests.get(picture_url, timeout=5)
            resp.raise_for_status()
            image = Image.open(io.BytesIO(resp.content))
            image = ImageOps.exif_transpose(image).convert("RGB")
            side = min(image.size)
            left, top = (image.width - side) // 2, (image.height - side) // 2
            image = image.crop((left, top, left + side, top + side)).resize(
                (AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS
            )
            avatar_dir = os.path.join(app.static_folder, "avatars")
            os.makedirs(avatar_dir, exist_ok=True)
            filename = f"{user.id}.png"
            image.save(os.path.join(avatar_dir, filename))
            user.avatar_path = f"avatars/{filename}"
            db.session.commit()
        except Exception:
            pass

    login_user(user)
    return redirect(url_for("explore"))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("explore"))
    return render_template("landing.html", examples_by_difficulty=EXAMPLES_BY_DIFFICULTY)


@app.route("/create")
@login_required
def create():
    return render_template("index.html")


@app.route("/profile")
@login_required
def profile():
    artworks = (
        Artwork.query.filter_by(user_id=current_user.id)
        .order_by(Artwork.created_at.desc())
        .all()
    )
    return render_template("profile.html", artworks=artworks)


@app.route("/u/<username>")
@login_required
def public_profile(username):
    profile_user = User.query.filter_by(username=username).first()
    if profile_user is None:
        abort(404)

    artworks = (
        Artwork.query.filter_by(user_id=profile_user.id)
        .order_by(Artwork.created_at.desc())
        .all()
    )
    is_own = profile_user.id == current_user.id
    is_following = (
        not is_own
        and Follow.query.filter_by(follower_id=current_user.id, followed_id=profile_user.id).first() is not None
    )
    followers_count = Follow.query.filter_by(followed_id=profile_user.id).count()
    following_count = Follow.query.filter_by(follower_id=profile_user.id).count()

    return render_template(
        "public_profile.html",
        profile_user=profile_user,
        artworks=artworks,
        is_own=is_own,
        is_following=is_following,
        followers_count=followers_count,
        following_count=following_count,
    )


@app.route("/u/<username>/follow", methods=["POST"])
@login_required
def follow_user(username):
    target = User.query.filter_by(username=username).first()
    if target is None:
        abort(404)
    if target.id != current_user.id:
        exists = Follow.query.filter_by(follower_id=current_user.id, followed_id=target.id).first()
        if exists is None:
            db.session.add(Follow(follower_id=current_user.id, followed_id=target.id))
            db.session.commit()
    return redirect(url_for("public_profile", username=username))


@app.route("/u/<username>/unfollow", methods=["POST"])
@login_required
def unfollow_user(username):
    target = User.query.filter_by(username=username).first()
    if target is None:
        abort(404)
    Follow.query.filter_by(follower_id=current_user.id, followed_id=target.id).delete()
    db.session.commit()
    return redirect(url_for("public_profile", username=username))


@app.route("/explore")
@login_required
def explore():
    artworks = Artwork.query.order_by(Artwork.created_at.desc()).limit(60).all()
    return render_template("explore.html", artworks=artworks, examples_by_difficulty=EXAMPLES_BY_DIFFICULTY)


AVATAR_SIZE = 300


@app.route("/profile/photo", methods=["POST"])
@login_required
def update_avatar():
    file = request.files.get("avatar")
    if not file or file.filename == "":
        flash("Παρακαλώ επιλέξτε μια φωτογραφία.", "error")
        return redirect(url_for("public_profile", username=current_user.username))

    try:
        image = Image.open(file.stream)
        image = ImageOps.exif_transpose(image).convert("RGB")
    except Exception:
        flash("Το αρχείο δεν είναι έγκυρη εικόνα.", "error")
        return redirect(url_for("public_profile", username=current_user.username))

    side = min(image.size)
    left = (image.width - side) // 2
    top = (image.height - side) // 2
    image = image.crop((left, top, left + side, top + side)).resize(
        (AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS
    )

    avatar_dir = os.path.join(app.static_folder, "avatars")
    os.makedirs(avatar_dir, exist_ok=True)
    filename = f"{current_user.id}.png"
    image.save(os.path.join(avatar_dir, filename))

    current_user.avatar_path = f"avatars/{filename}"
    db.session.commit()
    flash("Η φωτογραφία προφίλ ενημερώθηκε.", "success")
    return redirect(url_for("public_profile", username=current_user.username))


@app.route("/artwork/<int:artwork_id>")
@login_required
def view_artwork(artwork_id):
    artwork = Artwork.query.get(artwork_id)
    if artwork is None:
        abort(404)
    legend = json.loads(artwork.legend_json)
    is_owner = artwork.user_id == current_user.id
    return render_template("artwork.html", artwork=artwork, legend=legend, is_owner=is_owner)


@app.route("/artwork/<int:artwork_id>/delete", methods=["POST"])
@login_required
def delete_artwork(artwork_id):
    artwork = Artwork.query.filter_by(id=artwork_id, user_id=current_user.id).first()
    if artwork is None:
        abort(404)
    for rel_path in (artwork.preview_path, artwork.pattern_path):
        full_path = os.path.join(app.static_folder, rel_path)
        if os.path.exists(full_path):
            os.remove(full_path)
    db.session.delete(artwork)
    db.session.commit()
    flash("Το έργο διαγράφηκε.", "success")
    return redirect(url_for("profile"))


@app.route("/save", methods=["POST"])
@login_required
def save_artwork():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "Χωρίς τίτλο").strip()[:120] or "Χωρίς τίτλο"
    preview_b64 = data.get("preview_image")
    pattern_b64 = data.get("pattern_image")
    legend = data.get("legend")
    grid_w = data.get("grid_w")
    grid_h = data.get("grid_h")

    if not preview_b64 or not pattern_b64 or not legend or not grid_w or not grid_h:
        return jsonify({"error": "Λείπουν δεδομένα σχεδίου."}), 400

    artwork_uuid = uuid.uuid4().hex
    user_dir = user_upload_dir(current_user.id)
    preview_name = f"{artwork_uuid}_preview.png"
    pattern_name = f"{artwork_uuid}_pattern.png"

    try:
        with open(os.path.join(user_dir, preview_name), "wb") as f:
            f.write(base64.b64decode(preview_b64))
        with open(os.path.join(user_dir, pattern_name), "wb") as f:
            f.write(base64.b64decode(pattern_b64))
    except Exception:
        return jsonify({"error": "Δεν ήταν δυνατή η αποθήκευση της εικόνας."}), 400

    artwork = Artwork(
        user_id=current_user.id,
        title=title,
        preview_path=f"uploads/{current_user.id}/{preview_name}",
        pattern_path=f"uploads/{current_user.id}/{pattern_name}",
        legend_json=json.dumps(legend),
        grid_w=int(grid_w),
        grid_h=int(grid_h),
    )
    db.session.add(artwork)
    db.session.commit()
    return jsonify({"ok": True, "artwork_id": artwork.id})


@app.route("/process", methods=["POST"])
@login_required
def process():
    file = request.files.get("photo")
    if not file or file.filename == "":
        return jsonify({"error": "Δεν επιλέχθηκε φωτογραφία."}), 400

    try:
        grid_w = int(request.form.get("grid_w", 200))
        num_colors = int(request.form.get("num_colors", 40))
        show_symbols = request.form.get("show_symbols") == "true"
    except ValueError:
        return jsonify({"error": "Μη έγκυρες ρυθμίσεις."}), 400

    grid_w = max(10, min(1000, grid_w))
    num_colors = max(2, min(160, num_colors))

    try:
        image = Image.open(file.stream)
    except Exception:
        return jsonify({"error": "Το αρχείο δεν είναι έγκυρη εικόνα."}), 400

    grid_rgb, grid_symbols, legend, gw, gh = build_grid(image, grid_w, num_colors)
    preview_img = render_preview(grid_rgb, gw, gh)
    symbols_disabled = show_symbols and grid_w > SYMBOL_MAX_GRID
    effective_show_symbols = show_symbols and not symbols_disabled
    pattern_img = render_pattern(grid_rgb, grid_symbols, gw, gh, effective_show_symbols)

    return jsonify({
        "preview_image": to_base64_png(preview_img),
        "pattern_image": to_base64_png(pattern_img),
        "legend": legend,
        "grid_w": gw,
        "grid_h": gh,
        "symbols_disabled": symbols_disabled,
    })

@app.route("/pixelated_photo_conversion")
@login_required
def create_pixelated():
    return render_template("pixelated_photo_conversion.html")


@app.route("/process_pixelated", methods=["POST"])
@login_required
def process_pixelated():
    file = request.files.get("photo")
    if not file or file.filename == "":
        return jsonify({"error": "Δεν επιλέχθηκε φωτογραφία."}), 400

    try:
        grid_w = int(request.form.get("grid_w", 80))
        num_colors = int(request.form.get("num_colors", 12))
        show_symbols = request.form.get("show_symbols") == "true"
    except ValueError:
        return jsonify({"error": "Μη έγκυρες ρυθμίσεις."}), 400

    grid_w = max(10, min(1000, grid_w))
    num_colors = max(2, min(160, num_colors))

    try:
        image = Image.open(file.stream)
    except Exception:
        return jsonify({"error": "Το αρχείο δεν είναι έγκυρη εικόνα."}), 400

    symbols_disabled = show_symbols and grid_w > SYMBOL_MAX_GRID
    effective_show_symbols = show_symbols and not symbols_disabled

    small, pattern_img, legend = convert_pixelated_photo(
        image, grid_w, n_colors=num_colors, show_symbols=effective_show_symbols
    )
    gw, gh = small.size
    preview_img = small.resize((gw * 14, gh * 14), Image.NEAREST)

    return jsonify({
        "preview_image": to_base64_png(preview_img),
        "pattern_image": to_base64_png(pattern_img),
        "legend": legend,
        "grid_w": gw,
        "grid_h": gh,
        "symbols_disabled": symbols_disabled,
    })


if __name__ == "__main__":
    from waitress import serve

    serve(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 5000)))
