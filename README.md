# Document Automation API

Headless FastAPI service for template upload, AI-assisted variable detection, admin review, and document generation.

## Stack

- FastAPI
- PostgreSQL (template metadata)
- MinIO (template files and preview thumbnails)
- OpenAI (optional semantic variable naming)

## Local Setup

```bash
cp .env.example .env
docker compose up -d
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-backend.txt
uvicorn app.main:app --reload
```

API: `http://localhost:8000`  
OpenAPI docs: `http://localhost:8000/docs`

## Workflow

1. **Admin uploads** a template → status `draft`, variables detected + AI-enriched, preview generated
2. **Admin reviews** variables via preview and edit APIs
3. **Admin confirms** → status `published`
4. **End users** list published templates, fetch schema, generate documents

## Admin API

### Upload template

```http
POST /admin/templates/upload
```

Form fields: `client_id`, `file`

```bash
curl -X POST http://localhost:8000/admin/templates/upload \
  -F 'client_id=client_001' \
  -F 'file=@sample.docx'
```

### List templates

```http
GET /admin/templates?status=draft&client_id=client_001
```

### Get template (draft or published)

```http
GET /admin/templates/{id}
```

### Get preview metadata

```http
GET /admin/templates/{id}/preview
```

### Get preview page image

```http
GET /admin/templates/{id}/preview/pages/0/image
```

### Update variables (draft only)

```http
PUT /admin/templates/{id}/variables
```

Body: `{ "variables_schema": { "variables": [...], "sections": [...], "display_order": [...] } }`

### Confirm template

```http
POST /admin/templates/{id}/confirm
```

Publishes the template for end-user generation.

## End-User API

### List published templates

```http
GET /templates?client_id=client_001
```

### Get published template

```http
GET /templates/{id}
```

### Get variable schema

```http
GET /templates/{id}/schema
```

### Generate document

```http
POST /templates/{id}/generate?output_format=pdf
```

Body: JSON object of variable values, e.g. `{"invoice_number": "INV-001", "buyer_name": "Acme Corp"}`

Only **published** templates can be used for generation.

## AI Variable Detection

When `OPENAI_API_KEY` is set and `AI_ENABLED=true`, detected field labels are mapped to semantic names (e.g. `invoice_number`, `buyer_name`, `quantity`, `amount`). If AI is unavailable, heuristic names are used (`AI_FALLBACK_TO_HEURISTIC=true`).

## Legacy Routes

These remain for backward compatibility but are not documented in OpenAPI:

- `POST /templates` — upload (creates draft)
- `PUT /templates/{id}/config` — legacy config update

Use the admin API for new integrations.
