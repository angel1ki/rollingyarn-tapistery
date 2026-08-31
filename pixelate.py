import base64
import io
from collections import Counter

from PIL import Image, ImageDraw, ImageFont, ImageOps

# the libraries used are base64, io, collections.Counter and the standard image Python library PIL
# base 64 and io are used to the end to turn a finished image into a base64 text string (so that it can be embedded straight into a JSON response / HTML <img> tag, so there is no need for a temp file) 
# counter is like a ducr-class from the library collections, this one is used to count how many times a specific color apperas and the it ranks the colours based on the frequency they are shown.
# The Pillow library is the one tha handles the images, with Inage it opens, creates and resized an image, with ImageDraw it draws lines, rectangles and text on the image
# with ImageFont it loads the font of the numbers that are shown on the IMage and with ImageOps it handles the image orientation and color conversion 

CELL_SIZE = 22  # pixels per stitch, for grids small enough to afford it
MIN_CELL_SIZE = 6  # floor so very fine grids don't balloon into huge images
MAX_RENDER_SPAN = 3600  # target output width/height in px, regardless of grid size
THICK_LINE_EVERY = 10  # bold gridline every N stitches, like real tapestry charts

# These are the constats for the stitches. Each grid cell is normally drawn in 22px wide/tall, but if the grid is very wide - like 1000 cell- the 22px would make
#the image huge so we have a const to cap on total image size to 3600 and the cells shrink down to smaller than 6px

def cell_size_for(grid_w):
    return max(MIN_CELL_SIZE, min(CELL_SIZE, MAX_RENDER_SPAN // max(grid_w, 1)))


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


def build_grid(image: Image.Image, grid_w: int, num_colors: int):
    image = ImageOps.exif_transpose(image).convert("RGB")
    w, h = image.size
    grid_h = max(1, round(grid_w * h / w))

    small = image.resize((grid_w, grid_h), Image.Resampling.BOX)
    quantized = small.quantize(colors=num_colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    palette = quantized.convert("RGB")

    pixels = list(quantized.getdata())
    rgb_pixels = list(palette.getdata())

    counts = Counter(pixels)
    ordered_indices = [idx for idx, _ in counts.most_common()]
    symbol_by_index = {idx: str(i + 1) for i, idx in enumerate(ordered_indices)}

    legend = []
    for idx in ordered_indices:
        pos = pixels.index(idx)
        rgb = rgb_pixels[pos]
        legend.append({
            "symbol": symbol_by_index[idx],
            "hex": "#%02x%02x%02x" % rgb,
            "rgb": rgb,
            "count": counts[idx],
        })

    grid_rgb = [rgb_pixels[r * grid_w:(r + 1) * grid_w] for r in range(grid_h)]
    grid_symbols = [
        [symbol_by_index[pixels[r * grid_w + c]] for c in range(grid_w)]
        for r in range(grid_h)
    ]
    return grid_rgb, grid_symbols, legend, grid_w, grid_h


def render_preview(grid_rgb, grid_w, grid_h, cell_size=None):
    cell_size = cell_size or cell_size_for(grid_w)
    img = Image.new("RGB", (grid_w * cell_size, grid_h * cell_size))
    draw = ImageDraw.Draw(img)
    for r, row in enumerate(grid_rgb):
        for c, rgb in enumerate(row):
            x0, y0 = c * cell_size, r * cell_size
            draw.rectangle([x0, y0, x0 + cell_size, y0 + cell_size], fill=rgb)
    return img


def render_pattern(grid_rgb, grid_symbols, grid_w, grid_h, show_symbols):
    cell_size = cell_size_for(grid_w)
    img = render_preview(grid_rgb, grid_w, grid_h, cell_size)
    draw = ImageDraw.Draw(img)
    font = load_font(max(6, int(cell_size * 0.6)))

    for c in range(grid_w + 1):
        thick = c % THICK_LINE_EVERY == 0
        x = c * cell_size
        draw.line([x, 0, x, grid_h * cell_size], fill=(60, 60, 60), width=2 if thick else 1)
    for r in range(grid_h + 1):
        thick = r % THICK_LINE_EVERY == 0
        y = r * cell_size
        draw.line([0, y, grid_w * cell_size, y], fill=(60, 60, 60), width=2 if thick else 1)

    if show_symbols:
        bbox_cache = {}
        for r, row in enumerate(grid_rgb):
            for c, rgb in enumerate(row):
                luminance = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
                text_color = (0, 0, 0) if luminance > 150 else (255, 255, 255)
                symbol = grid_symbols[r][c]
                if symbol not in bbox_cache:
                    bbox = draw.textbbox((0, 0), symbol, font=font)
                    bbox_cache[symbol] = (
                        bbox[2] - bbox[0], bbox[3] - bbox[1], bbox[0], bbox[1]
                    )
                tw, th, bx, by = bbox_cache[symbol]
                x0, y0 = c * cell_size, r * cell_size
                draw.text(
                    (x0 + (cell_size - tw) / 2 - bx, y0 + (cell_size - th) / 2 - by),
                    symbol, fill=text_color, font=font,
                )
    return img


def to_base64_png(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")
