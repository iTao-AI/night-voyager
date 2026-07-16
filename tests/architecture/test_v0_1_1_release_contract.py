from __future__ import annotations

import json
import tomllib
from pathlib import Path

from night_voyager.api import create_app

ROOT = Path(__file__).resolve().parents[2]
VERSION = "0.1.1"
DESCRIPTION = "Evidence-grounded advisor-to-family decision workflow with durable Agent tasks"


def test_current_release_identity_is_v0_1_1_without_dependency_drift() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    uv_lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    package = json.loads((ROOT / "web/package.json").read_text(encoding="utf-8"))
    package_lock = json.loads(
        (ROOT / "web/package-lock.json").read_text(encoding="utf-8")
    )
    locked_project = next(
        item for item in uv_lock["package"] if item.get("name") == "night-voyager"
    )

    assert pyproject["project"]["version"] == VERSION
    assert pyproject["project"]["description"] == DESCRIPTION
    assert locked_project["version"] == VERSION
    assert package["version"] == VERSION
    assert package_lock["version"] == VERSION
    assert package_lock["packages"][""]["version"] == VERSION
    assert create_app().version == VERSION
    verifier = (ROOT / "scripts/verify_release.py").read_text(encoding="utf-8")
    assert f'VERSION = "{VERSION}"' in verifier
    assert 'f"docs/releases/v{VERSION}.md"' in verifier
    assert 'f"docs/how-to/verify-v{VERSION}-release.md"' in verifier


def test_current_release_entries_point_to_v0_1_1_and_keep_v0_1_0_as_history() -> None:
    current_entries = {
        "README.md": (
            "docs/releases/v0.1.1.md",
            "docs/how-to/verify-v0.1.1-release.md",
            "local synthetic portfolio release",
        ),
        "README_CN.md": (
            "docs/releases/v0.1.1.md",
            "docs/how-to/verify-v0.1.1-release.md",
            "local synthetic portfolio release",
        ),
        "docs/README.md": (
            "releases/v0.1.1.md",
            "how-to/verify-v0.1.1-release.md",
            "local synthetic portfolio release",
        ),
        "CONTRIBUTING.md": ("v0.1.1", "local synthetic portfolio release"),
        "SECURITY.md": ("v0.1.1", "local synthetic portfolio release"),
    }
    for relative, tokens in current_entries.items():
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert all(token in source for token in tokens), relative

    for relative in ("README.md", "README_CN.md", "docs/README.md"):
        assert "v0.1.0" in (ROOT / relative).read_text(encoding="utf-8"), relative


def test_v0_1_1_release_notes_freeze_the_governed_dra_release_claim() -> None:
    release = (ROOT / "docs/releases/v0.1.1.md").read_text(encoding="utf-8")
    headings = (
        "## Summary",
        "## Completion",
        "## Verification",
        "## Scope",
        "## Risk / Impact",
        "## Documentation impact",
    )
    assert [release.index(heading) for heading in headings] == sorted(
        release.index(heading) for heading in headings
    )
    for token in (
        "local synthetic portfolio release",
        "deterministic offline governed DRA closure",
        "UNTRUSTED_CANDIDATE",
        "atomic authority gate",
        "australia_program_fit -> program_fit -> externally_verified",
        "synthetic baseline",
        "cost/FX",
        "ranking",
        "pinned current Case revision",
        "Live provider proof was not run",
        "local synthetic walkthrough",
        "GitHub-generated source archive",
    ):
        assert token in release


def test_v0_1_1_verification_guide_defines_publication_and_archive_gates() -> None:
    how_to = (ROOT / "docs/how-to/verify-v0.1.1-release.md").read_text(
        encoding="utf-8"
    )
    for token in (
        "local synthetic portfolio release",
        "git fetch origin --tags --prune",
        "git status --short --branch",
        "git rev-parse HEAD",
        "git rev-parse origin/main",
        "git describe --tags --exact-match HEAD",
        "git cat-file -t v0.1.1",
        "git rev-parse v0.1.1^{tag}",
        "git rev-parse v0.1.1^{commit}",
        'curl --fail --location --output "$archive"',
        "https://github.com/iTao-AI/night-voyager/archive/refs/tags/v0.1.1.tar.gz",
        'wc -c "$archive"',
        'shasum -a 256 "$archive"',
        'tar -xzf "$archive" -C "$tmp_dir"',
        'cd "$tmp_dir/night-voyager-0.1.1"',
        "make doctor",
        "make dra-check",
        "make db-check",
        "make check",
        "make proof",
        "make compose-proof",
        "make down",
        "docker compose ps --all",
        "Never move the tag after publication",
        "Use the extracted source archive",
        "Do not force-move `v0.1.1`",
        "normal pull request",
    ):
        assert token in how_to
