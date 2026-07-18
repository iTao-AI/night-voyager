from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from night_voyager.skills.models import (
    SkillActivationKind,
    SkillBindingKind,
    SkillChangeProvenance,
    SkillEvaluationStatus,
    SkillKey,
    SkillLeafBindingV1,
    SkillRuntimeManifestEntryV1,
    SkillRuntimePin,
    canonical_sha256,
)

RUNTIME_BINDING_SHA256 = "cd897b22d034c7aa1c841a3a5d67b70367a8556009cc665b4a27fa16e8170a29"


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def runtime_entry(**changes: object) -> dict[str, Any]:
    tools = ["planning_policy"]
    scopes = ["accepted_evidence", "case_revision"]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "skill_key": "study-destination-compare",
        "version": "1.0.0",
        "binding_kind": "planning_runtime",
        "input_contract_id": "night-voyager.planning-input.v1",
        "input_schema_sha256": "1" * 64,
        "output_contract_id": "night-voyager.planning-result.v1",
        "output_schema_sha256": "2" * 64,
        "content_sha256": "3" * 64,
        "tool_ids": tools,
        "tool_allowlist_sha256": _digest(tools),
        "data_scopes": scopes,
        "data_scope_sha256": _digest(scopes),
        "side_effect_level": "bounded_product_write",
        "approval_policy": "advisor_review_required",
        "policy_version": "m3a-policy-v1",
        "policy_sha256": _digest(
            {
                "approval_policy": "advisor_review_required",
                "policy_version": "m3a-policy-v1",
                "side_effect_level": "bounded_product_write",
            }
        ),
        "evaluation_dataset_id": "night-voyager.study-destination-compare.eval",
        "evaluation_dataset_version": "1.0.0",
        "evaluation_dataset_sha256": "4" * 64,
        "executor_id": "planning_adapter_router",
        "executor_version": "v1",
        "operation_bindings": [
            {
                "operation": "generate_planning_run_v1",
                "adapter_id": "deterministic_planning",
                "adapter_version": "m4a-v1",
            },
            {
                "operation": "generate_governed_mixed_planning_run_v1",
                "adapter_id": "governed_mixed_planning",
                "adapter_version": "dra-mixed-v1",
            },
        ],
        "runtime_binding_sha256": RUNTIME_BINDING_SHA256,
    }
    payload.update(changes)
    return payload


def catalog_entry(**changes: object) -> dict[str, Any]:
    tools = ["collaboration_policy"]
    scopes = ["case_revision"]
    payload = runtime_entry(
        skill_key="student-profile-intake",
        binding_kind="catalog_only",
        input_contract_id="night-voyager.profile-fact-proposal.v1",
        output_contract_id="night-voyager.confirmed-fact.v1",
        tool_ids=tools,
        tool_allowlist_sha256=_digest(tools),
        data_scopes=scopes,
        data_scope_sha256=_digest(scopes),
        side_effect_level="none",
        approval_policy="advisor_review_required",
        policy_version="collaboration-fact-policy-v1",
        policy_sha256=_digest(
            {
                "approval_policy": "advisor_review_required",
                "policy_version": "collaboration-fact-policy-v1",
                "side_effect_level": "none",
            }
        ),
        evaluation_dataset_id="night-voyager.student-profile-intake.eval",
    )
    for field in (
        "executor_id",
        "executor_version",
        "operation_bindings",
        "runtime_binding_sha256",
    ):
        payload.pop(field)
    payload.update(changes)
    return payload


def validate_entry(payload: dict[str, Any]) -> SkillRuntimeManifestEntryV1:
    return SkillRuntimeManifestEntryV1.model_validate_json(json.dumps(payload))


def test_closed_catalog_and_governance_vocabularies_are_exact() -> None:
    assert tuple(item.value for item in SkillKey) == (
        "student-profile-intake",
        "study-destination-compare",
        "evidence-research",
        "document-evidence-retrieval",
        "family-decision-brief",
        "application-timeline-guard",
    )
    assert tuple(item.value for item in SkillBindingKind) == (
        "catalog_only",
        "planning_runtime",
    )
    assert tuple(item.value for item in SkillChangeProvenance) == (
        "badcase",
        "advisor_feedback",
        "eval_failure",
        "maintainer_proposal",
    )
    assert tuple(item.value for item in SkillEvaluationStatus) == ("passed", "failed")
    assert tuple(item.value for item in SkillActivationKind) == ("seed", "promote", "rollback")


@pytest.mark.parametrize("value", ["1", "1.0", "01.0.0", "1.0.0-rc1", " 1.0.0"])
def test_semantic_version_is_exact_major_minor_patch(value: str) -> None:
    with pytest.raises(ValidationError):
        validate_entry(runtime_entry(version=value))


