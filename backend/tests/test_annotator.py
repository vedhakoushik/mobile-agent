import base64
import io
import pytest
from PIL import Image

from perception.annotator import annotate_screenshot
from perception.xml_parser import InteractiveElement


def _blank_png(width: int = 200, height: int = 400) -> bytes:
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_element(id_: int, x1: int, y1: int, x2: int, y2: int) -> InteractiveElement:
    return InteractiveElement(
        id=id_,
        bounds=(x1, y1, x2, y2),
        class_name="android.widget.Button",
        resource_id=f"com.test:id/btn_{id_}",
        content_desc="",
        text=f"Button {id_}",
        clickable=True,
        focusable=True,
        scrollable=False,
        checkable=False,
        checked=False,
    )


def test_annotate_returns_base64_string():
    png = _blank_png()
    elements = [_make_element(1, 10, 10, 80, 60)]
    result = annotate_screenshot(png, elements)
    assert isinstance(result, str)
    # must be valid base64
    decoded = base64.b64decode(result)
    assert len(decoded) > 100


def test_annotated_image_is_valid_png():
    png = _blank_png()
    elements = [_make_element(1, 10, 10, 80, 60)]
    result_b64 = annotate_screenshot(png, elements)
    result_bytes = base64.b64decode(result_b64)
    img = Image.open(io.BytesIO(result_bytes))
    assert img.format == "PNG"


def test_annotated_preserves_dimensions():
    png = _blank_png(200, 400)
    elements = [_make_element(1, 10, 10, 80, 60)]
    result_b64 = annotate_screenshot(png, elements)
    result_bytes = base64.b64decode(result_b64)
    img = Image.open(io.BytesIO(result_bytes))
    assert img.size == (200, 400)


def test_annotate_with_no_elements():
    png = _blank_png()
    result = annotate_screenshot(png, [])
    assert isinstance(result, str)
    decoded = base64.b64decode(result)
    assert len(decoded) > 0


def test_annotate_draws_orange_badge():
    png = _blank_png(300, 300)
    elements = [_make_element(1, 5, 5, 100, 80)]
    result_b64 = annotate_screenshot(png, elements)
    result_bytes = base64.b64decode(result_b64)
    img = Image.open(io.BytesIO(result_bytes)).convert("RGB")
    # badge is at top-left of element bounds — pixel at (5, 5) should be orange
    r, g, b = img.getpixel((5, 5))
    assert r > 200  # high red channel = orange
