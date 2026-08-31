"""One-off script: draws simple scenes and runs them through the app's own
pixelation pipeline to produce example tapestry art for the landing page and
explore feed, grouped into easy/medium/hard difficulty tiers. Flat-color
scenes are snapped to an exact palette (so small details survive regardless
of area); gradient-heavy scenes are quantized instead, for smooth banding.
Run with:
    python generate_examples.py
"""
import math
import os
from collections import Counter

import numpy as np
from PIL import Image, ImageDraw

from pixelate import build_grid, render_pattern, render_preview

OUT_DIR = os.path.join(os.path.dirname(__file__), "static", "examples")
os.makedirs(OUT_DIR, exist_ok=True)


def nearest_color(rgb, palette):
    return min(palette, key=lambda c: sum((a - b) ** 2 for a, b in zip(rgb, c)))


def build_grid_exact(image, grid_w, palette_colors):
    w, h = image.size
    grid_h = max(1, round(grid_w * h / w))
    small = image.resize((grid_w, grid_h), Image.Resampling.BOX)
    pixels = [nearest_color(p, palette_colors) for p in small.getdata()]

    counts = Counter(pixels)
    ordered = [c for c, _ in counts.most_common()]
    symbol_by_color = {c: str(i + 1) for i, c in enumerate(ordered)}

    legend = [
        {"symbol": symbol_by_color[c], "hex": "#%02x%02x%02x" % c, "rgb": c, "count": counts[c]}
        for c in ordered
    ]
    grid_rgb = [pixels[r * grid_w:(r + 1) * grid_w] for r in range(grid_h)]
    grid_symbols = [
        [symbol_by_color[pixels[r * grid_w + c]] for c in range(grid_w)]
        for r in range(grid_h)
    ]
    return grid_rgb, grid_symbols, legend, grid_w, grid_h


def mirror_bbox(bbox, cx):
    x0, y0, x1, y1 = bbox
    return [2 * cx - x1, y0, 2 * cx - x0, y1]


# ---------------------------------------------------------------- easy ----

def draw_star():
    bg, fg = (207, 224, 240), (244, 196, 48)
    img = Image.new("RGB", (400, 400), bg)
    draw = ImageDraw.Draw(img)
    cx, cy, outer_r, inner_r = 200, 200, 150, 150 * 0.382
    points = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        radius = outer_r if i % 2 == 0 else inner_r
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    draw.polygon(points, fill=fg)
    return img, [bg, fg]


def draw_heart():
    bg, fg = (251, 232, 238), (214, 69, 80)
    img = Image.new("RGB", (400, 400), bg)
    draw = ImageDraw.Draw(img)
    cx, cy, r = 200, 180, 70
    draw.ellipse([cx - 2 * r, cy - r, cx, cy + r], fill=fg)
    draw.ellipse([cx, cy - r, cx + 2 * r, cy + r], fill=fg)
    draw.polygon([(cx - 2 * r, cy), (cx + 2 * r, cy), (cx, cy + 2 * r + 20)], fill=fg)
    return img, [bg, fg]


def draw_sun():
    bg, disc, ray = (196, 225, 242), (247, 200, 60), (240, 150, 60)
    img = Image.new("RGB", (400, 400), bg)
    draw = ImageDraw.Draw(img)
    cx, cy, outer_r, inner_r, disc_r = 200, 200, 170, 95, 100
    n_rays = 8
    for i in range(n_rays):
        angle = i * (2 * math.pi / n_rays)
        half_width = (math.pi / n_rays) * 0.5
        p1 = (cx + inner_r * math.cos(angle - half_width), cy + inner_r * math.sin(angle - half_width))
        p2 = (cx + inner_r * math.cos(angle + half_width), cy + inner_r * math.sin(angle + half_width))
        p3 = (cx + outer_r * math.cos(angle), cy + outer_r * math.sin(angle))
        draw.polygon([p1, p2, p3], fill=ray)
    draw.ellipse([cx - disc_r, cy - disc_r, cx + disc_r, cy + disc_r], fill=disc)
    return img, [bg, disc, ray]


