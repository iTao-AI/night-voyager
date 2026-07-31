"""Byte-stable Slice 0 canonicalization and exact-evidence deduplication."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, cast

CANONICALIZATION_ID = "night-voyager.slice0.compact-sorted-utf8-lf.v1"

_IDENTITY_FIELDS = (
    "evaluation_canonical_source_id",
    "evaluation_canonical_evidence_id",
    "decision_dimension",
    "fact_key",
    "value",
)


def canonical_json_bytes(value: object) -> bytes:
    """Return compact sorted UTF-8 JSON with exactly one LF terminator."""

    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def canonicalize_units(
    units: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Collapse exact evidence identities while retaining every provenance path."""

    grouped: dict[str, dict[str, Any]] = {}
    for raw in units:
        unit = dict(raw)
        for field in _IDENTITY_FIELDS:
            if not isinstance(unit.get(field), str) or not unit[field]:
                raise ValueError("canonical evidence identity missing")
        evidence_id = str(unit["evaluation_canonical_evidence_id"])
        source_id = str(unit["evaluation_canonical_source_id"])
        if len(evidence_id) != 64 or len(source_id) != 64:
            raise ValueError("canonical evidence identity invalid")
        paths_value = unit.get("provenance_paths")
        if (
            not isinstance(paths_value, list)
            or not paths_value
            or any(
                not isinstance(path, str) or not path
                for path in cast(list[object], paths_value)
            )
        ):
            raise ValueError("canonical provenance missing")
        paths = cast(list[str], paths_value)
        if (
            unit.get("origin_kind") == "untrusted_evidence"
            and unit.get("content_trust") != "untrusted_evidence"
        ):
            raise ValueError("untrusted evidence trust marker missing")

        existing = grouped.get(evidence_id)
        if existing is None:
            normalized = dict(unit)
            normalized["provenance_paths"] = sorted(set(paths))
            normalized["origin_kinds"] = [str(unit.get("origin_kind"))]
            grouped[evidence_id] = normalized
            continue
        if any(existing[field] != unit[field] for field in _IDENTITY_FIELDS):
            raise ValueError("canonical evidence identity conflict")
        existing_paths = cast(list[str], existing["provenance_paths"])
        existing["provenance_paths"] = sorted({*existing_paths, *paths})
        existing_origins = cast(list[str], existing["origin_kinds"])
        existing["origin_kinds"] = sorted(
            {*existing_origins, str(unit.get("origin_kind"))}
        )

    return tuple(grouped[key] for key in sorted(grouped))
