from __future__ import annotations

import pytest

from night_voyager.evidence_loop.schema_validation import (
    validate_strict_json_schema,
)


def test_strict_schema_rejects_extra_top_level_and_nested_fields() -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["identity"],
        "properties": {
            "identity": {
                "type": "object",
                "additionalProperties": False,
                "required": ["case_id"],
                "properties": {"case_id": {"type": "string"}},
            }
        },
    }
    validate_strict_json_schema({"identity": {"case_id": "case-1"}}, schema)

    with pytest.raises(ValueError, match="additional property"):
        validate_strict_json_schema({"identity": {"case_id": "case-1"}, "extra": True}, schema)
    with pytest.raises(ValueError, match="additional property"):
        validate_strict_json_schema({"identity": {"case_id": "case-1", "extra": True}}, schema)


def test_strict_schema_enforces_required_types_enums_and_unique_items() -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "items"],
        "properties": {
            "status": {"type": "string", "enum": ["complete"]},
            "items": {
                "type": "array",
                "minItems": 2,
                "maxItems": 2,
                "uniqueItems": True,
                "items": {"type": "integer", "minimum": 1},
            },
        },
    }
    validate_strict_json_schema({"status": "complete", "items": [1, 2]}, schema)

    for invalid in (
        {"status": "capped", "items": [1, 2]},
        {"status": "complete", "items": [1, 1]},
        {"status": "complete", "items": [0, 2]},
        {"status": "complete"},
    ):
        with pytest.raises(ValueError):
            validate_strict_json_schema(invalid, schema)