def draw_flower():
    bg, stem, petal, center = (235, 245, 230), (110, 165, 90), (224, 105, 145), (247, 200, 60)
    img = Image.new("RGB", (400, 400), bg)
    draw = ImageDraw.Draw(img)
    draw.rectangle([190, 260, 210, 380], fill=stem)
    draw.ellipse([140, 300, 200, 345], fill=stem)
    cx, cy, petal_r, dist, n_petals = 200, 190, 42, 50, 6
    for i in range(n_petals):
        angle = i * (2 * math.pi / n_petals)
        px, py = cx + dist * math.cos(angle), cy + dist * math.sin(angle)
        draw.ellipse([px - petal_r, py - petal_r, px + petal_r, py + petal_r], fill=petal)
    draw.ellipse([cx - 35, cy - 35, cx + 35, cy + 35], fill=center)
    return img, [bg, stem, petal, center]


def draw_house():
    sky, ground = (188, 220, 240), (168, 216, 160)
    wall, roof, door, window = (250, 240, 222), (196, 84, 66), (120, 78, 52), (120, 172, 205)
    w, h, ground_y = 400, 400, 300
    img = Image.new("RGB", (w, h), sky)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, ground_y, w, h], fill=ground)
    draw.rectangle([110, 190, 290, ground_y], fill=wall)
    draw.polygon([(90, 190), (310, 190), (200, 90)], fill=roof)
    draw.rectangle([180, 240, 220, ground_y], fill=door)
    draw.rectangle([130, 210, 165, 245], fill=window)
    draw.rectangle([235, 210, 270, 245], fill=window)
    return img, [sky, ground, wall, roof, door, window]


SKY = (188, 220, 240)
GROUND = (168, 216, 160)
SUN = (247, 215, 116)
SKIN = (240, 192, 144)
HAIR1 = (110, 70, 50)
HAIR2 = (50, 50, 55)
SHIRT1 = (110, 150, 205)
SHIRT2 = (222, 120, 120)
HOLD = (200, 150, 100)
BALL = (230, 105, 60)


def draw_kid(draw, cx, ground_y, shirt_color, hair_color):
    head_r = 24
    head_cy = ground_y - 105
    draw.ellipse([cx - head_r, head_cy - head_r, cx + head_r, head_cy + head_r], fill=SKIN)
    draw.pieslice(
        [cx - head_r - 2, head_cy - head_r - 10, cx + head_r + 2, head_cy + 10],
        180, 360, fill=hair_color,
    )
    draw.rounded_rectangle(
        [cx - 26, head_cy + head_r - 4, cx + 26, ground_y - 32], radius=14, fill=shirt_color
    )
    draw.rectangle([cx - 20, ground_y - 36, cx - 6, ground_y], fill=shirt_color)
    draw.rectangle([cx + 6, ground_y - 36, cx + 20, ground_y], fill=shirt_color)
    hand_y = ground_y - 70
    return (cx + 26 if cx < 240 else cx - 26, hand_y)


def draw_kids_playing():
    w, h = 480, 360
    ground_y = 250
    img = Image.new("RGB", (w, h), SKY)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, ground_y, w, h], fill=GROUND)
    draw.ellipse([40, 30, 112, 102], fill=SUN)

    hand1 = draw_kid(draw, 195, ground_y, SHIRT1, HAIR1)
    hand2 = draw_kid(draw, 285, ground_y, SHIRT2, HAIR2)
    draw.line([hand1, hand2], fill=HOLD, width=6)

    draw.ellipse([220, ground_y + 35, 260, ground_y + 75], fill=BALL)

    palette = [SKY, GROUND, SUN, SKIN, HAIR1, HAIR2, SHIRT1, SHIRT2, HOLD, BALL]
    return img, palette


# -------------------------------------------------------------- medium ----

