from __future__ import annotations

import hashlib
import ipaddress
from datetime import date
from pathlib import PurePosixPath
from typing import Annotated, Literal, Self, cast
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    StringConstraints,
    computed_field,
    field_validator,
    model_validator,
)

DRA_RELEASE = "v0.1.3"
DRA_COMMIT = "87b2a8e335385eb865086f7a69fe2b190567cfa2"
DRA_LIVE_RELEASE = "v0.1.6"
DRA_LIVE_COMMIT = "7d43324b469cb5e445c2e8be83af3be4d841cf1c"
DRA_LIVE_TAG_OBJECT = "9e0b0b443c435cf636dfce932c3c77d91d0a43e4"
DRA_CONTRACT_SCHEMA = "dra.downstream-consumer.v1"
DRA_FIXTURE_SHA256 = "cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157"
DRA_STRICT_REPOSITORY = "https://github.com/iTao-AI/decision-research-agent"
DRA_STRICT_COMMIT = "01ba21f2996769e68cbc88f4bb0596740df27f6b"
DRA_STRICT_PROFILE_ID = "generic-strict-citation"
DRA_STRICT_PROFILE_VERSION = "1"
DRA_STRICT_PROOF_SCHEMA = "dra.strict-citation-profile.v1"
MAX_ARTIFACT_BYTES = 1024 * 1024

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
BoundedId = Annotated[str, StringConstraints(min_length=1, max_length=200)]
BoundedText = Annotated[str, StringConstraints(min_length=1, max_length=2048)]
GitObjectSha = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def is_public_source_host(host: str) -> bool:
    normalized = host.rstrip(".").lower()
    if (
        normalized == "localhost"
        or normalized.endswith(".localhost")
        or normalized.endswith(".local")
    ):
        return False
    literal = normalized.removeprefix("[").removesuffix("]")
    try:
        return ipaddress.ip_address(literal).is_global
    except ValueError:
        return "." in normalized


def validate_raw_public_https_url(raw_url: str) -> str:
    if any(character.isspace() or ord(character) < 32 for character in raw_url):
        raise ValueError("dra_source_url_invalid")
    try:
        parsed = urlsplit(raw_url)
        host = parsed.hostname
        _ = parsed.port
    except ValueError as error:
        raise ValueError("dra_source_url_invalid") from error
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or host is None
        or parsed.username is not None
        or parsed.password is not None
        or not is_public_source_host(host)
    ):
        raise ValueError("dra_source_url_invalid")
    return raw_url


class DraHealthProjectionV1(FrozenModel):
    status: Literal["ok"]
    service: Literal["decision-research-agent"]


class DraProducerPinV1(FrozenModel):
    name: Literal["decision-research-agent"] = "decision-research-agent"
    release: Literal["v0.1.3", "v0.1.6"] = DRA_RELEASE
    commit: GitObjectSha = DRA_COMMIT
    contract_schema: Literal["dra.downstream-consumer.v1"] = DRA_CONTRACT_SCHEMA
    fixture_sha256: Literal[
        "cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157"
    ] = DRA_FIXTURE_SHA256

    @model_validator(mode="after")
    def exact_supported_tuple(self) -> Self:
        if (self.release, self.commit) not in {
            (DRA_RELEASE, DRA_COMMIT),
            (DRA_LIVE_RELEASE, DRA_LIVE_COMMIT),
        }:
            raise ValueError("dra_producer_identity_invalid")
        return self


DRA_HISTORICAL_PRODUCER = DraProducerPinV1()
DRA_LIVE_PRODUCER = DraProducerPinV1(
    release=DRA_LIVE_RELEASE,
    commit=DRA_LIVE_COMMIT,
)


class DraProducerPinV2(FrozenModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        serialize_by_alias=True,
        validate_by_name=True,
    )

    schema_: Literal["night-voyager.dra-producer-pin.v2"] = Field(
        default="night-voyager.dra-producer-pin.v2",
        alias="schema",
    )
    repository: Literal[
        "https://github.com/iTao-AI/decision-research-agent"
    ] = DRA_STRICT_REPOSITORY
    ref_kind: Literal["commit"] = "commit"
    ref: Literal[
        "01ba21f2996769e68cbc88f4bb0596740df27f6b"
    ] = DRA_STRICT_COMMIT
    commit: Literal[
        "01ba21f2996769e68cbc88f4bb0596740df27f6b"
    ] = DRA_STRICT_COMMIT
    consumer_contract_schema: Literal["dra.downstream-consumer.v1"] = (
        DRA_CONTRACT_SCHEMA
    )
    consumer_fixture_sha256: Literal[
        "cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157"
    ] = DRA_FIXTURE_SHA256
    profile_id: Literal["generic-strict-citation"] = DRA_STRICT_PROFILE_ID
    profile_version: Literal["1"] = DRA_STRICT_PROFILE_VERSION
    proof_schema: Literal["dra.strict-citation-profile.v1"] = (
        DRA_STRICT_PROOF_SCHEMA
    )