@pytest.mark.parametrize("field", ["input_schema_sha256", "content_sha256"])
@pytest.mark.parametrize("value", ["A" * 64, "a" * 63, "sha256:" + "a" * 64])
def test_sha256_is_exact_lowercase_hex(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        validate_entry(runtime_entry(**{field: value}))


def test_models_are_strict_frozen_and_forbid_extra_fields() -> None:
    entry = validate_entry(runtime_entry())
    with pytest.raises(ValidationError):
        entry.version = "1.0.1"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        validate_entry(runtime_entry(unexpected="authority"))
    with pytest.raises(ValidationError):
        SkillRuntimePin.model_validate(
            {
                "skill_definition_id": str(UUID(int=1)),
                "skill_version_id": str(UUID(int=2)),
                "skill_activation_event_id": str(UUID(int=3)),
                "skill_activation_sequence": 1,
                "runtime_binding_sha256": RUNTIME_BINDING_SHA256,
            }
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("tool_ids", ["planning_policy", "planning_policy"]),
        ("tool_ids", ["planning_policy", "collaboration_policy"]),
        ("tool_ids", ["arbitrary_shell"]),
        ("data_scopes", ["case_revision", "accepted_evidence"]),
        ("data_scopes", ["case_revision", "case_revision"]),
        ("data_scopes", ["browser_session"]),
    ],
)
def test_tool_and_data_scope_allowlists_are_closed_sorted_and_unique(
    field: str, value: list[str]
) -> None:
    with pytest.raises(ValidationError):
        validate_entry(runtime_entry(**{field: value}))


def test_catalog_only_entry_requires_executable_fields_to_be_absent() -> None:
    entry = validate_entry(catalog_entry())
    projection = entry.model_dump(mode="json", exclude_none=True)
    assert "executor_id" not in projection
    assert "executor_version" not in projection
    assert "operation_bindings" not in projection
    assert "runtime_binding_sha256" not in projection

    executable_values: tuple[tuple[str, object], ...] = (
        ("executor_id", "planning_adapter_router"),
        ("executor_version", "v1"),
        ("operation_bindings", []),
        ("runtime_binding_sha256", None),
    )
    for field, value in executable_values:
        with pytest.raises(ValidationError):
            validate_entry(catalog_entry(**{field: value}))


def test_planning_runtime_requires_the_complete_canonical_operation_map() -> None:
    entry = validate_entry(runtime_entry())
    assert entry.runtime_binding_sha256 == RUNTIME_BINDING_SHA256
    assert tuple(binding.operation for binding in entry.operation_bindings or ()) == (
        "generate_planning_run_v1",
        "generate_governed_mixed_planning_run_v1",
    )

    for bindings in (
        runtime_entry()["operation_bindings"][:1],
        list(reversed(runtime_entry()["operation_bindings"])),
    ):
        with pytest.raises(ValidationError):
            validate_entry(runtime_entry(operation_bindings=bindings))


def test_leaf_binding_rejects_noncanonical_operation_adapter_pair() -> None:
    with pytest.raises(ValidationError):
        SkillLeafBindingV1.model_validate_json(
            json.dumps(
                {
                    "operation": "generate_planning_run_v1",
                    "adapter_id": "governed_mixed_planning",
                    "adapter_version": "dra-mixed-v1",
                }
            )
        )


def test_canonical_hash_is_stable_and_binds_content() -> None:
    assert canonical_sha256({"b": 2, "a": 1}) == (
        "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777"
    )
    assert canonical_sha256({"a": 1, "b": 2}) == canonical_sha256({"b": 2, "a": 1})
    assert canonical_sha256({"a": 1, "b": 3}) != canonical_sha256({"b": 2, "a": 1})


def test_runtime_pin_requires_positive_sequence_and_is_frozen() -> None:
    pin = SkillRuntimePin(
        skill_definition_id=UUID(int=1),
        skill_version_id=UUID(int=2),
        skill_activation_event_id=UUID(int=3),
        skill_activation_sequence=1,
        runtime_binding_sha256=RUNTIME_BINDING_SHA256,
    )
    with pytest.raises(ValidationError):
        pin.skill_activation_sequence = 2  # type: ignore[misc]
    with pytest.raises(ValidationError):
        SkillRuntimePin(
            skill_definition_id=UUID(int=1),
            skill_version_id=UUID(int=2),
            skill_activation_event_id=UUID(int=3),
            skill_activation_sequence=0,
            runtime_binding_sha256=RUNTIME_BINDING_SHA256,
        )
