"""
Sunset — a photograph compiled into a tapestry chart
====================================================

A photograph of the sun going down over the Greek sea, turned by code into
something a person can stitch by hand in yarn.

The program does not filter the photograph; it *compiles* it. Three steps:

  1. RESAMPLE.  The 12-megapixel photograph is resampled with a BOX filter down
     to an exact stitch grid, so each cell is the true average of the thousands
     of pixels beneath it. 12,192,768 pixels become 33,440 stitches. The grid,
     not the camera, decides the resolution.

  2. REDUCE.  A median-cut algorithm searches the photograph for the N yarn
     colours that best describe it, repeatedly splitting the colour space along
     its widest axis. Nothing is dithered: a stitch is one solid colour, so the
     smooth gradient of the sky has to survive as bands of flat thread.

  3. CHART.  Each colour is numbered by how often it occurs, so colour 1 is the
     one you will stitch most, and every cell is labelled with its number.

The interesting constraint is the medium. A screen has sixteen million colours
and a photograph leans on all of them; a sky like this one is almost entirely
gradient. Yarn has none of that. The image has to be rebuilt out of a few dozen
flat tones, and what survives that reduction — the sun, its reflection, the
ridge of the mountains — is what the photograph was actually about.

Outputs (written next to this script):
    sunset_artwork.png   the artwork: 190 x 142 stitches, rendered as blocks
    sunset_chart.png     the working chart: gridlines + a number in every cell
    sunset_legend.txt    each colour, its hex code, and its stitch count

Deterministic: median cut is deterministic and dithering is off, so every run
on the same photograph is byte-for-byte identical. No seed is needed.

The exhibited piece is one photograph run through this program, but the program
is not specific to it: hand it any photograph and it will compile that instead.

Dependencies: Pillow      (pip install pillow)
Asset:        IMG_1716.jpg — the source photograph, beside this script

Run:
    python sunset_tapestry.py                    # reproduces the exhibited artwork
    python sunset_tapestry.py my_photo.jpg       # any photograph, whole frame
    python sunset_tapestry.py my_photo.jpg --stitches 240 --colours 40
    python sunset_tapestry.py my_photo.jpg --crop 0.2 0.45 0.78 0.99
"""

import argparse
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

PHOTO = "IMG_1716.jpg"  # source photograph; override with a command-line argument

# Framing, as fractions of the original photograph (left, top, right, bottom).
# The photograph is mostly empty sky, and at this stitch count the sun is only a
# few cells across -- wide, it averages away into the surrounding glow entirely.
# Cropping in is what lets the sun survive the reduction as a distinct disc.
CROP = (0.20, 0.45, 0.78, 0.99)

STITCHES_WIDE = 190   # chart width, in stitches
COLOURS = 34          # yarn colours the photograph is reduced to
CELL = 18             # pixels per stitch when rendering (190 * 18 = 3420px)
BOLD_EVERY = 10       # heavier gridline every N stitches, as on paper charts


# --- 1 & 2. resample, then reduce to yarn colours ---------------------------
def build_chart(photo_path, stitches_wide, colours, crop=(0.0, 0.0, 1.0, 1.0)):
    """Compile a photograph into a grid of stitches.

    BOX resampling averages every source pixel falling inside a cell, which is
    what makes this work on a photograph: fine detail is integrated away rather
    than point-sampled, so the chart is a faithful reduction and not a
    subsample of whatever pixels happened to land on the grid lines.
    """
    image = Image.open(photo_path)
    image = ImageOps.exif_transpose(image).convert("RGB")  # honour camera rotation

    W, H = image.size
    left, top, right, bottom = crop
    image = image.crop((round(W * left), round(H * top),
                        round(W * right), round(H * bottom)))

    w, h = image.size
    stitches_high = max(1, round(stitches_wide * h / w))
    small = image.resize((stitches_wide, stitches_high), Image.Resampling.BOX)

    # Median cut picks the palette from the photograph itself. Dithering is
    # off: it would scatter lone off-colour stitches through the sky, which is
    # invisible on a screen but unstitchable in yarn.
    reduced = small.quantize(colors=colours,
                             method=Image.Quantize.MEDIANCUT,
                             dither=Image.Dither.NONE).convert("RGB")

    raw = reduced.tobytes()
    cells = [tuple(raw[i:i + 3]) for i in range(0, len(raw), 3)]

    # Number the colours by frequency, so colour 1 is the one you stitch most.
    counts = Counter(cells)
    order = [rgb for rgb, _ in counts.most_common()]
    symbol = {rgb: str(i + 1) for i, rgb in enumerate(order)}

    grid = [cells[r * stitches_wide:(r + 1) * stitches_wide]
            for r in range(stitches_high)]
    legend = [(symbol[rgb], rgb, counts[rgb]) for rgb in order]
    return grid, legend, symbol


