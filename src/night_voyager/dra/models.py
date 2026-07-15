from __future__ import annotations

import hashlib
import ipaddress
from datetime import date
from pathlib import PurePosixPath
from typing import Annotated, Literal, Self, cast
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    HttpUrl,
    PositiveInt,
    StringConstraints,
    computed_field,
    field_validator,
    model_validator,
)

DRA_RELEASE = "v0.1.3"
DRA_COMMIT = "87b2a8e335385eb865086f7a69fe2b190567cfa2"
DRA_CONTRACT_SCHEMA = "dra.downstream-consumer.v1"
DRA_FIXTURE_SHA256 = "cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157"
MAX_ARTIFACT_BYTES = 1024 * 1024

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
BoundedId = Annotated[str, StringConstraints(min_length=1, max_length=200)]
BoundedText = Annotated[str, StringConstraints(min_length=1, max_length=2048)]


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


class DraHealthProjectionV1(FrozenModel):
    status: Literal["ok"]
    service: Literal["decision-research-agent"]


class DraProducerPinV1(FrozenModel):
    name: Literal["decision-research-agent"] = "decision-research-agent"
    release: Literal["v0.1.3"] = DRA_RELEASE
    commit: Literal["87b2a8e335385eb865086f7a69fe2b190567cfa2"] = DRA_COMMIT
    contract_schema: Literal["dra.downstream-consumer.v1"] = DRA_CONTRACT_SCHEMA
    fixture_sha256: Literal[
        "cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157"
    ] = DRA_FIXTURE_SHA256


class DraRunRequestIdentityV1(FrozenModel):
    profile_id: Literal["generic"] = "generic"
    request_sha256: Sha256


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


class DraEvidenceProjectionV1(FrozenModel):
    evidence_id: BoundedId
    source_url: HttpUrl | None
    source_identity: BoundedText
    retrieved_at: AwareDatetime
    citation_status: Literal["cited"]
    verification_status: Literal["verified", "unverified"]

    @model_validator(mode="after")
    def exact_public_identity(self) -> Self:
        if self.source_url is None:
            return self
        url = str(self.source_url)
        if (
            self.source_url.scheme != "https"
            or self.source_url.username is not None
            or self.source_url.password is not None
            or self.source_url.host is None
            or not is_public_source_host(self.source_url.host)
        ):
            raise ValueError("dra_source_url_invalid")
        if self.source_identity != url:
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
        return self


class SourceAttestationV1(FrozenModel):
    canonical_url: HttpUrl
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
        if (
            self.canonical_url.scheme != "https"
            or self.canonical_url.host is None
            or not is_public_source_host(self.canonical_url.host)
        ):
            raise ValueError("dra_source_url_invalid")
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
