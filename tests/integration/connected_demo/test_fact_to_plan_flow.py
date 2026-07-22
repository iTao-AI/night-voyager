from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def load_verifier():
    path = Path("scripts/verify_fact_to_plan_flow.py")
    spec = importlib.util.spec_from_file_location("verify_fact_to_plan_flow", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def proof() -> dict[str, object]:
    return {
        "schema_version": 1,
        "case_id": "41000000-0000-0000-0000-000000000001",
        "case_revision": 2,
        "task_id": "61000000-0000-0000-0000-000000000001",
    }


def authority_row() -> dict[str, object]:
    return {
        "case_id": proof()["case_id"],
        "case_state": "plan_ready",
        "current_revision": 2,
        "candidate_id": "44000000-0000-0000-0000-000000000001",
        "candidate_revision": 1,
        "verification_decision": "confirm",
        "result_fact_id": "45000000-0000-0000-0000-000000000001",
        "result_revision": 2,
        "fact_id": "45000000-0000-0000-0000-000000000001",
        "fact_key": "family.budget",
        "fact_version": 1,
        "revision_fact_id": "45000000-0000-0000-0000-000000000001",
        "task_id": proof()["task_id"],
        "task_case_id": proof()["case_id"],
        "operation": "generate_planning_run_v1",
        "task_revision": 2,
        "task_state": "waiting_review",
        "skill_definition_id": "81000000-0000-0000-0000-000000000002",
        "skill_version_id": "82000000-0000-0000-0000-000000000002",
        "skill_activation_event_id": "84000000-0000-0000-0000-000000000001",
        "skill_activation_sequence": 1,
        "runtime_binding_sha256": "a" * 64,
        "execution_status": "succeeded",
        "execution_run_id": "70000000-0000-0000-0000-000000000001",
        "execution_definition_id": "81000000-0000-0000-0000-000000000002",
        "execution_version_id": "82000000-0000-0000-0000-000000000002",
        "execution_activation_id": "84000000-0000-0000-0000-000000000001",
        "execution_activation_sequence": 1,
        "execution_runtime_sha256": "a" * 64,
        "planning_run_id": "70000000-0000-0000-0000-000000000001",
        "planning_case_id": proof()["case_id"],
        "run_revision": 2,
        "run_state": "review_required",
        "review_id": "88000000-0000-0000-0000-000000000001",
        "review_case_id": proof()["case_id"],
        "review_action": "approve_for_consultation",
        "review_run_id": "70000000-0000-0000-0000-000000000001",
        "review_revision": 2,
        "brief_id": "89000000-0000-0000-0000-000000000001",
        "brief_case_id": proof()["case_id"],
        "brief_run_id": "70000000-0000-0000-0000-000000000001",
        "brief_review_id": "88000000-0000-0000-0000-000000000001",
        "brief_revision": 2,
        "decision_id": "91000000-0000-0000-0000-000000000001",
        "decision_case_id": proof()["case_id"],
        "decision_brief_id": "89000000-0000-0000-0000-000000000001",
        "decision_run_id": "70000000-0000-0000-0000-000000000001",
        "receipt_id": "90000000-0000-0000-0000-000000000001",
        "timeline_decision_id": "91000000-0000-0000-0000-000000000001",
        "queued_events": 1,
        "waiting_review_events": 1,
        "event_count": 5,
        "dispatch_remaining": 0,
        "version_runtime_sha256": "a" * 64,
        "activation_version_id": "82000000-0000-0000-0000-000000000002",
        "activation_sequence": 1,
    }


def test_proof_file_is_exact_and_uuid_bounded(tmp_path: Path) -> None:
    verifier = load_verifier()
    path = tmp_path / "proof.json"
    path.write_text(json.dumps(proof()), encoding="utf-8")
    assert verifier.load_proof(path) == proof()

    path.write_text(json.dumps({**proof(), "extra": True}), encoding="utf-8")
    with pytest.raises(SystemExit, match="invalid fact-to-plan proof file"):
        verifier.load_proof(path)


def test_authority_validator_binds_every_same_case_identity() -> None:
    verifier = load_verifier()
    verifier.validate_authority_row(authority_row(), proof())

    for field in (
        "result_fact_id",
        "task_revision",
        "execution_version_id",
        "review_run_id",
        "decision_run_id",
        "timeline_decision_id",
    ):
        changed = authority_row()
        changed[field] = "ffffffff-ffff-ffff-ffff-ffffffffffff" if field.endswith("id") else 3
        with pytest.raises(SystemExit, match="fact-to-plan database authority mismatch"):
            verifier.validate_authority_row(changed, proof())
