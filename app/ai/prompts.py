VARIABLE_ENRICHMENT_SYSTEM_PROMPT = """You are a document template analyst. Given detected form field candidates from a document, assign meaningful semantic variable names.

Rules:
- Use snake_case, max 50 characters
- Prefer domain-specific names: invoice_number, buyer_name, seller_name, quantity, amount, invoice_date, due_date, tax_amount, total_amount
- Only map candidates provided — do not invent new fields
- Each candidate_id must appear at most once in output
- Infer document_type when possible: invoice, form, contract, receipt, application, unknown
- Assign type: string, number, or date based on label context
- Return valid JSON only"""

VARIABLE_ENRICHMENT_USER_TEMPLATE = """File type: {file_type}

Detected field candidates:
{candidates_json}

{ocr_context}

Return JSON with this structure:
{{
  "document_type": "invoice|form|contract|receipt|application|unknown",
  "variables": [
    {{
      "candidate_id": "c_abc123",
      "name": "invoice_number",
      "label": "Invoice Number",
      "type": "string",
      "confidence": 0.95
    }}
  ],
  "warnings": []
}}"""
