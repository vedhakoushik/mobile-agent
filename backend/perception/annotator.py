import base64
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .xml_parser import InteractiveElement


ASSETS_DIR = Path(__file__).parent.parent / "assets"
FONT_PATH = ASSETS_DIR / "DejaVuSans-Bold.ttf"
LABEL_FONT_SIZE = 28
BADGE_PADDING = 4
BOX_FILL_ALPHA = 77    # 30% opacity
BOX_COLOR = (255, 100, 0)
MAX_WIDTH = 1080


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    if FONT_PATH.exists():
        return ImageFont.truetype(str(FONT_PATH), size)
    return ImageFont.load_default()


def annotate_screenshot(
    img_bytes: bytes,
    elements: list[InteractiveElement],
    max_width: int = MAX_WIDTH,
) -> str:
    """
    Draw numbered orange bounding boxes on a screenshot.
    Returns the annotated image as a base64-encoded PNG string.
    """
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")

    # resize to max_width if needed (reduces Gemini token count)
    if img.width > max_width:
        ratio = max_width / img.width
        new_h = int(img.height * ratio)
        img = img.resize((max_width, new_h), Image.LANCZOS)
        scale = ratio
    else:
        scale = 1.0

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _load_font(LABEL_FONT_SIZE)

    for elem in elements:
        x1, y1, x2, y2 = [int(c * scale) for c in elem.bounds]
        if x2 <= x1 or y2 <= y1:
            continue

        # semi-transparent fill
        draw.rectangle([x1, y1, x2, y2], fill=(*BOX_COLOR, BOX_FILL_ALPHA))
        # solid border
        draw.rectangle([x1, y1, x2, y2], outline=(*BOX_COLOR, 255), width=3)

        # badge
        label = str(elem.id)
        bbox = font.getbbox(label)
        lw = bbox[2] - bbox[0]
        lh = bbox[3] - bbox[1]
        bx2 = x1 + lw + BADGE_PADDING * 2
        by2 = y1 + lh + BADGE_PADDING * 2
        draw.rectangle([x1, y1, bx2, by2], fill=(*BOX_COLOR, 255))
        draw.text(
            (x1 + BADGE_PADDING, y1 + BADGE_PADDING),
            label,
            fill=(255, 255, 255, 255),
            font=font,
        )

    result = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()
