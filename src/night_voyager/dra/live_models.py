from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    Field,
    PositiveInt,
    StringConstraints,
    computed_field,
    model_validator,
)

from night_voyager.dra.models import (
    DRA_CONTRACT_SCHEMA,
    DRA_FIXTURE_SHA256,
    DRA_LIVE_COMMIT,
    DRA_LIVE_PRODUCER,
    DRA_LIVE_RELEASE,
    DRA_LIVE_TAG_OBJECT,
    BoundedId,
    BoundedText,
    DraProducerPinV1,
    FrozenModel,
    Sha256,
    validate_raw_public_https_url,
)

PublicCode = Annotated[str, StringConstraints(min_length=1, max_length=100)]
SafeLogicalName = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$"),
]
SafeIdentity = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$"),
]


class DraLiveFailurePhase(StrEnum):
    PREFLIGHT_INVALID = "preflight_invalid"
    PRODUCER_IDENTITY_INVALID = "producer_identity_invalid"
    PRODUCER_UNAVAILABLE = "producer_unavailable"
    RUN_ACCEPTANCE_AMBIGUOUS = "run_acceptance_ambiguous"
    RUN_POLL_DEADLINE_EXHAUSTED = "run_poll_deadline_exhausted"
    TERMINAL_STATE_INVALID = "terminal_state_invalid"
    ARTIFACT_CONTRACT_INVALID = "artifact_contract_invalid"
    EVIDENCE_OWNERSHIP_INVALID = "evidence_ownership_invalid"
    EVIDENCE_PROJECTION_INVALID = "evidence_projection_invalid"
    SOURCE_SELECTION_INVALID = "source_selection_invalid"
    CANDIDATE_IMPORT_CONFLICT = "candidate_import_conflict"
    CANDIDATE_AUTHORITY_DENIED = "candidate_authority_denied"
    SOURCE_ATTESTATION_INVALID = "source_attestation_invalid"
    PROMOTION_CONFLICT = "promotion_conflict"
    PLANNING_TASK_CONFLICT = "planning_task_conflict"
    PLANNING_EXECUTION_FAILED = "planning_execution_failed"
    ADVISOR_REVIEW_CONFLICT = "advisor_review_conflict"
    FAMILY_DECISION_CONFLICT = "family_decision_conflict"
    OUTCOME_PROJECTION_INVALID = "outcome_projection_invalid"
    CLEANUP_INCOMPLETE = "cleanup_incomplete"


class DraLiveProducerIdentityV1(FrozenModel):
    name: Literal["decision-research-agent"] = "decision-research-agent"
    release: Literal["v0.1.6"] = DRA_LIVE_RELEASE
    commit: Literal["7d43324b469cb5e445c2e8be83af3be4d841cf1c"] = DRA_LIVE_COMMIT
    tag_object: Literal["9e0b0b443c435cf636dfce932c3c77d91d0a43e4"] = (
        DRA_LIVE_TAG_OBJECT
    )
    contract_schema: Literal["dra.downstream-consumer.v1"] = DRA_CONTRACT_SCHEMA
    fixture_sha256: Literal[
        "cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157"
    ] = DRA_FIXTURE_SHA256

    @property
    def pin(self) -> DraProducerPinV1:
        return DRA_LIVE_PRODUCER


class DraLiveEvidenceEnvelopeV1(FrozenModel):
    evidence_id: BoundedId
    run_id: BoundedId
    segment_id: BoundedId
    source_url: BoundedText | None
    source_identity: BoundedText
    retrieved_at: AwareDatetime
    citation_status: Literal["cited", "uncited"]
    verification_status: Literal["verified", "unverified"]


class DraLiveStatusEnvelopeV1(FrozenModel):
    run_id: BoundedId
    thread_id: BoundedId
    segment_id: BoundedId
    profile_id: Literal["generic"]
    state_version: Annotated[int, Field(gt=0)]
    execution_status: Literal["completed"]
    review_status: Literal["not_required"]
    delivery_status: Literal["ready"]
    failure_cause: None = None


class DraLiveFailureCauseEnvelopeV1(FrozenModel):
    schema_version: Literal["dra.run-failure-cause.v1"]
    observation_status: Literal["observed"]
    phase: PublicCode
    code: PublicCode
    recorded_at: AwareDatetime


