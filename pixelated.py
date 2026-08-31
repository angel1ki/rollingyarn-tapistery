"""
pixelated.py
------------
Converts a photo -- even one that is ALREADY pixelated -- into a clean
tapestry / cross-stitch chart: a grid where every cell is exactly one stitch
in one solid colour.

Why "already pixelated" needs care:
    A source image that is already blocky has its OWN pixel/block size that
    almost never lines up with the number of stitches you want. If you just
    "pixelate" it again you get ugly half-blocks along the seams. The fix is
    to RESAMPLE it down to the exact stitch grid with a BOX filter (which
    averages the source pixels that fall inside each new cell). That
    re-pixelates cleanly and ignores whatever block size the source happened
    to have.

Ported from the standalone tapestry_pixelate.py CLI script, adapted to work
on already-open PIL Images and return in-memory results (no argparse, no
file I/O) so it can run inside a Flask request.
"""

from collections import Counter

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


def load_font(size):
    for name in (
        "DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Colour science: sRGB -> CIELAB, so "nearest yarn colour" matches how the eye
# sees closeness, not raw RGB numbers (which are perceptually lumpy).
# ---------------------------------------------------------------------------
def srgb_to_lab(rgb):
    """rgb: array (..., 3) with values 0-255  ->  Lab array (..., 3)."""
    rgb = np.asarray(rgb, dtype=np.float64) / 255.0
    linear = np.where(rgb > 0.04045, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)
    M = np.array([[0.4124, 0.3576, 0.1805],
                  [0.2126, 0.7152, 0.0722],
                  [0.0193, 0.1192, 0.9505]])
    xyz = linear @ M.T
    xyz = xyz / np.array([0.95047, 1.0, 1.08883])  # normalise to D65 white
    eps, kappa = 216 / 24389, 24389 / 27
    f = np.where(xyz > eps, np.cbrt(xyz), (kappa * xyz + 16) / 116)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def map_to_palette(small_rgb, palette_rgb):
    """Snap every cell to its nearest palette colour (deltaE in Lab)."""
    h, w, _ = small_rgb.shape
    pix = srgb_to_lab(small_rgb.reshape(-1, 3))
    pal = srgb_to_lab(palette_rgb)
    dist = np.linalg.norm(pix[:, None, :] - pal[None, :, :], axis=2)
    idx = dist.argmin(axis=1)
    mapped = np.asarray(palette_rgb, dtype=np.uint8)[idx].reshape(h, w, 3)
    return mapped


def auto_reduce(img_small, n_colors):
    """Automatic palette reduction with median cut."""
    q = img_small.convert("RGB").quantize(colors=n_colors, method=Image.MEDIANCUT)
    return q.convert("RGB")


# ---------------------------------------------------------------------------
# Chart building
# ---------------------------------------------------------------------------
def build_small(image: Image.Image, stitches_wide, n_colors=None, palette=None):
    """image: an already-open PIL Image (already-pixelated or not).
    Resamples down to the exact stitch grid with a BOX filter, then reduces
    colours either to `palette` (nearest match in CIELAB) or to `n_colors`
    (automatic median-cut reduction)."""
    image = ImageOps.exif_transpose(image).convert("RGB")
    w, h = image.size
    stitches_high = max(1, round(stitches_wide * h / w))

    small = image.resize((stitches_wide, stitches_high), Image.BOX)

    if palette is not None:
        arr = np.array(small)
        small = Image.fromarray(map_to_palette(arr, np.array(palette, dtype=np.uint8)))
    elif n_colors is not None:
        small = auto_reduce(small, n_colors)

    return small


def render_preview(small, cell=14):
    """Enlarge with NEAREST (crisp blocks) and draw a cross-stitch style grid."""
    sw, sh = small.size
    W, H = sw * cell, sh * cell
    big = small.resize((W, H), Image.NEAREST).convert("RGB")
    draw = ImageDraw.Draw(big)

    for x in range(0, W + 1, cell):                     # thin gridlines
        draw.line([(x, 0), (x, H)], fill=(190, 190, 190), width=1)
    for y in range(0, H + 1, cell):
        draw.line([(0, y), (W, y)], fill=(190, 190, 190), width=1)
    for x in range(0, W + 1, cell * 10):                # bold every 10 stitches
        draw.line([(x, 0), (x, H)], fill=(30, 30, 30), width=2)
    for y in range(0, H + 1, cell * 10):
        draw.line([(0, y), (W, y)], fill=(30, 30, 30), width=2)

    return big


def build_legend(small):
    """Legend (colour + count, most common first) and a same-shaped 2D grid
    of symbol strings ("1", "2", ...) -- one number per distinct colour, so
    numbered stitch charts can label every cell."""
    sw, sh = small.size
    pixels = list(small.getdata())
    counts = Counter(pixels)
    ordered = [rgb for rgb, _ in counts.most_common()]
    symbol_by_rgb = {rgb: str(i + 1) for i, rgb in enumerate(ordered)}

    legend = [
        {
            "symbol": symbol_by_rgb[rgb],
            "hex": "#%02x%02x%02x" % rgb,
            "rgb": rgb,
            "count": counts[rgb],
        }
        for rgb in ordered
    ]
    grid_symbols = [
        [symbol_by_rgb[pixels[r * sw + c]] for c in range(sw)]
        for r in range(sh)
    ]
    return legend, grid_symbols


def render_pattern(small, grid_symbols, show_symbols, cell=14):
    """render_preview(small, cell) plus, when show_symbols is True, the
    stitch-count number from grid_symbols drawn centred on every cell."""
    img = render_preview(small, cell=cell)
    if not show_symbols:
        return img

    draw = ImageDraw.Draw(img)
    font = load_font(max(6, int(cell * 0.6)))
    sw, sh = small.size
    pixels = list(small.getdata())

    bbox_cache = {}
    for r in range(sh):
        for c in range(sw):
            rgb = pixels[r * sw + c]
            luminance = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
            text_color = (0, 0, 0) if luminance > 150 else (255, 255, 255)
            symbol = grid_symbols[r][c]
            if symbol not in bbox_cache:
                bbox = draw.textbbox((0, 0), symbol, font=font)
                bbox_cache[symbol] = (
                    bbox[2] - bbox[0], bbox[3] - bbox[1], bbox[0], bbox[1]
                )
            tw, th, bx, by = bbox_cache[symbol]
            x0, y0 = c * cell, r * cell
            draw.text(
                (x0 + (cell - tw) / 2 - bx, y0 + (cell - th) / 2 - by),
                symbol, fill=text_color, font=font,
            )
    return img


def convert_pixelated_photo(image: Image.Image, stitches_wide, n_colors=None, palette=None,
                             cell=14, show_symbols=False):
    """End-to-end: photo (already pixelated or not) -> tapestry chart.
    Returns (small, pattern_img, legend):
        small       -> 1 px per stitch (the raw chart data)
        pattern_img -> big blocks + grid lines every 10 stitches, with
                       stitch-count numbers if show_symbols is True
        legend      -> list of {symbol, hex, rgb, count}, most-used colour first
    """
    small = build_small(image, stitches_wide, n_colors=n_colors, palette=palette)
    legend, grid_symbols = build_legend(small)
    pattern_img = render_pattern(small, grid_symbols, show_symbols, cell=cell)
    return small, pattern_img, legend
