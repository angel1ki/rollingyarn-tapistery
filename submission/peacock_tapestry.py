"""
Peacock -- an algorithmic tapestry chart
========================================

A peacock drawn entirely in code, then compiled into a chart that a person can
stitch by hand in yarn.

The program has two halves, and the second is the interesting one:

  1. DRAW.  The bird is described only as geometry -- the eleven tail feathers
     are placed by sweeping an angle across a half-circle, and every feather is
     five concentric ellipses. Nothing is traced, photographed or imported.

  2. COMPILE TO STITCHES.  The drawing is resampled with a BOX filter down to an
     exact stitch grid, so each cell averages the pixels beneath it, and every
     cell is then snapped to the nearest colour in a fixed eleven-colour yarn
     palette. The result is a chart: one cell, one stitch, one colour, plus a
     numbered legend counting how many stitches each colour needs.

The output is therefore not only a picture. It is a set of instructions -- the
last compilation step happens on fabric, by hand, and takes weeks.

Outputs (written next to this script):
    peacock_artwork.png   the artwork: 190 x 176 stitches, rendered as blocks
    peacock_chart.png     the working chart: gridlines + a number in every cell
    peacock_legend.txt    each colour, its hex code, and its stitch count

Deterministic: there is no randomness anywhere, so every run is identical.

Dependencies: Pillow      (pip install pillow)
Run:          python peacock_tapestry.py
"""

import math
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# --- the yarn palette -------------------------------------------------------
# Eleven colours; every stitch in the finished piece is exactly one of these.
BACKGROUND = (250, 245, 235)
TAIL_OUTER = (40, 110, 90)
TAIL_MID = (60, 150, 120)
EYE_GOLD = (210, 175, 60)
EYE_BLUE = (40, 90, 160)
EYE_CENTER = (30, 40, 90)
BODY = (35, 95, 150)
BODY_DARK = (25, 70, 115)
HEAD = (45, 110, 170)
BEAK = (60, 50, 45)
EYE = (20, 15, 15)

PALETTE = [BACKGROUND, TAIL_OUTER, TAIL_MID, EYE_GOLD, EYE_BLUE, EYE_CENTER,
           BODY, BODY_DARK, HEAD, BEAK, EYE]

STITCHES_WIDE = 190   # chart width, in stitches
CELL = 18             # pixels per stitch when rendering (190 * 18 = 3420px)
BOLD_EVERY = 10       # heavier gridline every N stitches, as on paper charts


# --- 1. draw ----------------------------------------------------------------
def draw_peacock():
    """The bird as pure geometry: ellipses, lines and one polygon."""
    w, h = 700, 650
    img = Image.new("RGB", (w, h), BACKGROUND)
    draw = ImageDraw.Draw(img)
    cx, cy = 350, 430

    # Eleven feather tips, swept across a half-circle above the body.
    n_feathers = 11
    tips = []
    for i in range(n_feathers):
        angle = math.pi * (0.12 + 0.76 * i / (n_feathers - 1))
        tips.append((cx + 260 * math.cos(angle),
                     cy - 260 * math.sin(angle) - 30))

    # Quills first: thick strokes from the body out to each tip, so the fan
    # reads as attached to the bird rather than floating above it.
    for tip in tips:
        draw.line([(cx, cy - 15), tip], fill=TAIL_OUTER, width=48)
    draw.ellipse([cx - 70, cy - 65, cx + 70, cy + 15], fill=TAIL_OUTER)

    # Each eye is five concentric ellipses, drawn largest to smallest.
    for fx, fy in tips:
        draw.ellipse([fx - 38, fy - 55, fx + 38, fy + 55], fill=TAIL_OUTER)
        draw.ellipse([fx - 28, fy - 42, fx + 28, fy + 30], fill=TAIL_MID)
        draw.ellipse([fx - 20, fy - 30, fx + 20, fy + 18], fill=EYE_GOLD)
        draw.ellipse([fx - 13, fy - 22, fx + 13, fy + 10], fill=EYE_BLUE)
        draw.ellipse([fx - 6, fy - 14, fx + 6, fy + 2], fill=EYE_CENTER)

    # Body, then a darker overlapping ellipse for the shaded underside.
    draw.ellipse([cx - 50, cy - 40, cx + 50, cy + 80], fill=BODY)
    draw.ellipse([cx - 45, cy + 10, cx + 45, cy + 80], fill=BODY_DARK)

    # Neck and head.
    draw.line([cx, cy - 30, cx - 10, cy - 140], fill=HEAD, width=34)
    draw.ellipse([cx - 40, cy - 175, cx, cy - 135], fill=HEAD)

    # The three-feather crest.
    for i in range(3):
        bx = cx - 30 + i * 10
        draw.line([bx, cy - 172, bx - 4, cy - 200], fill=BODY, width=4)
        draw.ellipse([bx - 8, cy - 206, bx, cy - 198], fill=EYE_GOLD)

    draw.polygon([(cx - 40, cy - 155), (cx - 58, cy - 150), (cx - 40, cy - 145)],
                 fill=BEAK)
    draw.ellipse([cx - 24, cy - 160, cx - 16, cy - 152], fill=EYE)
    return img


# --- 2. compile to stitches -------------------------------------------------
def nearest(rgb, palette):
    """The palette colour closest to rgb, by squared distance."""
    return min(palette, key=lambda c: sum((a - b) ** 2 for a, b in zip(rgb, c)))


def build_chart(image, stitches_wide, palette):
    """Resample to an exact stitch grid, then snap every cell to the palette.

    BOX resampling averages all the source pixels falling inside each cell, so
    the grid is decided here and not by whatever resolution we happened to draw
    at -- the drawing could be any size and the chart would be the same.
    """
    w, h = image.size
    stitches_high = max(1, round(stitches_wide * h / w))
    small = image.resize((stitches_wide, stitches_high), Image.Resampling.BOX)

    raw = small.convert("RGB").tobytes()
    cells = [nearest(raw[i:i + 3], palette) for i in range(0, len(raw), 3)]

    # Number the colours by how often they occur, so colour 1 is the one you
    # will stitch most -- the order a person actually works in.
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
    font = load_font(int(CELL * 0.6))

    for c in range(w + 1):
        x = c * CELL
        draw.line([x, 0, x, h * CELL], fill=(60, 60, 60),
                  width=2 if c % BOLD_EVERY == 0 else 1)
    for r in range(h + 1):
        y = r * CELL
        draw.line([0, y, w * CELL, y], fill=(60, 60, 60),
                  width=2 if r % BOLD_EVERY == 0 else 1)

    # Cache each glyph's metrics: only eleven distinct numbers, ~33k cells.
    box = {}
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
    out = Path(__file__).parent
    grid, legend, symbol = build_chart(draw_peacock(), STITCHES_WIDE, PALETTE)

    render_artwork(grid).save(out / "peacock_artwork.png")
    render_chart(grid, symbol).save(out / "peacock_chart.png")

    lines = [f"{'No.':>4}  {'HEX':<9}  Stitches", "-" * 28]
    lines += [f"{s:>4}  #{r:02X}{g:02X}{b:02X}  {n:>8}" for s, (r, g, b), n in legend]
    total = sum(n for _, _, n in legend)
    lines += ["-" * 28, f"{total} stitches, {len(legend)} colours"]
    (out / "peacock_legend.txt").write_text("\n".join(lines), encoding="utf-8")

    print(f"{len(grid[0])} x {len(grid)} stitches, {total} total, {len(legend)} colours")
    print("wrote peacock_artwork.png, peacock_chart.png, peacock_legend.txt")


if __name__ == "__main__":
    main()
