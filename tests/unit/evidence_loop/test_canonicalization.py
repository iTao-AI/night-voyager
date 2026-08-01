from __future__ import annotations

import json

import pytest

from night_voyager.evidence_loop.canonicalization import (
    canonical_json_bytes,
    canonicalize_units,
)


def test_canonical_json_is_compact_sorted_utf8_with_one_lf() -> None:
    assert canonical_json_bytes({"z": "日本", "a": 1}) == (
        b'{"a":1,"z":"\xe6\x97\xa5\xe6\x9c\xac"}\n'
    )


def test_exact_duplicate_retains_both_provenance_paths() -> None:
    units = canonicalize_units(
        (
            {
                "evaluation_canonical_source_id": "a" * 64,
                "evaluation_canonical_evidence_id": "b" * 64,
                "decision_dimension": "program_requirements",
                "fact_key": "program.language",
                "value": "English",
                "provenance_paths": ["dra:row-1"],
                "access_kind": "baseline",
                "origin_kind": "night_voyager_typed_governed_row",
            },
            {
                "evaluation_canonical_source_id": "a" * 64,
                "evaluation_canonical_evidence_id": "b" * 64,
                "decision_dimension": "program_requirements",
                "fact_key": "program.language",
                "value": "English",
                "provenance_paths": ["mke:evidence-1"],
                "access_kind": "baseline",
                "origin_kind": "untrusted_evidence",
                "content_trust": "untrusted_evidence",
            },
        )
    )

    assert len(units) == 1
    assert units[0]["provenance_paths"] == ["dra:row-1", "mke:evidence-1"]
    assert json.loads(canonical_json_bytes(units)) == list(units)


def test_same_evidence_identity_cannot_hide_conflicting_values() -> None:
    shared = {
        "evaluation_canonical_source_id": "a" * 64,
        "evaluation_canonical_evidence_id": "b" * 64,
        "decision_dimension": "application_timeline",
        "fact_key": "application.deadline",
        "provenance_paths": ["dra:row-1"],
        "access_kind": "baseline",
        "origin_kind": "night_voyager_typed_governed_row",
    }

    with pytest.raises(ValueError, match="canonical evidence identity conflict"):
        canonicalize_units(({**shared, "value": "May"}, {**shared, "value": "June"}))
