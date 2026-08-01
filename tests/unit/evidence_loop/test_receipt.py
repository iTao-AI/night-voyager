from __future__ import annotations

import hashlib
from typing import Any

import pytest

from night_voyager.evidence_loop.canonicalization import canonical_json_bytes
from night_voyager.evidence_loop.receipt import (
    build_terminal_receipt,
    verify_terminal_receipt,
)


def test_terminal_receipt_is_byte_stable_and_self_verifying() -> None:
    evaluation: dict[str, Any] = {
        "schema_version": "night-voyager.evidence-loop-evaluation.v2",
        "terminal_disposition": "no_incremental_value",
        "case_results": [
            {"identity": {"case_id": f"case-{index}"}, "status": "evaluated"}
            for index in range(4)
        ],
    }

    first = build_terminal_receipt(evaluation, run_kind="development")
    second = build_terminal_receipt(evaluation, run_kind="development")

    assert first == second
    verified = verify_terminal_receipt(first)
    assert verified["terminal_disposition"] == "no_incremental_value"


def test_terminal_receipt_rejects_tampering() -> None:
    receipt = build_terminal_receipt(
        {
            "schema_version": "night-voyager.evidence-loop-evaluation.v2",
            "terminal_disposition": "no_incremental_value",
            "case_results": [],
        },
        run_kind="development",
    )
    tampered = receipt.replace(b"no_incremental_value", b"evaluation_invalid", 1)

    with pytest.raises(ValueError, match="receipt digest mismatch"):
        verify_terminal_receipt(tampered)


def test_terminal_receipt_redacts_raw_values_queries_and_provenance_paths() -> None:
    evaluation: dict[str, Any] = {
        "schema_version": "night-voyager.evidence-loop-evaluation.v2",
        "terminal_disposition": "incremental_value_confirmed",
        "case_results": [
            {
                "identity": {"case_id": "public-case"},
                "status": "evaluated",
                "arms": {
                    "mke": {
                        "canonical_source_count": 1,
                        "canonical_evidence_count": 1,
                        "units": [
                            {
                                "evaluation_canonical_source_id": "a" * 64,
                                "evaluation_canonical_evidence_id": "b" * 64,
                                "decision_dimension": "program_requirements",
                                "fact_key": "program.language",
                                "value": "RAW_VALUE_MUST_NOT_PERSIST",
                                "provenance_paths": ["mke:private-trace"],
                                "access_kind": "source_access",
                            }
                        ],
                    }
                },
                "mechanism_metrics": {},
                "target_metrics": {},
                "guardrail_metrics": {"passed": True},
                "conflicts": [],
                "sensitivity": {},
            }
        ],
    }

    receipt = build_terminal_receipt(evaluation, run_kind="holdout")

    assert b"RAW_VALUE_MUST_NOT_PERSIST" not in receipt
    assert b"private-trace" not in receipt
    assert b'"value_sha256"' in receipt


def test_terminal_verifier_rejects_self_hashed_unknown_disposition() -> None:
    body: dict[str, Any] = {
        "schema_version": "night-voyager.evidence-loop-receipt.v2",
        "canonicalization_id": "night-voyager.slice0.compact-sorted-utf8-lf.v1",
        "run_kind": "holdout",
        "terminal_disposition": "retry_later",
        "evaluation": {
            "schema_version": "night-voyager.evidence-loop-evaluation.v2",
            "terminal_disposition": "retry_later",
            "case_results": [],
        },
    }
    content = canonical_json_bytes(
        {
            **body,
            "receipt_sha256": hashlib.sha256(
                canonical_json_bytes(body)
            ).hexdigest(),
        }
    )

    with pytest.raises(ValueError, match="receipt contract invalid"):
        verify_terminal_receipt(content)