def draw_cat():
    bg = (250, 240, 225)
    body = (224, 148, 74)
    stripe = (188, 108, 46)
    white = (255, 255, 255)
    pink = (232, 150, 160)
    pink_dark = (206, 116, 128)
    black = (40, 30, 30)
    green = (140, 190, 110)
    green_dark = (95, 140, 80)
    shadow = (216, 205, 190)

    img = Image.new("RGB", (400, 400), bg)
    draw = ImageDraw.Draw(img)

    draw.ellipse([100, 340, 300, 372], fill=shadow)

    draw.ellipse([255, 250, 335, 330], fill=body)
    draw.ellipse([110, 200, 290, 380], fill=body)
    draw.ellipse([160, 260, 240, 380], fill=white)
    draw.ellipse([120, 330, 155, 372], fill=white)
    draw.ellipse([245, 330, 280, 372], fill=white)

    for sx in range(135, 275, 28):
        draw.line([sx, 208, sx - 12, 258], fill=stripe, width=6)

    draw.ellipse([130, 90, 270, 230], fill=body)
    draw.polygon([(140, 120), (108, 55), (172, 100)], fill=body)
    draw.polygon([(260, 120), (292, 55), (228, 100)], fill=body)
    draw.polygon([(140, 110), (120, 75), (162, 102)], fill=pink)
    draw.polygon([(260, 110), (280, 75), (238, 102)], fill=pink)
    draw.line([148, 78, 138, 100], fill=pink_dark, width=3)
    draw.line([252, 78, 262, 100], fill=pink_dark, width=3)

    draw.line([160, 95, 150, 130], fill=stripe, width=5)
    draw.line([240, 95, 250, 130], fill=stripe, width=5)
    draw.line([200, 88, 200, 118], fill=stripe, width=5)

    draw.ellipse([158, 148, 190, 176], fill=green)
    draw.ellipse([210, 148, 242, 176], fill=green)
    draw.ellipse([158, 158, 190, 176], fill=green_dark)
    draw.ellipse([210, 158, 242, 176], fill=green_dark)
    draw.ellipse([170, 156, 182, 172], fill=black)
    draw.ellipse([220, 156, 232, 172], fill=black)
    draw.ellipse([173, 158, 177, 162], fill=white)
    draw.ellipse([223, 158, 227, 162], fill=white)

    draw.polygon([(195, 180), (205, 180), (200, 190)], fill=pink_dark)
    draw.line([200, 190, 190, 200], fill=black, width=3)
    draw.line([200, 190, 210, 200], fill=black, width=3)

    for y in (185, 193, 201):
        draw.line([95, y, 148, y + 3], fill=black, width=2)
        draw.line([305, y, 252, y + 3], fill=black, width=2)

    palette = [bg, body, stripe, white, pink, pink_dark, black, green, green_dark, shadow]
    return img, palette


def draw_parrot():
    bg = (210, 235, 210)
    red = (216, 60, 50)
    red_dark = (180, 40, 35)
    blue = (60, 110, 200)
    yellow = (250, 200, 40)
    green = (90, 165, 90)
    white = (255, 255, 255)
    black = (30, 25, 25)
    beak_light = (75, 68, 68)
    branch = (120, 85, 55)

    w, h = 500, 500
    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 400, w, 430], fill=branch)

    for i, col in enumerate([blue, yellow, green, blue]):
        x0 = 255 + i * 18
        draw.polygon([(x0, 250), (x0 + 16, 250), (x0 + 40, 420), (x0 + 24, 420)], fill=col)

    draw.ellipse([150, 180, 300, 340], fill=red)
    draw.ellipse([150, 260, 300, 340], fill=red_dark)

    draw.ellipse([190, 210, 300, 320], fill=blue)
    draw.ellipse([200, 220, 280, 300], fill=yellow)
    draw.ellipse([210, 230, 265, 285], fill=green)

    draw.ellipse([130, 130, 230, 230], fill=red)
    draw.ellipse([145, 155, 190, 195], fill=white)
    draw.ellipse([160, 165, 178, 183], fill=black)
    draw.ellipse([163, 167, 169, 173], fill=white)

    draw.polygon([(130, 190), (88, 206), (130, 216)], fill=beak_light)
    draw.polygon([(96, 203), (78, 210), (100, 214)], fill=black)

    draw.rectangle([190, 335, 200, 405], fill=black)
    draw.rectangle([230, 335, 240, 405], fill=black)

    palette = [bg, red, red_dark, blue, yellow, green, white, black, beak_light, branch]
    return img, palette


def _sky_gradient(w, h, top_rgb, bottom_rgb):
    t = np.linspace(0, 1, h)[:, None, None]
    top = np.array(top_rgb, dtype=float)
    bottom = np.array(bottom_rgb, dtype=float)
    grad = top * (1 - t) + bottom * t
    return np.tile(grad, (1, w, 1))