class DraLiveRunEnvelopeV1(FrozenModel):
    run_id: BoundedId
    thread_id: BoundedId
    segment_id: BoundedId
    profile_id: Literal["generic"]
    state_version: int
    execution_status: Literal[
        "pending", "running", "completed", "completed_with_fallback", "failed"
    ]
    review_status: Literal["not_required", "required", "resolved"]
    delivery_status: Literal[
        "pending", "ready", "review_required", "blocked", "failed"
    ]
    failure_cause: DraLiveFailureCauseEnvelopeV1 | None
    evidence: tuple[DraLiveEvidenceEnvelopeV1, ...] = Field(
        max_length=100
    )

    @model_validator(mode="after")
    def exact_segment_and_unique_evidence(self) -> Self:
        identifiers: set[str] = set()
        for row in self.evidence:
            if row.evidence_id in identifiers:
                raise ValueError("dra_evidence_ids_not_unique")
            identifiers.add(row.evidence_id)
        return self

    @computed_field
    @property
    def disposition(
        self,
    ) -> Literal["in_progress", "canonical_ready", "terminal_invalid"]:
        state = (
            self.execution_status,
            self.review_status,
            self.delivery_status,
        )
        if (
            state
            in {
                ("pending", "not_required", "pending"),
                ("running", "not_required", "pending"),
            }
            and self.failure_cause is None
        ):
            return "in_progress"
        if (
            state == ("completed", "not_required", "ready")
            and self.state_version > 0
            and self.failure_cause is None
        ):
            return "canonical_ready"
        return "terminal_invalid"


class DraArtifactIdentityV1(FrozenModel):
    artifact_id: Literal["research-report.md"]
    kind: Literal["research_report_markdown"]
    media_type: Literal["text/markdown"]
    byte_length: PositiveInt = Field(le=1_048_576)
    sha256: Sha256


class DraLiveResultIdentityV1(FrozenModel):
    run_id: BoundedId
    execution_status: Literal["completed"]
    delivery_status: Literal["ready"]
    artifact: DraArtifactIdentityV1


