from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from typing import Annotated, Literal, Self, cast

from pydantic import (
    Field,
    ModelWrapValidatorHandler,
    PositiveInt,
    computed_field,
    model_validator,
)

from night_voyager.dra.live_models import (
    DraLiveProducerIdentityV1,
    DraLiveScenarioV1,
    PublicCode,
)
from night_voyager.dra.models import BoundedId, FrozenModel, Sha256

TrajectoryAssertionId = Literal[
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
]
OutcomeAssertionId = Literal[
    "candidate_exactly_one",
    "verification_exactly_one",
    "promoted_pack_mapping_exact",
    "external_claim_exact",
    "evidence_role_exact",
    "external_authority_exact",
    "governed_task_exactly_one",
    "task_terminal_state_exact",
    "planning_run_terminal_state_exact",
    "advisor_review_exactly_one",
    "family_decision_exactly_one",
    "decision_receipt_exactly_one",
    "timeline_plan_exactly_one",
    "tenant_isolation_preserved",
    "no_partial_row_set",
]
AssertionId = TrajectoryAssertionId | OutcomeAssertionId
EvaluationStage = Literal["capture-live", "promote", "review", "decide"]
EvaluationStatus = Literal["passed", "failed"]
OutcomeCount = Annotated[int, Field(ge=0)]

TRAJECTORY_ASSERTIONS: tuple[TrajectoryAssertionId, ...] = (
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
)
OUTCOME_ASSERTIONS: tuple[OutcomeAssertionId, ...] = (
    "candidate_exactly_one",
    "verification_exactly_one",
    "promoted_pack_mapping_exact",
    "external_claim_exact",
    "evidence_role_exact",
    "external_authority_exact",
    "governed_task_exactly_one",
    "task_terminal_state_exact",
    "planning_run_terminal_state_exact",
    "advisor_review_exactly_one",
    "family_decision_exactly_one",
    "decision_receipt_exactly_one",
    "timeline_plan_exactly_one",
    "tenant_isolation_preserved",
    "no_partial_row_set",
)
ALL_ASSERTIONS: frozenset[AssertionId] = frozenset(
    (*TRAJECTORY_ASSERTIONS, *OUTCOME_ASSERTIONS)
)
_STATUS_NOT_SUPPLIED = object()
STAGE_ORDER: tuple[EvaluationStage, ...] = (
    "capture-live",
    "promote",
    "review",
    "decide",
)
STAGE_ASSERTIONS: dict[EvaluationStage, frozenset[TrajectoryAssertionId]] = {
    "capture-live": frozenset(
        {
            "producer_pin_exact",
            "provider_attempt_exactly_one",
            "terminal_transition_valid",
            "artifact_identity_exact",
            "evidence_ownership_and_selection_valid",
            "no_second_provider_run",
        }
    ),
    "promote": frozenset(
        {
            "candidate_precedes_promotion",
            "candidate_untrusted_until_advisor",
            "promotion_actor_explicit",
            "promoted_pack_exact",
            "no_auto_promotion",
        }
    ),
    "review": frozenset(
        {
            "skill_pin_exact",
            "task_execution_event_sse_run_correlated",
            "advisor_review_explicit",
        }
    ),
    "decide": frozenset(
        {
            "family_decision_explicit",
            "receipt_timeline_correlated",
            "no_auto_decision",
        }
    ),
}
FORBIDDEN_REPORT_KEYS = frozenset(
    {"content", "body", "prompt", "headers", "environment"}
)


class DraEvaluationReceiptV1(FrozenModel):
    receipt_id: BoundedId
    parent_receipt_id: BoundedId | None
    stage: EvaluationStage
    intent_sha256: Sha256
    assertion_ids: tuple[TrajectoryAssertionId, ...] = Field(min_length=1)
    observed_identity_hashes: tuple[Sha256, ...]

    @model_validator(mode="after")
    def unique_observations(self) -> Self:
        if len(self.assertion_ids) != len(set(self.assertion_ids)):
            raise ValueError("dra_evaluation_assertion_duplicate")
        if len(self.observed_identity_hashes) != len(
            set(self.observed_identity_hashes)
        ):
            raise ValueError("dra_evaluation_identity_duplicate")
        return self


class DraLiveOutcomeExpectedV1(FrozenModel):
    candidate_id: BoundedId
    source_pack_id: BoundedId
    source_pack_version: PositiveInt
    source_entry_id: BoundedId
    evidence_id: BoundedId
    task_id: BoundedId
    task_state: BoundedId
    planning_run_id: BoundedId
    planning_run_state: BoundedId


class DraLiveOutcomeProjectionV1(FrozenModel):
    candidate_id: BoundedId | None
    candidate_count: OutcomeCount
    verification_count: OutcomeCount
    approved_verification_count: OutcomeCount
    promoted_source_pack_id: BoundedId | None
    promoted_source_pack_version: PositiveInt | None
    promoted_source_entry_id: BoundedId | None
    promoted_evidence_id: BoundedId | None
    external_claim: BoundedId | None
    evidence_role: BoundedId | None
    external_authority: BoundedId | None
    governed_task_count: OutcomeCount
    task_id: BoundedId | None
    task_state: BoundedId | None
    planning_run_id: BoundedId | None
    planning_run_state: BoundedId | None
    advisor_review_count: OutcomeCount
    family_decision_count: OutcomeCount
    decision_receipt_count: OutcomeCount
    timeline_plan_count: OutcomeCount
    tenant_isolated: bool
    partial_row_set_absent: bool
    observed_identity_hashes: tuple[Sha256, ...]


