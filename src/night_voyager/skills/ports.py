from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, Literal, Protocol, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    PositiveInt,
    StringConstraints,
    field_validator,
    model_validator,
)

from night_voyager.identity.models import ActorContext
from night_voyager.skills.models import (
    ContractId,
    SemanticVersion,
    Sha256,
    SkillActivationKind,
    SkillApprovalPolicy,
    SkillBindingKind,
    SkillChangeProvenance,
    SkillEvaluationStatus,
    SkillKey,
    SkillRuntimeManifestEntryV1,
    SkillSideEffectLevel,
)

DigestPrefix = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{12}$")]
PlanningOperation = Literal[
    "generate_planning_run_v1",
    "generate_governed_mixed_planning_run_v1",
]
PinStatus = Literal["not_created", "matched", "legacy_unpinned"]


class _StrictPortModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


def _validate_public_text(value: str | None, *, field: str) -> str | None:
    if value is None:
        return None
    size = len(value.encode("utf-8"))
    if not 1 <= size <= 512:
        raise ValueError(f"{field} must contain 1..512 UTF-8 bytes")
    return value


class CreateSkillCandidateCommand(_StrictPortModel):
    schema_version: Literal[1] = 1
    skill_key: SkillKey
    proposed_version: SemanticVersion
    provenance: SkillChangeProvenance
    reason: str
    reference: str | None = None

    @field_validator("reason")
    @classmethod
    def bounded_reason(cls, value: str) -> str:
        return _validate_public_text(value, field="reason") or ""

    @field_validator("reference")
    @classmethod
    def bounded_reference(cls, value: str | None) -> str | None:
        return _validate_public_text(value, field="reference")


class EvaluateSkillCandidateCommand(_StrictPortModel):
    schema_version: Literal[1] = 1
    candidate_id: UUID


class ActivateSkillCandidateCommand(_StrictPortModel):
    schema_version: Literal[1] = 1
    candidate_id: UUID
    expected_active_version: SemanticVersion
    expected_activation_sequence: PositiveInt
    reason: str

    @field_validator("reason")
    @classmethod
    def bounded_reason(cls, value: str) -> str:
        return _validate_public_text(value, field="reason") or ""


class RollbackSkillCommand(_StrictPortModel):
    schema_version: Literal[1] = 1
    skill_key: SkillKey
    target_version: SemanticVersion
    expected_active_version: SemanticVersion
    expected_activation_sequence: PositiveInt
    reason: str

    @field_validator("reason")
    @classmethod
    def bounded_reason(cls, value: str) -> str:
        return _validate_public_text(value, field="reason") or ""


class SkillCatalogSummaryV1(_StrictPortModel):
    schema_version: Literal[1]
    skill_key: SkillKey
    definition_id: UUID
    owner_actor_id: UUID
    binding_kind: SkillBindingKind
    latest_version: SemanticVersion
    active_version: SemanticVersion | None
    activation_sequence: PositiveInt | None

    @model_validator(mode="after")
    def active_identity_is_paired(self) -> Self:
        if (self.active_version is None) != (self.activation_sequence is None):
            raise ValueError("active version and activation sequence must be paired")
        if self.binding_kind is SkillBindingKind.CATALOG_ONLY and self.active_version:
            raise ValueError("catalog-only Skill cannot have an active version")
        return self


class SkillCatalogV1(_StrictPortModel):
    schema_version: Literal[1]
    items: tuple[SkillCatalogSummaryV1, ...]


