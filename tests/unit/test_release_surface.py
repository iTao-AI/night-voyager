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
