from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_verifier():
    path = ROOT / "scripts/verify_release.py"
    spec = importlib.util.spec_from_file_location("verify_release", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def copy_release_surface(destination: Path) -> None:
    for relative in (
        "pyproject.toml",
        "README.md",
        "README_CN.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "docs/README.md",
        "docs/releases/v0.1.0.md",
        "docs/how-to/verify-v0.1.0-release.md",
        "docs/releases/v0.1.1.md",
        "docs/how-to/verify-v0.1.1-release.md",
    ):
        source = ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def test_release_verifier_checks_the_public_v0_1_1_surface(
    capsys: pytest.CaptureFixture[str],
) -> None:
    verifier = load_verifier()

    verifier.verify_release_surface()

    output = capsys.readouterr().out
    assert "proof release surface: v0.1.1 local synthetic portfolio contract confirmed" in output


def test_release_verifier_checks_the_governed_mixed_planning_surface(
    capsys: pytest.CaptureFixture[str],
) -> None:
    verifier = load_verifier()

    verifier.verify_dra_surface()

    output = capsys.readouterr().out
    assert "proof DRA surface: offline governed mixed decision closure confirmed" in output


@pytest.mark.parametrize(
    ("relative", "required", "message"),
    (
        (
            "docs/how-to/verify-v0.1.1-release.md",
            "git cat-file -t v0.1.1",
            "published release document drift",
        ),
        (
            "docs/how-to/verify-v0.1.1-release.md",
            "https://github.com/iTao-AI/night-voyager/archive/refs/tags/v0.1.1.tar.gz",
            "published release document drift",
        ),
        (
            "docs/how-to/verify-v0.1.1-release.md",
            "Do not force-move `v0.1.1`",
            "published release document drift",
        ),
        (
            "docs/releases/v0.1.1.md",
            "## Risk / Impact",
            "published release document drift",
        ),
        (
            "docs/releases/v0.1.1.md",
            "UNTRUSTED_CANDIDATE",
            "published release document drift",
        ),
        (
            "docs/releases/v0.1.1.md",
            "australia_program_fit",
            "published release document drift",
        ),
        (
            "docs/releases/v0.1.1.md",
            "Live provider proof was not run",
            "published release document drift",
        ),
    ),
)
def test_release_verifier_rejects_missing_publication_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative: str,
    required: str,
    message: str,
) -> None:
    verifier = load_verifier()
    copy_release_surface(tmp_path)
    target = tmp_path / relative
    source = target.read_text(encoding="utf-8")
    assert required in source
    target.write_text(source.replace(required, "", 1), encoding="utf-8")
    monkeypatch.setattr(verifier, "ROOT", tmp_path)

    with pytest.raises(SystemExit, match=message):
        verifier.verify_release_surface()


@pytest.mark.parametrize(
    "relative",
    (
        "docs/releases/v0.1.0.md",
        "docs/how-to/verify-v0.1.0-release.md",
        "docs/releases/v0.1.1.md",
        "docs/how-to/verify-v0.1.1-release.md",
    ),
)
def test_release_verifier_rejects_mutated_published_release_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative: str
) -> None:
    verifier = load_verifier()
    copy_release_surface(tmp_path)
    target = tmp_path / relative
    target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    monkeypatch.setattr(verifier, "ROOT", tmp_path)

    with pytest.raises(SystemExit, match="published release document drift"):
        verifier.verify_release_surface()


def test_release_verifier_registers_collaboration_authority_without_version_change() -> None:
    verifier = load_verifier()
    assert verifier.VERSION == "0.1.1"
    assert {
        "collaboration_threads",
        "message_events",
        "memory_candidates",
        "memory_candidate_verifications",
        "confirmed_facts",
        "case_revision_confirmed_fact_refs",
    } == verifier.COLLABORATION_TABLES
    assert {
        "create_collaboration_thread",
        "append_collaboration_message",
        "propose_memory_candidate",
        "verify_memory_candidate",
        "read_collaboration_thread",
        "read_collaboration_messages",
        "read_memory_candidates",
        "read_confirmed_facts",
    } == verifier.COLLABORATION_API_FUNCTIONS
    source = (ROOT / "scripts/verify_release.py").read_text(encoding="utf-8")
    assert '"read_confirmed_facts": (' in source
    assert '"uuid, uuid, text, uuid, integer, text, integer, integer"' in source


def test_release_verifier_checks_the_collaboration_authority_surface(
    capsys: pytest.CaptureFixture[str],
) -> None:
    verifier = load_verifier()

    verifier.verify_collaboration_surface()

    output = capsys.readouterr().out
    assert (
        "proof collaboration surface: governed conversation and memory authority confirmed"
        in output
    )


def test_release_verifier_freezes_the_cross_runtime_lock_order() -> None:
    source = (ROOT / "scripts/verify_release.py").read_text(encoding="utf-8")
    assert '"CREATE OR REPLACE FUNCTION app.persist_planning_result("' in source
    assert '"LEGACY_PLANNING_PERSISTENCE_SQL"' in source
    assert '"Case FOR UPDATE -> superseded PlanningRun update"' in source
    assert '"planning result lock order drift"' in source


def test_release_verifier_registers_skill_authority_without_version_change() -> None:
    verifier = load_verifier()

    assert verifier.VERSION == "0.1.1"
    assert verifier.LOCKED_FASTAPI_VERSION == "0.139.2"
    assert {
        "skill_definitions",
        "skill_versions",
        "skill_change_candidates",
        "skill_evaluation_results",
        "skill_activation_events",
    } == verifier.SKILL_TABLES
    assert {
        "create_skill_change_candidate",
        "record_skill_candidate_evaluation",
        "promote_skill_change_candidate",
        "rollback_skill_activation",
        "list_skill_catalog",
        "get_skill_catalog_item",
        "load_skill_candidate_context",
        "inspect_planning_skill",
    } == verifier.SKILL_API_FUNCTIONS
    assert {
        "load_agent_task_skill_pin",
        "load_persisted_synthetic_planning_snapshot",
    } == verifier.SKILL_WORKER_FUNCTIONS


def test_release_verifier_checks_the_versioned_skill_surface(
    capsys: pytest.CaptureFixture[str],
) -> None:
    verifier = load_verifier()

    verifier.verify_skill_surface()

    output = capsys.readouterr().out
    assert (
        "proof Skill surface: six governed definitions, packaged runtime pins, "
        "and deferred PR C confirmed"
    ) in output


def test_release_verifier_installed_wheel_loads_exact_skill_manifests() -> None:
    source = (ROOT / "scripts/verify_release.py").read_text(encoding="utf-8")

    for token in (
        "SkillRuntimeRegistry.load_packaged()",
        "SkillEvaluator.load_packaged(registry)",
        "len(registry.entries) == 7",
        "len(evaluator.manifest.datasets) == 7",
    ):
        assert token in source
