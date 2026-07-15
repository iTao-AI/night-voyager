from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, PositiveInt, field_validator

from night_voyager.planning.models import (
    CostEvidence,
    EvidenceAuthority,
    EvidenceRole,
    FrozenModel,
    RankingEvidence,
    SourcePackEntryV1,
    SourcePackManifestV1,
    StudentCaseRevision,
)


class TrustedEvidenceRef(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    schema_version: Literal[1]
    organization_id: UUID
    evidence_id: UUID
    claim: str
    source_pack_id: UUID
    source_pack_version: PositiveInt
    source_entry_id: UUID
    source_sha256: str
    authority: Literal[
        EvidenceAuthority.ACCEPTED_SYNTHETIC_DEMO,
        EvidenceAuthority.EXTERNALLY_VERIFIED,
    ]

    _validate_sha256 = field_validator("source_sha256")(
        SourcePackEntryV1.validate_sha256.__func__
    )


class GovernedMixedPlanningInput(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    schema_version: Literal[1]
    operation: Literal["generate_governed_mixed_planning_run_v1"]
    organization_id: UUID
    case: StudentCaseRevision
    source_pack: SourcePackManifestV1
    evidence: tuple[TrustedEvidenceRef, ...]
    costs: tuple[CostEvidence, ...]
    rankings: tuple[RankingEvidence, ...]
    narrative: str | None = None


class GovernedMixedSnapshotV1(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    schema_version: Literal[1]
    organization_id: UUID
    case: StudentCaseRevision
    source_pack: SourcePackManifestV1
    evidence: tuple[TrustedEvidenceRef, ...]
    verification_decision: Literal["approve"]
    verification_claim: Literal["australia_program_fit"]
    verification_evidence_role: Literal[EvidenceRole.PROGRAM_FIT]
    baseline_source_pack_id: UUID
    baseline_source_pack_version: Literal[1]
    baseline_manifest_sha256: str
    baseline_raw_manifest_sha256: str
    promoted_source_pack_version: PositiveInt
    promoted_source_entry_id: UUID
    promoted_evidence_id: UUID

    _validate_hashes = field_validator(
        "baseline_manifest_sha256", "baseline_raw_manifest_sha256"
    )(SourcePackEntryV1.validate_sha256.__func__)