class DraLiveScenarioV1(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-closure-scenario.v1"]
    scenario_id: Literal["dra-v0-1-6-live-closure-v1"]
    producer: DraLiveProducerIdentityV1
    profile_id: Literal["generic"]
    max_attempts: Literal[1]
    request_sha256: Sha256
    status: DraLiveStatusEnvelopeV1
    result: DraLiveResultIdentityV1
    evidence: tuple[DraLiveEvidenceEnvelopeV1, ...] = Field(min_length=1, max_length=100)
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
    def exact_ownership_and_non_claims(self) -> Self:
        if self.status.run_id != self.result.run_id:
            raise ValueError("dra_run_identity_mismatch")
        identifiers: set[str] = set()
        for evidence in self.evidence:
            if (
                evidence.run_id != self.status.run_id
                or evidence.segment_id != self.status.segment_id
            ):
                raise ValueError("dra_evidence_ownership_invalid")
            if evidence.evidence_id in identifiers:
                raise ValueError("dra_evidence_ids_not_unique")
            identifiers.add(evidence.evidence_id)
        if self.expected_non_claims != (
            "provider_quality",
            "source_truth",
            "production_readiness",
            "admissions_outcome",
        ):
            raise ValueError("dra_expected_non_claims_invalid")
        return self


class DraLiveRunIntentV1(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-run-intent.v1"] = (
        "night-voyager.dra-live-run-intent.v1"
    )
    scenario_id: Literal["dra-v0-1-6-live-closure-v1"]
    attempt_id: BoundedId
    producer: DraLiveProducerIdentityV1
    profile_id: Literal["generic"]
    request_sha256: Sha256
    deadline_seconds: PositiveInt = Field(default=900, le=3600)
    poll_seconds: float = Field(default=2.0, gt=0, le=60)
    expected_terminal_contract: Literal["completed:not_required:ready"] = (
        "completed:not_required:ready"
    )
    privacy_policy: Literal["content_ephemeral_receipts_redacted"] = (
        "content_ephemeral_receipts_redacted"
    )
    receipt_schema_version: Literal["night-voyager.dra-live-receipts.v1"] = (
        "night-voyager.dra-live-receipts.v1"
    )

    @classmethod
    def from_scenario(
        cls, scenario: DraLiveScenarioV1, *, attempt_id: str
    ) -> DraLiveRunIntentV1:
        return cls(
            scenario_id=scenario.scenario_id,
            attempt_id=attempt_id,
            producer=scenario.producer,
            profile_id=scenario.profile_id,
            request_sha256=scenario.request_sha256,
        )

    @computed_field
    @property
    def intent_sha256(self) -> str:
        payload = self.model_dump(mode="json", exclude={"intent_sha256"})
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class DraFrozenRequestV1(FrozenModel):
    logical_name: SafeLogicalName
    encoding: Literal["utf-8"]
    byte_length: PositiveInt = Field(le=1_048_576)
    sha256: Sha256


class DraCaptureInputV1(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-capture-input.v1"] = (
        "night-voyager.dra-live-capture-input.v1"
    )
    scenario_id: Literal["dra-v0-1-6-live-closure-v1"]
    producer: DraLiveProducerIdentityV1
    organization_id: UUID
    case_id: UUID
    expected_case_revision: PositiveInt
    advisor_actor_identity_sha256: Sha256
    tenant_identity_sha256: Sha256
    actor_role: Literal["advisor"] = "advisor"
    request: DraFrozenRequestV1
    receipt_root_id: SafeLogicalName
    one_attempt_authorized: Literal[True]


class DraCaptureIntentV1(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-capture-intent.v1"] = (
        "night-voyager.dra-live-capture-intent.v1"
    )
    capture: DraCaptureInputV1
    attempt_id: SafeIdentity

    @classmethod
    def freeze(
        cls,
        capture: DraCaptureInputV1,
        *,
        attempt_id_factory: Callable[[], str],
    ) -> DraCaptureIntentV1:
        return cls(capture=capture, attempt_id=attempt_id_factory())

    def _identity_payload(self) -> dict[str, object]:
        return self.model_dump(
            mode="json",
            exclude={"intent_sha256"},
            exclude_computed_fields=True,
        )

    @computed_field
    @property
    def intent_sha256(self) -> str:
        encoded = json.dumps(
            self._identity_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")


def derive_stage_key(
    intent_sha256: str,
    stage: str,
    target_identity: str,
) -> str:
    if re.fullmatch(r"[0-9a-f]{64}", intent_sha256) is None:
        raise ValueError("dra_live_intent_sha256_invalid")
    for value in (stage, target_identity):
        if (
            not value
            or len(value) > 200
            or any(character.isspace() or ord(character) < 32 for character in value)
        ):
            raise ValueError("dra_live_stage_key_identity_invalid")
    payload = (
        "night-voyager.dra-live.v1"
        f"\0{intent_sha256}\0{stage}\0{target_identity}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class DraReceiptIdentityV1(FrozenModel):
    logical_name: SafeLogicalName
    byte_length: PositiveInt = Field(le=1_048_576)
    sha256: Sha256


class DraReconciliationRequiredReceiptV1(FrozenModel):
    schema_version: Literal[
        "night-voyager.dra-live-reconciliation-required.v1"
    ]
    intent_sha256: Sha256
    attempt_id: SafeIdentity
    intent_receipt: DraReceiptIdentityV1
    create_key: Sha256
    provider_attempt_consumed: Literal[True]
    permitted_next_command: Literal["reconcile-create"]


class DraSelectedEvidenceV1(FrozenModel):
    evidence_id: BoundedId
    run_id: BoundedId
    segment_id: BoundedId
    source_url: BoundedText
    source_identity: BoundedText
    retrieved_at: AwareDatetime
    citation_status: Literal["cited"]
    verification_status: Literal["verified", "unverified"]

    @model_validator(mode="after")
    def exact_raw_identity(self) -> Self:
        validate_raw_public_https_url(self.source_url)
        if self.source_identity != self.source_url:
            raise ValueError("dra_source_identity_mismatch")
        return self


class DraStageStateV1(FrozenModel):
    stage: Literal["capture-live", "promote", "review", "decide"]
    status: Literal["pending", "completed", "failed"]


class DraCaptureReceiptV1(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-capture-receipt.v1"]
    intent_sha256: Sha256
    attempt_id: BoundedId
    producer: DraLiveProducerIdentityV1
    run_id: BoundedId
    segment_id: BoundedId
    artifact: DraArtifactIdentityV1
    selected_evidence: DraSelectedEvidenceV1 | None
    stage_states: tuple[DraStageStateV1, ...]
    provider_attempt_consumed: bool

    @model_validator(mode="after")
    def unique_stage_names(self) -> Self:
        names = [item.stage for item in self.stage_states]
        if len(names) != len(set(names)):
            raise ValueError("dra_receipt_stage_duplicate")
        return self


class DraFailureReceiptV1(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-failure-receipt.v1"]
    intent_sha256: Sha256
    attempt_id: BoundedId
    phase: DraLiveFailurePhase
    public_code: PublicCode
    retryability: Literal[
        "not_retryable",
        "same_run_recovery",
        "separate_authorization_required",
    ]
    provider_attempt_consumed: bool
    known_identity_hashes: tuple[Sha256, ...]
    last_completed_stage: Literal["capture-live", "promote", "review", "decide"] | None
    permitted_next_action: Literal[
        "stop", "same_run_recovery", "separate_authorization"
    ]
