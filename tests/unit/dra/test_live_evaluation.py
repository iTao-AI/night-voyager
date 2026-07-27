from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from night_voyager.dra.fixtures import (
    load_live_closure_scenario,
    load_strict_live_closure_scenario,
)
from night_voyager.dra.live_evaluation import (
    OUTCOME_ASSERTIONS,
    TRAJECTORY_ASSERTIONS,
    DraDurableCandidateIdentityV2,
    DraEvaluationReceiptV1,
    DraLiveCandidateReadinessV3,
    DraLiveEvaluationReportV1,
    DraLiveEvaluationReportV2,
    DraLiveOutcomeExpectedV1,
    DraLiveOutcomeProjectionV1,
    DraLiveOutcomeProjectionV2,
    build_evaluation_report,
    canonical_report_bytes,
    evaluate_outcome,
    evaluate_strict_candidate,
    evaluate_trajectory,
)
from night_voyager.dra.live_models import (
    DraCaptureReceiptV1,
    DraDecisionAuthorityV1,
    DraDecisionReceiptV1,
    DraPlanningTaskProjectionV1,
    DraPromotionReceiptV1,
    DraProviderAttemptEvidenceV1,
    DraReviewAuthorityV1,
    DraReviewReceiptV1,
    DraSelectedEvidenceV1,
    DraStageStateV1,
    SnapshotIdentityV1,
)
from night_voyager.skills.models import SkillRuntimePin

INTENT = "a" * 64
CANDIDATE = UUID("10000000-0000-4000-8000-000000000001")
PACK = UUID("10000000-0000-4000-8000-000000000002")
ENTRY = UUID("10000000-0000-4000-8000-000000000003")
EVIDENCE = UUID("10000000-0000-4000-8000-000000000004")
VERIFICATION = UUID("10000000-0000-4000-8000-000000000005")
TASK = UUID("10000000-0000-4000-8000-000000000006")
RUN = UUID("10000000-0000-4000-8000-000000000007")
REVIEW = UUID("10000000-0000-4000-8000-000000000008")
BRIEF = UUID("10000000-0000-4000-8000-000000000009")
ROUTE = UUID("10000000-0000-4000-8000-000000000010")
DECISION = UUID("10000000-0000-4000-8000-000000000011")
DECISION_RECEIPT = UUID("10000000-0000-4000-8000-000000000012")
TIMELINE = UUID("10000000-0000-4000-8000-000000000013")
EXECUTION = UUID("10000000-0000-4000-8000-000000000014")
SKILL_DEFINITION = UUID("10000000-0000-4000-8000-000000000015")
SKILL_VERSION = UUID("10000000-0000-4000-8000-000000000016")
SKILL_EVENT = UUID("10000000-0000-4000-8000-000000000017")
URL = "https://example.edu/source"


def strict_readiness() -> DraLiveCandidateReadinessV3:
    scenario = load_strict_live_closure_scenario()
    return DraLiveCandidateReadinessV3(
        schema_version="night-voyager.dra-live-candidate-readiness.v3",
        status="INCOMPLETE_PENDING_LIVE_ACCEPTANCE",
        producer=scenario.producer,
        request_identity=scenario.request_identity,
        observed_profile=scenario.profile_manifest,
        authorization="PENDING_SEPARATE_LIVE_ACCEPTANCE_AUTHORIZATION",
    )


def strict_outcome_projection() -> DraLiveOutcomeProjectionV2:
    scenario = load_strict_live_closure_scenario()
    base = outcome_projection()
    return DraLiveOutcomeProjectionV2(
        **base.model_dump(mode="python"),
        schema_version="night-voyager.dra-live-outcome-projection.v2",
        durable_candidate=DraDurableCandidateIdentityV2(
            schema_version="night-voyager.dra-durable-candidate-identity.v2",
            candidate_id=str(CANDIDATE),
            producer=scenario.producer,
            request_identity=scenario.request_identity,
            observed_profile=scenario.profile_manifest,
        ),
    )


