from __future__ import annotations

import inspect
from pathlib import Path
from uuid import UUID

import pytest

from night_voyager.skills.models import SkillKey, SkillRuntimePin
from night_voyager.skills.registry import (
    SkillRuntimeIncompatibility,
    SkillRuntimeRegistry,
)

RUNTIME_MANIFEST = Path("fixtures/skills/runtime-manifest-v1.json")
RUNTIME_BINDING_SHA256 = "cd897b22d034c7aa1c841a3a5d67b70367a8556009cc665b4a27fa16e8170a29"


def registry() -> SkillRuntimeRegistry:
    return SkillRuntimeRegistry.from_json(RUNTIME_MANIFEST.read_bytes())


def pin(**changes: object) -> SkillRuntimePin:
    payload: dict[str, object] = {
        "skill_definition_id": UUID(int=1),
        "skill_version_id": UUID(int=2),
        "skill_activation_event_id": UUID(int=3),
        "skill_activation_sequence": 1,
        "runtime_binding_sha256": RUNTIME_BINDING_SHA256,
    }
    payload.update(changes)
    return SkillRuntimePin.model_validate(payload)


def test_registry_contains_exact_closed_catalog_and_supported_versions() -> None:
    loaded = registry()
    assert tuple((entry.skill_key.value, entry.version) for entry in loaded.entries) == (
        ("student-profile-intake", "1.0.0"),
        ("study-destination-compare", "1.0.0"),
        ("study-destination-compare", "1.0.1"),
        ("evidence-research", "1.0.0"),
        ("document-evidence-retrieval", "1.0.0"),
        ("family-decision-brief", "1.0.0"),
        ("application-timeline-guard", "1.0.0"),
    )


def test_registry_resolves_version_identity_even_when_binding_digest_is_shared() -> None:
    loaded = registry()
    initial = loaded.get(SkillKey.STUDY_DESTINATION_COMPARE, "1.0.0")
    compatible = loaded.get(SkillKey.STUDY_DESTINATION_COMPARE, "1.0.1")
    assert initial.version == "1.0.0"
    assert compatible.version == "1.0.1"
    assert initial.runtime_binding_sha256 == compatible.runtime_binding_sha256
    assert initial.content_sha256 != compatible.content_sha256
    assert initial.evaluation_dataset_sha256 != compatible.evaluation_dataset_sha256


def test_registry_rejects_unknown_skill_version_pair() -> None:
    with pytest.raises(SkillRuntimeIncompatibility, match="unsupported Skill key/version"):
        registry().get(SkillKey.STUDY_DESTINATION_COMPARE, "9.9.9")


def test_supported_planning_bindings_are_only_the_two_exact_versions() -> None:
    supported = registry().supported_planning_bindings()
    assert tuple((entry.skill_key, entry.version) for entry in supported) == (
        (SkillKey.STUDY_DESTINATION_COMPARE, "1.0.0"),
        (SkillKey.STUDY_DESTINATION_COMPARE, "1.0.1"),
    )


def test_validate_pin_proves_exact_version_operation_and_actual_leaf() -> None:
    loaded = registry()
    entry = loaded.get(SkillKey.STUDY_DESTINATION_COMPARE, "1.0.1")
    bindings = entry.operation_bindings
    assert bindings is not None
    leaf = bindings[0]
    assert (
        loaded.validate_pin(
            pin(),
            SkillKey.STUDY_DESTINATION_COMPARE,
            "1.0.1",
            "generate_planning_run_v1",
            leaf,
        )
        is entry
    )


def test_validate_pin_fails_closed_for_digest_operation_leaf_and_catalog_only() -> None:
    loaded = registry()
    runtime = loaded.get(SkillKey.STUDY_DESTINATION_COMPARE, "1.0.0")
    bindings = runtime.operation_bindings
    assert bindings is not None
    first, second = bindings

    calls = (
        (
            pin(runtime_binding_sha256="f" * 64),
            SkillKey.STUDY_DESTINATION_COMPARE,
            "1.0.0",
            "generate_planning_run_v1",
            first,
        ),
        (
            pin(),
            SkillKey.STUDY_DESTINATION_COMPARE,
            "1.0.0",
            "generate_governed_mixed_planning_run_v1",
            first,
        ),
        (
            pin(),
            SkillKey.STUDY_DESTINATION_COMPARE,
            "1.0.0",
            "generate_planning_run_v1",
            second,
        ),
        (
            pin(),
            SkillKey.STUDENT_PROFILE_INTAKE,
            "1.0.0",
            "generate_planning_run_v1",
            first,
        ),
    )
    for arguments in calls:
        with pytest.raises(SkillRuntimeIncompatibility):
            loaded.validate_pin(*arguments)


def test_packaged_loader_accepts_no_operator_path() -> None:
    assert tuple(inspect.signature(SkillRuntimeRegistry.load_packaged).parameters) == ()
