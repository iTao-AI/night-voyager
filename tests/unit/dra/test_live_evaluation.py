from __future__ import annotations

import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from night_voyager.dra.fixtures import load_live_closure_scenario
from night_voyager.dra.live_evaluation import (
    DraEvaluationReceiptV1,
    DraLiveOutcomeExpectedV1,
    DraLiveOutcomeProjectionV1,
    build_evaluation_report,
    canonical_report_bytes,
    evaluate_outcome,
    evaluate_trajectory,
    render_evaluation_report,
)

INTENT_SHA = "a" * 64
CAPTURE_SHA = "b" * 64
PROMOTE_SHA = "c" * 64
REVIEW_SHA = "d" * 64
DECIDE_SHA = "e" * 64


def receipts() -> tuple[DraEvaluationReceiptV1, ...]:
    return (
        DraEvaluationReceiptV1(
            receipt_id="capture-receipt",
            parent_receipt_id=None,
            stage="capture-live",
            intent_sha256=INTENT_SHA,
            assertion_ids=(
                "producer_pin_exact",
                "provider_attempt_exactly_one",
                "terminal_transition_valid",
                "artifact_identity_exact",
                "evidence_ownership_and_selection_valid",
                "no_second_provider_run",
            ),
            observed_identity_hashes=(CAPTURE_SHA,),
        ),
        DraEvaluationReceiptV1(
            receipt_id="promote-receipt",
            parent_receipt_id="capture-receipt",
            stage="promote",
            intent_sha256=INTENT_SHA,
            assertion_ids=(
                "candidate_precedes_promotion",
                "candidate_untrusted_until_advisor",
                "promotion_actor_explicit",
                "promoted_pack_exact",
                "no_auto_promotion",
            ),
            observed_identity_hashes=(PROMOTE_SHA,),
        ),
        DraEvaluationReceiptV1(
            receipt_id="review-receipt",
            parent_receipt_id="promote-receipt",
            stage="review",
            intent_sha256=INTENT_SHA,
            assertion_ids=(
                "skill_pin_exact",
                "task_execution_event_sse_run_correlated",
                "advisor_review_explicit",
            ),
            observed_identity_hashes=(REVIEW_SHA,),
        ),
        DraEvaluationReceiptV1(
            receipt_id="decide-receipt",
            parent_receipt_id="review-receipt",
            stage="decide",
            intent_sha256=INTENT_SHA,
            assertion_ids=(
                "family_decision_explicit",
                "receipt_timeline_correlated",
                "no_auto_decision",
            ),
            observed_identity_hashes=(DECIDE_SHA,),
        ),
    )


def expected_outcome() -> DraLiveOutcomeExpectedV1:
    return DraLiveOutcomeExpectedV1(
        candidate_id="candidate-1",
        source_pack_id="source-pack-1",
        source_pack_version=2,
        source_entry_id="source-entry-1",
        evidence_id="evidence-1",
        task_id="task-1",
        task_state="completed",
        planning_run_id="planning-run-1",
        planning_run_state="needs_advisor_review",
    )


def outcome_projection() -> DraLiveOutcomeProjectionV1:
    return DraLiveOutcomeProjectionV1(
        candidate_id="candidate-1",
        candidate_count=1,
        verification_count=1,
        approved_verification_count=1,
        promoted_source_pack_id="source-pack-1",
        promoted_source_pack_version=2,
        promoted_source_entry_id="source-entry-1",
        promoted_evidence_id="evidence-1",
        external_claim="australia_program_fit",
        evidence_role="program_fit",
        external_authority="externally_verified",
        governed_task_count=1,
        task_id="task-1",
        task_state="completed",
        planning_run_id="planning-run-1",
        planning_run_state="needs_advisor_review",
        advisor_review_count=1,
        family_decision_count=1,
        decision_receipt_count=1,
        timeline_plan_count=1,
        tenant_isolated=True,
        partial_row_set_absent=True,
        observed_identity_hashes=("f" * 64,),
    )


