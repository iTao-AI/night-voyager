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
    assert (
        "proof DRA surface: offline governed mixed decision closure confirmed"
        in output
    )


@pytest.mark.parametrize(
    ("relative", "required", "message"),
    (
        (
            "docs/how-to/verify-v0.1.1-release.md",
            "git cat-file -t v0.1.1",
            "release how-to contract",
        ),
        (
            "docs/how-to/verify-v0.1.1-release.md",
            "https://github.com/iTao-AI/night-voyager/archive/refs/tags/v0.1.1.tar.gz",
            "release how-to contract",
        ),
        (
            "docs/how-to/verify-v0.1.1-release.md",
            "Do not force-move `v0.1.1`",
            "release how-to contract",
        ),
        (
            "docs/releases/v0.1.1.md",
            "## Risk / Impact",
            "release notes contract",
        ),
        (
            "docs/releases/v0.1.1.md",
            "UNTRUSTED_CANDIDATE",
            "release notes contract",
        ),
        (
            "docs/releases/v0.1.1.md",
            "australia_program_fit",
            "release notes contract",
        ),
        (
            "docs/releases/v0.1.1.md",
            "Live provider proof was not run",
            "release notes contract",
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


def test_release_verifier_rejects_mutated_v0_1_0_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    verifier = load_verifier()
    copy_release_surface(tmp_path)
    target = tmp_path / "docs/releases/v0.1.0.md"
    target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    monkeypatch.setattr(verifier, "ROOT", tmp_path)

    with pytest.raises(SystemExit, match="v0.1.0 historical release document drift"):
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
    assert (
        '"uuid, uuid, text, uuid, timestamp with time zone, text, integer, integer"'
        in source
    )


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