def draw_mountain():
    w, h = 500, 400
    sky = _sky_gradient(w, h, (176, 216, 235), (255, 224, 189))
    img = Image.fromarray(sky.astype("uint8"), "RGB")
    draw = ImageDraw.Draw(img)

    draw.ellipse([360, 55, 440, 135], fill=(255, 236, 179))

    draw.polygon([(0, 220), (120, 90), (220, 220)], fill=(178, 168, 204))
    draw.polygon([(150, 220), (280, 110), (400, 220)], fill=(160, 150, 190))
    draw.polygon([(100, 120), (120, 90), (140, 120)], fill=(246, 246, 250))
    draw.polygon([(255, 140), (280, 110), (305, 140)], fill=(246, 246, 250))

    draw.polygon([(-20, 260), (180, 140), (380, 260)], fill=(110, 120, 140))
    draw.polygon([(300, 260), (460, 150), (540, 260)], fill=(95, 105, 128))
    draw.polygon([(150, 175), (180, 140), (210, 175)], fill=(225, 225, 232))
    draw.polygon([(415, 185), (460, 150), (490, 185)], fill=(225, 225, 232))

    draw.rectangle([0, 260, w, h], fill=(100, 150, 96))
    draw.rectangle([0, 320, w, h], fill=(76, 122, 78))
    for tx in range(20, w, 55):
        draw.polygon([(tx, 330), (tx + 12, 290), (tx + 24, 330)], fill=(52, 92, 58))

    return img


def draw_castle():
    w, h = 500, 400
    ground_y = 300
    sky = _sky_gradient(w, h, (170, 205, 235), (235, 225, 200))
    img = Image.fromarray(sky.astype("uint8"), "RGB")
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, ground_y, w, h], fill=(140, 190, 110))

    wall = (205, 198, 190)
    wall_dark = (176, 168, 158)
    roof = (150, 70, 95)
    door = (90, 58, 42)
    window = (70, 95, 135)
    flag_pole = (90, 70, 55)
    flag = (214, 60, 50)

    draw.rectangle([180, 160, 320, ground_y], fill=wall)
    draw.rectangle([120, 190, 180, ground_y], fill=wall_dark)
    draw.rectangle([320, 190, 380, ground_y], fill=wall_dark)
    draw.polygon([(110, 190), (150, 130), (190, 190)], fill=roof)
    draw.polygon([(310, 190), (350, 130), (390, 190)], fill=roof)
    for bx in range(180, 320, 20):
        draw.rectangle([bx, 150, bx + 12, 170], fill=wall)

    draw.line([150, 130, 150, 105], fill=flag_pole, width=3)
    draw.polygon([(150, 105), (150, 120), (170, 112)], fill=flag)
    draw.line([350, 130, 350, 105], fill=flag_pole, width=3)
    draw.polygon([(350, 105), (350, 120), (370, 112)], fill=flag)

    draw.rectangle([230, 250, 270, ground_y], fill=door)
    draw.ellipse([230, 235, 270, 265], fill=door)

    for wy in (190, 230):
        draw.rectangle([200, wy, 215, wy + 20], fill=window)
        draw.rectangle([285, wy, 300, wy + 20], fill=window)
    draw.rectangle([143, 220, 157, 240], fill=window)
    draw.rectangle([343, 220, 357, 240], fill=window)

    return img


def draw_sailboat():
    w, h = 500, 400
    horizon = 220
    sky = _sky_gradient(w, horizon, (200, 230, 245), (255, 250, 235))
    sea = _sky_gradient(w, h - horizon, (80, 150, 180), (28, 78, 118))
    full = np.concatenate([sky, sea], axis=0)
    img = Image.fromarray(full.astype("uint8"), "RGB")
    draw = ImageDraw.Draw(img)

    draw.ellipse([380, 40, 440, 100], fill=(255, 245, 210))
    draw.ellipse([60, 55, 165, 100], fill=(255, 255, 255))
    draw.ellipse([105, 45, 195, 88], fill=(255, 255, 255))

    draw.polygon([(195, 235), (305, 235), (282, 268), (218, 268)], fill=(120, 80, 50))
    draw.line([250, 145, 250, 235], fill=(90, 60, 40), width=4)
    draw.polygon([(250, 148), (250, 232), (302, 222)], fill=(206, 200, 188))
    draw.polygon([(250, 148), (250, 232), (203, 225)], fill=(172, 165, 150))

    draw.polygon([(198, 278), (302, 278), (286, 300), (214, 300)], fill=(45, 95, 132))
    for i, y in enumerate(range(292, 355, 13)):
        span = max(20, 90 - i * 10)
        draw.line([250 - span, y, 250 + span, y], fill=(120, 175, 200), width=2)

    return img


