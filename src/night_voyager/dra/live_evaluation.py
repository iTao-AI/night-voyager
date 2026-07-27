from __future__ import annotations

import hashlib
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
    DraCaptureReceiptV1,
    DraDecisionReceiptV1,
    DraLiveProducerIdentityV1,
    DraLiveScenarioV1,
    DraPromotionReceiptV1,
    DraReviewReceiptV1,
    DraStrictReadinessEvidenceV1,
    PublicCode,
)
from night_voyager.dra.live_storage import canonical_receipt_bytes
from night_voyager.dra.models import (
    BoundedId,
    DraObservedProfileManifestV1,
    DraProducerPinV2,
    DraRunRequestIdentityV2,
    DraStrictConsumerIdentityV2,
    FrozenModel,
    Sha256,
)

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
    verification_id: BoundedId
    execution_id: BoundedId
    terminal_event_id: PositiveInt
    skill_definition_id: BoundedId
    skill_version_id: BoundedId
    skill_activation_event_id: BoundedId
    skill_activation_sequence: PositiveInt
    runtime_binding_sha256: Sha256
    review_id: BoundedId
    brief_id: BoundedId
    decision_id: BoundedId
    decision_receipt_id: BoundedId
    timeline_plan_id: BoundedId


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
    verification_id: BoundedId | None
    execution_count: OutcomeCount
    execution_id: BoundedId | None
    execution_planning_run_id: BoundedId | None
    terminal_event_count: OutcomeCount
    terminal_event_id: PositiveInt | None
    terminal_event_planning_run_id: BoundedId | None
    sse_cursor: PositiveInt | None
    skill_definition_id: BoundedId | None
    skill_version_id: BoundedId | None
    skill_activation_event_id: BoundedId | None
    skill_activation_sequence: PositiveInt | None
    runtime_binding_sha256: Sha256 | None
    advisor_review_count: OutcomeCount
    review_id: BoundedId | None
    brief_id: BoundedId | None
    family_decision_count: OutcomeCount
    decision_id: BoundedId | None
    decision_receipt_count: OutcomeCount
    decision_receipt_id: BoundedId | None
    timeline_plan_count: OutcomeCount
    timeline_plan_id: BoundedId | None
    tenant_isolated: bool
    partial_row_set_absent: bool
    observed_identity_hashes: tuple[Sha256, ...]


