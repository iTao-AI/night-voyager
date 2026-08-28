from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def load_verifier():
    path = Path("scripts/verify_connected_plan_execution_flow.py")
    spec = importlib.util.spec_from_file_location(
        "verify_connected_plan_execution_flow", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CASE_ID = "40000000-0000-0000-0000-000000000002"
TASK_ID = "61000000-0000-0000-0000-000000000002"
DECISION_ID = "91000000-0000-0000-0000-000000000002"
DECISION_RECEIPT_ID = "90000000-0000-0000-0000-000000000002"
TIMELINE_ID = "9e000000-0000-0000-0000-000000000002"
EXECUTION_ID = "71000000-0000-0000-0000-000000000002"
RECEIPT_IDS = [
    "72000000-0000-0000-0000-000000000001",
    "72000000-0000-0000-0000-000000000002",
    "72000000-0000-0000-0000-000000000003",
    "72000000-0000-0000-0000-000000000004",
]
CHECKPOINT_IDS = [
    "73000000-0000-0000-0000-000000000001",
    "73000000-0000-0000-0000-000000000002",
    "73000000-0000-0000-0000-000000000003",
    "73000000-0000-0000-0000-000000000004",
]
BLOCKED_ATTESTATION_ID = "74000000-0000-0000-0000-000000000001"
REASSESSMENT_ID = "75000000-0000-0000-0000-000000000001"


def proof() -> dict[str, object]:
    return {
        "schema_version": 1,
        "locale": "zh-CN",
        "case_id": CASE_ID,
        "case_revision": 2,
        "task_id": TASK_ID,
        "decision_id": DECISION_ID,
        "decision_receipt_id": DECISION_RECEIPT_ID,
        "timeline_plan_id": TIMELINE_ID,
        "execution_id": EXECUTION_ID,
        "lost_ack_receipt_id": RECEIPT_IDS[1],
        "blocked_attestation_id": BLOCKED_ATTESTATION_ID,
        "reassessment_request_id": REASSESSMENT_ID,
        "accepted_receipt_ids": RECEIPT_IDS,
        "checkpoint_ids": CHECKPOINT_IDS,
    }


def authority_row() -> dict[str, object]:
    return {
        "case_id": CASE_ID,
        "case_state": "plan_ready",
        "current_revision": 2,
        "revision": 2,
        "brief_id": "89000000-0000-0000-0000-000000000002",
        "brief_case_id": CASE_ID,
        "brief_revision": 2,
        "brief_run_id": "7a000000-0000-0000-0000-000000000002",
        "decision_id": DECISION_ID,
        "decision_case_id": CASE_ID,
        "decision_brief_id": "89000000-0000-0000-0000-000000000002",
        "decision_run_id": "7a000000-0000-0000-0000-000000000002",
        "decision_receipt_id": DECISION_RECEIPT_ID,
        "timeline_plan_id": TIMELINE_ID,
        "timeline_decision_id": DECISION_ID,
        "execution_id": EXECUTION_ID,
        "execution_case_id": CASE_ID,
        "execution_case_revision": 2,
        "execution_decision_id": DECISION_ID,
        "execution_decision_receipt_id": DECISION_RECEIPT_ID,
        "execution_timeline_plan_id": TIMELINE_ID,
        "execution_state": "reassessment_required",
    }


def test_connected_proof_file_is_strict_and_identity_bounded(tmp_path: Path) -> None:
    verifier = load_verifier()
    path = tmp_path / "proof.json"
    path.write_text(json.dumps(proof()), encoding="utf-8")

    assert verifier.load_proof(path) == proof()

    for invalid in (
        {**proof(), "authority_kind": "connected"},
        {**proof(), "accepted_receipt_ids": [RECEIPT_IDS[0]] * 4},
        {**proof(), "case_revision": 1},
        {**proof(), "lost_ack_receipt_id": DECISION_RECEIPT_ID},
    ):
        path.write_text(json.dumps(invalid), encoding="utf-8")
        with pytest.raises(SystemExit, match="invalid connected plan execution proof"):
            verifier.load_proof(path)


def test_connected_validator_binds_the_exact_predecessor_chain() -> None:
    verifier = load_verifier()
    verifier.validate_authority_row(authority_row(), proof())

    for field in (
        "decision_id",
        "decision_receipt_id",
        "timeline_plan_id",
        "execution_case_revision",
        "execution_state",
    ):
        changed = authority_row()
        changed[field] = 3 if field.endswith("revision") else "ffffffff-ffff-ffff-ffff-ffffffffffff"
        with pytest.raises(SystemExit, match="connected plan execution authority mismatch"):
            verifier.validate_authority_row(changed, proof())
