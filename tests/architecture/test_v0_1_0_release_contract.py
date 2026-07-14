from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = "0.1.0"
DESCRIPTION = "Evidence-grounded advisor-to-family decision workflow with durable Agent tasks"


def test_release_identity_is_consistent_without_dependency_drift() -> None:
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
    assert f'VERSION = "{VERSION}"' in (
        ROOT / "scripts/verify_release.py"
    ).read_text(encoding="utf-8")


def test_readmes_are_outcome_first_and_link_release_history() -> None:
    contracts = (
        (
            "README.md",
            "Night Voyager turns a synthetic study-abroad comparison",
            "## Engineering proof",
            "## Evaluate the release",
            "## Synthetic and local limits",
            "## Milestones and history",
        ),
        (
            "README_CN.md",
            "Night Voyager 将一组三国留学比较",
            "## 工程证据",
            "## 验证 release",
            "## 合成与本地边界",
            "## Milestone 与历史",
        ),
    )
    screenshots = (
        "docs/assets/m5-advisor-ledger.png",
        "docs/assets/m5-family-receipt-timeline.png",
    )

    for relative, outcome, proof, evaluator, limits, history in contracts:
        source = (ROOT / relative).read_text(encoding="utf-8")
        required = (outcome, *screenshots, proof, evaluator, limits, history)
        positions = [source.index(value) for value in required]
        assert positions == sorted(positions)
        assert "docs/releases/v0.1.0.md" in source
        assert "docs/how-to/verify-v0.1.0-release.md" in source


def test_release_docs_freeze_local_synthetic_source_archive_boundary() -> None:
    release = (ROOT / "docs/releases/v0.1.0.md").read_text(encoding="utf-8")
    how_to = (ROOT / "docs/how-to/verify-v0.1.0-release.md").read_text(encoding="utf-8")
    docs_index = (ROOT / "docs/README.md").read_text(encoding="utf-8")

    release_headings = (
        "## Summary",
        "## Completion",
        "## Verification",
        "## Scope",
        "## Risk / Impact",
        "## Documentation impact",
    )
    release_positions = [release.index(heading) for heading in release_headings]
    assert release_positions == sorted(release_positions)
    for token in (
        "local synthetic portfolio release",
        "GitHub-generated source archive",
        "UNTRUSTED_CANDIDATE",
        "production tenancy",
        "真实学生",
        "SLA",
        "业务收益",
    ):
        assert token in release

    for command in (
        "git fetch origin --tags --prune",
        "git status --short --branch",
        "git rev-parse HEAD",
        "git rev-parse origin/main",
        "git describe --tags --exact-match HEAD",
        "git cat-file -t v0.1.0",
        "git rev-parse v0.1.0^{tag}",
        "git rev-parse v0.1.0^{commit}",
        'curl --fail --location --output "$archive"',
        "https://github.com/iTao-AI/night-voyager/archive/refs/tags/v0.1.0.tar.gz",
        'wc -c "$archive"',
        'shasum -a 256 "$archive"',
        'tar -xzf "$archive" -C "$tmp_dir"',
        'cd "$tmp_dir/night-voyager-0.1.0"',
        "make doctor",
        "make proof",
        "make compose-proof",
        "make down",
        "docker compose ps --all",
    ):
        assert command in how_to
    for boundary in (
        "annotated tag",
        "Never move the tag after publication",
        "Use the extracted source archive",
        "not the development `.venv`, `node_modules`, retained demo volume, or a custom wheel",
        "Do not force-move `v0.1.0`",
        "normal pull request",
    ):
        assert boundary in how_to
    assert "releases/v0.1.0.md" in docs_index
    assert "how-to/verify-v0.1.0-release.md" in docs_index
    assert "source-archive verification" in docs_index


def test_readmes_name_the_release_and_source_archive_verification_path() -> None:
    for relative in ("README.md", "README_CN.md"):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "release/source-archive verification" in source, relative


def test_supported_public_docs_do_not_describe_the_project_as_bootstrap() -> None:
    stale = ("bootstrap stage", "local bootstrap phase", "no released production version")
    for relative in ("SECURITY.md", "CONTRIBUTING.md", "docs/README.md"):
        source = (ROOT / relative).read_text(encoding="utf-8").lower()
        assert all(phrase not in source for phrase in stale), relative
