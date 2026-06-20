from __future__ import annotations

import re
from uuid import uuid4

from app.ai.variable_enricher import AIEnrichmentResult
from app.services.detection_service import DetectionResult


def _make_field_name(text: str) -> str:
    text = re.sub(r"[^a-z0-9\s]", "", text.lower())
    text = re.sub(r"\s+", "_", text.strip())
    return text[:50] or "field"


def _dedupe_name(name: str, used: set[str]) -> str:
    if name not in used:
        used.add(name)
        return name
    base, n = name, 2
    while f"{base}_{n}" in used:
        n += 1
    final = f"{base}_{n}"
    used.add(final)
    return final


def build_variables_schema_from_detection(
    detection: DetectionResult,
    enrichment: AIEnrichmentResult,
) -> dict:
    """Build canonical variables_schema from detection + AI enrichment."""
    enrichment_by_id = {v.candidate_id: v for v in enrichment.variables}
    used_names: set[str] = set()
    variables: list[dict] = []
    name_by_candidate: dict[str, str] = {}

    for candidate in detection.raw_candidates:
        enriched = enrichment_by_id.get(candidate.id)
        if enriched:
            name = _dedupe_name(enriched.name, used_names)
            label = enriched.label
            var_type = enriched.type
            ai_suggested = True
        else:
            name = _dedupe_name(_make_field_name(candidate.label), used_names)
            label = candidate.label
            var_type = "string"
            ai_suggested = False

        name_by_candidate[candidate.id] = name
        pos = dict(candidate.position)
        pos["name"] = name

        variables.append({
            "id": f"var_{uuid4().hex[:8]}",
            "name": name,
            "label": label,
            "type": var_type,
            "required": False,
            "hidden": False,
            "default": "",
            "position": pos,
            "ai_suggested": ai_suggested,
            "source_label": candidate.label,
        })

    display_order: list[str] = []
    for entry in detection.field_order:
        if entry.startswith("#") or entry.startswith("~"):
            display_order.append(entry)
            continue
        candidate = next(
            (c for c in detection.raw_candidates if c.position.get("name") == entry),
            None,
        )
        if candidate and candidate.id in name_by_candidate:
            display_order.append(name_by_candidate[candidate.id])
        else:
            display_order.append(entry)

    return {
        "variables": variables,
        "sections": detection.sections,
        "display_order": display_order,
    }


def validate_variables_schema(schema: dict, file_type: str) -> list[str]:
    errors: list[str] = []
    variables = schema.get("variables", [])
    if not variables:
        errors.append("At least one variable is required")
        return errors

    names = [v.get("name", "") for v in variables]
    if len(names) != len(set(names)):
        errors.append("Variable names must be unique")

    for var in variables:
        if not var.get("name"):
            errors.append("Each variable must have a name")
        if file_type in ("pdf", "jpeg", "png"):
            pos = var.get("position", {})
            if "x" not in pos:
                errors.append(f"Variable '{var.get('name')}' missing image position")

    return errors


def apply_variables_schema_to_legacy(template) -> None:
    """Sync variables_schema into legacy generation columns."""
    schema = template.variables_schema or {}
    variables_list = schema.get("variables", [])
    display_order = schema.get("display_order", [])

    field_labels: dict[str, str] = {}
    hidden_fields: list[str] = []
    variables: dict[str, str] = {}
    field_positions: list[dict] = []

    for var in variables_list:
        name = var["name"]
        field_labels[name] = var.get("label", name.replace("_", " ").title())
        if var.get("hidden"):
            hidden_fields.append(name)
        variables[name] = var.get("default", "")
        pos = dict(var.get("position", {}))
        pos["name"] = name
        field_positions.append(pos)

    field_order = list(display_order) if display_order else [v["name"] for v in variables_list]

    template.field_order = field_order
    template.field_labels = field_labels
    template.hidden_fields = hidden_fields
    template.variables = variables
    template.field_positions = field_positions


def schema_from_legacy_update(
    template,
    field_order: list[str] | None = None,
    field_labels: dict[str, str] | None = None,
    hidden_fields: list[str] | None = None,
    extra_positions: list[dict] | None = None,
) -> dict:
    """Update variables_schema from legacy config format."""
    schema = dict(template.variables_schema or {"variables": [], "sections": [], "display_order": []})
    variables = {v["name"]: v for v in schema.get("variables", [])}

    if extra_positions:
        for pos in extra_positions:
            name = pos["name"]
            if name not in variables:
                variables[name] = {
                    "id": f"var_{uuid4().hex[:8]}",
                    "name": name,
                    "label": name.replace("_", " ").title(),
                    "type": "string",
                    "required": False,
                    "hidden": False,
                    "default": "",
                    "position": pos,
                    "ai_suggested": False,
                    "source_label": None,
                }
            else:
                variables[name]["position"] = pos

    if field_labels:
        for name, label in field_labels.items():
            if name in variables:
                variables[name]["label"] = label

    if hidden_fields is not None:
        hidden_set = set(hidden_fields)
        for var in variables.values():
            var["hidden"] = var["name"] in hidden_set

    if field_order is not None:
        schema["display_order"] = field_order

    schema["variables"] = list(variables.values())
    return schema
