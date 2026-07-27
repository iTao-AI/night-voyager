from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from enum import StrEnum
from typing import Annotated, Literal, Self, cast
from uuid import UUID

from pydantic import (
    AwareDatetime,
    Field,
    ModelWrapValidatorHandler,
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
    DraCanonicalArtifactInputV1,
    DraObservedProfileManifestV1,
    DraProducerPinV1,
    DraProducerPinV2,
    DraRunRequestIdentityV2,
    FrozenModel,
    Sha256,
    SourceAttestationV1,
    validate_raw_public_https_url,
)
from night_voyager.skills.models import SkillRuntimePin

PublicCode = Annotated[str, StringConstraints(min_length=1, max_length=100)]
SafeLogicalName = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$"),
]
SafeIdentity = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$"),
]
_INTENT_HASH_NOT_SUPPLIED = object()
DRA_LIVE_CITATION_CLAUSE_MARKER_V2 = (
    b"[NIGHT_VOYAGER_DRA_LIVE_CITATION_CONTRACT_V2]"
)
DRA_LIVE_CITATION_CLAUSE_V2 = (
    DRA_LIVE_CITATION_CLAUSE_MARKER_V2
    + b"\nUse internet_search. The final canonical report must include the exact raw "
    b"URL of at least one public HTTPS source that internet_search actually returned "
    b"and that passes the current source-admission contract. Do not invent, alter, "
    b"normalize, or guess any URL."
)
_DRA_LIVE_EFFECTIVE_QUERY_SEPARATOR_V2 = b"\n\n"
_DRA_LIVE_MAX_QUERY_BYTES = 1_048_576


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
    tag_object: Literal["9e0b0b443c435cf636dfce932c3c77d91d0a43e4"] = DRA_LIVE_TAG_OBJECT
    contract_schema: Literal["dra.downstream-consumer.v1"] = DRA_CONTRACT_SCHEMA
    fixture_sha256: Literal["cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157"] = (
        DRA_FIXTURE_SHA256
    )

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
    delivery_status: Literal["pending", "ready", "review_required", "blocked", "failed"]
    failure_cause: DraLiveFailureCauseEnvelopeV1 | None
    evidence: tuple[DraLiveEvidenceEnvelopeV1, ...] = Field(max_length=100)

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


class DraLiveStatusEnvelopeV2(FrozenModel):
    run_id: BoundedId
    thread_id: BoundedId
    segment_id: BoundedId
    profile_id: Literal["generic-strict-citation"]
    state_version: Annotated[int, Field(gt=0)]
    execution_status: Literal["completed"]
    review_status: Literal["not_required"]
    delivery_status: Literal["ready"]
    failure_cause: None = None