# ---------------------------------------------------------------- hard ----

def draw_butterfly():
    bg = (245, 240, 250)
    body_dark = (45, 35, 40)
    outer = (35, 25, 30)
    band1 = (230, 110, 40)
    band2 = (250, 180, 70)
    band3 = (255, 228, 150)
    spot = (30, 25, 35)
    dot = (255, 255, 255)
    eyespot = (85, 120, 190)

    w, h = 600, 560
    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)
    cx, cy = 300, 270

    def pair(bbox, color):
        draw.ellipse(bbox, fill=color)
        draw.ellipse(mirror_bbox(bbox, cx), fill=color)

    pair([cx + 10, cy - 160, cx + 230, cy + 10], outer)
    pair([cx + 25, cy - 140, cx + 205, cy - 5], band1)
    pair([cx + 45, cy - 118, cx + 175, cy - 25], band2)
    pair([cx + 65, cy - 98, cx + 145, cy - 45], band3)
    pair([cx + 150, cy - 100, cx + 186, cy - 64], eyespot)
    pair([cx + 160, cy - 90, cx + 176, cy - 74], spot)
    pair([cx + 164, cy - 86, cx + 170, cy - 80], dot)

    pair([cx + 15, cy + 5, cx + 160, cy + 130], outer)
    pair([cx + 28, cy + 18, cx + 145, cy + 115], band1)
    pair([cx + 42, cy + 32, cx + 120, cy + 98], band3)
    for i in range(3):
        bx = cx + 50 + i * 22
        pair([bx, cy + 95, bx + 12, cy + 107], dot)

    draw.ellipse([cx - 14, cy - 30, cx + 14, cy + 90], fill=body_dark)
    draw.ellipse([cx - 18, cy - 55, cx + 18, cy - 15], fill=body_dark)
    draw.line([cx - 6, cy - 50, cx - 30, cy - 95], fill=body_dark, width=4)
    draw.line([cx + 6, cy - 50, cx + 30, cy - 95], fill=body_dark, width=4)
    draw.ellipse([cx - 36, cy - 103, cx - 24, cy - 91], fill=body_dark)
    draw.ellipse([cx + 24, cy - 103, cx + 36, cy - 91], fill=body_dark)

    palette = [bg, body_dark, outer, band1, band2, band3, spot, dot, eyespot]
    return img, palette


def draw_peacock():
    bg = (250, 245, 235)
    tail_outer = (40, 110, 90)
    tail_mid = (60, 150, 120)
    eye_gold = (210, 175, 60)
    eye_blue = (40, 90, 160)
    eye_center = (30, 40, 90)
    body = (35, 95, 150)
    body_dark = (25, 70, 115)
    head = (45, 110, 170)
    beak = (60, 50, 45)
    eye = (20, 15, 15)

    w, h = 700, 650
    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)
    cx, cy = 350, 430

    n_feathers = 11
    feather_pos = []
    for i in range(n_feathers):
        angle = math.pi * (0.12 + 0.76 * i / (n_feathers - 1))
        fx = cx + 260 * math.cos(angle)
        fy = cy - 260 * math.sin(angle) - 30
        feather_pos.append((fx, fy))

    # quill fan: thick strokes from the body up to each feather so the tail
    # visibly attaches instead of floating above the bird
    fan_origin = (cx, cy - 15)
    for fx, fy in feather_pos:
        draw.line([fan_origin, (fx, fy)], fill=tail_outer, width=48)
    draw.ellipse([cx - 70, cy - 65, cx + 70, cy + 15], fill=tail_outer)

    for fx, fy in feather_pos:
        draw.ellipse([fx - 38, fy - 55, fx + 38, fy + 55], fill=tail_outer)
        draw.ellipse([fx - 28, fy - 42, fx + 28, fy + 30], fill=tail_mid)
        draw.ellipse([fx - 20, fy - 30, fx + 20, fy + 18], fill=eye_gold)
        draw.ellipse([fx - 13, fy - 22, fx + 13, fy + 10], fill=eye_blue)
        draw.ellipse([fx - 6, fy - 14, fx + 6, fy + 2], fill=eye_center)

    draw.ellipse([cx - 50, cy - 40, cx + 50, cy + 80], fill=body)
    draw.ellipse([cx - 45, cy + 10, cx + 45, cy + 80], fill=body_dark)

    draw.line([cx, cy - 30, cx - 10, cy - 140], fill=head, width=34)
    draw.ellipse([cx - 40, cy - 175, cx, cy - 135], fill=head)

    for i in range(3):
        bx = cx - 30 + i * 10
        draw.line([bx, cy - 172, bx - 4, cy - 200], fill=body, width=4)
        draw.ellipse([bx - 8, cy - 206, bx, cy - 198], fill=eye_gold)

    draw.polygon([(cx - 40, cy - 155), (cx - 58, cy - 150), (cx - 40, cy - 145)], fill=beak)
    draw.ellipse([cx - 24, cy - 160, cx - 16, cy - 152], fill=eye)

    palette = [bg, tail_outer, tail_mid, eye_gold, eye_blue, eye_center, body, body_dark, head, beak, eye]
    return img, palette