def typed_receipts() -> tuple[
    DraCaptureReceiptV1,
    DraPromotionReceiptV1,
    DraReviewReceiptV1,
    DraDecisionReceiptV1,
]:
    scenario = load_live_closure_scenario()
    stages = (DraStageStateV1(stage="capture-live", status="completed"),)
    capture = DraCaptureReceiptV1(
        schema_version="night-voyager.dra-live-capture-receipt.v1",
        intent_sha256=INTENT,
        attempt_id="attempt-1",
        producer=scenario.producer,
        run_id="run-1",
        segment_id="segment-1",
        artifact=scenario.result.artifact,
        selected_evidence=DraSelectedEvidenceV1(
            evidence_id="evidence-1",
            run_id="run-1",
            segment_id="segment-1",
            source_url=URL,
            source_identity=URL,
            retrieved_at=datetime(2026, 7, 25, tzinfo=UTC),
            citation_status="cited",
            verification_status="verified",
        ),
        stage_states=stages,
        provider_attempt_consumed=True,
        provider_attempt_evidence=DraProviderAttemptEvidenceV1(
            create_keys=("9" * 64,),
            observed_run_ids=("run-1",),
            accepted_run_id="run-1",
        ),
        candidate_id=CANDIDATE,
        candidate_authority="untrusted_candidate",
        candidate_import_key="b" * 64,
        cleanup_status="removed",
    )
    promotion = DraPromotionReceiptV1(
        intent_sha256=INTENT,
        attempt_id="attempt-1",
        candidate_id=CANDIDATE,
        dra_evidence_id="evidence-1",
        selected_raw_url=URL,
        promotion_key="c" * 64,
        verification_id=VERIFICATION,
        promoted_source_pack_version=2,
        promoted_source_entry_id=ENTRY,
        promoted_evidence_id=EVIDENCE,
        snapshot=SnapshotIdentityV1(
            canonical_url=URL,
            logical_path="source/page.html",
            byte_length=10,
            sha256="d" * 64,
        ),
        stage_states=(*stages, DraStageStateV1(stage="promote", status="completed")),
    )
    pin = SkillRuntimePin(
        skill_definition_id=SKILL_DEFINITION,
        skill_version_id=SKILL_VERSION,
        skill_activation_event_id=SKILL_EVENT,
        skill_activation_sequence=1,
        runtime_binding_sha256="e" * 64,
    )
    task = DraPlanningTaskProjectionV1(
        task_id=TASK,
        case_id=UUID("10000000-0000-4000-8000-000000000020"),
        case_revision=1,
        operation="generate_governed_mixed_planning_run_v1",
        source_pack_id=PACK,
        source_pack_version=2,
        status="needs_advisor_review",
        planning_run_id=RUN,
        execution_id=EXECUTION,
        terminal_event_id=4,
        skill_pin=pin,
        request_sha256="f" * 64,
    )
    review_authority = DraReviewAuthorityV1(
        review_id=REVIEW,
        case_id=task.case_id,
        expected_case_revision=1,
        planning_run_id=RUN,
        brief_id=BRIEF,
        eligible_route_ids=(ROUTE,),
        request_sha256="1" * 64,
    )
    review = DraReviewReceiptV1(
        intent_sha256=INTENT,
        attempt_id="attempt-1",
        candidate_id=CANDIDATE,
        source_pack_id=PACK,
        source_pack_version=2,
        task_key="2" * 64,
        review_key="3" * 64,
        task=task,
        review=review_authority,
        stage_states=(
            *promotion.stage_states,
            DraStageStateV1(stage="review", status="completed"),
        ),
    )
    decision = DraDecisionReceiptV1(
        intent_sha256=INTENT,
        attempt_id="attempt-1",
        decision_key="4" * 64,
        review_id=REVIEW,
        planning_run_id=RUN,
        decision=DraDecisionAuthorityV1(
            decision_id=DECISION,
            decision_receipt_id=DECISION_RECEIPT,
            timeline_plan_id=TIMELINE,
            brief_id=BRIEF,
            selected_route_id=ROUTE,
            expected_brief_version=1,
            accepted_budget_min_minor=100,
            accepted_budget_max_minor=200,
            currency="CNY",
            accepted_trade_offs=("bounded",),
            request_sha256="5" * 64,
        ),
        stage_states=(
            *review.stage_states,
            DraStageStateV1(stage="decide", status="completed"),
        ),
    )
    return capture, promotion, review, decision


def expected_outcome() -> DraLiveOutcomeExpectedV1:
    return DraLiveOutcomeExpectedV1(
        candidate_id=str(CANDIDATE),
        source_pack_id=str(PACK),
        source_pack_version=2,
        source_entry_id=str(ENTRY),
        evidence_id=str(EVIDENCE),
        task_id=str(TASK),
        task_state="waiting_review",
        planning_run_id=str(RUN),
        planning_run_state="review_required",
        verification_id=str(VERIFICATION),
        execution_id=str(EXECUTION),
        terminal_event_id=4,
        skill_definition_id=str(SKILL_DEFINITION),
        skill_version_id=str(SKILL_VERSION),
        skill_activation_event_id=str(SKILL_EVENT),
        skill_activation_sequence=1,
        runtime_binding_sha256="e" * 64,
        review_id=str(REVIEW),
        brief_id=str(BRIEF),
        decision_id=str(DECISION),
        decision_receipt_id=str(DECISION_RECEIPT),
        timeline_plan_id=str(TIMELINE),
    )


