from __future__ import annotations

from typing import Annotated, Literal, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, PositiveInt, StringConstraints, model_validator

from night_voyager.dra.models import (
    DraEvidenceProjectionV1,
    DraProducerPinV1,
    DraRunRequestIdentityV1,
    Sha256,
    SourceAttestationV1,
)
from night_voyager.identity.models import ActorContext

IdempotencyKey = Annotated[str, StringConstraints(min_length=16, max_length=200)]
DecisionReason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class FrozenPortModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ImportDraCandidateCommand(FrozenPortModel):
    organization_id: UUID
    case_id: UUID
    expected_case_revision: PositiveInt
    producer: DraProducerPinV1
    request_identity: DraRunRequestIdentityV1
    run_id: str
    artifact_id: Literal["research-report.md"]
    artifact_kind: Literal["research_report_markdown"]
    artifact_media_type: Literal["text/markdown"]
    artifact_byte_length: PositiveInt
    artifact_sha256: Sha256
    artifact_content: None = None
    evidence: tuple[DraEvidenceProjectionV1, ...]
    import_request_sha256: Sha256


class VerifyDraCandidateCommand(FrozenPortModel):
    case_id: UUID
    candidate_id: UUID
    expected_case_revision: PositiveInt
    dra_evidence_id: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    decision: Literal["approve", "reject"]
    reason: DecisionReason
    source_attestation: SourceAttestationV1 | None = None

    @model_validator(mode="after")
    def exact_decision_shape(self) -> Self:
        if (self.decision == "approve") != (self.source_attestation is not None):
            raise ValueError("dra_verification_decision_shape_invalid")
        return self


class CopiedEvidenceIdentity(FrozenPortModel):
    claim: str
    evidence_id: UUID


class PromotionIdentities(FrozenPortModel):
    verification_id: UUID
    claim: Literal["australia_program_fit"] = "australia_program_fit"
    evidence_role: Literal["program_fit"] = "program_fit"
    authority: Literal["externally_verified"] = "externally_verified"
    external_source_entry_id: UUID
    promoted_external_evidence_id: UUID
    copied_baseline_evidence: tuple[CopiedEvidenceIdentity, ...]


class DraVerificationViewV1(FrozenPortModel):
    verification_id: UUID
    decision: Literal["approve", "reject"]
    promoted_source_pack_version: PositiveInt | None = None
    promoted_source_entry_id: UUID | None = None
    promoted_evidence_id: UUID | None = None


class DraCandidateViewV1(FrozenPortModel):
    candidate_id: UUID
    verification: DraVerificationViewV1 | None


class DraCandidateRepository(Protocol):
    async def import_candidate(
        self,
        context: ActorContext,
        command: ImportDraCandidateCommand,
        candidate_id: UUID,
        idempotency_key: str,
    ) -> DraCandidateViewV1: ...

    async def get_candidate(
        self,
        context: ActorContext,
        case_id: UUID,
        candidate_id: UUID,
    ) -> DraCandidateViewV1 | None: ...

    async def verify_and_promote(
        self,
        context: ActorContext,
        command: VerifyDraCandidateCommand,
        identities: PromotionIdentities,
        idempotency_key: str,
    ) -> DraVerificationViewV1: ...
