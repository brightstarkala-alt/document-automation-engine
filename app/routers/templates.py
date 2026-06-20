from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.constants import DOCX_MIME, EXCEL_MIME, TEMPLATE_STATUS_PUBLISHED
from app.database import get_db
from app.documents import generate_document, generate_pdf
from app.excel_processing import excel_to_pdf, fill_excel
from app.image_processing import overlay_and_export_pdf, pdf_to_image
from app.models import DocumentTemplate
from app.schemas import ConsumerTemplateResponse, DocumentTemplateResponse, TemplateConfigUpdate, TemplateSchemaResponse
from app.services.template_service import (
    assert_published,
    build_schema_response,
    create_draft_template,
    get_template_or_404,
    update_draft_legacy_config,
)
from app.storage import download_template_file

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[ConsumerTemplateResponse])
def list_published_templates(
    client_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[DocumentTemplate]:
    query = db.query(DocumentTemplate).filter(DocumentTemplate.status == TEMPLATE_STATUS_PUBLISHED)
    if client_id:
        query = query.filter(DocumentTemplate.client_id == client_id)
    return query.order_by(DocumentTemplate.created_at.desc()).all()


@router.get("/{template_id}", response_model=ConsumerTemplateResponse)
def get_published_template(template_id: int, db: Session = Depends(get_db)) -> DocumentTemplate:
    template = get_template_or_404(db, template_id)
    assert_published(template)
    return template


@router.get("/{template_id}/schema", response_model=TemplateSchemaResponse)
def get_template_schema(template_id: int, db: Session = Depends(get_db)) -> TemplateSchemaResponse:
    template = get_template_or_404(db, template_id)
    assert_published(template)
    return build_schema_response(template)


@router.post("/{template_id}/generate")
async def generate_from_template(
    template_id: int,
    values: dict[str, str],
    output_format: str = Query(default="pdf", pattern="^(pdf|excel|docx)$"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    template = get_template_or_404(db, template_id)
    assert_published(template)

    try:
        original_bytes = download_template_file(bucket=template.bucket, file_key=template.file_key)
        stem = Path(template.file_name).stem
        orig_ext = Path(template.file_name).suffix.lower()

        if template.file_type == "docx":
            if output_format == "docx":
                content_bytes = generate_document(docx_bytes=original_bytes, values=values)
                output_name = f"{stem}_filled.docx"
                media_type = DOCX_MIME
            else:
                content_bytes = generate_pdf(docx_bytes=original_bytes, values=values)
                output_name = f"{stem}_filled.pdf"
                media_type = "application/pdf"

        elif template.file_type == "excel":
            if template.field_positions and "x" in template.field_positions[0]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "This Excel template was uploaded with an older version of the app. "
                        "Please re-upload the file."
                    ),
                )
            filled_bytes = fill_excel(original_bytes, values, template.field_positions, suffix=orig_ext)
            if output_format == "excel":
                content_bytes = filled_bytes
                output_name = f"{stem}_filled.xlsx"
                media_type = EXCEL_MIME
            else:
                content_bytes = excel_to_pdf(filled_bytes, suffix=".xlsx")
                output_name = f"{stem}_filled.pdf"
                media_type = "application/pdf"

        else:
            if template.file_type == "pdf":
                image_bytes = pdf_to_image(original_bytes)
            else:
                image_bytes = original_bytes
            content_bytes = overlay_and_export_pdf(image_bytes, values, template.field_positions)
            output_name = f"{stem}_filled.pdf"
            media_type = "application/pdf"

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc

    return StreamingResponse(
        BytesIO(content_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{output_name}"'},
    )


# Legacy endpoints — backward compatibility


@router.post("", response_model=DocumentTemplateResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def legacy_create_template(
    client_id: str = Form(...),
    variables: str = Form("{}"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    return await create_draft_template(db, client_id, file)


@router.get("/{template_id}/detail", response_model=DocumentTemplateResponse, include_in_schema=False)
def legacy_get_template(template_id: int, db: Session = Depends(get_db)) -> DocumentTemplate:
    return get_template_or_404(db, template_id)


@router.put("/{template_id}/config", response_model=DocumentTemplateResponse, include_in_schema=False)
def legacy_update_config(
    template_id: int,
    config: TemplateConfigUpdate,
    db: Session = Depends(get_db),
) -> DocumentTemplate:
    return update_draft_legacy_config(
        db,
        template_id,
        field_order=config.field_order,
        field_labels=config.field_labels,
        hidden_fields=config.hidden_fields,
        extra_positions=config.extra_positions,
    )
