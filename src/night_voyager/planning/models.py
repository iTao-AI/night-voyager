from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import AnyUrl, BaseModel, ConfigDict, PositiveInt, field_validator, model_validator


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class EvidenceAuthority(StrEnum):
    UNTRUSTED_CANDIDATE = "untrusted_candidate"
    ACCEPTED_SYNTHETIC_DEMO = "accepted_synthetic_demo"
    EXTERNALLY_VERIFIED = "externally_verified"


class EvidenceClass(StrEnum):
    SYNTHETIC_DEMO = "synthetic_demo"
    INSTITUTIONAL = "institutional"
    GOVERNMENT = "government"


class RedistributionClass(StrEnum):
    SYNTHETIC_PUBLIC = "synthetic_public"
    LINK_ONLY = "link_only"


class Country(StrEnum):
    AUSTRALIA = "australia"
    JAPAN = "japan"
    MALAYSIA = "malaysia"


class RouteOutcome(StrEnum):
    RECOMMENDED_WITH_CONDITION = "recommended_with_condition"
    CONDITIONAL = "conditional"
    BLOCKED = "blocked"


class DimensionOutcome(StrEnum):
    SUPPORTED = "supported"
    CONDITIONAL = "conditional"
    BLOCKED = "blocked"


class EvidenceRole(StrEnum):
    PROGRAM_FIT = "program_fit"
    TUITION = "tuition"
    LIVING_COST = "living_cost"
    FX = "fx"
    RANKING = "ranking"


class RunState(StrEnum):
    DRAFT = "draft"
    COLLECTING_EVIDENCE = "collecting_evidence"
    SYNTHESIZING = "synthesizing"
    FAILED = "failed"
    BLOCKED = "blocked"
    REVIEW_REQUIRED = "review_required"


class CaseState(StrEnum):
    INTAKE = "intake"
    PLANNING = "planning"
    ADVISOR_REVIEW = "advisor_review"


class BudgetEnvelope(FrozenModel):
    schema_version: Literal[1]
    currency: Literal["CNY"]
    period: Literal["program_total"]
    preferred_minor: PositiveInt | None
    hard_ceiling_minor: PositiveInt | None
    elasticity_bps: int
    refused: bool = False

    @model_validator(mode="after")
    def validate_envelope(self) -> BudgetEnvelope:
        if not 0 <= self.elasticity_bps <= 2500:
            raise ValueError("elasticity_bps must be inside the approved 0..2500 boundary")
        if self.refused:
            if self.preferred_minor is not None or self.hard_ceiling_minor is not None:
                raise ValueError("refused budget cannot carry monetary ceilings")
        elif self.preferred_minor is None or self.hard_ceiling_minor is None:
            raise ValueError("non-refused budget requires preferred and hard ceilings")
        elif self.preferred_minor > self.hard_ceiling_minor:
            raise ValueError("preferred budget cannot exceed hard ceiling")
        return self


class StudentPreferences(FrozenModel):
    schema_version: Literal[1]
    intended_field: str
    preferred_countries: tuple[Country, ...]
    intake: str


class FamilyPreferences(FrozenModel):
    schema_version: Literal[1]
    risk_tolerance: Literal["low", "medium", "high"]
    japan_risk_accepted: bool
    budget: BudgetEnvelope


class StudentCaseRevision(FrozenModel):
    schema_version: Literal[1]
    organization_id: UUID
    case_id: UUID
    revision: PositiveInt
    student: StudentPreferences
    family: FamilyPreferences


class SourcePackEntryV1(FrozenModel):
    schema_version: Literal[1]
    entry_id: UUID
    path: str
    sha256: str
    snapshot_date: date
    publisher: str
    institution: str
    canonical_url: AnyUrl
    freshness_days: PositiveInt
    redistribution_class: RedistributionClass
    evidence_class: EvidenceClass
    coverage: tuple[str, ...]
    known_gaps: tuple[str, ...]

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if value.startswith("/") or ".." in value.split("/"):
            raise ValueError("source path must be relative and traversal-free")
        return value

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
        return value


class SourcePackManifestV1(FrozenModel):
    schema_version: Literal[1]
    organization_id: UUID
    pack_id: UUID
    version: PositiveInt
    entries: tuple[SourcePackEntryV1, ...]

    @model_validator(mode="after")
    def unique_entries(self) -> SourcePackManifestV1:
        if len({entry.entry_id for entry in self.entries}) != len(self.entries):
            raise ValueError("source entry IDs must be unique")
        return self


class EvidenceRef(FrozenModel):
    schema_version: Literal[1]
    organization_id: UUID
    evidence_id: UUID
    claim: str
    source_pack_id: UUID
    source_pack_version: PositiveInt
    source_entry_id: UUID
    source_sha256: str
    authority: EvidenceAuthority

    _validate_sha256 = field_validator("source_sha256")(SourcePackEntryV1.validate_sha256.__func__)

    @model_validator(mode="after")
    def caller_authority_boundary(self) -> EvidenceRef:
        if self.authority is EvidenceAuthority.EXTERNALLY_VERIFIED:
            raise ValueError(
                "externally_verified requires a trusted authority record outside M3A input"
            )
        return self


class CostEvidence(FrozenModel):
    schema_version: Literal[1]
    organization_id: UUID
    country: Country
    intake: str
    period: Literal["program_total"]
    currency: str
    tuition_minor: PositiveInt
    living_minor: PositiveInt
    fx_rate: Decimal
    fx_source: str
    fx_date: date
    tuition_evidence_id: UUID
    living_evidence_id: UUID
    fx_evidence_id: UUID

    @field_validator("fx_rate")
    @classmethod
    def positive_fx(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0:
            raise ValueError("fx_rate must be finite and positive")
        return value


class RankingEvidence(FrozenModel):
    schema_version: Literal[1]
    organization_id: UUID
    country: Country
    ranking_system: str
    rank: PositiveInt
    publication_year: int
    evidence_id: UUID


class PlanningInput(FrozenModel):
    schema_version: Literal[1]
    organization_id: UUID
    case: StudentCaseRevision
    source_pack: SourcePackManifestV1
    evidence: tuple[EvidenceRef, ...]
    costs: tuple[CostEvidence, ...]
    rankings: tuple[RankingEvidence, ...]
    narrative: str | None = None


class EvidenceUse(FrozenModel):
    role: EvidenceRole
    evidence_id: UUID


class DimensionResult(FrozenModel):
    dimension_key: str
    outcome: DimensionOutcome
    reason_code: str
    evidence_uses: tuple[EvidenceUse, ...]


class RouteResult(FrozenModel):
    country: Country
    outcome: RouteOutcome
    reason_code: str
    dimensions: tuple[DimensionResult, ...]


class PlanningResult(FrozenModel):
    state: RunState
    reason_code: str
    routes: tuple[RouteResult, ...]