def draw_lion():
    bg = (250, 240, 220)
    mane1 = (140, 80, 30)
    mane2 = (170, 105, 40)
    mane3 = (200, 135, 55)
    mane4 = (225, 165, 80)
    face = (235, 190, 130)
    face_shade = (215, 165, 105)
    nose = (60, 45, 40)
    eye_white = (250, 250, 245)
    eye_iris = (140, 95, 40)
    eye_pupil = (20, 15, 10)
    mouth = (90, 55, 40)

    w, h = 600, 600
    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)
    cx, cy = 300, 300

    for radius, color in [(260, mane1), (225, mane2), (195, mane3), (165, mane4)]:
        n = 28
        for i in range(n):
            a = 2 * math.pi * i / n
            tx = cx + radius * math.cos(a)
            ty = cy + radius * math.sin(a)
            draw.ellipse([tx - 26, ty - 26, tx + 26, ty + 26], fill=color)

    draw.ellipse([cx - 140, cy - 120, cx + 140, cy + 140], fill=face)
    draw.ellipse([cx - 140, cy + 20, cx + 140, cy + 140], fill=face_shade)

    draw.ellipse([cx - 140, cy - 160, cx - 70, cy - 95], fill=mane2)
    draw.ellipse([cx + 70, cy - 160, cx + 140, cy - 95], fill=mane2)
    draw.ellipse([cx - 125, cy - 145, cx - 85, cy - 110], fill=face)
    draw.ellipse([cx + 85, cy - 145, cx + 125, cy - 110], fill=face)

    draw.ellipse([cx - 70, cy - 30, cx - 20, cy + 10], fill=eye_white)
    draw.ellipse([cx + 20, cy - 30, cx + 70, cy + 10], fill=eye_white)
    draw.ellipse([cx - 55, cy - 25, cx - 25, cy + 5], fill=eye_iris)
    draw.ellipse([cx + 25, cy - 25, cx + 55, cy + 5], fill=eye_iris)
    draw.ellipse([cx - 46, cy - 18, cx - 34, cy - 6], fill=eye_pupil)
    draw.ellipse([cx + 34, cy - 18, cx + 46, cy - 6], fill=eye_pupil)

    draw.polygon([(cx - 25, cy + 35), (cx + 25, cy + 35), (cx, cy + 60)], fill=nose)
    draw.line([cx, cy + 60, cx, cy + 85], fill=mouth, width=4)
    draw.arc([cx - 40, cy + 55, cx, cy + 105], 0, 90, fill=mouth, width=4)
    draw.arc([cx, cy + 55, cx + 40, cy + 105], 90, 180, fill=mouth, width=4)

    for wx, wy in [(cx - 90, cy + 45), (cx - 90, cy + 60), (cx - 90, cy + 75),
                   (cx + 90, cy + 45), (cx + 90, cy + 60), (cx + 90, cy + 75)]:
        draw.ellipse([wx - 3, wy - 3, wx + 3, wy + 3], fill=mouth)

    palette = [bg, mane1, mane2, mane3, mane4, face, face_shade, nose, eye_white, eye_iris, eye_pupil, mouth]
    return img, palette


