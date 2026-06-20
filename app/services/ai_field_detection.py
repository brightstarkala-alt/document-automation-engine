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
Return JSON exactly in this format:

{
  "document_type": "invoice",
  "fields": [
    {
      "name": "invoice_number",
      "label": "Invoice Number"
    },
    {
      "name": "buyer_name",
      "label": "Buyer Name"
    }
  ]
}
"""
            },

            {
                "role": "user",
                "content": ocr_text[:8000]
            }
        ],
        temperature=0.1,
    )
    content = response.choices[0].message.content

    print("===== AI RESPONSE =====")
    print(content)
    print("=======================")

    return json.loads(content)

