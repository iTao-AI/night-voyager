from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from inspect import signature
from typing import cast

import pytest
from pydantic import ValidationError

from night_voyager.dra.fixtures import load_live_closure_scenario
from night_voyager.dra.live_evaluation import (
    OUTCOME_ASSERTIONS,
    TRAJECTORY_ASSERTIONS,
    AssertionResultV1,
    DraEvaluationReceiptV1,
    DraLiveEvaluationReportV1,
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
Receipts = tuple[DraEvaluationReceiptV1, ...]
ReceiptMutator = Callable[[Receipts], Receipts]


def receipts() -> Receipts:
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


def duplicate_receipt(values: Receipts) -> Receipts:
    return values + (values[0],)


def replace_parent_with_missing(values: Receipts) -> Receipts:
    return values[:-1] + (
        values[-1].model_copy(update={"parent_receipt_id": "missing-parent"}),
    )


def forge_child_parent(values: Receipts) -> Receipts:
    return values[:-1] + (
        values[-1].model_copy(
            update={"parent_receipt_id": values[0].receipt_id}
        ),
    )


@pytest.mark.parametrize(
    "mutate",
    (
        duplicate_receipt,
        replace_parent_with_missing,
        forge_child_parent,
    ),
)
def test_duplicate_missing_parent_and_forged_child_are_rejected(
    mutate: ReceiptMutator,
) -> None:
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
    outcome = evaluate_outcome(expected_outcome(), outcome_projection())
    first = build_evaluation_report(
        scenario=scenario,
        receipts=receipts(),
        outcome=outcome,
    )
    second = build_evaluation_report(
        scenario=scenario,
        receipts=tuple(reversed(receipts())),
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


def test_final_report_requires_the_exact_closed_assertion_union() -> None:
    scenario = load_live_closure_scenario()
    subset = AssertionResultV1(
        assertion_id="producer_pin_exact",
        status="passed",
        public_code="producer_pin_exact_passed",
        observed_identity_hashes=(),
    )
    with pytest.raises(ValidationError, match="dra_evaluation_assertion_set_invalid"):
        DraLiveEvaluationReportV1(
            schema_version="night-voyager.dra-live-evaluation.v1",
            scenario_id=scenario.scenario_id,
            producer=scenario.producer,
            intent_sha256=INTENT_SHA,
            assertions=(subset,),
            expected_non_claims=scenario.expected_non_claims,
        )

    with pytest.raises(ValidationError, match="dra_evaluation_assertion_set_invalid"):
        build_evaluation_report(
            scenario=scenario,
            receipts=receipts(),
            outcome=(),
        )


def test_final_report_rejects_duplicate_unknown_and_extra_assertions() -> None:
    scenario = load_live_closure_scenario()
    report = build_evaluation_report(
        scenario=scenario,
        receipts=receipts(),
        outcome=evaluate_outcome(expected_outcome(), outcome_projection()),
    )
    payload = cast(dict[str, object], report.model_dump(mode="json"))
    assertion_value = payload["assertions"]
    assert isinstance(assertion_value, list)
    assertions = cast(list[dict[str, object]], assertion_value)

    duplicate = deepcopy(payload)
    duplicate["assertions"] = [*assertions, deepcopy(assertions[0])]
    with pytest.raises(ValidationError):
        DraLiveEvaluationReportV1.model_validate(duplicate)

    unknown = deepcopy(payload)
    unknown_assertions = deepcopy(assertions)
    unknown_assertions[0]["assertion_id"] = "unknown_assertion"
    unknown["assertions"] = unknown_assertions
    with pytest.raises(ValidationError):
        DraLiveEvaluationReportV1.model_validate(unknown)

    extra = deepcopy(payload)
    extra["assertions"] = [
        *assertions,
        {
            "assertion_id": "unexpected_extra",
            "status": "passed",
            "public_code": "unexpected_extra_passed",
            "observed_identity_hashes": [],
        },
    ]
    with pytest.raises(ValidationError):
        DraLiveEvaluationReportV1.model_validate(extra)


def test_report_intent_is_derived_from_the_validated_receipt_root() -> None:
    scenario = load_live_closure_scenario()
    receipt_intent = "b" * 64
    bound_receipts = tuple(
        receipt.model_copy(update={"intent_sha256": receipt_intent})
        for receipt in receipts()
    )
    report = build_evaluation_report(
        scenario=scenario,
        receipts=bound_receipts,
        outcome=evaluate_outcome(expected_outcome(), outcome_projection()),
    )
    assert report.intent_sha256 == receipt_intent
    assert "intent_sha256" not in signature(build_evaluation_report).parameters

    with pytest.raises(ValueError, match="dra_evaluation_intent_mismatch"):
        build_evaluation_report(
            scenario=scenario,
            receipts=(
                *bound_receipts[:-1],
                bound_receipts[-1].model_copy(
                    update={"intent_sha256": "d" * 64}
                ),
            ),
            outcome=evaluate_outcome(expected_outcome(), outcome_projection()),
        )
    with pytest.raises(ValueError, match="dra_evaluation_receipt_root_missing"):
        build_evaluation_report(
            scenario=scenario,
            receipts=(),
            outcome=evaluate_outcome(expected_outcome(), outcome_projection()),
        )
    with pytest.raises(ValueError, match="dra_evaluation_parent_invalid"):
        build_evaluation_report(
            scenario=scenario,
            receipts=forge_child_parent(bound_receipts),
            outcome=evaluate_outcome(expected_outcome(), outcome_projection()),
        )


def test_canonical_report_round_trips_through_its_versioned_schema() -> None:
    scenario = load_live_closure_scenario()
    report = build_evaluation_report(
        scenario=scenario,
        receipts=receipts(),
        outcome=evaluate_outcome(expected_outcome(), outcome_projection()),
    )
    encoded = canonical_report_bytes(report)
    decoded = DraLiveEvaluationReportV1.model_validate_json(encoded)
    assert decoded.status == "passed"
    assert canonical_report_bytes(decoded) == encoded
    assert tuple(item.assertion_id for item in decoded.assertions) == tuple(
        sorted((*TRAJECTORY_ASSERTIONS, *OUTCOME_ASSERTIONS))
    )


@pytest.mark.parametrize(
    "forbidden",
    ("content", "body", "prompt", "headers", "environment"),
)
def test_report_schema_rejects_content_bearing_keys(forbidden: str) -> None:
    scenario = load_live_closure_scenario()
    report = build_evaluation_report(
        scenario=scenario,
        receipts=receipts(),
        outcome=evaluate_outcome(expected_outcome(), outcome_projection()),
    )
    payload = deepcopy(report.model_dump(mode="json"))
    payload[forbidden] = "forbidden"
    with pytest.raises(ValidationError):
        type(report).model_validate(payload)