def outcome_projection() -> DraLiveOutcomeProjectionV1:
    expected = expected_outcome()
    return DraLiveOutcomeProjectionV1(
        candidate_id=expected.candidate_id,
        candidate_count=1,
        verification_count=1,
        approved_verification_count=1,
        verification_id=expected.verification_id,
        promoted_source_pack_id=expected.source_pack_id,
        promoted_source_pack_version=2,
        promoted_source_entry_id=expected.source_entry_id,
        promoted_evidence_id=expected.evidence_id,
        external_claim="australia_program_fit",
        evidence_role="program_fit",
        external_authority="externally_verified",
        governed_task_count=1,
        task_id=expected.task_id,
        task_state=expected.task_state,
        planning_run_id=expected.planning_run_id,
        planning_run_state=expected.planning_run_state,
        execution_count=1,
        execution_id=expected.execution_id,
        execution_planning_run_id=expected.planning_run_id,
        terminal_event_count=1,
        terminal_event_id=4,
        terminal_event_planning_run_id=expected.planning_run_id,
        sse_cursor=4,
        skill_definition_id=expected.skill_definition_id,
        skill_version_id=expected.skill_version_id,
        skill_activation_event_id=expected.skill_activation_event_id,
        skill_activation_sequence=1,
        runtime_binding_sha256=expected.runtime_binding_sha256,
        advisor_review_count=1,
        review_id=expected.review_id,
        brief_id=expected.brief_id,
        family_decision_count=1,
        decision_id=expected.decision_id,
        decision_receipt_count=1,
        decision_receipt_id=expected.decision_receipt_id,
        timeline_plan_count=1,
        timeline_plan_id=expected.timeline_plan_id,
        tenant_isolated=True,
        partial_row_set_absent=True,
        observed_identity_hashes=("6" * 64,),
    )


def test_typed_trajectory_is_closed_complete_and_order_independent() -> None:
    scenario = load_live_closure_scenario()
    first = evaluate_trajectory(scenario, typed_receipts())
    reordered = evaluate_trajectory(scenario, tuple(reversed(typed_receipts())))
    assert first == reordered
    assert all(result.status == "passed" for result in first)
    assert {result.assertion_id for result in first} == set(TRAJECTORY_ASSERTIONS)


def test_provider_attempt_assertions_reject_multiple_runs_or_keys() -> None:
    capture, promotion, review, decision = typed_receipts()
    payload = capture.model_dump(mode="json")
    payload["provider_attempt_evidence"] = {
        "create_keys": ("9" * 64, "8" * 64),
        "observed_run_ids": ("run-1", "run-2"),
        "accepted_run_id": "run-1",
    }
    forged = DraCaptureReceiptV1.model_validate(payload)
    failed = {
        item.assertion_id
        for item in evaluate_trajectory(
            load_live_closure_scenario(),
            (forged, promotion, review, decision),
        )
        if item.status == "failed"
    }
    assert failed == {"provider_attempt_exactly_one", "no_second_provider_run"}


def test_self_asserted_trajectory_receipts_are_not_authority() -> None:
    forged = (
        DraEvaluationReceiptV1(
            receipt_id="forged",
            parent_receipt_id=None,
            stage="capture-live",
            intent_sha256=INTENT,
            assertion_ids=("producer_pin_exact",),
            observed_identity_hashes=("7" * 64,),
        ),
    )
    with pytest.raises(ValueError, match="typed_stage_receipts_required"):
        evaluate_trajectory(load_live_closure_scenario(), forged)  # type: ignore[arg-type]


def test_missing_or_forged_typed_receipt_chain_fails_closed() -> None:
    with pytest.raises(ValueError, match="typed_stage_receipts_required"):
        evaluate_trajectory(load_live_closure_scenario(), typed_receipts()[:-1])
    capture, promotion, review, decision = typed_receipts()
    forged = decision.model_copy(update={"review_id": UUID(int=999)})
    with pytest.raises(ValueError, match="receipt_chain_invalid"):
        evaluate_trajectory(
            load_live_closure_scenario(), (capture, promotion, review, forged)
        )


def test_outcome_requires_execution_event_sse_pin_and_exact_receipt_identities() -> None:
    passed = evaluate_outcome(expected_outcome(), outcome_projection())
    assert all(item.status == "passed" for item in passed)
    failed = outcome_projection().model_copy(
        update={
            "execution_planning_run_id": "wrong-run",
            "sse_cursor": 5,
            "runtime_binding_sha256": "8" * 64,
            "decision_receipt_id": "wrong-receipt",
            "timeline_plan_id": "wrong-timeline",
        }
    )
    failed_ids = {
        item.assertion_id
        for item in evaluate_outcome(expected_outcome(), failed)
        if item.status == "failed"
    }
    assert failed_ids == {
        "task_terminal_state_exact",
        "decision_receipt_exactly_one",
        "timeline_plan_exactly_one",
    }


