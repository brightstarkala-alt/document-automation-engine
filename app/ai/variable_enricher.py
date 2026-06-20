from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from app.ai.prompts import VARIABLE_ENRICHMENT_SYSTEM_PROMPT, VARIABLE_ENRICHMENT_USER_TEMPLATE
from app.config import get_settings
from app.services.detection_service import RawCandidate

logger = logging.getLogger(__name__)


@dataclass
class EnrichedVariable:
    candidate_id: str
    name: str
    label: str
    type: str
    confidence: float


@dataclass
class AIEnrichmentResult:
    variables: list[EnrichedVariable] = field(default_factory=list)
    document_type: str | None = None
    warnings: list[str] = field(default_factory=list)


def _make_field_name(text: str) -> str:
    text = re.sub(r"[^a-z0-9\s]", "", text.lower())
    text = re.sub(r"\s+", "_", text.strip())
    return text[:50] or "field"


def _heuristic_enrichment(candidates: list[RawCandidate]) -> AIEnrichmentResult:
    return AIEnrichmentResult(
        variables=[
            EnrichedVariable(
                candidate_id=c.id,
                name=_make_field_name(c.label),
                label=c.label,
                type="string",
                confidence=0.5,
            )
            for c in candidates
        ],
        document_type=None,
        warnings=["AI enrichment unavailable; using heuristic names"],
    )


def enrich_variables(
    raw_candidates: list[RawCandidate],
    file_type: str,
    ocr_text: str | None = None,
) -> AIEnrichmentResult:
    settings = get_settings()

    if not raw_candidates:
        return AIEnrichmentResult()

    if not settings.ai_enabled or not settings.openai_api_key:
        return _heuristic_enrichment(raw_candidates)

    candidates_json = json.dumps([
        {
            "candidate_id": c.id,
            "label": c.label,
            "source": c.source,
            "position_hint": {k: v for k, v in c.position.items() if k in ("row", "col", "x", "y")},
        }
        for c in raw_candidates
    ], indent=2)

    ocr_context = ""
    if ocr_text:
        truncated = ocr_text[:3000]
        ocr_context = f"OCR text excerpt:\n{truncated}"

    user_prompt = VARIABLE_ENRICHMENT_USER_TEMPLATE.format(
        file_type=file_type,
        candidates_json=candidates_json,
        ocr_context=ocr_context,
    )

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.ai_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": VARIABLE_ENRICHMENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)

        variables = [
            EnrichedVariable(
                candidate_id=v["candidate_id"],
                name=v["name"],
                label=v.get("label", v["name"].replace("_", " ").title()),
                type=v.get("type", "string"),
                confidence=float(v.get("confidence", 0.8)),
            )
            for v in parsed.get("variables", [])
            if v.get("candidate_id") and v.get("name")
        ]

        if not variables:
            if settings.ai_fallback_to_heuristic:
                return _heuristic_enrichment(raw_candidates)
            return AIEnrichmentResult(warnings=["AI returned no variables"])

        return AIEnrichmentResult(
            variables=variables,
            document_type=parsed.get("document_type"),
            warnings=parsed.get("warnings", []),
        )

    except Exception as exc:
        logger.warning("AI enrichment failed: %s", exc)
        if settings.ai_fallback_to_heuristic:
            result = _heuristic_enrichment(raw_candidates)
            result.warnings.append(f"AI failed: {exc}")
            return result
        return AIEnrichmentResult(warnings=[str(exc)])