DRA_STRICT_PRODUCER = DraProducerPinV2()


class DraRunRequestIdentityV1(FrozenModel):
    profile_id: Literal["generic"] = "generic"
    request_sha256: Sha256


class DraRunRequestIdentityV2(FrozenModel):
    schema_version: Literal["night-voyager.dra-run-request-identity.v2"]
    profile_id: Literal["generic-strict-citation"]
    request_sha256: Sha256


class DraObservedProfileManifestV1(FrozenModel):
    schema_version: Literal["night-voyager.dra-observed-profile-manifest.v1"]
    profile_id: Literal["generic-strict-citation"]
    profile_version: Literal["1"]


class DraStrictConsumerIdentityV2(FrozenModel):
    schema_version: Literal["night-voyager.dra-strict-consumer-identity.v2"]
    producer: DraProducerPinV2
    request: DraRunRequestIdentityV2
    observed_profile: DraObservedProfileManifestV1

    @model_validator(mode="after")
    def exact_strict_profile(self) -> Self:
        if (
            self.request.profile_id != self.producer.profile_id
            or self.observed_profile.profile_id != self.producer.profile_id
            or self.observed_profile.profile_version != self.producer.profile_version
        ):
            raise ValueError("dra_strict_profile_identity_invalid")
        return self


class DraRunAcceptanceV1(FrozenModel):
    thread_id: BoundedId
    run_id: BoundedId
    segment_id: BoundedId
    idempotent_replay: bool