class SkillVersionSummaryV1(_StrictPortModel):
    schema_version: Literal[1]
    version_id: UUID
    semantic_version: SemanticVersion
    binding_kind: SkillBindingKind
    input_contract_id: ContractId
    input_schema_sha256: Sha256
    output_contract_id: ContractId
    output_schema_sha256: Sha256
    content_sha256: Sha256
    tool_allowlist_sha256: Sha256
    data_scope_sha256: Sha256
    side_effect_level: SkillSideEffectLevel
    approval_policy: SkillApprovalPolicy
    policy_version: ContractId
    policy_sha256: Sha256
    evaluation_dataset_id: ContractId
    evaluation_dataset_version: SemanticVersion
    evaluation_dataset_sha256: Sha256
    runtime_manifest_id: ContractId
    runtime_manifest_version: SemanticVersion
    runtime_manifest_sha256: Sha256
    runtime_binding_sha256: Sha256 | None

    @classmethod
    def from_manifest(
        cls,
        *,
        version_id: UUID,
        entry: SkillRuntimeManifestEntryV1,
        runtime_manifest_id: str,
        runtime_manifest_version: str,
        runtime_manifest_sha256: str,
    ) -> SkillVersionSummaryV1:
        return cls(
            schema_version=1,
            version_id=version_id,
            semantic_version=entry.version,
            binding_kind=entry.binding_kind,
            input_contract_id=entry.input_contract_id,
            input_schema_sha256=entry.input_schema_sha256,
            output_contract_id=entry.output_contract_id,
            output_schema_sha256=entry.output_schema_sha256,
            content_sha256=entry.content_sha256,
            tool_allowlist_sha256=entry.tool_allowlist_sha256,
            data_scope_sha256=entry.data_scope_sha256,
            side_effect_level=entry.side_effect_level,
            approval_policy=entry.approval_policy,
            policy_version=entry.policy_version,
            policy_sha256=entry.policy_sha256,
            evaluation_dataset_id=entry.evaluation_dataset_id,
            evaluation_dataset_version=entry.evaluation_dataset_version,
            evaluation_dataset_sha256=entry.evaluation_dataset_sha256,
            runtime_manifest_id=runtime_manifest_id,
            runtime_manifest_version=runtime_manifest_version,
            runtime_manifest_sha256=runtime_manifest_sha256,
            runtime_binding_sha256=entry.runtime_binding_sha256,
        )


class SkillActivationEventSummaryV1(_StrictPortModel):
    schema_version: Literal[1]
    event_id: UUID
    kind: SkillActivationKind
    activated_version_id: UUID
    previous_version_id: UUID | None
    activation_sequence: PositiveInt
    created_at: datetime


class SkillCatalogDetailV1(_StrictPortModel):
    schema_version: Literal[1]
    skill_key: SkillKey
    definition_id: UUID
    owner_actor_id: UUID
    binding_kind: SkillBindingKind
    versions: tuple[SkillVersionSummaryV1, ...]
    activation_events: tuple[SkillActivationEventSummaryV1, ...]

    @model_validator(mode="after")
    def detail_matches_definition(self) -> Self:
        if not self.versions or any(
            version.binding_kind is not self.binding_kind for version in self.versions
        ):
            raise ValueError("catalog versions must match their definition")
        if self.binding_kind is SkillBindingKind.CATALOG_ONLY and self.activation_events:
            raise ValueError("catalog-only Skill cannot expose activation events")
        return self


class SkillCandidateContextV1(_StrictPortModel):
    schema_version: Literal[1]
    candidate_id: UUID
    skill_key: SkillKey
    binding_kind: SkillBindingKind
    base_version_id: UUID
    proposed_version_id: UUID
    proposed_version: SemanticVersion
    manifest_projection: dict[str, object]
    evaluation_id: UUID | None
    evaluation_status: SkillEvaluationStatus | None

    @model_validator(mode="after")
    def evaluation_identity_is_paired(self) -> Self:
        if (self.evaluation_id is None) != (self.evaluation_status is None):
            raise ValueError("evaluation identity and status must be paired")
        return self


class SkillCandidateCreatedV1(_StrictPortModel):
    schema_version: Literal[1]
    candidate_id: UUID
    replayed: bool


class SkillEvaluationRecordedV1(_StrictPortModel):
    schema_version: Literal[1]
    evaluation_id: UUID
    status: SkillEvaluationStatus
    replayed: bool


class SkillActivationRecordedV1(_StrictPortModel):
    schema_version: Literal[1]
    activation_event_id: UUID
    activation_sequence: PositiveInt
    replayed: bool


