from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import TEMPLATE_STATUS_DRAFT
from app.database import Base


class DocumentTemplate(Base):
    __tablename__ = "document_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    bucket: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    file_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    variables: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    field_order: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False, default="docx")
    field_positions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    field_labels: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    hidden_fields: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TEMPLATE_STATUS_DRAFT, index=True)
    preview_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    variables_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    document_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