# --- 3. render --------------------------------------------------------------
def render_artwork(grid):
    """One solid block per stitch."""
    h, w = len(grid), len(grid[0])
    img = Image.new("RGB", (w * CELL, h * CELL))
    draw = ImageDraw.Draw(img)
    for r, row in enumerate(grid):
        for c, rgb in enumerate(row):
            draw.rectangle([c * CELL, r * CELL, (c + 1) * CELL, (r + 1) * CELL],
                           fill=rgb)
    return img


def load_font(size):
    for name in ("DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_chart(grid, symbol):
    """The working chart: gridlines, plus each cell's colour number."""
    img = render_artwork(grid)
    draw = ImageDraw.Draw(img)
    h, w = len(grid), len(grid[0])
    font = load_font(int(CELL * 0.55))

    for c in range(w + 1):
        x = c * CELL
        draw.line([x, 0, x, h * CELL], fill=(60, 60, 60),
                  width=2 if c % BOLD_EVERY == 0 else 1)
    for r in range(h + 1):
        y = r * CELL
        draw.line([0, y, w * CELL, y], fill=(60, 60, 60),
                  width=2 if r % BOLD_EVERY == 0 else 1)

    box = {}  # glyph metrics cache: few distinct numbers, tens of thousands of cells
    for r, row in enumerate(grid):
        for c, rgb in enumerate(row):
            s = symbol[rgb]
            if s not in box:
                b = draw.textbbox((0, 0), s, font=font)
                box[s] = (b[2] - b[0], b[3] - b[1], b[0], b[1])
            tw, th, bx, by = box[s]
            # Dark ink on light yarn, light ink on dark, by perceived brightness.
            luma = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
            draw.text((c * CELL + (CELL - tw) / 2 - bx,
                       r * CELL + (CELL - th) / 2 - by),
                      s, fill=(0, 0, 0) if luma > 150 else (255, 255, 255),
                      font=font)
    return img


def main():
    here = Path(__file__).parent
    ap = argparse.ArgumentParser(
        description="Compile a photograph into a tapestry chart. "
                    "With no arguments, reproduces the exhibited artwork.")
    ap.add_argument("photo", nargs="?",
                    help=f"any photograph (default: {PHOTO}, the exhibited piece)")
    ap.add_argument("--stitches", type=int, default=STITCHES_WIDE,
                    help=f"chart width in stitches (default {STITCHES_WIDE})")
    ap.add_argument("--colours", "--colors", dest="colours", type=int, default=COLOURS,
                    help=f"number of yarn colours (default {COLOURS})")
    ap.add_argument("--crop", type=float, nargs=4, metavar=("L", "T", "R", "B"),
                    help="crop as fractions of the photograph, e.g. 0.2 0.45 0.78 0.99")
    args = ap.parse_args()

    if args.photo:
        # Someone else's photograph: use the whole frame unless they crop it
        # themselves. The exhibited crop belongs to the sunset alone.
        photo, name = Path(args.photo), Path(args.photo).stem
        crop = tuple(args.crop) if args.crop else (0.0, 0.0, 1.0, 1.0)
    else:
        photo, name = here / PHOTO, "sunset"
        crop = tuple(args.crop) if args.crop else CROP

    if not photo.exists():
        raise SystemExit(f"photograph not found: {photo}\n"
                         f"place {PHOTO} beside this script, or pass a path")

    grid, legend, symbol = build_chart(photo, args.stitches, args.colours, crop)

    render_artwork(grid).save(here / f"{name}_artwork.png")
    render_chart(grid, symbol).save(here / f"{name}_chart.png")

    lines = [f"{'No.':>4}  {'HEX':<9}  Stitches", "-" * 28]
    lines += [f"{s:>4}  #{r:02X}{g:02X}{b:02X}  {n:>8}" for s, (r, g, b), n in legend]
    total = sum(n for _, _, n in legend)
    lines += ["-" * 28, f"{total} stitches, {len(legend)} colours"]
    (here / f"{name}_legend.txt").write_text("\n".join(lines), encoding="utf-8")

    print(f"{len(grid[0])} x {len(grid)} stitches, {total} total, {len(legend)} colours")
    print(f"wrote {name}_artwork.png, {name}_chart.png, {name}_legend.txt")


if __name__ == "__main__":
    main()
