from fastapi import FastAPI
from sqlalchemy import text

from app.database import Base, engine
from app.routers import admin_templates, templates

Base.metadata.create_all(bind=engine)

# Add columns introduced after the initial schema — safe to run on every startup
with engine.connect() as _conn:
    _conn.execute(text("ALTER TABLE document_templates ADD COLUMN IF NOT EXISTS field_labels JSONB NOT NULL DEFAULT '{}'"))
    _conn.execute(text("ALTER TABLE document_templates ADD COLUMN IF NOT EXISTS hidden_fields JSONB NOT NULL DEFAULT '[]'"))
    _conn.execute(text("ALTER TABLE document_templates ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'draft'"))
    _conn.execute(text("ALTER TABLE document_templates ADD COLUMN IF NOT EXISTS preview_metadata JSONB NOT NULL DEFAULT '{}'"))
    _conn.execute(text("ALTER TABLE document_templates ADD COLUMN IF NOT EXISTS variables_schema JSONB NOT NULL DEFAULT '{}'"))
    _conn.execute(text("ALTER TABLE document_templates ADD COLUMN IF NOT EXISTS document_type VARCHAR(50)"))
    _conn.execute(text("ALTER TABLE document_templates ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMPTZ"))
    _conn.commit()

app = FastAPI(title="Document Template API")

app.include_router(admin_templates.router)
app.include_router(templates.router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
