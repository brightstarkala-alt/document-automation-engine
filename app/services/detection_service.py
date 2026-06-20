from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from app.documents import extract_placeholders
from app.excel_processing import detect_excel_fields
from app.image_processing import detect_fields, extract_ocr_text, pdf_to_image


@dataclass
class RawCandidate:
    id: str
    label: str
    position: dict
    source: str  # ocr | excel | docx_placeholder


@dataclass
class DetectionResult:
    field_order: list[str]
    field_positions: list[dict]
    raw_candidates: list[RawCandidate] = field(default_factory=list)
    sections: list[dict] = field(default_factory=list)
    ocr_text: str | None = None
    image_bytes: bytes | None = None


def detect_template_fields(content: bytes, file_type: str, ext: str) -> DetectionResult:
    """Run structural field detection for all supported file types."""
    if file_type == "docx":
        return _detect_docx(content)
    if file_type == "excel":
        return _detect_excel(content, ext)
    return _detect_image(content, file_type)


def _detect_docx(content: bytes) -> DetectionResult:
    extracted = extract_placeholders(content)
    sections: list[dict] = []
    field_order: list[str] = []
    field_positions: list[dict] = []
    raw_candidates: list[RawCandidate] = []

    for entry in extracted:
        if entry.startswith("#"):
            sections.append({"type": "header", "text": entry[1:], "order": len(sections)})
            field_order.append(entry)
        elif entry.startswith("~"):
            sections.append({"type": "note", "text": entry[1:], "order": len(sections)})
            field_order.append(entry)
        else:
            cid = f"c_{uuid4().hex[:8]}"
            label = entry.replace("_", " ").title()
            field_order.append(entry)
            pos = {"name": entry, "label": label}
            field_positions.append(pos)
            raw_candidates.append(RawCandidate(
                id=cid,
                label=label,
                position=pos,
                source="docx_placeholder",
            ))

    return DetectionResult(
        field_order=field_order,
        field_positions=field_positions,
        raw_candidates=raw_candidates,
        sections=sections,
    )


def _detect_excel(content: bytes, ext: str) -> DetectionResult:
    field_order, field_positions = detect_excel_fields(content, suffix=ext)
    raw_candidates = [
        RawCandidate(
            id=f"c_{uuid4().hex[:8]}",
            label=pos.get("label", pos["name"]),
            position=pos,
            source="excel",
        )
        for pos in field_positions
    ]
    return DetectionResult(
        field_order=field_order,
        field_positions=field_positions,
        raw_candidates=raw_candidates,
    )


def _detect_image(content: bytes, file_type: str) -> DetectionResult:
    image_bytes = pdf_to_image(content) if file_type == "pdf" else content
    field_order, field_positions = detect_fields(image_bytes)
    ocr_text = extract_ocr_text(image_bytes)
    raw_candidates = [
        RawCandidate(
            id=f"c_{uuid4().hex[:8]}",
            label=pos.get("label", pos["name"]),
            position=pos,
            source="ocr",
        )
        for pos in field_positions
    ]
    return DetectionResult(
        field_order=field_order,
        field_positions=field_positions,
        raw_candidates=raw_candidates,
        ocr_text=ocr_text,
        image_bytes=image_bytes,
    )
