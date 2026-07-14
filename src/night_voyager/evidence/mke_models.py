"""Night Voyager-owned M4B manifest, query, candidate, and failure models."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    PositiveInt,
    StringConstraints,
    ValidationInfo,
    field_validator,
    model_validator,
)

from night_voyager.evidence.mke_contract import LocatorV1, PageLocatorV1, TimestampLocatorV1
from night_voyager.planning.models import EvidenceRef, EvidenceRole

LocatorKind = Literal["page", "timestamp_ms"]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
BoundedClaim = Annotated[str, StringConstraints(min_length=1, max_length=128)]
BoundedQuery = Annotated[str, StringConstraints(min_length=1, max_length=4096)]
SelectedText = Annotated[str, StringConstraints(min_length=1, max_length=65_536)]

MkeFailureCode = Literal[
    "mke_candidate_inputs_missing",
    "mke_candidate_mismatch",
    "mke_environment_failed",
    "mke_install_failed",
    "mke_store_setup_failed",
    "mke_contract_incompatible",
    "mke_response_invalid",
    "mke_store_empty",
    "mke_no_active_publication",
    "mke_active_store_no_match",
    "mke_manifest_mapping_failed",
    "mke_evidence_role_mismatch",
    "mke_locator_mismatch",
    "mke_source_snapshot_changed",
    "mke_snapshot_pair_mismatch",
    "mke_startup_timeout",
    "mke_tool_timeout",
    "mke_transport_failed",
    "mke_server_exit",
    "mke_output_limit_exceeded",
    "mke_cleanup_failed",
    "mke_consumer_failed",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class M4BSourceEntryV1(FrozenModel):
    schema_version: Literal["night_voyager.m4b_source_entry.v1"]
    entry_id: UUID
    path: str
    sha256: Sha256
    media_type: Literal["application/pdf"]
    claim: BoundedClaim
    evidence_role: Literal[EvidenceRole.PROGRAM_FIT]
    allowed_locators: tuple[LocatorV1, ...]

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if not value or value.startswith("/") or ".." in value.split("/"):
            raise ValueError("source path must be relative and traversal-free")
        return value

    @model_validator(mode="after")
    def validate_smoke_locator(self) -> M4BSourceEntryV1:
        kinds = [locator.kind for locator in self.allowed_locators]
        if len(kinds) != len(set(kinds)):
            raise ValueError("allowed locator kinds must be unique")
        if self.allowed_locators != (PageLocatorV1(kind="page", start=1, end=1),):
            raise ValueError("M4B smoke source must allow exactly page locator [1, 1]")
        return self


class M4BManifestV1(FrozenModel):
    schema_version: Literal["night_voyager.m4b_manifest.v1"]
    organization_id: UUID
    source_pack_id: UUID
    source_pack_version: PositiveInt
    sources: tuple[M4BSourceEntryV1, ...]

    @model_validator(mode="after")
    def validate_sources(self) -> M4BManifestV1:
        if len(self.sources) != 1:
            raise ValueError("M4B smoke manifest must contain exactly one source")
        if len({source.entry_id for source in self.sources}) != len(self.sources):
            raise ValueError("source entry IDs must be unique")
        if len({source.sha256 for source in self.sources}) != len(self.sources):
            raise ValueError("source fingerprints must be unique")
        return self


class EvidenceQuery(FrozenModel):
    schema_version: Literal[1]
    organization_id: UUID
    source_pack_id: UUID
    source_pack_version: PositiveInt
    claim: BoundedClaim
    evidence_role: EvidenceRole
    query: BoundedQuery
    allowed_locator_kinds: tuple[LocatorKind, ...]
    limit: Literal[1] = 1

    @field_validator("allowed_locator_kinds")
    @classmethod
    def unique_locator_kinds(cls, value: tuple[LocatorKind, ...]) -> tuple[LocatorKind, ...]:
        if not value or len(value) != len(set(value)):
            raise ValueError("allowed locator kinds must be non-empty and unique")
        return value

    @model_validator(mode="after")
    def validate_manifest_identity(self, info: ValidationInfo) -> EvidenceQuery:
        manifest = info.context.get("manifest") if info.context else None
        if not isinstance(manifest, M4BManifestV1):
            return self
        source = manifest.sources[0]
        if (
            self.organization_id != manifest.organization_id
            or self.source_pack_id != manifest.source_pack_id
            or self.source_pack_version != manifest.source_pack_version
            or self.claim != source.claim
            or self.evidence_role is not source.evidence_role
        ):
            raise ValueError("query identity does not match manifest")
        source_kinds = {locator.kind for locator in source.allowed_locators}
        if not set(self.allowed_locator_kinds).issubset(source_kinds):
            raise ValueError("query locator kinds do not match manifest")
        return self

    @classmethod
    def model_validate_for_manifest(
        cls, value: Any, manifest: M4BManifestV1
    ) -> EvidenceQuery:
        return cls.model_validate(value, context={"manifest": manifest})


class MkeTraceV1(FrozenModel):
    evidence_id: str
    source_id: str
    publication_id: str
    publication_revision: PositiveInt
    run_id: str


class CandidateEvidence(FrozenModel):
    schema_version: Literal["night_voyager.candidate_evidence.v1"]
    source_pack_id: UUID
    source_pack_version: PositiveInt
    source_entry_id: UUID
    claim: str
    evidence_role: EvidenceRole
    locator: PageLocatorV1 | TimestampLocatorV1
    selected_text: SelectedText
    trace: MkeTraceV1
    projection_status: Literal["manifest_mapped"]
    evidence_ref: EvidenceRef


class CandidateStoreNoMatch(FrozenModel):
    schema_version: Literal["night_voyager.candidate_store_no_match.v1"]
    organization_id: UUID
    source_pack_id: UUID
    source_pack_version: PositiveInt
    claim: str
    evidence_role: EvidenceRole
    query_sha256: Sha256
    observation_state: Literal["active"]
    projection_status: Literal["active_store_no_match"]


class MkeFailure(FrozenModel):
    code: MkeFailureCode


class MkeConsumerError(RuntimeError):
    """Typed fail-closed error whose public surface is the closed M4B code set."""

    def __init__(self, code: MkeFailureCode) -> None:
        self.failure = MkeFailure(code=code)
        super().__init__(code)
