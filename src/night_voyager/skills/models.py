from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    PositiveInt,
    StringConstraints,
    field_validator,
    model_validator,
)

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
SemanticVersion = Annotated[
    str,
    StringConstraints(pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"),
]
ContractId = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]{0,127}$"),
]


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class SkillKey(StrEnum):
    STUDENT_PROFILE_INTAKE = "student-profile-intake"
    STUDY_DESTINATION_COMPARE = "study-destination-compare"
    EVIDENCE_RESEARCH = "evidence-research"
    DOCUMENT_EVIDENCE_RETRIEVAL = "document-evidence-retrieval"
    FAMILY_DECISION_BRIEF = "family-decision-brief"
    APPLICATION_TIMELINE_GUARD = "application-timeline-guard"


class SkillBindingKind(StrEnum):
    CATALOG_ONLY = "catalog_only"
    PLANNING_RUNTIME = "planning_runtime"


class SkillChangeProvenance(StrEnum):
    BADCASE = "badcase"
    ADVISOR_FEEDBACK = "advisor_feedback"
    EVAL_FAILURE = "eval_failure"
    MAINTAINER_PROPOSAL = "maintainer_proposal"


class SkillEvaluationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class SkillActivationKind(StrEnum):
    SEED = "seed"
    PROMOTE = "promote"
    ROLLBACK = "rollback"


class SkillToolId(StrEnum):
    COLLABORATION_POLICY = "collaboration_policy"
    DECISION_POLICY = "decision_policy"
    DRA_READONLY = "dra_readonly"
    MKE_READONLY = "mke_readonly"
    PLANNING_POLICY = "planning_policy"
    TIMELINE_POLICY = "timeline_policy"


class SkillDataScope(StrEnum):
    ACCEPTED_EVIDENCE = "accepted_evidence"
    ADVISOR_REVIEW = "advisor_review"
    CASE_REVISION = "case_revision"
    FAMILY_DECISION = "family_decision"
    PLANNING_RUN = "planning_run"
    SOURCE_MANIFEST = "source_manifest"


class SkillSideEffectLevel(StrEnum):
    NONE = "none"
    BOUNDED_PRODUCT_WRITE = "bounded_product_write"


class SkillApprovalPolicy(StrEnum):
    ADVISOR_REVIEW_REQUIRED = "advisor_review_required"
    FAMILY_DECISION_REQUIRED = "family_decision_required"


class SkillRuntimePin(FrozenModel):
    skill_definition_id: UUID
    skill_version_id: UUID
    skill_activation_event_id: UUID
    skill_activation_sequence: PositiveInt
    runtime_binding_sha256: Sha256


class SkillLeafBindingV1(FrozenModel):
    operation: Literal[
        "generate_planning_run_v1",
        "generate_governed_mixed_planning_run_v1",
    ]
    adapter_id: Literal["deterministic_planning", "governed_mixed_planning"]
    adapter_version: Literal["m4a-v1", "dra-mixed-v1"]

    @model_validator(mode="after")
    def exact_operation_leaf(self) -> Self:
        expected = {
            "generate_planning_run_v1": ("deterministic_planning", "m4a-v1"),
            "generate_governed_mixed_planning_run_v1": (
                "governed_mixed_planning",
                "dra-mixed-v1",
            ),
        }
        if (self.adapter_id, self.adapter_version) != expected[self.operation]:
            raise ValueError("operation leaf must be an approved exact binding")
        return self


