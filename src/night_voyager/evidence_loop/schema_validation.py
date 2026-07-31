"""Small strict validator for the committed Slice 0 JSON-schema subset."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import date
from typing import Any, cast
from urllib.parse import urlparse
from uuid import UUID


def _fail(location: str, problem: str) -> None:
    raise ValueError(f"schema validation failed at {location}: {problem}")


def _matches_type(value: object, expected: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(expected, False)


def validate_strict_json_schema(
    value: object,
    schema: Mapping[str, Any],
    *,
    location: str = "$",
) -> None:
    expected_type = schema.get("type")
    if isinstance(expected_type, str) and not _matches_type(value, expected_type):
        _fail(location, f"expected {expected_type}")
    if "const" in schema and value != schema["const"]:
        _fail(location, "const mismatch")
    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        _fail(location, "enum mismatch")

    if isinstance(value, dict):
        typed_value = cast(dict[str, object], value)
        properties_value = schema.get("properties", {})
        properties = cast(
            dict[str, object],
            properties_value if isinstance(properties_value, dict) else {},
        )
        required_value = schema.get("required", [])
        required = cast(list[object], required_value if isinstance(required_value, list) else [])
        required_keys = [key for key in required if isinstance(key, str)]
        missing = [key for key in required_keys if key not in typed_value]
        if missing:
            _fail(location, "required property missing")
        if schema.get("additionalProperties") is False:
            extra = set(typed_value) - set(properties)
            if extra:
                _fail(location, "additional property")
        for key, item in typed_value.items():
            child = properties.get(key)
            if isinstance(child, dict):
                validate_strict_json_schema(
                    item,
                    cast(dict[str, Any], child),
                    location=f"{location}.{key}",
                )

    if isinstance(value, list):
        typed_items = cast(list[object], value)
        minimum = schema.get("minItems")
        maximum = schema.get("maxItems")
        if isinstance(minimum, int) and len(typed_items) < minimum:
            _fail(location, "too few items")
        if isinstance(maximum, int) and len(typed_items) > maximum:
            _fail(location, "too many items")
        if schema.get("uniqueItems") is True:
            encoded = [
                json.dumps(item, separators=(",", ":"), sort_keys=True) for item in typed_items
            ]
            if len(encoded) != len(set(encoded)):
                _fail(location, "items not unique")
        child = schema.get("items")
        if isinstance(child, dict):
            for index, item in enumerate(typed_items):
                validate_strict_json_schema(
                    item,
                    cast(dict[str, Any], child),
                    location=f"{location}[{index}]",
                )

    if isinstance(value, str):
        minimum = schema.get("minLength")
        maximum = schema.get("maxLength")
        if isinstance(minimum, int) and len(value) < minimum:
            _fail(location, "string too short")
        if isinstance(maximum, int) and len(value) > maximum:
            _fail(location, "string too long")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            _fail(location, "pattern mismatch")
        format_name = schema.get("format")
        try:
            if format_name == "uuid":
                UUID(value)
            elif format_name == "date":
                date.fromisoformat(value)
            elif format_name == "uri":
                parsed = urlparse(value)
                if not parsed.scheme:
                    raise ValueError
        except ValueError:
            _fail(location, f"{format_name} format mismatch")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, (int, float)) and value < minimum:
            _fail(location, "below minimum")
        if isinstance(maximum, (int, float)) and value > maximum:
            _fail(location, "above maximum")
