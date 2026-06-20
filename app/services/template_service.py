from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.ai.variable_enricher import enrich_variables
from app.config import get_settings
from app.constants import SUPPORTED_EXTENSIONS, TEMPLATE_STATUS_DRAFT, TEMPLATE_STATUS_PUBLISHED
from app.models import DocumentTemplate
from app.schemas import TemplateSchemaResponse, TemplateSchemaVariable, VariableUpdateRequest
from app.services.detection_service import detect_template_fields
from app.services.preview_service import generate_preview
from app.services.variable_sync_service import (
    apply_variables_schema_to_legacy,
    build_variables_schema_from_detection,
    schema_from_legacy_update,
    validate_variables_schema,
)
from app.storage import upload_template_file


def get_template_or_404(db: Session, template_id: int) -> DocumentTemplate:
    template = db.get(DocumentTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template not found")
    return template


def assert_draft(template: DocumentTemplate) -> None:
    if template.status != TEMPLATE_STATUS_DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft templates can be modified",
        )


def assert_published(template: DocumentTemplate) -> None:
    if template.status != TEMPLATE_STATUS_PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found or not published",
        )


async def create_draft_template(
    db: Session,
    client_id: str,
    file: UploadFile,
) -> DocumentTemplate:
    ext = Path(file.filename or "").suffix.lower()
    file_type = SUPPORTED_EXTENSIONS.get(ext)
    if not file_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supported formats: .docx, .pdf, .jpg, .jpeg, .png, .xlsx, .xls",
        )

    content = await file.read()

    detection = detect_template_fields(content, file_type, ext)
    print("===== OCR TEXT =====")
print(detection.ocr_text)
print("====================")
    enrichment = enrich_variables(
        detection.raw_candidates,
        file_type,
        ocr_text=detection.ocr_text,
    )

    variables_schema = build_variables_schema_from_detection(detection, enrichment)
    field_labels = {v["name"]: v["label"] for v in variables_schema["variables"]}

    settings = get_settings()
    file_key = await upload_template_file(
        content=content,
        filename=file.filename or "uploaded-file",
        content_type=file.content_type or "application/octet-stream",
        client_id=client_id,
    )

    template = DocumentTemplate(
        client_id=client_id,
        file_name=file.filename or "uploaded-file",
        bucket=settings.minio_bucket,
        file_key=file_key,
        variables={v["name"]: "" for v in variables_schema["variables"]},
        field_order=variables_schema.get("display_order", []),
        file_type=file_type,
        field_positions=[v["position"] for v in variables_schema["variables"]],
        field_labels=field_labels,
        status=TEMPLATE_STATUS_DRAFT,
        variables_schema=variables_schema,
        document_type=enrichment.document_type,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    preview_metadata = generate_preview(
        content=content,
        file_type=file_type,
        ext=ext,
        field_positions=template.field_positions,
        field_labels=field_labels,
        client_id=client_id,
        template_id=template.id,
        field_order=detection.field_order,
    )
    template.preview_metadata = preview_metadata
    db.commit()
    db.refresh(template)
    return template


def update_draft_variables(
    db: Session,
    template_id: int,
    body: VariableUpdateRequest,
) -> DocumentTemplate:
    template = get_template_or_404(db, template_id)
    assert_draft(template)

    schema = body.variables_schema.model_dump()
    errors = validate_variables_schema(schema, template.file_type)
    if errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="; ".join(errors))

    template.variables_schema = schema
    field_labels = {v["name"]: v["label"] for v in schema["variables"]}
    template.field_labels = field_labels
    template.field_order = schema.get("display_order", [])
    template.field_positions = [{**v["position"], "name": v["name"]} for v in schema["variables"]]
    template.variables = {v["name"]: v.get("default", "") for v in schema["variables"]}
    template.hidden_fields = [v["name"] for v in schema["variables"] if v.get("hidden")]

    db.commit()
    db.refresh(template)
    return template


def update_draft_legacy_config(
    db: Session,
    template_id: int,
    field_order: list[str] | None,
    field_labels: dict[str, str] | None,
    hidden_fields: list[str] | None,
    extra_positions: list[dict] | None,
) -> DocumentTemplate:
    template = get_template_or_404(db, template_id)
    assert_draft(template)

    schema = schema_from_legacy_update(
        template,
        field_order=field_order,
        field_labels=field_labels,
        hidden_fields=hidden_fields,
        extra_positions=extra_positions,
    )
    template.variables_schema = schema
    if field_order is not None:
        template.field_order = field_order
    if field_labels is not None:
        template.field_labels = field_labels
    if hidden_fields is not None:
        template.hidden_fields = hidden_fields
    if extra_positions:
        by_name = {p["name"]: p for p in (template.field_positions or [])}
        for pos in extra_positions:
            by_name[pos["name"]] = pos
        template.field_positions = list(by_name.values())

    db.commit()
    db.refresh(template)
    return template


def confirm_template(db: Session, template_id: int) -> DocumentTemplate:
    from datetime import datetime, timezone

    template = get_template_or_404(db, template_id)
    if template.status == TEMPLATE_STATUS_PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template is already published",
        )

    schema = template.variables_schema or {}
    errors = validate_variables_schema(schema, template.file_type)
    if errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="; ".join(errors))

    apply_variables_schema_to_legacy(template)
    template.status = TEMPLATE_STATUS_PUBLISHED
    template.confirmed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(template)
    return template


def build_schema_response(template: DocumentTemplate) -> TemplateSchemaResponse:
    schema = template.variables_schema or {}
    variables = [
        TemplateSchemaVariable(
            name=v["name"],
            label=v.get("label", v["name"]),
            type=v.get("type", "string"),
            required=v.get("required", False),
            hidden=v.get("hidden", False),
            default=v.get("default", ""),
            position=v.get("position", {}),
        )
        for v in schema.get("variables", [])
        if not v.get("hidden")
    ]
    from app.schemas import SectionDefinition

    sections = [SectionDefinition(**s) for s in schema.get("sections", [])]
    return TemplateSchemaResponse(
        template_id=template.id,
        file_name=template.file_name,
        file_type=template.file_type,
        document_type=template.document_type,
        variables=variables,
        sections=sections,
        display_order=schema.get("display_order", []),
    )
