from __future__ import annotations

import inspect
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from night_voyager.skills.evaluation import (
    SkillEvaluationIncompatibility,
    SkillEvaluationManifestV1,
    SkillEvaluator,
)
from night_voyager.skills.models import (
    SkillEvaluationStatus,
    SkillKey,
    canonical_sha256,
)
from night_voyager.skills.registry import SkillRuntimeRegistry

RUNTIME_MANIFEST = Path("fixtures/skills/runtime-manifest-v1.json")
EVAL_MANIFEST = Path("fixtures/skills/eval-manifest-v1.json")

EXPECTED_OUTPUT_SHA256 = {
    ("student-profile-intake", "1.0.0"): (
        "5cd49da59fd1a4cac81903be2ffc68126e9613f8cb1cc93c61166c5d53520bf7"
    ),
    ("study-destination-compare", "1.0.0"): (
        "648c11216bb16bd89de218b1bf52a66eb977de4200d27b68d951c66f16200115"
    ),
    ("study-destination-compare", "1.0.1"): (
        "b89b005d35cd6b78506a68cd7352766ab12d8620c6def1db989f8015ffe76a6b"
    ),
    ("evidence-research", "1.0.0"): (
        "2dfee7c078610d45fa090dccfacd143d637a0ec08d90f83d64eedfbe1c8e608b"
    ),
    ("document-evidence-retrieval", "1.0.0"): (
        "4eb45a6415d180d3f132f9d20c573aeb0ce36e4b0586bd807613a5c07d524d22"
    ),
    ("family-decision-brief", "1.0.0"): (
        "f7bee5a60553ab7aa292aa9748e28908bcbedcdbe2034b6f34819c35dd21bcf7"
    ),
    ("application-timeline-guard", "1.0.0"): (
        "6197a698b8f4b1f0aa3b24237f8ac9161357d11bf40e9f44b594cd453fa22821"
    ),
}

EXPECTED_ASSERTION_IDS = {
    ("student-profile-intake", "1.0.0"): (
        "student-profile-intake.cross-role-fact-rejected",
        "student-profile-intake.unconfirmed-remains-unconfirmed",
        "student-profile-intake.unsafe-value-rejected",
    ),
    ("study-destination-compare", "1.0.0"): (
        "study-destination-compare.australia-conditional",
        "study-destination-compare.baseline-hash-drift-failed",
        "study-destination-compare.budget-refusal-blocked",
        "study-destination-compare.malaysia-blocked",
    ),
    ("study-destination-compare", "1.0.1"): (
        "study-destination-compare.australia-conditional",
        "study-destination-compare.baseline-hash-drift-failed",
        "study-destination-compare.budget-refusal-blocked",
        "study-destination-compare.duplicate-claim-failed",
        "study-destination-compare.malaysia-blocked",
        "study-destination-compare.untrusted-evidence-failed",
    ),
    ("evidence-research", "1.0.0"): (
        "evidence-research.fallback-remains-untrusted",
        "evidence-research.terminal-invalid-not-promotable",
    ),
    ("document-evidence-retrieval", "1.0.0"): (
        "document-evidence-retrieval.active-no-match-not-evidence",
        "document-evidence-retrieval.no-match-not-sufficient",
    ),
    ("family-decision-brief", "1.0.0"): (
        "family-decision-brief.blocked-route-ineligible",
        "family-decision-brief.unreviewed-run-rejected",
    ),
    ("application-timeline-guard", "1.0.0"): (
        "application-timeline-guard.dates-deterministic",
        "application-timeline-guard.no-decision-no-timeline",
    ),
}


def runtime_registry() -> SkillRuntimeRegistry:
    return SkillRuntimeRegistry.from_json(RUNTIME_MANIFEST.read_bytes())


def evaluator(
    payload: dict[str, Any] | None = None,
    registry: SkillRuntimeRegistry | None = None,
) -> SkillEvaluator:
    source = EVAL_MANIFEST.read_bytes() if payload is None else json.dumps(payload).encode()
    return SkillEvaluator.from_json(source, registry or runtime_registry())


def eval_payload() -> dict[str, Any]:
    return json.loads(EVAL_MANIFEST.read_text(encoding="utf-8"))


def _rehash_dataset(dataset: dict[str, Any]) -> None:
    projection = {
        "skill_key": dataset["skill_key"],
        "version": dataset["version"],
        "dataset_id": dataset["dataset_id"],
        "dataset_version": dataset["dataset_version"],
        "assertions": dataset["assertions"],
    }
    dataset["dataset_sha256"] = canonical_sha256(projection)


def _rehash_manifest(payload: dict[str, Any]) -> None:
    projection = {key: value for key, value in payload.items() if key != "manifest_sha256"}
    payload["manifest_sha256"] = canonical_sha256(projection)


def _assertion_id(item: dict[str, Any]) -> str:
    return cast(str, item["assertion_id"])


def _runtime_registry_with_dataset_hash(
    skill_key: str,
    version: str,
    dataset_sha256: str,
) -> SkillRuntimeRegistry:
    payload = json.loads(RUNTIME_MANIFEST.read_text(encoding="utf-8"))
    for entry in payload["entries"]:
        if entry["skill_key"] == skill_key and entry["version"] == version:
            entry["evaluation_dataset_sha256"] = dataset_sha256
            break
    projection = {key: value for key, value in payload.items() if key != "manifest_sha256"}
    payload["manifest_sha256"] = canonical_sha256(projection)
    return SkillRuntimeRegistry.from_json(json.dumps(payload))