class AssertionResultV1(FrozenModel):
    assertion_id: AssertionId
    status: EvaluationStatus
    public_code: PublicCode
    observed_identity_hashes: tuple[Sha256, ...]


class DraLiveEvaluationReportV1(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-evaluation.v1"]
    scenario_id: Literal["dra-v0-1-6-live-closure-v1"]
    producer: DraLiveProducerIdentityV1
    intent_sha256: Sha256
    assertions: tuple[AssertionResultV1, ...] = Field(min_length=1)
    expected_non_claims: tuple[
        Literal[
            "provider_quality",
            "source_truth",
            "production_readiness",
            "admissions_outcome",
        ],
        ...,
    ]

    @model_validator(mode="after")
    def unique_assertions_and_exact_non_claims(self) -> Self:
        identifiers: list[AssertionId] = [
            item.assertion_id for item in self.assertions
        ]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("dra_evaluation_assertion_duplicate")
        if len(identifiers) != len(ALL_ASSERTIONS):
            raise ValueError("dra_evaluation_assertion_set_invalid")
        if self.expected_non_claims != (
            "provider_quality",
            "source_truth",
            "production_readiness",
            "admissions_outcome",
        ):
            raise ValueError("dra_expected_non_claims_invalid")
        object.__setattr__(
            self,
            "assertions",
            tuple(sorted(self.assertions, key=lambda item: item.assertion_id)),
        )
        return self

    @model_validator(mode="wrap")
    @classmethod
    def validate_derived_status(
        cls,
        value: object,
        handler: ModelWrapValidatorHandler[Self],
    ) -> Self:
        supplied_status: object = _STATUS_NOT_SUPPLIED
        candidate = value
        if isinstance(value, dict) and "status" in value:
            payload = cast(dict[str, object], value).copy()
            supplied_status = payload.pop("status")
            candidate = payload
        report = handler(candidate)
        if (
            supplied_status is not _STATUS_NOT_SUPPLIED
            and supplied_status != report.status
        ):
            raise ValueError("dra_evaluation_status_invalid")
        return report

    @computed_field
    @property
    def status(self) -> EvaluationStatus:
        return (
            "passed"
            if all(item.status == "passed" for item in self.assertions)
            else "failed"
        )


def _result(
    assertion_id: AssertionId,
    passed: bool,
    observed_identity_hashes: Iterable[str],
) -> AssertionResultV1:
    status: EvaluationStatus = "passed" if passed else "failed"
    return AssertionResultV1(
        assertion_id=assertion_id,
        status=status,
        public_code=f"{assertion_id}_{status}",
        observed_identity_hashes=tuple(sorted(set(observed_identity_hashes))),
    )


def _validated_receipts(
    receipts: Sequence[DraEvaluationReceiptV1],
) -> dict[EvaluationStage, DraEvaluationReceiptV1]:
    receipt_ids = [receipt.receipt_id for receipt in receipts]
    if len(receipt_ids) != len(set(receipt_ids)):
        raise ValueError("dra_evaluation_receipt_duplicate")
    by_stage: dict[EvaluationStage, DraEvaluationReceiptV1] = {}
    by_id = {receipt.receipt_id: receipt for receipt in receipts}
    intent_hashes = {receipt.intent_sha256 for receipt in receipts}
    if len(intent_hashes) > 1:
        raise ValueError("dra_evaluation_intent_mismatch")
    for receipt in receipts:
        if receipt.stage in by_stage:
            raise ValueError("dra_evaluation_stage_duplicate")
        if not set(receipt.assertion_ids).issubset(STAGE_ASSERTIONS[receipt.stage]):
            raise ValueError("dra_evaluation_stage_assertion_invalid")
        stage_index = STAGE_ORDER.index(receipt.stage)
        if stage_index == 0:
            if receipt.parent_receipt_id is not None:
                raise ValueError("dra_evaluation_parent_invalid")
        else:
            parent = (
                by_id.get(receipt.parent_receipt_id)
                if receipt.parent_receipt_id is not None
                else None
            )
            if parent is None or parent.stage != STAGE_ORDER[stage_index - 1]:
                raise ValueError("dra_evaluation_parent_invalid")
        by_stage[receipt.stage] = receipt
    return by_stage


def evaluate_trajectory(
    scenario: DraLiveScenarioV1,
    receipts: Sequence[DraEvaluationReceiptV1],
) -> tuple[AssertionResultV1, ...]:
    validated = _validated_receipts(receipts)
    observed: dict[TrajectoryAssertionId, tuple[Sha256, ...]] = {}
    for stage in STAGE_ORDER:
        receipt = validated.get(stage)
        if receipt is None:
            continue
        for assertion_id in receipt.assertion_ids:
            observed[assertion_id] = receipt.observed_identity_hashes
    exact_producer = (
        scenario.producer.release == "v0.1.6"
        and scenario.producer.commit
        == "7d43324b469cb5e445c2e8be83af3be4d841cf1c"
        and scenario.producer.tag_object
        == "9e0b0b443c435cf636dfce932c3c77d91d0a43e4"
    )
    return tuple(
        _result(
            assertion_id,
            assertion_id in observed
            and (assertion_id != "producer_pin_exact" or exact_producer),
            observed.get(assertion_id, ()),
        )
        for assertion_id in TRAJECTORY_ASSERTIONS
    )


def evaluate_outcome(
    expected: DraLiveOutcomeExpectedV1,
    projection: DraLiveOutcomeProjectionV1,
) -> tuple[AssertionResultV1, ...]:
    checks: dict[OutcomeAssertionId, bool] = {
        "candidate_exactly_one": projection.candidate_count == 1
        and projection.candidate_id == expected.candidate_id,
        "verification_exactly_one": projection.verification_count == 1
        and projection.approved_verification_count == 1,
        "promoted_pack_mapping_exact": (
            projection.promoted_source_pack_id == expected.source_pack_id
            and projection.promoted_source_pack_version
            == expected.source_pack_version
            and projection.promoted_source_entry_id == expected.source_entry_id
            and projection.promoted_evidence_id == expected.evidence_id
        ),
        "external_claim_exact": projection.external_claim
        == "australia_program_fit",
        "evidence_role_exact": projection.evidence_role == "program_fit",
        "external_authority_exact": projection.external_authority
        == "externally_verified",
        "governed_task_exactly_one": projection.governed_task_count == 1
        and projection.task_id == expected.task_id,
        "task_terminal_state_exact": projection.task_state
        == expected.task_state,
        "planning_run_terminal_state_exact": (
            projection.planning_run_id == expected.planning_run_id
            and projection.planning_run_state == expected.planning_run_state
        ),
        "advisor_review_exactly_one": projection.advisor_review_count == 1,
        "family_decision_exactly_one": projection.family_decision_count == 1,
        "decision_receipt_exactly_one": projection.decision_receipt_count == 1,
        "timeline_plan_exactly_one": projection.timeline_plan_count == 1,
        "tenant_isolation_preserved": projection.tenant_isolated,
        "no_partial_row_set": projection.partial_row_set_absent,
    }
    return tuple(
        _result(
            assertion_id,
            checks[assertion_id],
            projection.observed_identity_hashes,
        )
        for assertion_id in OUTCOME_ASSERTIONS
    )


def build_evaluation_report(
    *,
    scenario: DraLiveScenarioV1,
    receipts: Sequence[DraEvaluationReceiptV1],
    outcome: Sequence[AssertionResultV1],
) -> DraLiveEvaluationReportV1:
    validated_receipts = _validated_receipts(receipts)
    receipt_root = validated_receipts.get("capture-live")
    if receipt_root is None:
        raise ValueError("dra_evaluation_receipt_root_missing")
    trajectory = evaluate_trajectory(scenario, receipts)
    assertions = tuple(
        sorted((*trajectory, *outcome), key=lambda item: item.assertion_id)
    )
    return DraLiveEvaluationReportV1(
        schema_version="night-voyager.dra-live-evaluation.v1",
        scenario_id=scenario.scenario_id,
        producer=scenario.producer,
        intent_sha256=receipt_root.intent_sha256,
        assertions=assertions,
        expected_non_claims=scenario.expected_non_claims,
    )


def evaluate_full_closure(
    scenario: DraLiveScenarioV1,
    receipts: Sequence[DraEvaluationReceiptV1],
    expected: DraLiveOutcomeExpectedV1,
    projection: DraLiveOutcomeProjectionV1,
) -> DraLiveEvaluationReportV1:
    return build_evaluation_report(
        scenario=scenario,
        receipts=receipts,
        outcome=evaluate_outcome(expected, projection),
    )


def _reject_content_keys(value: object) -> None:
    if isinstance(value, dict):
        mapping = cast(dict[object, object], value)
        if any(
            isinstance(key, str) and key in FORBIDDEN_REPORT_KEYS
            for key in mapping
        ):
            raise ValueError("dra_evaluation_content_key_forbidden")
        for child in mapping.values():
            _reject_content_keys(child)
    elif isinstance(value, list):
        for child in cast(list[object], value):
            _reject_content_keys(child)


def canonical_report_bytes(report: DraLiveEvaluationReportV1) -> bytes:
    payload = report.model_dump(mode="json")
    _reject_content_keys(payload)
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def render_evaluation_report(
    report: DraLiveEvaluationReportV1, *, duration_ms: int
) -> str:
    if duration_ms < 0:
        raise ValueError("dra_evaluation_duration_invalid")
    passed = sum(item.status == "passed" for item in report.assertions)
    return (
        f"DRA live evaluation: {report.status}\n"
        f"Assertions: {passed}/{len(report.assertions)} passed\n"
        f"Duration: {duration_ms} ms (non-canonical)\n"
    )
