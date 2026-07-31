import base64
import io

from PIL import Image, ImageDraw

from .annotator import _load_font


GRID_ROWS = 9
GRID_COLS = 9
GRID_COLOR = (180, 180, 180, 160)
LABEL_COLOR = (255, 255, 255, 200)
LABEL_SIZE = 20


def overlay_grid(
    img_bytes: bytes,
    rows: int = GRID_ROWS,
    cols: int = GRID_COLS,
) -> tuple[str, dict[str, tuple[int, int]]]:
    """
    Draw a labelled grid (A1..I9) on the screenshot.
    Returns:
        - base64 PNG string of annotated image
        - dict mapping cell label → center pixel (x, y)
    """
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    w, h = img.size

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _load_font(LABEL_SIZE)

    cell_w = w // cols
    cell_h = h // rows
    coords: dict[str, tuple[int, int]] = {}

    for row in range(rows):
        for col in range(cols):
            x1 = col * cell_w
            y1 = row * cell_h
            x2 = x1 + cell_w
            y2 = y1 + cell_h

            # grid lines
            draw.rectangle([x1, y1, x2 - 1, y2 - 1], outline=GRID_COLOR, width=1)

            # label: row letter + col number  (A1 = top-left, I9 = bottom-right)
            row_letter = chr(ord("A") + row)
            col_number = col + 1
            label = f"{row_letter}{col_number}"

            cx = x1 + cell_w // 2
            cy = y1 + cell_h // 2
            coords[label] = (cx, cy)

            draw.text((x1 + 3, y1 + 2), label, fill=LABEL_COLOR, font=font)

    result = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode(), coords