class DraLiveScenarioV2(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-closure-scenario.v2"]
    scenario_id: Literal["dra-strict-citation-live-closure-v2"]
    producer: DraProducerPinV2
    request_identity: DraRunRequestIdentityV2
    profile_manifest: DraObservedProfileManifestV1
    local_proof_schema: str
    max_attempts: Literal[0]
    status: DraLiveStatusEnvelopeV2
    result: DraLiveResultIdentityV1
    canonical_artifact: DraCanonicalArtifactInputV1
    evidence: tuple[DraLiveEvidenceEnvelopeV1, ...] = Field(
        min_length=1, max_length=100
    )
    expected_non_claims: tuple[
        Literal[
            "provider_quality",
            "source_truth",
            "production_readiness",
            "admissions_outcome",
        ],
        ...,
    ]

    @model_validator(mode="before")
    @classmethod
    def reject_mismatched_raw_identity(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        payload = cast(dict[str, object], value)
        producer = payload.get("producer")
        status = payload.get("status")
        profile_manifest = payload.get("profile_manifest")
        if (
            not isinstance(producer, dict)
            or not isinstance(status, dict)
            or not isinstance(profile_manifest, dict)
        ):
            return payload
        producer_payload = cast(dict[str, object], producer)
        status_payload = cast(dict[str, object], status)
        manifest_payload = cast(dict[str, object], profile_manifest)
        if (
            status_payload.get("profile_id") != producer_payload.get("profile_id")
            or manifest_payload.get("profile_id")
            != producer_payload.get("profile_id")
            or manifest_payload.get("profile_version")
            != producer_payload.get("profile_version")
        ):
            raise ValueError("dra_strict_profile_identity_invalid")
        if payload.get("local_proof_schema") != producer_payload.get("proof_schema"):
            raise ValueError("dra_strict_proof_schema_invalid")
        return payload

    @model_validator(mode="after")
    def exact_strict_contract(self) -> Self:
        if (
            self.status.profile_id != self.producer.profile_id
            or self.request_identity.profile_id != self.producer.profile_id
            or self.profile_manifest.profile_id != self.producer.profile_id
            or self.profile_manifest.profile_version != self.producer.profile_version
        ):
            raise ValueError("dra_strict_profile_identity_invalid")
        if self.local_proof_schema != self.producer.proof_schema:
            raise ValueError("dra_strict_proof_schema_invalid")
        if self.status.run_id != self.result.run_id:
            raise ValueError("dra_run_identity_mismatch")
        artifact = self.canonical_artifact
        result_artifact = self.result.artifact
        if (
            artifact.artifact_id != result_artifact.artifact_id
            or artifact.kind != result_artifact.kind
            or artifact.media_type != result_artifact.media_type
            or artifact.byte_length != result_artifact.byte_length
            or artifact.content_hash != result_artifact.sha256
        ):
            raise ValueError("dra_artifact_identity_mismatch")
        cited: list[DraLiveEvidenceEnvelopeV1] = []
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
            if evidence.citation_status == "cited":
                cited.append(evidence)
        if len(cited) != 1:
            raise ValueError("dra_cited_evidence_cardinality_invalid")
        selected = cited[0]
        source_url = selected.source_url
        if source_url is None:
            raise ValueError("dra_cited_evidence_cardinality_invalid")
        validate_raw_public_https_url(source_url)
        if (
            selected.source_identity != source_url
            or source_url not in artifact.content
        ):
            raise ValueError("dra_cited_source_not_in_canonical_artifact")
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
    def from_scenario(cls, scenario: DraLiveScenarioV1, *, attempt_id: str) -> DraLiveRunIntentV1:
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


class DraFrozenRequestV2(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-effective-query.v2"] = (
        "night-voyager.dra-live-effective-query.v2"
    )
    logical_name: SafeLogicalName
    encoding: Literal["utf-8"] = "utf-8"
    base_byte_length: PositiveInt = Field(le=_DRA_LIVE_MAX_QUERY_BYTES)
    base_sha256: Sha256
    effective_byte_length: PositiveInt = Field(le=_DRA_LIVE_MAX_QUERY_BYTES)
    effective_sha256: Sha256
    citation_clause_sha256: Sha256

    @model_validator(mode="after")
    def exact_code_owned_clause(self) -> Self:
        if self.citation_clause_sha256 != hashlib.sha256(
            DRA_LIVE_CITATION_CLAUSE_V2
        ).hexdigest():
            raise ValueError("dra_effective_query_clause_invalid")
        if self.effective_byte_length != (
            self.base_byte_length
            + len(_DRA_LIVE_EFFECTIVE_QUERY_SEPARATOR_V2)
            + len(DRA_LIVE_CITATION_CLAUSE_V2)
        ):
            raise ValueError("dra_effective_query_length_invalid")
        return self


def compose_effective_query_v2(
    base_query: bytes,
    *,
    logical_name: str,
) -> tuple[bytes, DraFrozenRequestV2]:
    try:
        decoded = base_query.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ValueError("dra_effective_query_invalid") from error
    if (
        not decoded.strip()
        or b"\r" in base_query
        or b"\n" in base_query
        or DRA_LIVE_CITATION_CLAUSE_MARKER_V2 in base_query
    ):
        raise ValueError("dra_effective_query_invalid")
    effective = (
        base_query
        + _DRA_LIVE_EFFECTIVE_QUERY_SEPARATOR_V2
        + DRA_LIVE_CITATION_CLAUSE_V2
    )
    if len(effective) > _DRA_LIVE_MAX_QUERY_BYTES:
        raise ValueError("dra_effective_query_invalid")
    identity = DraFrozenRequestV2(
        logical_name=logical_name,
        base_byte_length=len(base_query),
        base_sha256=hashlib.sha256(base_query).hexdigest(),
        effective_byte_length=len(effective),
        effective_sha256=hashlib.sha256(effective).hexdigest(),
        citation_clause_sha256=hashlib.sha256(
            DRA_LIVE_CITATION_CLAUSE_V2
        ).hexdigest(),
    )
    return effective, identity


def validate_effective_query_v2(
    base_query: bytes,
    expected: DraFrozenRequestV2,
) -> bytes:
    effective, observed = compose_effective_query_v2(
        base_query,
        logical_name=expected.logical_name,
    )
    if observed != expected:
        raise ValueError("dra_effective_query_identity_mismatch")
    return effective


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
    deadline_seconds: PositiveInt = Field(default=900, le=3600)
    poll_seconds: float = Field(default=2.0, gt=0, le=60)
    receipt_root_id: SafeLogicalName
    one_attempt_authorized: Literal[True]


class DraCaptureInputV2(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-capture-input.v2"] = (
        "night-voyager.dra-live-capture-input.v2"
    )
    scenario_id: Literal["dra-v0-1-6-live-closure-v1"]
    producer: DraLiveProducerIdentityV1
    organization_id: UUID
    case_id: UUID
    expected_case_revision: PositiveInt
    advisor_actor_identity_sha256: Sha256
    tenant_identity_sha256: Sha256
    actor_role: Literal["advisor"] = "advisor"
    request: DraFrozenRequestV2
    candidate_readiness_sha256: Sha256
    deadline_seconds: PositiveInt = Field(default=900, le=3600)
    poll_seconds: float = Field(default=2.0, gt=0, le=60)
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

    @model_validator(mode="wrap")
    @classmethod
    def validate_derived_intent_hash(
        cls,
        value: object,
        handler: ModelWrapValidatorHandler[Self],
    ) -> Self:
        supplied_hash: object = _INTENT_HASH_NOT_SUPPLIED
        candidate = value
        if isinstance(value, dict) and "intent_sha256" in value:
            payload = cast(dict[str, object], value).copy()
            supplied_hash = payload.pop("intent_sha256")
            candidate = payload
        intent = handler(candidate)
        if supplied_hash is not _INTENT_HASH_NOT_SUPPLIED and supplied_hash != intent.intent_sha256:
            raise ValueError("dra_live_intent_sha256_invalid")
        return intent


class DraCaptureIntentV2(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-capture-intent.v2"] = (
        "night-voyager.dra-live-capture-intent.v2"
    )
    capture: DraCaptureInputV2
    attempt_id: SafeIdentity

    @classmethod
    def freeze(
        cls,
        capture: DraCaptureInputV2,
        *,
        attempt_id_factory: Callable[[], str],
    ) -> DraCaptureIntentV2:
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

    @model_validator(mode="wrap")
    @classmethod
    def validate_derived_intent_hash(
        cls,
        value: object,
        handler: ModelWrapValidatorHandler[Self],
    ) -> Self:
        supplied_hash: object = _INTENT_HASH_NOT_SUPPLIED
        candidate = value
        if isinstance(value, dict) and "intent_sha256" in value:
            payload = cast(dict[str, object], value).copy()
            supplied_hash = payload.pop("intent_sha256")
            candidate = payload
        intent = handler(candidate)
        if (
            supplied_hash is not _INTENT_HASH_NOT_SUPPLIED
            and supplied_hash != intent.intent_sha256
        ):
            raise ValueError("dra_live_intent_sha256_invalid")
        return intent


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
    payload = f"night-voyager.dra-live.v1\0{intent_sha256}\0{stage}\0{target_identity}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def derive_identity_hash(kind: str, raw_identity: str) -> str:
    if kind not in {"actor", "tenant"} or not raw_identity:
        raise ValueError("dra_live_identity_invalid")
    payload = f"night-voyager.dra-live.identity.v1\0{kind}\0{raw_identity}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class DraReceiptIdentityV1(FrozenModel):
    logical_name: SafeLogicalName
    byte_length: PositiveInt = Field(le=1_048_576)
    sha256: Sha256


class DraReconciliationRequiredReceiptV1(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-reconciliation-required.v1"]
    intent_sha256: Sha256
    attempt_id: SafeIdentity
    intent_receipt: DraReceiptIdentityV1
    create_key: Sha256
    provider_attempt_consumed: Literal[True]
    permitted_next_command: Literal["reconcile-create"]


class DraPreflightReceiptV1(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-preflight.v1"] = (
        "night-voyager.dra-live-preflight.v1"
    )
    intent_sha256: Sha256
    attempt_id: SafeIdentity
    intent_receipt: DraReceiptIdentityV1
    scenario_id: Literal["dra-v0-1-6-live-closure-v1"]
    producer: DraLiveProducerIdentityV1
    advisor_actor_identity_sha256: Sha256
    tenant_identity_sha256: Sha256
    receipt_root_id: SafeLogicalName
    candidate_freeze: Literal["untrusted_candidate_only"] = "untrusted_candidate_only"
    provider_access: Literal["not_attempted"] = "not_attempted"
    environment_values_read: Literal[False] = False
    required_environment_names: tuple[
        Literal[
            "DECISION_RESEARCH_AGENT_API_KEY",
            "DRA_BASE_URL",
            "DRA_POLL_DEADLINE_SECONDS",
            "NIGHT_VOYAGER_LIVE_ACTOR_ID",
            "NIGHT_VOYAGER_LIVE_ORGANIZATION_ID",
            "NIGHT_VOYAGER_LIVE_SESSION_ID",
        ],
        ...,
    ] = (
        "DECISION_RESEARCH_AGENT_API_KEY",
        "DRA_BASE_URL",
        "DRA_POLL_DEADLINE_SECONDS",
        "NIGHT_VOYAGER_LIVE_ACTOR_ID",
        "NIGHT_VOYAGER_LIVE_ORGANIZATION_ID",
        "NIGHT_VOYAGER_LIVE_SESSION_ID",
    )
    filesystem_primitives_ready: Literal[True] = True
    one_shot_budget: Literal[1] = 1
    permitted_next_command: Literal["capture-live"] = "capture-live"


class DraPreflightReceiptV2(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-preflight.v2"] = (
        "night-voyager.dra-live-preflight.v2"
    )
    intent_sha256: Sha256
    attempt_id: SafeIdentity
    intent_receipt: DraReceiptIdentityV1
    candidate_readiness_receipt: DraReceiptIdentityV1
    effective_request_sha256: Sha256
    scenario_id: Literal["dra-v0-1-6-live-closure-v1"]
    producer: DraLiveProducerIdentityV1
    advisor_actor_identity_sha256: Sha256
    tenant_identity_sha256: Sha256
    receipt_root_id: SafeLogicalName
    candidate_freeze: Literal["untrusted_candidate_only"] = "untrusted_candidate_only"
    provider_access: Literal["not_attempted"] = "not_attempted"
    environment_values_read: Literal[False] = False
    required_environment_names: tuple[
        Literal[
            "DECISION_RESEARCH_AGENT_API_KEY",
            "DRA_BASE_URL",
            "DRA_POLL_DEADLINE_SECONDS",
            "NIGHT_VOYAGER_LIVE_ACTOR_ID",
            "NIGHT_VOYAGER_LIVE_ORGANIZATION_ID",
            "NIGHT_VOYAGER_LIVE_SESSION_ID",
        ],
        ...,
    ] = (
        "DECISION_RESEARCH_AGENT_API_KEY",
        "DRA_BASE_URL",
        "DRA_POLL_DEADLINE_SECONDS",
        "NIGHT_VOYAGER_LIVE_ACTOR_ID",
        "NIGHT_VOYAGER_LIVE_ORGANIZATION_ID",
        "NIGHT_VOYAGER_LIVE_SESSION_ID",
    )
    filesystem_primitives_ready: Literal[True] = True
    one_shot_budget: Literal[1] = 1
    permitted_next_command: Literal["capture-live"] = "capture-live"


class DraInspectionRequiredReceiptV1(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-inspection-required.v1"] = (
        "night-voyager.dra-live-inspection-required.v1"
    )
    intent_sha256: Sha256
    attempt_id: SafeIdentity
    preflight_receipt: DraReceiptIdentityV1
    producer: DraLiveProducerIdentityV1
    case_id: UUID
    expected_case_revision: PositiveInt
    advisor_actor_identity_sha256: Sha256
    tenant_identity_sha256: Sha256
    thread_id: BoundedId
    run_id: BoundedId
    segment_id: BoundedId
    state_version: PositiveInt
    acceptance_idempotent_replay: bool
    artifact: DraArtifactIdentityV1
    evidence: tuple[DraLiveEvidenceEnvelopeV1, ...] = Field(min_length=1, max_length=100)
    provider_attempt_consumed: Literal[True]
    operator_action_required: Literal[True] = True
    permitted_next_command: Literal["select-and-import"] = "select-and-import"

    @model_validator(mode="after")
    def exact_evidence_ownership(self) -> Self:
        identifiers: set[str] = set()
        for row in self.evidence:
            if row.run_id != self.run_id or row.segment_id != self.segment_id:
                raise ValueError("dra_evidence_ownership_invalid")
            if row.evidence_id in identifiers:
                raise ValueError("dra_evidence_ids_not_unique")
            identifiers.add(row.evidence_id)
        return self


class DraPollRecoveryReceiptV1(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-poll-recovery.v1"] = (
        "night-voyager.dra-live-poll-recovery.v1"
    )
    intent_sha256: Sha256
    attempt_id: SafeIdentity
    preflight_receipt: DraReceiptIdentityV1
    thread_id: BoundedId
    run_id: BoundedId
    segment_id: BoundedId
    last_state_version: int = Field(ge=0)
    provider_attempt_consumed: Literal[True]
    permitted_next_command: Literal["resume-poll"] = "resume-poll"


class DraControllerStopReceiptV1(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-controller-stop.v1"] = (
        "night-voyager.dra-live-controller-stop.v1"
    )
    intent_sha256: Sha256
    attempt_id: SafeIdentity
    phase: DraLiveFailurePhase
    public_code: PublicCode
    provider_attempt_consumed: bool
    cleanup_status: Literal["removed", "absent", "failed"]
    permitted_next_command: Literal["stop", "cleanup"]


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


class DraProviderAttemptEvidenceV1(FrozenModel):
    create_keys: tuple[Sha256, ...] = Field(min_length=1)
    observed_run_ids: tuple[BoundedId, ...] = Field(min_length=1)
    accepted_run_id: BoundedId

    @model_validator(mode="after")
    def accepted_run_was_observed(self) -> Self:
        if self.accepted_run_id not in self.observed_run_ids:
            raise ValueError("dra_provider_accepted_run_unobserved")
        return self


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
    provider_attempt_evidence: DraProviderAttemptEvidenceV1
    candidate_id: UUID | None = None
    candidate_authority: Literal["untrusted_candidate"] | None = None
    candidate_import_key: Sha256 | None = None
    cleanup_status: Literal["removed", "absent", "failed"] | None = None

    @model_validator(mode="after")
    def unique_stage_names(self) -> Self:
        names = [item.stage for item in self.stage_states]
        if len(names) != len(set(names)):
            raise ValueError("dra_receipt_stage_duplicate")
        candidate_fields = (
            self.candidate_id,
            self.candidate_authority,
            self.candidate_import_key,
            self.cleanup_status,
        )
        if self.selected_evidence is not None and any(value is None for value in candidate_fields):
            raise ValueError("dra_capture_candidate_identity_incomplete")
        return self


class SnapshotIdentityV1(FrozenModel):
    canonical_url: BoundedText
    logical_path: BoundedText
    byte_length: PositiveInt = Field(le=10_485_760)
    sha256: Sha256


class DraPromotionInputV1(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-promotion-input.v1"] = (
        "night-voyager.dra-live-promotion-input.v1"
    )
    intent_sha256: Sha256
    capture: DraCaptureReceiptV1
    organization_id: UUID
    case_id: UUID
    expected_case_revision: PositiveInt
    candidate_id: UUID
    dra_evidence_id: BoundedId
    selected_raw_url: BoundedText
    advisor_actor_identity_sha256: Sha256
    tenant_identity_sha256: Sha256
    reason: BoundedText
    source_attestation: SourceAttestationV1

    @model_validator(mode="after")
    def exact_capture_binding(self) -> Self:
        selected = self.capture.selected_evidence
        if (
            self.capture.intent_sha256 != self.intent_sha256
            or self.capture.candidate_id != self.candidate_id
            or self.capture.candidate_authority != "untrusted_candidate"
            or selected is None
            or selected.evidence_id != self.dra_evidence_id
            or selected.source_url != self.selected_raw_url
            or self.source_attestation.canonical_url != self.selected_raw_url
        ):
            raise ValueError("dra_promotion_capture_binding_invalid")
        return self


class DraPromotionReceiptV1(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-promotion-receipt.v1"] = (
        "night-voyager.dra-live-promotion-receipt.v1"
    )
    intent_sha256: Sha256
    attempt_id: BoundedId
    candidate_id: UUID
    dra_evidence_id: BoundedId
    selected_raw_url: BoundedText
    promotion_key: Sha256
    verification_id: UUID
    promoted_source_pack_version: PositiveInt
    promoted_source_entry_id: UUID
    promoted_evidence_id: UUID
    snapshot: SnapshotIdentityV1
    stage_states: tuple[DraStageStateV1, ...]
    acknowledgement: Literal["promotion_recorded"] = "promotion_recorded"
    provider_attempt_consumed: Literal[True] = True


class DraPlanningTaskProjectionV1(FrozenModel):
    task_id: UUID
    case_id: UUID
    case_revision: PositiveInt
    operation: Literal["generate_governed_mixed_planning_run_v1"]
    source_pack_id: UUID
    source_pack_version: PositiveInt
    status: Literal["needs_advisor_review"]
    planning_run_id: UUID
    execution_id: UUID
    terminal_event_id: PositiveInt
    skill_pin: SkillRuntimePin
    request_sha256: Sha256


class DraReviewAuthorityV1(FrozenModel):
    review_id: UUID
    case_id: UUID
    expected_case_revision: PositiveInt
    planning_run_id: UUID
    brief_id: UUID
    eligible_route_ids: tuple[UUID, ...] = Field(min_length=1)
    action: Literal["approve_for_consultation"] = "approve_for_consultation"
    request_sha256: Sha256


class DraReviewInputV1(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-review-input.v1"] = (
        "night-voyager.dra-live-review-input.v1"
    )
    intent_sha256: Sha256
    promotion: DraPromotionReceiptV1
    organization_id: UUID
    case_id: UUID
    expected_case_revision: PositiveInt
    candidate_id: UUID
    promoted_source_pack_id: UUID
    promoted_source_pack_version: PositiveInt
    advisor_actor_identity_sha256: Sha256
    tenant_identity_sha256: Sha256
    eligible_route_ids: tuple[UUID, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def exact_promotion_binding(self) -> Self:
        if (
            self.promotion.intent_sha256 != self.intent_sha256
            or self.promotion.candidate_id != self.candidate_id
            or self.promotion.promoted_source_pack_version
            != self.promoted_source_pack_version
            or len(self.eligible_route_ids) != len(set(self.eligible_route_ids))
        ):
            raise ValueError("dra_review_promotion_binding_invalid")
        return self


class DraReviewReceiptV1(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-review-receipt.v1"] = (
        "night-voyager.dra-live-review-receipt.v1"
    )
    intent_sha256: Sha256
    attempt_id: BoundedId
    candidate_id: UUID
    source_pack_id: UUID
    source_pack_version: PositiveInt
    task_key: Sha256
    review_key: Sha256
    task: DraPlanningTaskProjectionV1
    review: DraReviewAuthorityV1
    stage_states: tuple[DraStageStateV1, ...]
    acknowledgement: Literal["review_recorded"] = "review_recorded"


class DraDecisionAuthorityV1(FrozenModel):
    decision_id: UUID
    decision_receipt_id: UUID
    timeline_plan_id: UUID
    brief_id: UUID
    selected_route_id: UUID
    expected_brief_version: PositiveInt
    accepted_budget_min_minor: PositiveInt
    accepted_budget_max_minor: PositiveInt
    currency: Literal["CNY"]
    accepted_trade_offs: tuple[BoundedText, ...]
    request_sha256: Sha256


class DraMutationAmbiguousReceiptV1(FrozenModel):
    schema_version: Literal[
        "night-voyager.dra-live-mutation-ambiguous.v1"
    ] = "night-voyager.dra-live-mutation-ambiguous.v1"
    intent_sha256: Sha256
    attempt_id: BoundedId
    stage: Literal["promote", "review", "decide"]
    parent_receipt: DraReceiptIdentityV1
    mutation_key: Sha256
    request_sha256: Sha256
    target_identity_sha256: Sha256
    public_code: Literal["mutation_outcome_ambiguous"] = (
        "mutation_outcome_ambiguous"
    )
    permitted_next_command: Literal["promote", "review", "decide"]


class DraDecisionInputV1(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-decision-input.v1"] = (
        "night-voyager.dra-live-decision-input.v1"
    )
    intent_sha256: Sha256
    review: DraReviewReceiptV1
    organization_id: UUID
    case_id: UUID
    brief_id: UUID
    expected_brief_version: PositiveInt
    selected_route_id: UUID
    accepted_budget_min_minor: PositiveInt
    accepted_budget_max_minor: PositiveInt
    accepted_trade_offs: tuple[BoundedText, ...]
    family_actor_identity_sha256: Sha256
    tenant_identity_sha256: Sha256

    @model_validator(mode="after")
    def exact_review_binding(self) -> Self:
        if (
            self.review.intent_sha256 != self.intent_sha256
            or self.review.review.brief_id != self.brief_id
            or self.selected_route_id
            not in self.review.review.eligible_route_ids
            or self.accepted_budget_min_minor
            > self.accepted_budget_max_minor
        ):
            raise ValueError("dra_decision_review_binding_invalid")
        return self


class DraDecisionReceiptV1(FrozenModel):
    schema_version: Literal["night-voyager.dra-live-decision-receipt.v1"] = (
        "night-voyager.dra-live-decision-receipt.v1"
    )
    intent_sha256: Sha256
    attempt_id: BoundedId
    decision_key: Sha256
    review_id: UUID
    planning_run_id: UUID
    decision: DraDecisionAuthorityV1
    stage_states: tuple[DraStageStateV1, ...]
    acknowledgement: Literal["decision_recorded"] = "decision_recorded"


class DraCandidateReadinessReceiptV1(FrozenModel):
    schema_version: Literal[
        "night-voyager.dra-live-candidate-readiness.v1"
    ] = "night-voyager.dra-live-candidate-readiness.v1"
    merged_main_sha: Annotated[
        str, StringConstraints(pattern=r"^[0-9a-f]{40}$")
    ]
    spec_sha256: Sha256
    plan_sha256: Sha256
    scenario_sha256: Sha256
    intent_schema_sha256: Sha256
    receipt_schema_sha256: Sha256
    cli_sha256: Sha256
    producer: DraLiveProducerIdentityV1
    required_hosted_checks: tuple[
        Literal["compose", "frontend", "python"], ...
    ]
    recovery_matrix_status: Literal["passed"]
    docker_preflight_status: Literal["passed"]
    docker_inventory_sha256: Sha256
    hosted_checks_evidence_sha256: Sha256
    recovery_matrix_evidence_sha256: Sha256
    authority_review_evidence_sha256: Sha256
    cleanup_state: Literal["clean"]
    authorization_placeholder: Literal[
        "PENDING_SEPARATE_LIVE_ACCEPTANCE_AUTHORIZATION"
    ]
    capability_status: Literal[
        "INCOMPLETE_PENDING_LIVE_ACCEPTANCE"
    ] = "INCOMPLETE_PENDING_LIVE_ACCEPTANCE"

    @model_validator(mode="after")
    def exact_hosted_checks(self) -> Self:
        if self.required_hosted_checks != (
            "compose",
            "frontend",
            "python",
        ):
            raise ValueError("dra_live_required_checks_invalid")
        return self


class DraCandidateReadinessReceiptV2(FrozenModel):
    schema_version: Literal[
        "night-voyager.dra-live-candidate-readiness.v2"
    ] = "night-voyager.dra-live-candidate-readiness.v2"
    merged_main_sha: Annotated[
        str, StringConstraints(pattern=r"^[0-9a-f]{40}$")
    ]
    request: DraFrozenRequestV2
    spec_sha256: Sha256
    plan_sha256: Sha256
    scenario_sha256: Sha256
    intent_schema_sha256: Sha256
    receipt_schema_sha256: Sha256
    cli_sha256: Sha256
    producer: DraLiveProducerIdentityV1
    required_hosted_checks: tuple[
        Literal["compose", "frontend", "python"], ...
    ]
    recovery_matrix_status: Literal["passed"]
    docker_preflight_status: Literal["passed"]
    docker_inventory_sha256: Sha256
    hosted_checks_evidence_sha256: Sha256
    recovery_matrix_evidence_sha256: Sha256
    authority_review_evidence_sha256: Sha256
    cleanup_state: Literal["clean"]
    authorization_placeholder: Literal[
        "PENDING_SEPARATE_LIVE_ACCEPTANCE_AUTHORIZATION"
    ]
    capability_status: Literal[
        "INCOMPLETE_PENDING_LIVE_ACCEPTANCE"
    ] = "INCOMPLETE_PENDING_LIVE_ACCEPTANCE"

    @model_validator(mode="after")
    def exact_hosted_checks(self) -> Self:
        if self.required_hosted_checks != (
            "compose",
            "frontend",
            "python",
        ):
            raise ValueError("dra_live_required_checks_invalid")
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
    permitted_next_action: Literal["stop", "same_run_recovery", "separate_authorization"]
