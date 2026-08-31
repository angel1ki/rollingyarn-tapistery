import multiprocessing
import os

# Linux/macOS only -- Gunicorn relies on os.fork() and doesn't run on Windows.
# For local dev or a Windows host, run `python app.py` instead (uses Waitress).
bind = f"{os.environ.get('HOST', '127.0.0.1')}:{os.environ.get('PORT', 5000)}"

# One worker process per CPU core (plus one) so concurrent CPU-bound requests
# (image resizing/quantizing in /process and /process_pixelated) actually run
# in parallel across cores instead of serializing behind the GIL.
workers = multiprocessing.cpu_count() * 2 + 1

# Generous timeout so a large photo (up to the 20MB upload cap) with a big
# stitch grid doesn't get killed mid-request under load.
timeout = 60