def test_canonical_report_round_trips_and_status_is_derived() -> None:
    report = build_evaluation_report(
        scenario=load_live_closure_scenario(),
        receipts=typed_receipts(),
        outcome=evaluate_outcome(expected_outcome(), outcome_projection()),
    )
    encoded = canonical_report_bytes(report)
    parsed = DraLiveEvaluationReportV1.model_validate_json(encoded)
    assert canonical_report_bytes(parsed) == encoded
    assert parsed.status == "passed"
    payload = json.loads(encoded)
    without_status = dict(payload)
    without_status.pop("status")
    assert DraLiveEvaluationReportV1.model_validate(without_status).status == "passed"
    for invalid in (None, "failed", 1):
        with pytest.raises(ValidationError):
            DraLiveEvaluationReportV1.model_validate(payload | {"status": invalid})


def test_final_report_requires_exact_trajectory_and_outcome_union() -> None:
    report = build_evaluation_report(
        scenario=load_live_closure_scenario(),
        receipts=typed_receipts(),
        outcome=evaluate_outcome(expected_outcome(), outcome_projection()),
    )
    assert report.status == "passed"
    assert len(report.assertions) == len((*TRAJECTORY_ASSERTIONS, *OUTCOME_ASSERTIONS))
    payload = report.model_dump(mode="json")
    payload["assertions"] = payload["assertions"][:-1]
    with pytest.raises(ValidationError):
        DraLiveEvaluationReportV1.model_validate(payload)


def test_report_rejects_content_keys() -> None:
    report = build_evaluation_report(
        scenario=load_live_closure_scenario(),
        receipts=typed_receipts(),
        outcome=evaluate_outcome(expected_outcome(), outcome_projection()),
    )
    with pytest.raises(ValidationError):
        DraLiveEvaluationReportV1.model_validate(
            report.model_dump(mode="json") | {"content": "forbidden"}
        )


def test_strict_readiness_rejects_legacy_generic_and_mixed_identity() -> None:
    scenario = load_strict_live_closure_scenario()
    readiness = strict_readiness()
    assert readiness.producer == scenario.producer
    assert readiness.request_identity.profile_id == "generic-strict-citation"
    assert readiness.observed_profile.profile_version == "1"
    assert readiness.producer.proof_schema == "dra.strict-citation-profile.v1"

    payload = readiness.model_dump(mode="json")
    for mutation in (
        {"schema_version": "night-voyager.dra-live-candidate-readiness.v2"},
        {
            "request_identity": {
                "profile_id": "generic",
                "request_sha256": scenario.request_identity.request_sha256,
            }
        },
        {
            "producer": {
                **scenario.producer.model_dump(mode="json", by_alias=True),
                "commit": "0" * 40,
            }
        },
        {
            "producer": {
                key: value
                for key, value in scenario.producer.model_dump(
                    mode="json", by_alias=True
                ).items()
                if key != "proof_schema"
            }
        },
    ):
        with pytest.raises(ValidationError):
            DraLiveCandidateReadinessV3.model_validate(
                {**payload, **mutation}
            )


def test_strict_evaluation_binds_only_matching_durable_candidate_authority() -> None:
    readiness = strict_readiness()
    projection = strict_outcome_projection()

    report = evaluate_strict_candidate(readiness, projection)

    assert isinstance(report, DraLiveEvaluationReportV2)
    assert report.status == "passed"
    assert report.candidate_id == str(CANDIDATE)
    for field in (
        "durable_candidate_identity_sha256",
        "readiness_sha256",
        "request_identity_sha256",
        "outcome_projection_sha256",
    ):
        assert len(getattr(report, field)) == 64

    durable = projection.durable_candidate
    assert durable is not None
    for mutation in (
        {"candidate_id": "10000000-0000-4000-8000-000000000099"},
        {
            "request_identity": durable.request_identity.model_copy(
                update={"request_sha256": "f" * 64}
            )
        },
        {
            "observed_profile": durable.observed_profile.model_copy(
                update={"profile_version": "2"}
            )
        },
        {
            "producer": durable.producer.model_copy(
                update={"proof_schema": "dra.unknown.v1"}
            )
        },
    ):
        mismatched = projection.model_copy(
            update={
                "durable_candidate": durable.model_copy(update=mutation)
            }
        )
        with pytest.raises(ValueError, match="strict_candidate_identity"):
            evaluate_strict_candidate(readiness, mismatched)


def test_strict_evaluation_never_refills_missing_database_identity() -> None:
    projection = strict_outcome_projection().model_copy(
        update={"durable_candidate": None}
    )

    with pytest.raises(ValueError, match="strict_candidate_identity"):
        evaluate_strict_candidate(strict_readiness(), projection)
