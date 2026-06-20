from openai import OpenAI
from app.config import get_settings
import json


def detect_ai_fields(ocr_text: str) -> dict:
    settings = get_settings()

    if not settings.ai_enabled:
        return {"document_type": "unknown", "fields": []}

    if not settings.openai_api_key:
        return {"document_type": "unknown", "fields": []}

    client = OpenAI(api_key=settings.openai_api_key)

    response = client.chat.completions.create(
        model=settings.ai_model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": """
You are an intelligent document analysis engine.

Analyze OCR text and identify business fields that should become reusable template variables.

Supported documents:
- Invoices
- Purchase Orders
- Export Documents
- Contracts
- Government Forms
- Insurance Forms
- HR Forms
- Medical Forms
- Registration Forms

Rules:
- Return meaningful semantic field names.
- Never return field_1, field_2, field_3.
- Use snake_case names.
- Return only fields that appear in the document.
- Return valid JSON only.
"""
            },
            {
                "role": "user",
                "content": ocr_text[:8000]
            }
        ],
        temperature=0.1,
    )

    return json.loads(response.choices[0].message.content)