from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DocumentTemplate
from app.schemas import (
    AdminTemplateResponse,
    PreviewMetadata,
    VariableUpdateRequest,
)
from app.services.template_service import (
    confirm_template,
    create_draft_template,
    get_template_or_404,
    update_draft_variables,
)
from app.storage import download_preview_image

router = APIRouter(prefix="/admin/templates", tags=["admin"])


@router.post("/upload", response_model=AdminTemplateResponse, status_code=status.HTTP_201_CREATED)
async def upload_template(
    client_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DocumentTemplate:
    return await create_draft_template(db, client_id, file)


@router.get("", response_model=list[AdminTemplateResponse])
def list_admin_templates(
    client_id: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[DocumentTemplate]:
    query = db.query(DocumentTemplate)
    if client_id:
        query = query.filter(DocumentTemplate.client_id == client_id)
    if status:
        query = query.filter(DocumentTemplate.status == status)
    return query.order_by(DocumentTemplate.created_at.desc()).all()


@router.get("/{template_id}", response_model=AdminTemplateResponse)
def get_admin_template(template_id: int, db: Session = Depends(get_db)) -> DocumentTemplate:
    return get_template_or_404(db, template_id)


@router.get("/{template_id}/preview", response_model=PreviewMetadata)
def get_template_preview(template_id: int, db: Session = Depends(get_db)) -> dict:
    template = get_template_or_404(db, template_id)
    if not template.preview_metadata:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preview not available")
    return template.preview_metadata


@router.get("/{template_id}/preview/pages/{page_index}/image")
def get_preview_page_image(
    template_id: int,
    page_index: int,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    template = get_template_or_404(db, template_id)
    pages = (template.preview_metadata or {}).get("pages", [])
    if page_index < 0 or page_index >= len(pages):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
    thumbnail_key = pages[page_index].get("thumbnail_key")
    if not thumbnail_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No thumbnail for this page")
    image_bytes = download_preview_image(thumbnail_key)
    return StreamingResponse(BytesIO(image_bytes), media_type="image/png")


@router.put("/{template_id}/variables", response_model=AdminTemplateResponse)
def update_template_variables(
    template_id: int,
    body: VariableUpdateRequest,
    db: Session = Depends(get_db),
) -> DocumentTemplate:
    return update_draft_variables(db, template_id, body)


@router.post("/{template_id}/confirm", response_model=AdminTemplateResponse)
def confirm_template_endpoint(template_id: int, db: Session = Depends(get_db)) -> DocumentTemplate:
    return confirm_template(db, template_id)
