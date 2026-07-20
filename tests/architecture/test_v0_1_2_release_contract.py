from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path

from night_voyager.api import create_app

ROOT = Path(__file__).resolve().parents[2]
VERSION = "0.1.2"
DESCRIPTION = "Evidence-grounded advisor-to-family decision workflow with durable Agent tasks"
HISTORICAL_RELEASE_DIGESTS = {
    "docs/releases/v0.1.0.md": "a3251cdb572b4d982f989917f7e44d111cf887cf7fc8d75629cdd69c393d3a93",
    "docs/how-to/verify-v0.1.0-release.md": (
        "b65e18c6dc0e193e2de445ad41930230846bea3abfe43304f58f4cd133275ea3"
    ),
    "docs/releases/v0.1.1.md": "0e7724ca54a9d9c8b3ed403f6bbbd86c04dde3ee79e0644e95ee3ccf90513ab2",
    "docs/how-to/verify-v0.1.1-release.md": (
        "3e20b41e3256c275d557e6165e7e224a95a3a642286f6993da209a51aebe8f16"
    ),
}


def test_current_release_identity_is_v0_1_2_without_dependency_drift() -> None:
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


def test_current_release_entries_point_to_v0_1_2_and_keep_history() -> None:
    current_entries = {
        "README.md": (
            "docs/releases/v0.1.2.md",
            "docs/how-to/verify-v0.1.2-release.md",
            "local synthetic portfolio release",
        ),
        "README_CN.md": (
            "docs/releases/v0.1.2.md",
            "docs/how-to/verify-v0.1.2-release.md",
            "local synthetic portfolio release",
        ),
        "docs/README.md": (
            "releases/v0.1.2.md",
            "how-to/verify-v0.1.2-release.md",
            "local synthetic portfolio release",
        ),
        "CONTRIBUTING.md": ("v0.1.2", "local synthetic portfolio release"),
        "SECURITY.md": ("v0.1.2", "local synthetic portfolio release"),
    }
    for relative, tokens in current_entries.items():
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert all(token in source for token in tokens), relative

    for relative in ("README.md", "README_CN.md", "docs/README.md"):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "v0.1.0" in source, relative
        assert "v0.1.1" in source, relative


def test_v0_1_2_release_notes_define_governed_collaboration_core_v1() -> None:
    release = (ROOT / "docs/releases/v0.1.2.md").read_text(encoding="utf-8")
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
        "Governed Collaboration Core v1",
        "MessageEvent",
        "MemoryCandidate",
        "ConfirmedFact",
        "advisor verification",
        "Case revision",
        "versioned Skill",
        "activation",
        "rollback",
        "runtime task",
        "/demo/collaboration",
        "read-only Planning Skill inspector",
        "task-free",
        "Live provider proof was not run",
        "GitHub-generated source archive",
    ):
        assert token in release


def test_v0_1_2_release_notes_distinguish_included_maintenance_from_release_prep() -> None:
    release = (ROOT / "docs/releases/v0.1.2.md").read_text(encoding="utf-8")

    for token in (
        "routine dependency and repository maintenance",
        "React / ReactDOM `19.2.7`",
        "pytest `9.1.1`",
        "Ruff `>=0.15.22`",
        "Node / React types 与 ESLint patch updates",
        "PostgreSQL Alpine variant/digest pin",
        "GitHub Actions setup updates",
        "本次 release-prep diff 未再引入额外 dependency upgrade、migration、API 或 "
        "runtime behavior 变更",
    ):
        assert token in release

    assert "也未引入 dependency upgrade" not in release
    assert "dependency upgrade、CI redesign" not in release


def test_v0_1_2_verification_guide_defines_publication_and_archive_gates() -> None:
    how_to = (ROOT / "docs/how-to/verify-v0.1.2-release.md").read_text(
        encoding="utf-8"
    )
    for token in (
        "local synthetic portfolio release",
        "git fetch origin --tags --prune",
        "git status --short --branch",
        "git rev-parse HEAD",
        "git rev-parse origin/main",
        "git describe --tags --exact-match HEAD",
        "git cat-file -t v0.1.2",
        "git rev-parse v0.1.2^{tag}",
        "git rev-parse v0.1.2^{commit}",
        'curl --fail --location --output "$archive"',
        "https://github.com/iTao-AI/night-voyager/archive/refs/tags/v0.1.2.tar.gz",
        'wc -c "$archive"',
        'shasum -a 256 "$archive"',
        'tar -xzf "$archive" -C "$tmp_dir"',
        'cd "$tmp_dir/night-voyager-0.1.2"',
        "make doctor MODE=dev",
        "make collaboration-check",
        "make skills-check",
        "make db-check",
        "make check",
        "make proof",
        "make compose-proof",
        "make down",
        "docker compose ps --all",
        "Never move the tag after publication",
        "Use the extracted source archive",
        "Do not force-move `v0.1.2`",
        "normal pull request",
    ):
        assert token in how_to


def test_published_release_documents_remain_byte_identical() -> None:
    for relative, expected in HISTORICAL_RELEASE_DIGESTS.items():
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        assert actual == expected, relative


def test_release_documentation_skills_do_not_expand_authority() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for token in (
        "Every release PR must run the GStack `document-release` targeted audit before merge",
        "Invoking a Skill does not authorize push, PR mutation, merge, tag, GitHub Release",
        "Use `document-generate` only to close a concrete, in-scope documentation gap",
        "Do not generate every Diataxis quadrant mechanically",
        "duplicate existing",
    ):
        assert token in agents