def draw_sunset():
    w, h = 600, 500
    horizon = 320

    stops_pos = [0.0, 0.35, 0.65, 0.85, 1.0]
    stops_r = [35, 120, 230, 255, 255]
    stops_g = [30, 60, 110, 175, 225]
    stops_b = [70, 110, 90, 90, 140]

    ys = np.linspace(0, 1, horizon)
    sky_col = np.stack([
        np.interp(ys, stops_pos, stops_r),
        np.interp(ys, stops_pos, stops_g),
        np.interp(ys, stops_pos, stops_b),
    ], axis=-1)
    sky_arr = np.tile(sky_col[:, None, :], (1, w, 1))

    water_h = h - horizon
    water_col = sky_col[::-1] * 0.65
    if water_col.shape[0] < water_h:
        pad = np.tile(water_col[-1:], (water_h - water_col.shape[0], 1))
        water_col = np.concatenate([water_col, pad], axis=0)
    water_col = water_col[:water_h]
    water_arr = np.tile(water_col[:, None, :], (1, w, 1))

    full = np.clip(np.concatenate([sky_arr, water_arr], axis=0), 0, 255).astype("uint8")
    img = Image.fromarray(full, "RGB")
    draw = ImageDraw.Draw(img)

    sun_cy = horizon - 40
    draw.ellipse([w / 2 - 70, sun_cy - 70, w / 2 + 70, sun_cy + 70], fill=(255, 235, 190))
    draw.ellipse([w / 2 - 50, sun_cy - 50, w / 2 + 50, sun_cy + 50], fill=(255, 250, 225))

    for i, y in enumerate(range(horizon + 10, h, 14)):
        width = max(6, 70 - i * 6)
        draw.rectangle([w / 2 - width, y, w / 2 + width, y + 6], fill=(255, 225, 170))

    draw.polygon([
        (0, horizon), (80, horizon - 70), (180, horizon - 30), (260, horizon - 110),
        (360, horizon - 40), (460, horizon - 90), (560, horizon - 20), (w, horizon - 50),
        (w, horizon), (0, horizon),
    ], fill=(25, 20, 35))

    for bx, by in [(150, 90), (190, 70), (230, 95), (420, 60), (460, 80)]:
        draw.line([bx - 10, by, bx, by - 8], fill=(20, 15, 25), width=3)
        draw.line([bx, by - 8, bx + 10, by], fill=(20, 15, 25), width=3)

    return img


# ------------------------------------------------------------------------

EXACT_EXAMPLES = [
    ("star", "easy", *draw_star(), 36),
    ("heart", "easy", *draw_heart(), 36),
    ("sun", "easy", *draw_sun(), 36),
    ("flower", "easy", *draw_flower(), 36),
    ("house", "easy", *draw_house(), 36),
    ("kids", "easy", *draw_kids_playing(), 48),
    ("cat", "medium", *draw_cat(), 72),
    ("parrot", "medium", *draw_parrot(), 80),
    ("butterfly", "hard", *draw_butterfly(), 170),
    ("peacock", "hard", *draw_peacock(), 190),
    ("lion", "hard", *draw_lion(), 180),
]

QUANTIZE_EXAMPLES = [
    ("mountain", "medium", draw_mountain(), 80, 22),
    ("sailboat", "medium", draw_sailboat(), 80, 20),
    ("castle", "medium", draw_castle(), 80, 18),
    ("sunset", "hard", draw_sunset(), 190, 60),
]

for name, difficulty, source_img, palette, grid_w in EXACT_EXAMPLES:
    grid_rgb, grid_symbols, legend, gw, gh = build_grid_exact(source_img, grid_w, palette)
    preview_img = render_preview(grid_rgb, gw, gh)
    pattern_img = render_pattern(grid_rgb, grid_symbols, gw, gh, show_symbols=True)
    preview_img.save(os.path.join(OUT_DIR, f"{name}_preview.png"))
    pattern_img.save(os.path.join(OUT_DIR, f"{name}_pattern.png"))
    print(f"generated {name} ({difficulty}): {gw}x{gh} grid, {len(legend)} colors")

for name, difficulty, source_img, grid_w, num_colors in QUANTIZE_EXAMPLES:
    grid_rgb, grid_symbols, legend, gw, gh = build_grid(source_img, grid_w, num_colors)
    preview_img = render_preview(grid_rgb, gw, gh)
    show_symbols = gw <= 250
    pattern_img = render_pattern(grid_rgb, grid_symbols, gw, gh, show_symbols=show_symbols)
    preview_img.save(os.path.join(OUT_DIR, f"{name}_preview.png"))
    pattern_img.save(os.path.join(OUT_DIR, f"{name}_pattern.png"))
    print(f"generated {name} ({difficulty}): {gw}x{gh} grid, {len(legend)} colors")
