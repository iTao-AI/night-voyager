from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class EvidenceAuthority(StrEnum):
    UNTRUSTED_CANDIDATE = "untrusted_candidate"
    ACCEPTED_SYNTHETIC_DEMO = "accepted_synthetic_demo"
    EXTERNALLY_VERIFIED = "externally_verified"


class RouteOutcome(StrEnum):
    RECOMMENDED_WITH_CONDITION = "recommended_with_condition"
    CONDITIONAL = "conditional"
    BLOCKED = "blocked"


class RunState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    FAILED = "failed"
    BLOCKED = "blocked"
    REVIEW_REQUIRED = "review_required"


class StudentPreferences(FrozenModel):
    schema_version: int
    intended_field: str
    preferred_countries: tuple[str, ...]


class FamilyPreferences(FrozenModel):
    schema_version: int
    budget_currency: str
    budget_minor: int | None
    risk_tolerance: str


class StudentCaseRevision(FrozenModel):
    schema_version: int
    revision: int
    student: StudentPreferences
    family: FamilyPreferences


class SourcePackEntry(FrozenModel):
    schema_version: int
    entry_id: str
    path: str
    sha256: str

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
        return value


class EvidenceRef(FrozenModel):
    schema_version: int
    evidence_id: str
    claim: str
    source_pack_version: int
    source_entry_id: str
    source_sha256: str
    authority: EvidenceAuthority

    _validate_sha256 = field_validator("source_sha256")(SourcePackEntry.validate_sha256.__func__)


class CostEvidence(FrozenModel):
    schema_version: int
    currency: str
    tuition_minor: int | None
    living_minor: int | None
    fx_rate: float | None
    fx_boundary_bps: int | None

    @model_validator(mode="after")
    def reject_zero_filled_unknowns(self) -> CostEvidence:
        values = (self.tuition_minor, self.living_minor, self.fx_rate, self.fx_boundary_bps)
        if any(value == 0 for value in values if value is not None):
            raise ValueError("unknown cost and FX values must be null, never zero-filled")
        return self


class RankingEvidence(FrozenModel):
    schema_version: int
    ranking_system: str
    rank: int | None
    publication_year: int


class RouteCandidate(FrozenModel):
    route_id: str
    outcome: RouteOutcome
    required_claims: tuple[str, ...]
    evidence: tuple[EvidenceRef, ...]


class PlanningInput(FrozenModel):
    schema_version: int
    organization_id: str
    case_revision: int
    source_pack_version: int
    routes: tuple[RouteCandidate, ...]
    narrative: str | None = None


class PlanningResult(FrozenModel):
    state: RunState
    reason_code: str
