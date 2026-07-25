from __future__ import annotations

from night_voyager.dra.fixtures import load_live_closure_scenario
from night_voyager.dra.live_evaluation import (
    OUTCOME_ASSERTIONS,
    STAGE_ASSERTIONS,
    STAGE_ORDER,
    TRAJECTORY_ASSERTIONS,
    DraEvaluationReceiptV1,
    DraLiveOutcomeExpectedV1,
    DraLiveOutcomeProjectionV1,
    EvaluationStage,
    TrajectoryAssertionId,
    evaluate_full_closure,
)


def test_full_closure_requires_trajectory_and_authoritative_outcome() -> None:
    scenario = load_live_closure_scenario()
    grouped: tuple[
        tuple[EvaluationStage, tuple[TrajectoryAssertionId, ...]], ...
    ] = tuple(
        (
            stage,
            tuple(
                item
                for item in TRAJECTORY_ASSERTIONS
                if item in STAGE_ASSERTIONS[stage]
            ),
        )
        for stage in STAGE_ORDER
    )
    receipts = tuple(
        DraEvaluationReceiptV1(
            receipt_id=f"receipt-{index}",
            parent_receipt_id=None if index == 0 else f"receipt-{index - 1}",
            stage=stage,
            intent_sha256="a" * 64,
            assertion_ids=assertions,
            observed_identity_hashes=(f"{index + 1:064x}",),
        )
        for index, (stage, assertions) in enumerate(grouped)
    )
    expected = DraLiveOutcomeExpectedV1(
        candidate_id="candidate",
        source_pack_id="pack",
        source_pack_version=2,
        source_entry_id="entry",
        evidence_id="evidence",
        task_id="task",
        task_state="succeeded",
        planning_run_id="run",
        planning_run_state="awaiting_advisor_review",
    )
    outcome = DraLiveOutcomeProjectionV1(
        candidate_id="candidate",
        candidate_count=1,
        verification_count=1,
        approved_verification_count=1,
        promoted_source_pack_id="pack",
        promoted_source_pack_version=2,
        promoted_source_entry_id="entry",
        promoted_evidence_id="evidence",
        external_claim="australia_program_fit",
        evidence_role="program_fit",
        external_authority="externally_verified",
        governed_task_count=1,
        task_id="task",
        task_state="succeeded",
        planning_run_id="run",
        planning_run_state="awaiting_advisor_review",
        advisor_review_count=1,
        family_decision_count=1,
        decision_receipt_count=1,
        timeline_plan_count=1,
        tenant_isolated=True,
        partial_row_set_absent=True,
        observed_identity_hashes=("f" * 64,),
    )

    report = evaluate_full_closure(scenario, receipts, expected, outcome)

    assert report.status == "passed"
    assert len(report.assertions) == len(
        (*TRAJECTORY_ASSERTIONS, *OUTCOME_ASSERTIONS)
    )
    failed = outcome.model_copy(update={"timeline_plan_count": 0})
    assert (
        evaluate_full_closure(scenario, receipts, expected, failed).status
        == "failed"
    )