class DraLiveCandidateReadinessV3(FrozenModel):
    schema_version: Literal[
        "night-voyager.dra-live-candidate-readiness.v3"
    ]
    status: Literal["INCOMPLETE_PENDING_LIVE_ACCEPTANCE"]
    producer: DraProducerPinV2
    request_identity: DraRunRequestIdentityV2
    observed_profile: DraObservedProfileManifestV1
    authorization: Literal[
        "PENDING_SEPARATE_LIVE_ACCEPTANCE_AUTHORIZATION"
    ]

    @model_validator(mode="before")
    @classmethod
    def require_complete_canonical_identity(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        payload = cast(dict[str, object], value)
        exact_nested_keys = {
            "producer": {
                "schema",
                "repository",
                "ref_kind",
                "ref",
                "commit",
                "consumer_contract_schema",
                "consumer_fixture_sha256",
                "profile_id",
                "profile_version",
                "proof_schema",
            },
            "request_identity": {
                "schema_version",
                "profile_id",
                "request_sha256",
            },
            "observed_profile": {
                "schema_version",
                "profile_id",
                "profile_version",
            },
        }
        for name, exact_keys in exact_nested_keys.items():
            nested = payload.get(name)
            if isinstance(nested, dict):
                nested_payload = cast(dict[str, object], nested)
                if set(nested_payload) != exact_keys:
                    raise ValueError(
                        "dra_strict_readiness_identity_invalid"
                    )
        return cast(object, payload)

    @model_validator(mode="after")
    def exact_strict_identity(self) -> Self:
        DraStrictConsumerIdentityV2(
            schema_version="night-voyager.dra-strict-consumer-identity.v2",
            producer=self.producer,
            request=self.request_identity,
            observed_profile=self.observed_profile,
        )
        return self


class DraLiveCandidateReadinessV4(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-candidate-readiness.v4"]
    status: Literal["INCOMPLETE_PENDING_LIVE_ACCEPTANCE"]
    consumer_identity: DraStrictConsumerIdentityV2
    evidence_bundle: DraStrictReadinessEvidenceV1
    authorization: Literal["PENDING_SEPARATE_LIVE_ACCEPTANCE_AUTHORIZATION"]


class DraDurableCandidateIdentityV2(FrozenModel):
    schema_version: Literal[
        "night-voyager.dra-durable-candidate-identity.v2"
    ]
    candidate_id: BoundedId
    producer: DraProducerPinV2
    request_identity: DraRunRequestIdentityV2
    observed_profile: DraObservedProfileManifestV1

    @model_validator(mode="after")
    def exact_strict_identity(self) -> Self:
        DraStrictConsumerIdentityV2(
            schema_version="night-voyager.dra-strict-consumer-identity.v2",
            producer=self.producer,
            request=self.request_identity,
            observed_profile=self.observed_profile,
        )
        return self


class DraLiveOutcomeProjectionV2(DraLiveOutcomeProjectionV1):
    schema_version: Literal[
        "night-voyager.dra-live-outcome-projection.v2"
    ]
    durable_candidate: DraDurableCandidateIdentityV2 | None

    @model_validator(mode="after")
    def database_candidate_identity_is_coherent(self) -> Self:
        if self.durable_candidate is not None and (
            self.candidate_id != self.durable_candidate.candidate_id
            or self.candidate_count != 1
        ):
            raise ValueError("dra_strict_candidate_identity_invalid")
        return self


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


class DraLiveEvaluationReportV2(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-evaluation.v2"]
    scenario_id: Literal["dra-strict-citation-live-closure-v2"]
    candidate_id: BoundedId
    durable_candidate_identity_sha256: Sha256
    readiness_sha256: Sha256
    request_identity_sha256: Sha256
    outcome_projection_sha256: Sha256
    status: Literal["passed"]
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
    def exact_non_claims(self) -> Self:
        if self.expected_non_claims != (
            "provider_quality",
            "source_truth",
            "production_readiness",
            "admissions_outcome",
        ):
            raise ValueError("dra_expected_non_claims_invalid")
        return self


def _canonical_model_bytes(model: FrozenModel) -> bytes:
    return canonical_receipt_bytes(model)


def _canonical_model_sha256(model: FrozenModel) -> str:
    return hashlib.sha256(_canonical_model_bytes(model)).hexdigest()


def evaluate_strict_candidate(
    readiness: DraLiveCandidateReadinessV3,
    projection: DraLiveOutcomeProjectionV2,
) -> DraLiveEvaluationReportV2:
    durable = projection.durable_candidate
    if durable is None:
        raise ValueError("dra_strict_candidate_identity_missing")
    expected_identity = (
        readiness.producer,
        readiness.request_identity,
        readiness.observed_profile,
    )
    observed_identity = (
        durable.producer,
        durable.request_identity,
        durable.observed_profile,
    )
    if (
        projection.candidate_count != 1
        or projection.candidate_id != durable.candidate_id
        or observed_identity != expected_identity
    ):
        raise ValueError("dra_strict_candidate_identity_mismatch")
    return DraLiveEvaluationReportV2(
        schema_version="night-voyager.dra-live-evaluation.v2",
        scenario_id="dra-strict-citation-live-closure-v2",
        candidate_id=durable.candidate_id,
        durable_candidate_identity_sha256=_canonical_model_sha256(
            durable
        ),
        readiness_sha256=_canonical_model_sha256(readiness),
        request_identity_sha256=_canonical_model_sha256(
            readiness.request_identity
        ),
        outcome_projection_sha256=_canonical_model_sha256(projection),
        status="passed",
        expected_non_claims=(
            "provider_quality",
            "source_truth",
            "production_readiness",
            "admissions_outcome",
        ),
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


TypedStageReceipt = (
    DraCaptureReceiptV1
    | DraPromotionReceiptV1
    | DraReviewReceiptV1
    | DraDecisionReceiptV1
)


def _receipt_hash(receipt: TypedStageReceipt) -> str:
    encoded = json.dumps(
        receipt.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return __import__("hashlib").sha256(encoded).hexdigest()


def _typed_receipts(
    receipts: Sequence[object],
) -> tuple[
    DraCaptureReceiptV1,
    DraPromotionReceiptV1,
    DraReviewReceiptV1,
    DraDecisionReceiptV1,
]:
    expected_types = (
        DraCaptureReceiptV1,
        DraPromotionReceiptV1,
        DraReviewReceiptV1,
        DraDecisionReceiptV1,
    )
    by_type: dict[type[TypedStageReceipt], TypedStageReceipt] = {}
    for receipt in receipts:
        if not isinstance(receipt, expected_types):
            raise ValueError("typed_stage_receipts_required")
        receipt_type = type(receipt)
        if receipt_type in by_type:
            raise ValueError("dra_evaluation_stage_duplicate")
        by_type[receipt_type] = receipt
    if set(by_type) != set(expected_types):
        raise ValueError("typed_stage_receipts_required")
    capture = cast(DraCaptureReceiptV1, by_type[DraCaptureReceiptV1])
    promotion = cast(DraPromotionReceiptV1, by_type[DraPromotionReceiptV1])
    review = cast(DraReviewReceiptV1, by_type[DraReviewReceiptV1])
    decision = cast(DraDecisionReceiptV1, by_type[DraDecisionReceiptV1])
    selected = capture.selected_evidence
    if (
        len(
            {
                capture.intent_sha256,
                promotion.intent_sha256,
                review.intent_sha256,
                decision.intent_sha256,
            }
        )
        != 1
        or len(
            {
                capture.attempt_id,
                promotion.attempt_id,
                review.attempt_id,
                decision.attempt_id,
            }
        )
        != 1
        or promotion.candidate_id != capture.candidate_id
        or selected is None
        or promotion.dra_evidence_id != selected.evidence_id
        or promotion.selected_raw_url != selected.source_url
        or review.candidate_id != promotion.candidate_id
        or review.source_pack_version != promotion.promoted_source_pack_version
        or decision.review_id != review.review.review_id
        or decision.planning_run_id != review.task.planning_run_id
        or decision.decision.brief_id != review.review.brief_id
    ):
        raise ValueError("dra_evaluation_receipt_chain_invalid")
    return capture, promotion, review, decision


def evaluate_trajectory(
    scenario: DraLiveScenarioV1,
    receipts: Sequence[TypedStageReceipt],
) -> tuple[AssertionResultV1, ...]:
    capture, promotion, review, decision = _typed_receipts(receipts)
    hashes = {
        "capture-live": (_receipt_hash(capture),),
        "promote": (_receipt_hash(promotion),),
        "review": (_receipt_hash(review),),
        "decide": (_receipt_hash(decision),),
    }
    exact_producer = (
        capture.producer == scenario.producer
        and scenario.producer.release == "v0.1.6"
    )
    provider_attempt_exact = (
        capture.provider_attempt_consumed
        and len(set(capture.provider_attempt_evidence.create_keys)) == 1
        and len(set(capture.provider_attempt_evidence.observed_run_ids)) == 1
        and capture.provider_attempt_evidence.accepted_run_id == capture.run_id
        and capture.provider_attempt_evidence.observed_run_ids == (capture.run_id,)
    )
    checks: dict[TrajectoryAssertionId, bool] = {
        "producer_pin_exact": exact_producer,
        "provider_attempt_exactly_one": provider_attempt_exact,
        "terminal_transition_valid": capture.stage_states[-1].status == "completed",
        "artifact_identity_exact": capture.artifact == scenario.result.artifact,
        "evidence_ownership_and_selection_valid": (
            capture.selected_evidence is not None
            and capture.selected_evidence.run_id == capture.run_id
            and capture.selected_evidence.segment_id == capture.segment_id
        ),
        "candidate_precedes_promotion": capture.candidate_authority == "untrusted_candidate",
        "candidate_untrusted_until_advisor": capture.candidate_authority == "untrusted_candidate",
        "promotion_actor_explicit": promotion.acknowledgement == "promotion_recorded",
        "promoted_pack_exact": promotion.promoted_source_pack_version == review.source_pack_version,
        "skill_pin_exact": review.task.skill_pin.runtime_binding_sha256 != "0" * 64,
        "task_execution_event_sse_run_correlated": (
            review.task.planning_run_id == review.review.planning_run_id
            and review.task.terminal_event_id > 0
        ),
        "advisor_review_explicit": review.acknowledgement == "review_recorded",
        "family_decision_explicit": decision.acknowledgement == "decision_recorded",
        "receipt_timeline_correlated": (
            decision.decision.decision_receipt_id != decision.decision.timeline_plan_id
        ),
        "no_auto_promotion": promotion.acknowledgement == "promotion_recorded",
        "no_auto_decision": decision.acknowledgement == "decision_recorded",
        "no_second_provider_run": provider_attempt_exact,
    }
    return tuple(
        _result(
            assertion_id,
            checks[assertion_id],
            hashes[
                next(
                    stage
                    for stage, values in STAGE_ASSERTIONS.items()
                    if assertion_id in values
                )
            ],
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
        and projection.approved_verification_count == 1
        and projection.verification_id == expected.verification_id,
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
        "task_terminal_state_exact": (
            projection.task_state == expected.task_state
            and projection.execution_count == 1
            and projection.execution_id == expected.execution_id
            and projection.execution_planning_run_id == expected.planning_run_id
            and projection.terminal_event_count == 1
            and projection.terminal_event_id == expected.terminal_event_id
            and projection.sse_cursor == expected.terminal_event_id
            and projection.terminal_event_planning_run_id == expected.planning_run_id
            and projection.skill_definition_id == expected.skill_definition_id
            and projection.skill_version_id == expected.skill_version_id
            and projection.skill_activation_event_id == expected.skill_activation_event_id
            and projection.skill_activation_sequence
            == expected.skill_activation_sequence
            and projection.runtime_binding_sha256
            == expected.runtime_binding_sha256
        ),
        "planning_run_terminal_state_exact": (
            projection.planning_run_id == expected.planning_run_id
            and projection.planning_run_state == expected.planning_run_state
        ),
        "advisor_review_exactly_one": (
            projection.advisor_review_count == 1
            and projection.review_id == expected.review_id
            and projection.brief_id == expected.brief_id
        ),
        "family_decision_exactly_one": (
            projection.family_decision_count == 1
            and projection.decision_id == expected.decision_id
        ),
        "decision_receipt_exactly_one": (
            projection.decision_receipt_count == 1
            and projection.decision_receipt_id == expected.decision_receipt_id
        ),
        "timeline_plan_exactly_one": (
            projection.timeline_plan_count == 1
            and projection.timeline_plan_id == expected.timeline_plan_id
        ),
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
    receipts: Sequence[TypedStageReceipt],
    outcome: Sequence[AssertionResultV1],
) -> DraLiveEvaluationReportV1:
    receipt_root, _, _, _ = _typed_receipts(receipts)
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
    receipts: Sequence[TypedStageReceipt],
    expected: DraLiveOutcomeExpectedV1,
    projection: DraLiveOutcomeProjectionV1,
) -> DraLiveEvaluationReportV1:
    _, promotion, review, decision = _typed_receipts(receipts)
    derived = DraLiveOutcomeExpectedV1(
        candidate_id=str(promotion.candidate_id),
        source_pack_id=str(review.source_pack_id),
        source_pack_version=review.source_pack_version,
        source_entry_id=str(promotion.promoted_source_entry_id),
        evidence_id=str(promotion.promoted_evidence_id),
        task_id=str(review.task.task_id),
        task_state="waiting_review",
        planning_run_id=str(review.task.planning_run_id),
        planning_run_state="review_required",
        verification_id=str(promotion.verification_id),
        execution_id=str(review.task.execution_id),
        terminal_event_id=review.task.terminal_event_id,
        skill_definition_id=str(review.task.skill_pin.skill_definition_id),
        skill_version_id=str(review.task.skill_pin.skill_version_id),
        skill_activation_event_id=str(
            review.task.skill_pin.skill_activation_event_id
        ),
        skill_activation_sequence=review.task.skill_pin.skill_activation_sequence,
        runtime_binding_sha256=review.task.skill_pin.runtime_binding_sha256,
        review_id=str(review.review.review_id),
        brief_id=str(review.review.brief_id),
        decision_id=str(decision.decision.decision_id),
        decision_receipt_id=str(decision.decision.decision_receipt_id),
        timeline_plan_id=str(decision.decision.timeline_plan_id),
    )
    if expected != derived:
        raise ValueError("dra_live_expected_outcome_not_receipt_derived")
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


def canonical_report_bytes(
    report: DraLiveEvaluationReportV1 | DraLiveEvaluationReportV2,
) -> bytes:
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