def test_trajectory_assertions_are_closed_complete_and_order_independent() -> None:
    scenario = load_live_closure_scenario()
    first = evaluate_trajectory(scenario, receipts())
    reordered = evaluate_trajectory(scenario, tuple(reversed(receipts())))
    assert first == reordered
    assert all(result.status == "passed" for result in first)
    assert {result.assertion_id for result in first} == {
        "producer_pin_exact",
        "provider_attempt_exactly_one",
        "terminal_transition_valid",
        "artifact_identity_exact",
        "evidence_ownership_and_selection_valid",
        "candidate_precedes_promotion",
        "candidate_untrusted_until_advisor",
        "promotion_actor_explicit",
        "promoted_pack_exact",
        "skill_pin_exact",
        "task_execution_event_sse_run_correlated",
        "advisor_review_explicit",
        "family_decision_explicit",
        "receipt_timeline_correlated",
        "no_auto_promotion",
        "no_auto_decision",
        "no_second_provider_run",
    }


def test_missing_observation_is_failed_not_inferred() -> None:
    scenario = load_live_closure_scenario()
    incomplete = receipts()[:-1]
    results = evaluate_trajectory(scenario, incomplete)
    failed = {item.assertion_id for item in results if item.status == "failed"}
    assert failed == {
        "family_decision_explicit",
        "receipt_timeline_correlated",
        "no_auto_decision",
    }


@pytest.mark.parametrize(
    "mutate",
    (
        lambda values: values + (values[0],),
        lambda values: values[:-1]
        + (
            values[-1].model_copy(
                update={"parent_receipt_id": "missing-parent"}
            ),
        ),
        lambda values: values[:-1]
        + (
            values[-1].model_copy(
                update={"parent_receipt_id": values[0].receipt_id}
            ),
        ),
    ),
)
def test_duplicate_missing_parent_and_forged_child_are_rejected(mutate) -> None:
    with pytest.raises(ValueError):
        evaluate_trajectory(load_live_closure_scenario(), mutate(receipts()))


def test_receipt_rejects_content_and_unknown_assertion() -> None:
    payload = receipts()[0].model_dump(mode="json")
    with pytest.raises(ValidationError):
        DraEvaluationReceiptV1.model_validate(payload | {"content": "forbidden"})
    with pytest.raises(ValidationError):
        DraEvaluationReceiptV1.model_validate(
            payload | {"assertion_ids": ["unknown_assertion"]}
        )


def test_outcome_evaluation_is_exact_and_fail_closed() -> None:
    passed = evaluate_outcome(expected_outcome(), outcome_projection())
    assert all(result.status == "passed" for result in passed)
    failed = evaluate_outcome(
        expected_outcome(),
        outcome_projection().model_copy(
            update={
                "governed_task_count": 2,
                "external_authority": "untrusted_candidate",
                "tenant_isolated": False,
            }
        ),
    )
    assert {
        result.assertion_id for result in failed if result.status == "failed"
    } == {
        "external_authority_exact",
        "governed_task_exactly_one",
        "tenant_isolation_preserved",
    }


def test_canonical_report_is_stable_and_excludes_ambient_time() -> None:
    scenario = load_live_closure_scenario()
    trajectory = evaluate_trajectory(scenario, receipts())
    outcome = evaluate_outcome(expected_outcome(), outcome_projection())
    first = build_evaluation_report(
        scenario=scenario,
        intent_sha256=INTENT_SHA,
        trajectory=trajectory,
        outcome=outcome,
    )
    second = build_evaluation_report(
        scenario=scenario,
        intent_sha256=INTENT_SHA,
        trajectory=tuple(reversed(trajectory)),
        outcome=tuple(reversed(outcome)),
    )
    assert canonical_report_bytes(first) == canonical_report_bytes(second)
    payload = json.loads(canonical_report_bytes(first))
    assert payload["status"] == "passed"
    assert "duration" not in payload
    assert "clock" not in payload
    assert render_evaluation_report(first, duration_ms=1) != (
        render_evaluation_report(first, duration_ms=999)
    )
    assert canonical_report_bytes(first) == canonical_report_bytes(second)


@pytest.mark.parametrize(
    "forbidden",
    ("content", "body", "prompt", "headers", "environment"),
)
def test_report_schema_rejects_content_bearing_keys(forbidden: str) -> None:
    scenario = load_live_closure_scenario()
    report = build_evaluation_report(
        scenario=scenario,
        intent_sha256=INTENT_SHA,
        trajectory=evaluate_trajectory(scenario, receipts()),
        outcome=evaluate_outcome(expected_outcome(), outcome_projection()),
    )
    payload = deepcopy(report.model_dump(mode="json"))
    payload[forbidden] = "forbidden"
    with pytest.raises(ValidationError):
        type(report).model_validate(payload)
