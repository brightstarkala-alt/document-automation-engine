from __future__ import annotations

from app.documents import build_docx_preview_metadata, docx_to_preview_image
from app.excel_processing import build_excel_preview_metadata
from app.image_processing import build_image_preview_metadata, pdf_to_image, render_preview_thumbnail
from app.storage import upload_preview_image


def generate_preview(
    content: bytes,
    file_type: str,
    ext: str,
    field_positions: list[dict],
    field_labels: dict[str, str],
    client_id: str,
    template_id: int,
    field_order: list[str] | None = None,
) -> dict:
    """Build preview metadata and upload thumbnails where applicable."""
    if file_type == "docx":
        metadata = build_docx_preview_metadata(content, field_order or [])
        thumb_bytes = docx_to_preview_image(content)
        if thumb_bytes:
            key = upload_preview_image(thumb_bytes, client_id, template_id, 0)
            metadata["pages"][0]["thumbnail_key"] = key
            metadata["pages"][0]["width_px"] = _image_width(thumb_bytes)
            metadata["pages"][0]["height_px"] = _image_height(thumb_bytes)
        return metadata

    if file_type == "excel":
        return build_excel_preview_metadata(content, field_positions, suffix=ext)

    image_bytes = pdf_to_image(content) if file_type == "pdf" else content
    metadata = build_image_preview_metadata(image_bytes, field_positions, field_labels)
    thumb_bytes = render_preview_thumbnail(image_bytes)
    key = upload_preview_image(thumb_bytes, client_id, template_id, 0)
    metadata["pages"][0]["thumbnail_key"] = key
    metadata["file_type"] = file_type
    return metadata


def _image_width(png_bytes: bytes) -> int:
    from PIL import Image
    import io
    return Image.open(io.BytesIO(png_bytes)).size[0]


def _image_height(png_bytes: bytes) -> int:
    from PIL import Image
    import io
    return Image.open(io.BytesIO(png_bytes)).size[1]