class PlanningSkillInspectorV1(_StrictPortModel):
    schema_version: Literal[1]
    case_id: UUID
    operation: PlanningOperation | None
    active_skill_key: Literal[SkillKey.STUDY_DESTINATION_COMPARE]
    active_version: SemanticVersion
    activation_sequence: PositiveInt
    evaluator_id: Literal["night-voyager.deterministic-skill-evaluator"]
    evaluator_version: Literal["v1"]
    evaluation_dataset_id: ContractId
    evaluation_dataset_version: SemanticVersion
    task_request_sha256_prefix: DigestPrefix | None
    version_content_sha256_prefix: DigestPrefix
    runtime_binding_sha256_prefix: DigestPrefix
    adapter_id: Literal["deterministic_planning", "governed_mixed_planning"] | None
    adapter_version: Literal["m4a-v1", "dra-mixed-v1"] | None
    pin_status: PinStatus

    @model_validator(mode="after")
    def exact_pin_projection(self) -> Self:
        if (self.adapter_id is None) != (self.adapter_version is None):
            raise ValueError("adapter identity must be paired")
        if self.pin_status == "not_created":
            if any(
                value is not None
                for value in (
                    self.operation,
                    self.task_request_sha256_prefix,
                    self.adapter_id,
                )
            ):
                raise ValueError("not-created inspector cannot expose task data")
            return self
        if self.operation is None or self.task_request_sha256_prefix is None:
            raise ValueError("persisted task inspector requires task identity")
        if self.pin_status == "matched" and self.adapter_id is None:
            raise ValueError("matched inspector requires actual adapter identity")
        if self.adapter_id is not None:
            expected = {
                "generate_planning_run_v1": ("deterministic_planning", "m4a-v1"),
                "generate_governed_mixed_planning_run_v1": (
                    "governed_mixed_planning",
                    "dra-mixed-v1",
                ),
            }[self.operation]
            if (self.adapter_id, self.adapter_version) != expected:
                raise ValueError("inspector adapter does not match planning operation")
        return self


class SkillRepository(Protocol):
    async def list_catalog(self, context: ActorContext) -> SkillCatalogV1: ...

    async def get_catalog_item(
        self, context: ActorContext, skill_key: SkillKey
    ) -> SkillCatalogDetailV1: ...

    async def create_candidate(
        self,
        context: ActorContext,
        command: CreateSkillCandidateCommand,
        candidate_id: UUID,
        manifest_projection: Mapping[str, object],
        request_sha256: str,
        idempotency_key: str,
    ) -> SkillCandidateCreatedV1: ...

    async def load_candidate_context(
        self, context: ActorContext, candidate_id: UUID
    ) -> SkillCandidateContextV1: ...

    async def record_evaluation(
        self,
        context: ActorContext,
        command: EvaluateSkillCandidateCommand,
        evaluation_id: UUID,
        result_projection: Mapping[str, object],
        request_sha256: str,
        idempotency_key: str,
    ) -> SkillEvaluationRecordedV1: ...

    async def activate_candidate(
        self,
        context: ActorContext,
        command: ActivateSkillCandidateCommand,
        activation_event_id: UUID,
        manifest_projection: Mapping[str, object],
        request_sha256: str,
        idempotency_key: str,
    ) -> SkillActivationRecordedV1: ...

    async def rollback_skill(
        self,
        context: ActorContext,
        command: RollbackSkillCommand,
        activation_event_id: UUID,
        manifest_projection: Mapping[str, object],
        request_sha256: str,
        idempotency_key: str,
    ) -> SkillActivationRecordedV1: ...

    async def inspect_planning_skill(
        self, context: ActorContext, case_id: UUID
    ) -> PlanningSkillInspectorV1: ...


__all__ = [
    "ActivateSkillCandidateCommand",
    "CreateSkillCandidateCommand",
    "EvaluateSkillCandidateCommand",
    "PlanningSkillInspectorV1",
    "RollbackSkillCommand",
    "SkillActivationEventSummaryV1",
    "SkillActivationRecordedV1",
    "SkillCandidateContextV1",
    "SkillCandidateCreatedV1",
    "SkillCatalogDetailV1",
    "SkillCatalogSummaryV1",
    "SkillCatalogV1",
    "SkillEvaluationRecordedV1",
    "SkillRepository",
    "SkillVersionSummaryV1",
]