class DraRunProjectionV1(FrozenModel):
    run_id: BoundedId
    state_version: int
    execution_status: Literal["completed"]
    review_status: Literal["not_required"]
    delivery_status: Literal["ready"]

    @field_validator("state_version")
    @classmethod
    def positive_state_version(cls, value: int) -> int:
        if value < 1:
            raise ValueError("dra_run_not_canonical_ready")
        return value

    @model_validator(mode="before")
    @classmethod
    def canonical_ready_only(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        payload = cast(dict[str, object], value)
        if (
            payload.get("execution_status") != "completed"
            or payload.get("review_status") != "not_required"
            or payload.get("delivery_status") != "ready"
        ):
            raise ValueError("dra_run_not_canonical_ready")
        return payload


class DraRunStateProjectionV1(FrozenModel):
    run_id: BoundedId
    state_version: int
    execution_status: Literal[
        "pending", "running", "completed", "completed_with_fallback", "failed"
    ]
    review_status: Literal["not_required", "required", "resolved"]
    delivery_status: Literal["pending", "ready", "review_required", "blocked", "failed"]

    @computed_field
    @property
    def disposition(self) -> Literal["in_progress", "canonical_ready", "terminal_invalid"]:
        state = (
            self.execution_status,
            self.review_status,
            self.delivery_status,
        )
        if state in {
            ("pending", "not_required", "pending"),
            ("running", "not_required", "pending"),
        }:
            return "in_progress"
        if state == ("completed", "not_required", "ready") and self.state_version > 0:
            return "canonical_ready"
        return "terminal_invalid"


class DraEvidenceProjectionV1(FrozenModel):
    evidence_id: BoundedId
    source_url: BoundedText | None
    source_identity: BoundedText
    retrieved_at: AwareDatetime
    citation_status: Literal["cited"]
    verification_status: Literal["verified", "unverified"]

    @model_validator(mode="after")
    def exact_public_identity(self) -> Self:
        if self.source_url is None:
            return self
        validate_raw_public_https_url(self.source_url)
        if self.source_identity != self.source_url:
            raise ValueError("dra_source_identity_mismatch")
        return self

    @computed_field
    @property
    def is_promotable(self) -> bool:
        return self.source_url is not None


class DraCanonicalArtifactInputV1(FrozenModel):
    artifact_id: Literal["research-report.md"]
    kind: Literal["research_report_markdown"]
    media_type: Literal["text/markdown"]
    content: Annotated[str, StringConstraints(min_length=1)]
    content_hash: Sha256

    @computed_field
    @property
    def byte_length(self) -> int:
        return len(self.content.encode("utf-8"))

    @model_validator(mode="after")
    def exact_bytes(self) -> Self:
        encoded = self.content.encode("utf-8")
        if len(encoded) > MAX_ARTIFACT_BYTES:
            raise ValueError("dra_artifact_oversize")
        if hashlib.sha256(encoded).hexdigest() != self.content_hash:
            raise ValueError("dra_artifact_hash_mismatch")
        return self


class DraCanonicalResultProjectionV1(FrozenModel):
    run_id: BoundedId
    execution_status: Literal["completed"]
    delivery_status: Literal["ready"]
    artifact: DraCanonicalArtifactInputV1


class DraCandidateImportV1(FrozenModel):
    schema_version: Literal["night-voyager.dra-candidate-import.v1"]
    organization_id: UUID
    case_id: UUID
    expected_case_revision: PositiveInt
    producer: DraProducerPinV1
    request_identity: DraRunRequestIdentityV1
    acceptance: DraRunAcceptanceV1
    run: DraRunProjectionV1
    artifact: DraCanonicalArtifactInputV1
    evidence: tuple[DraEvidenceProjectionV1, ...]

    @model_validator(mode="after")
    def unique_ordered_evidence(self) -> Self:
        identifiers = [item.evidence_id for item in self.evidence]
        if not identifiers or len(identifiers) != len(set(identifiers)):
            raise ValueError("dra_evidence_ids_not_unique")
        if self.acceptance.run_id != self.run.run_id:
            raise ValueError("dra_run_identity_mismatch")
        if sum(item.is_promotable for item in self.evidence) != 1:
            raise ValueError("dra_promotable_evidence_cardinality")
        return self


class DraCandidateImportV2(FrozenModel):
    schema_version: Literal["night-voyager.dra-candidate-import.v2"]
    organization_id: UUID
    case_id: UUID
    expected_case_revision: PositiveInt
    consumer_identity: DraStrictConsumerIdentityV2
    acceptance: DraRunAcceptanceV1
    run: DraRunProjectionV1
    artifact: DraCanonicalArtifactInputV1
    evidence: tuple[DraEvidenceProjectionV1, ...]

    @model_validator(mode="after")
    def exact_strict_candidate(self) -> Self:
        identifiers = [item.evidence_id for item in self.evidence]
        if not identifiers or len(identifiers) != len(set(identifiers)):
            raise ValueError("dra_evidence_ids_not_unique")
        if self.acceptance.run_id != self.run.run_id:
            raise ValueError("dra_run_identity_mismatch")
        if sum(item.is_promotable for item in self.evidence) != 1:
            raise ValueError("dra_promotable_evidence_cardinality")
        source_url = next(
            item.source_url for item in self.evidence if item.is_promotable
        )
        if source_url is None or source_url not in self.artifact.content:
            raise ValueError("dra_cited_source_not_in_canonical_artifact")
        return self


class DraResearchCandidateV1(FrozenModel):
    schema_version: Literal["night-voyager.dra-candidate.v1"]
    candidate_id: UUID
    organization_id: UUID
    case_id: UUID
    expected_case_revision: PositiveInt
    producer: DraProducerPinV1
    request_identity: DraRunRequestIdentityV1
    run_id: BoundedId
    artifact_id: Literal["research-report.md"]
    artifact_kind: Literal["research_report_markdown"]
    artifact_media_type: Literal["text/markdown"]
    artifact_byte_length: PositiveInt
    artifact_sha256: Sha256
    evidence: tuple[DraEvidenceProjectionV1, ...]
    import_request_sha256: Sha256
    authority: Literal["untrusted_candidate"] = "untrusted_candidate"
    created_at: AwareDatetime

    @model_validator(mode="after")
    def unique_ordered_evidence(self) -> Self:
        identifiers = [item.evidence_id for item in self.evidence]
        if not identifiers or len(identifiers) != len(set(identifiers)):
            raise ValueError("dra_evidence_ids_not_unique")
        if sum(item.is_promotable for item in self.evidence) != 1:
            raise ValueError("dra_promotable_evidence_cardinality")
        return self


class SourceAttestationV1(FrozenModel):
    canonical_url: BoundedText
    publisher: BoundedText
    institution: BoundedText
    snapshot_date: date
    freshness_days: PositiveInt
    redistribution_class: Literal["link_only"]
    evidence_class: Literal["institutional", "government"]
    logical_path: BoundedText
    snapshot_byte_length: PositiveInt
    snapshot_sha256: Sha256
    known_gaps: tuple[BoundedId, ...]

    @field_validator("logical_path")
    @classmethod
    def traversal_free_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("dra_source_path_invalid")
        return value

    @model_validator(mode="after")
    def required_gaps_and_public_url(self) -> Self:
        if not {"applicant_eligibility", "intake_availability"}.issubset(self.known_gaps):
            raise ValueError("dra_source_known_gaps_missing")
        validate_raw_public_https_url(self.canonical_url)
        return self


class VerificationDecisionV1(FrozenModel):
    decision: Literal["approve", "reject"]
    reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    source_attestation: SourceAttestationV1 | None = None

    @model_validator(mode="after")
    def decision_shape(self) -> Self:
        if (self.decision == "approve") != (self.source_attestation is not None):
            raise ValueError("dra_verification_decision_shape_invalid")
        return self


class DraFixtureProjectionV1(FrozenModel):
    schema_version: Literal["dra.downstream-consumer.v1"]
    health: DraHealthProjectionV1
    dispositions: dict[str, str]
    canonical_import: DraCandidateImportV1
