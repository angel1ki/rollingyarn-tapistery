# 🧵 Tapestry Art

A Flask web app that turns photos into cross-stitch/tapestry patterns (pixel art), ready for printing and stitching. Built in Greek, with large text and simple navigation so it's easy to use for older users.

## Examples

| Star | Heart | Sun |
|---|---|---|
| ![star](static/examples/star_preview.png) | ![heart](static/examples/heart_preview.png) | ![sun](static/examples/sun_preview.png) |

| Flower | House | Kids Playing |
|---|---|---|
| ![flower](static/examples/flower_preview.png) | ![house](static/examples/house_preview.png) | ![kids](static/examples/kids_preview.png) |

## Features

- **Photo upload** and conversion into pixel art / tapestry pattern
- **Adjustable detail level**: grid size (20–1000 stitches) and color count (2–160), so even faces and complex photos stay recognizable
- **Printable pattern** with grid lines, numbered cells per color, and a color/thread legend
- **Download** the preview image or the print-ready pattern
- **User accounts** (register/login) with encrypted passwords
- **"My Art"**: a personal gallery to save, view, and delete your creations
- **Public profile per user** (`/u/<username>`) with a profile photo and the ability to follow other users
- **"Explore" feed** with baseline example designs and other users' creations for inspiration
- **Public landing page** with examples, visible even when logged out

## Tech stack

- Python 3, Flask
- Flask-Login, Flask-SQLAlchemy (SQLite)
- Pillow (pixelation / image processing)
- Werkzeug (password hashing)

## Setup

```bash
git clone <this-repo-url>
cd myproject
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000)

> The built-in Flask server (`python app.py`) is for local/development use only, not for public deployment.

## Project structure

```
app.py                 Main Flask app and routes
models.py               Database models (User, Artwork, Follow)
pixelate.py              Image-to-pixel-art / tapestry pattern logic
generate_examples.py     Generates the example designs in static/examples/
templates/               HTML templates (Jinja2)
static/                  CSS, JS, example artwork images
instance/                SQLite database (created automatically, excluded from git)
```

## Notes

- The database (`instance/app.db`) and user-uploaded images (`static/uploads/`, `static/avatars/`) are not committed to git.
- To regenerate the baseline feed examples: `python generate_examples.py`.