class SkillRuntimeManifestEntryV1(FrozenModel):
    schema_version: Literal[1]
    skill_key: SkillKey
    version: SemanticVersion
    binding_kind: SkillBindingKind
    input_contract_id: ContractId
    input_schema_sha256: Sha256
    output_contract_id: ContractId
    output_schema_sha256: Sha256
    content_sha256: Sha256
    tool_ids: tuple[SkillToolId, ...]
    tool_allowlist_sha256: Sha256
    data_scopes: tuple[SkillDataScope, ...]
    data_scope_sha256: Sha256
    side_effect_level: SkillSideEffectLevel
    approval_policy: SkillApprovalPolicy
    policy_version: ContractId
    policy_sha256: Sha256
    evaluation_dataset_id: ContractId
    evaluation_dataset_version: SemanticVersion
    evaluation_dataset_sha256: Sha256
    executor_id: Literal["planning_adapter_router"] | None = None
    executor_version: Literal["v1"] | None = None
    operation_bindings: tuple[SkillLeafBindingV1, ...] | None = None
    runtime_binding_sha256: Sha256 | None = None

    @field_validator("tool_ids")
    @classmethod
    def sorted_unique_tools(
        cls, value: tuple[SkillToolId, ...]
    ) -> tuple[SkillToolId, ...]:
        values = tuple(item.value for item in value)
        if values != tuple(sorted(values)) or len(values) != len(set(values)):
            raise ValueError("tool IDs must be sorted and unique")
        return value

    @field_validator("data_scopes")
    @classmethod
    def sorted_unique_data_scopes(
        cls, value: tuple[SkillDataScope, ...]
    ) -> tuple[SkillDataScope, ...]:
        values = tuple(item.value for item in value)
        if not values or values != tuple(sorted(values)) or len(values) != len(set(values)):
            raise ValueError("data scopes must be non-empty, sorted, and unique")
        return value

    @model_validator(mode="after")
    def canonical_contract(self) -> Self:
        tools = [item.value for item in self.tool_ids]
        scopes = [item.value for item in self.data_scopes]
        policy = {
            "approval_policy": self.approval_policy.value,
            "policy_version": self.policy_version,
            "side_effect_level": self.side_effect_level.value,
        }
        if self.tool_allowlist_sha256 != canonical_sha256(tools):
            raise ValueError("tool allowlist hash does not match canonical tools")
        if self.data_scope_sha256 != canonical_sha256(scopes):
            raise ValueError("data scope hash does not match canonical scopes")
        if self.policy_sha256 != canonical_sha256(policy):
            raise ValueError("policy hash does not match canonical policy")

        executable_fields = {
            "executor_id",
            "executor_version",
            "operation_bindings",
            "runtime_binding_sha256",
        }
        supplied_executable_fields = executable_fields & self.model_fields_set
        if self.binding_kind is SkillBindingKind.CATALOG_ONLY:
            if supplied_executable_fields:
                raise ValueError("catalog-only entries must omit executable fields")
            return self

        if self.skill_key is not SkillKey.STUDY_DESTINATION_COMPARE:
            raise ValueError("only study-destination-compare is runtime-bound")
        if supplied_executable_fields != executable_fields:
            raise ValueError("planning runtime entries require every executable field")
        if self.executor_id != "planning_adapter_router" or self.executor_version != "v1":
            raise ValueError("planning runtime executor must be planning_adapter_router@v1")

        bindings = self.operation_bindings or ()
        expected_bindings = (
            (
                "generate_planning_run_v1",
                "deterministic_planning",
                "m4a-v1",
            ),
            (
                "generate_governed_mixed_planning_run_v1",
                "governed_mixed_planning",
                "dra-mixed-v1",
            ),
        )
        actual_bindings = tuple(
            (binding.operation, binding.adapter_id, binding.adapter_version)
            for binding in bindings
        )
        if actual_bindings != expected_bindings:
            raise ValueError("planning runtime requires the complete canonical operation map")
        binding_projection = {
            "executor_id": self.executor_id,
            "executor_version": self.executor_version,
            "operation_bindings": [
                binding.model_dump(mode="json") for binding in bindings
            ],
        }
        if self.runtime_binding_sha256 != canonical_sha256(binding_projection):
            raise ValueError("runtime binding hash does not match the complete operation map")
        return self


class SkillRuntimeManifestV1(FrozenModel):
    schema_version: Literal[1]
    manifest_id: Literal["night-voyager.skill-runtime-manifest"]
    manifest_version: Literal["1.0.0"]
    entries: tuple[SkillRuntimeManifestEntryV1, ...]
    manifest_sha256: Sha256

    @model_validator(mode="after")
    def exact_catalog(self) -> Self:
        expected = (
            (SkillKey.STUDENT_PROFILE_INTAKE, "1.0.0"),
            (SkillKey.STUDY_DESTINATION_COMPARE, "1.0.0"),
            (SkillKey.STUDY_DESTINATION_COMPARE, "1.0.1"),
            (SkillKey.EVIDENCE_RESEARCH, "1.0.0"),
            (SkillKey.DOCUMENT_EVIDENCE_RETRIEVAL, "1.0.0"),
            (SkillKey.FAMILY_DECISION_BRIEF, "1.0.0"),
            (SkillKey.APPLICATION_TIMELINE_GUARD, "1.0.0"),
        )
        actual = tuple((entry.skill_key, entry.version) for entry in self.entries)
        if actual != expected:
            raise ValueError("runtime manifest must contain the exact supported key/version set")
        projection = self.model_dump(
            mode="json",
            exclude={"manifest_sha256"},
            exclude_none=True,
        )
        if self.manifest_sha256 != canonical_sha256(projection):
            raise ValueError("runtime manifest hash does not match canonical content")
        return self