def test_eval_manifest_freezes_exact_datasets_and_stable_assertion_ids() -> None:
    manifest = SkillEvaluationManifestV1.model_validate_json(EVAL_MANIFEST.read_bytes())
    assert tuple((item.skill_key.value, item.version) for item in manifest.datasets) == tuple(
        EXPECTED_ASSERTION_IDS
    )
    assert {item.skill_key for item in manifest.datasets} == set(SkillKey)
    assert {
        (item.skill_key.value, item.version): tuple(
            assertion.assertion_id for assertion in item.assertions
        )
        for item in manifest.datasets
    } == EXPECTED_ASSERTION_IDS


def test_evaluator_runs_all_six_skills_with_stable_complete_output() -> None:
    loaded = evaluator()
    for identity, expected_output_sha256 in EXPECTED_OUTPUT_SHA256.items():
        result = loaded.evaluate(*identity)
        assert result.status is SkillEvaluationStatus.PASSED
        assert result.failed_assertion_ids == ()
        assert tuple(item.assertion_id for item in result.assertions) == (
            EXPECTED_ASSERTION_IDS[identity]
        )
        assert all(item.passed for item in result.assertions)
        assert result.output_sha256 == expected_output_sha256


def test_compatible_1_0_1_adds_negative_assertions_without_changing_baseline() -> None:
    loaded = evaluator()
    initial = loaded.evaluate(SkillKey.STUDY_DESTINATION_COMPARE, "1.0.0")
    compatible = loaded.evaluate(SkillKey.STUDY_DESTINATION_COMPARE, "1.0.1")
    initial_projection = {
        item.assertion_id: item.observed_sha256 for item in initial.assertions
    }
    compatible_projection = {
        item.assertion_id: item.observed_sha256 for item in compatible.assertions
    }
    assert set(compatible_projection) - set(initial_projection) == {
        "study-destination-compare.duplicate-claim-failed",
        "study-destination-compare.untrusted-evidence-failed",
    }
    assert {
        key: compatible_projection[key] for key in initial_projection
    } == initial_projection


def test_expected_output_mutation_is_computed_as_a_failed_evaluation() -> None:
    payload = eval_payload()
    dataset = payload["datasets"][0]
    assertion = dataset["assertions"][0]
    assertion["expected_sha256"] = "f" * 64
    _rehash_dataset(dataset)
    _rehash_manifest(payload)

    registry = _runtime_registry_with_dataset_hash(
        "student-profile-intake",
        "1.0.0",
        dataset["dataset_sha256"],
    )
    result = evaluator(payload, registry).evaluate("student-profile-intake", "1.0.0")
    assert result.status is SkillEvaluationStatus.FAILED
    assert result.failed_assertion_ids == (
        "student-profile-intake.cross-role-fact-rejected",
    )
    assert result.assertions[0].passed is False
    assert result.output_sha256 != EXPECTED_OUTPUT_SHA256[("student-profile-intake", "1.0.0")]


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate"])
def test_missing_extra_or_duplicate_assertion_ids_are_rejected(mutation: str) -> None:
    payload = eval_payload()
    dataset = payload["datasets"][0]
    if mutation == "missing":
        dataset["assertions"].pop()
    elif mutation == "extra":
        assertions = cast(list[dict[str, Any]], dataset["assertions"])
        assertions.append(
            {
                "assertion_id": "student-profile-intake.forged-authority",
                "expected_sha256": "f" * 64,
            }
        )
        assertions.sort(key=_assertion_id)
    else:
        dataset["assertions"].append(deepcopy(dataset["assertions"][0]))
    _rehash_dataset(dataset)
    _rehash_manifest(payload)

    with pytest.raises(ValidationError):
        SkillEvaluationManifestV1.model_validate_json(json.dumps(payload))


def test_forged_status_and_dataset_hash_drift_are_rejected() -> None:
    forged = eval_payload()
    forged["datasets"][0]["status"] = "passed"
    _rehash_manifest(forged)
    with pytest.raises(ValidationError):
        SkillEvaluationManifestV1.model_validate_json(json.dumps(forged))

    drifted = eval_payload()
    drifted["datasets"][0]["assertions"][0]["expected_sha256"] = "f" * 64
    _rehash_manifest(drifted)
    with pytest.raises(ValidationError, match="dataset hash"):
        SkillEvaluationManifestV1.model_validate_json(json.dumps(drifted))


def test_unknown_skill_or_version_is_rejected() -> None:
    loaded = evaluator()
    with pytest.raises(SkillEvaluationIncompatibility, match="unsupported evaluation"):
        loaded.evaluate(SkillKey.STUDY_DESTINATION_COMPARE, "9.9.9")


def test_evaluation_models_are_strict_frozen_and_forbid_extra_fields() -> None:
    result = evaluator().evaluate(SkillKey.STUDENT_PROFILE_INTAKE, "1.0.0")
    with pytest.raises(ValidationError):
        result.status = SkillEvaluationStatus.FAILED  # type: ignore[misc]
    payload = eval_payload()
    payload["unexpected"] = "browser authority"
    with pytest.raises(ValidationError):
        SkillEvaluationManifestV1.model_validate_json(json.dumps(payload))


def test_evaluator_has_no_external_or_browser_authority_and_no_repo_fallback() -> None:
    module = inspect.getmodule(SkillEvaluator)
    assert module is not None
    source = inspect.getsource(module)
    loader = inspect.getsource(SkillEvaluator.load_packaged)
    for forbidden in (
        "httpx",
        "openai",
        "sqlalchemy",
        "subprocess",
        "pytest.main",
        "os.system",
        "fixtures/skills",
        "from pathlib",
    ):
        assert forbidden not in source
    assert 'resources.files("night_voyager.skills")' in loader
    assert '.joinpath("data", "eval-manifest-v1.json")' in loader
    assert not Path("src/night_voyager/skills/data/eval-manifest-v1.json").exists()
