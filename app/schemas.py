from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DocumentTemplateResponse(BaseModel):
    """Legacy full template response."""

    id: int
    client_id: str
    file_name: str
    bucket: str
    file_key: str
    variables: dict[str, Any]
    field_order: list[str]
    file_type: str
    field_positions: list[dict]
    field_labels: dict[str, str]
    hidden_fields: list[str]
    status: str
    preview_metadata: dict[str, Any]
    variables_schema: dict[str, Any]
    document_type: str | None
    confirmed_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TemplateConfigUpdate(BaseModel):
    """Legacy config update — maps to variables endpoint."""

    field_order: list[str] | None = None
    field_labels: dict[str, str] | None = None
    hidden_fields: list[str] | None = None
    extra_positions: list[dict] | None = None


class VariableDefinition(BaseModel):
    id: str
    name: str
    label: str
    type: str = "string"
    required: bool = False
    hidden: bool = False
    default: str = ""
    position: dict[str, Any] = Field(default_factory=dict)
    ai_suggested: bool = False
    source_label: str | None = None


class SectionDefinition(BaseModel):
    type: Literal["header", "note"]
    text: str
    order: int = 0


class VariablesSchema(BaseModel):
    variables: list[VariableDefinition] = Field(default_factory=list)
    sections: list[SectionDefinition] = Field(default_factory=list)
    display_order: list[str] = Field(default_factory=list)


class PreviewRegion(BaseModel):
    field_id: str
    variable_name: str
    label_text: str
    bbox: dict[str, int] | None = None
    cell_ref: str | None = None
    row: int | None = None
    col: int | None = None
    source: str = "detection"


class PreviewPage(BaseModel):
    page_index: int
    width_px: int
    height_px: int
    thumbnail_key: str | None = None
    regions: list[PreviewRegion] = Field(default_factory=list)


class PreviewMetadata(BaseModel):
    version: int = 1
    page_count: int = 1
    pages: list[PreviewPage] = Field(default_factory=list)
    file_type: str


class AdminTemplateResponse(BaseModel):
    id: int
    client_id: str
    file_name: str
    file_type: str
    status: str
    document_type: str | None
    variables_schema: dict[str, Any]
    preview_metadata: dict[str, Any]
    field_order: list[str]
    field_labels: dict[str, str]
    hidden_fields: list[str]
    variables: dict[str, Any]
    confirmed_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConsumerTemplateResponse(BaseModel):
    id: int
    client_id: str
    file_name: str
    file_type: str
    document_type: str | None
    created_at: datetime
    confirmed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class TemplateSchemaVariable(BaseModel):
    name: str
    label: str
    type: str
    required: bool
    hidden: bool
    default: str
    position: dict[str, Any]


class TemplateSchemaResponse(BaseModel):
    template_id: int
    file_name: str
    file_type: str
    document_type: str | None
    variables: list[TemplateSchemaVariable]
    sections: list[SectionDefinition]
    display_order: list[str]


class VariableUpdateRequest(BaseModel):
    variables_schema: VariablesSchema
