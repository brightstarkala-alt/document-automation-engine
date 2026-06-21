import io
import re

import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageDraw, ImageFont


def pdf_to_image(pdf_bytes: bytes, scale: float = 2.0) -> bytes:
    """Render the first page of a PDF to PNG bytes."""
    import fitz  # PyMuPDF

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat)
    return pix.tobytes("png")


def excel_to_image(excel_bytes: bytes, suffix: str = ".xlsx") -> bytes:
    """Convert the first sheet of an Excel file to PNG bytes via LibreOffice."""
    import shutil
    import subprocess
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        excel_path = tmp / f"form{suffix}"
        excel_path.write_bytes(excel_bytes)

        soffice = (
            shutil.which("soffice")
            or "/Applications/LibreOffice.app/Contents/MacOS/soffice"
        )
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(tmp), str(excel_path)],
            check=True,
            capture_output=True,
        )

        pdf_path = tmp / "form.pdf"
        return pdf_to_image(pdf_path.read_bytes())


def _make_field_name(text: str) -> str:
    text = re.sub(r"[^a-z0-9\s]", "", text.lower())
    text = re.sub(r"\s+", "_", text.strip())
    return text[:50] or "field"
def extract_document_text(image_bytes: bytes) -> str:
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return pytesseract.image_to_string(img)

def detect_fields(image_bytes: bytes) -> tuple[list[str], list[dict]]:
    """
    Detect form fields from image bytes using OpenCV + Tesseract.
    Returns (field_order, field_positions).
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Get full OCR output with bounding boxes
    ocr = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    # Lower threshold to catch lighter/thinner marks
    _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)

    # Aggressive horizontal dilation to connect dashed/dotted/underscore lines
    connect_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (45, 1))
    connected = cv2.dilate(thresh, connect_kernel)

    # Detect solid horizontal lines — smaller open kernel allows shorter fields
    detect_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(w // 20, 20), 1))
    lines_img = cv2.morphologyEx(connected, cv2.MORPH_OPEN, detect_kernel)

    contours, _ = cv2.findContours(lines_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Keep lines wider than 3% of image width (catches short fields like Suffix)
    raw_lines = [cv2.boundingRect(c) for c in contours]
    lines = sorted(
        [(x, y, lw, lh) for x, y, lw, lh in raw_lines if lw > w * 0.03],
        key=lambda r: (r[1], r[0]),
    )

    field_order: list[str] = []
    field_positions: list[dict] = []
    seen: set[str] = set()

    for lx, ly, lw, lh in lines:
        # Skip lines that have text sitting ON them (hyperlinks, existing content)
        # A real blank field line has no text overlapping it horizontally
        text_on_line = False
        for i, word in enumerate(ocr["text"]):
            word_text = ocr["text"][i].strip()
            if not word_text:
                continue
            wx = int(ocr["left"][i])
            wy = int(ocr["top"][i])
            ww = int(ocr["width"][i])
            wh = int(ocr["height"][i])
            word_cx = wx + ww // 2
            word_mid_y = wy + wh // 2
            # Word centre falls within the inner 80% of the line's span at same height
            if (
                lx + lw * 0.1 <= word_cx <= lx + lw * 0.9
                and abs(word_mid_y - (ly + lh // 2)) < 30
            ):
                text_on_line = True
                break
        if text_on_line:
            continue

        # Find OCR words to the left of this line at roughly the same height
        words_left = []
        for i, word in enumerate(ocr["text"]):
            word = word.strip()
            if not word:
                continue
            wx = int(ocr["left"][i])
            wy = int(ocr["top"][i])
            ww = int(ocr["width"][i])
            wh = int(ocr["height"][i])
            word_mid_y = wy + wh // 2
            line_mid_y = ly + lh // 2
            if (
                wx + ww <= lx + 30
                and wx >= max(0, lx - 500)
                and abs(word_mid_y - line_mid_y) < 20
            ):
                words_left.append((wx, word))

        if words_left:
            words_left.sort()
            label = " ".join(word for _, word in words_left)
        else:
            label = f"field {len(field_order) + 1}"

        name = _make_field_name(label)
        if name in seen:
            base, n = name, 2
            while f"{base}_{n}" in seen:
                n += 1
            name = f"{base}_{n}"
        seen.add(name)

        field_order.append(name)
        field_positions.append({
            "name": name,
            "label": label,
            "x": lx,
            "y": ly,
            "w": lw,
            "h": max(lh, 18),
        })

    return field_order, field_positions


def extract_ocr_text(image_bytes: bytes) -> str:
    """Return plain OCR text from an image for AI context."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return pytesseract.image_to_string(img)

def extract_ocr_words(image_bytes: bytes) -> list[dict]:
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    data = pytesseract.image_to_data(
        img,
        output_type=pytesseract.Output.DICT,
    )

    words = []

    for i in range(len(data["text"])):
        text = data["text"][i].strip()

        if not text:
            continue

        words.append({
            "text": text,
            "x": int(data["left"][i]),
            "y": int(data["top"][i]),
            "w": int(data["width"][i]),
            "h": int(data["height"][i]),
        })

    return words
def build_image_preview_metadata(
    image_bytes: bytes,
    field_positions: list[dict],
    field_labels: dict[str, str] | None = None,
) -> dict:
    """Build preview metadata with layout-preserving regions."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    width, height = img.size
    labels = field_labels or {}

    regions = []

    for pos in field_positions:
        name = pos["name"]

        bbox = None
        if all(k in pos for k in ["x", "y", "w", "h"]):
            bbox = {
                "x": pos["x"],
                "y": pos["y"],
                "w": pos["w"],
                "h": pos["h"],
            }

        regions.append({
            "field_id": name,
            "variable_name": name,
            "label_text": labels.get(
                name,
                pos.get("label", name.replace("_", " ").title()),
            ),
            "bbox": bbox,
            "source": pos.get("source", "ai"),
        })

    return {
        "version": 1,
        "page_count": 1,
        "file_type": "image",
        "pages": [{
            "page_index": 0,
            "width_px": width,
            "height_px": height,
            "thumbnail_key": None,
            "regions": regions,
        }],
    }


def render_preview_thumbnail(image_bytes: bytes, max_width: int = 1200) -> bytes:
    """Resize image for admin preview while preserving aspect ratio."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def overlay_and_export_pdf(
    image_bytes: bytes,
    values: dict[str, str],
    positions: list[dict],
) -> bytes:
    """
    Draw filled values onto the original form image and export as PDF.
    Preserves the original design exactly — text is placed just above each underline.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)

    font_size = max(16, img.size[1] // 55)

    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            font_size,
        )
    except Exception:
        font = ImageFont.load_default()

    pos_map = {p["name"]: p for p in positions}

    for name, value in values.items():
        if not value or not value.strip():
            continue

        p = pos_map.get(name)
        if not p:
            continue

        # Skip semantic fields that don't have coordinates
        if "x" not in p or "y" not in p:
            continue

        text_y = p["y"] - font_size - 3
        if text_y < 0:
            text_y = p["y"] + 2

        draw.text(
            (p["x"] + 8, text_y),
            value.strip(),
            fill=(0, 0, 0),
            font=font,
        )

    out = io.BytesIO()
    img.save(out, format="PDF")
    return out.getvalue()
