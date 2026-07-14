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

    assert "local synthetic portfolio release" in release
    assert "GitHub-generated source archive" in release
    assert "No separately built wheel, container image, or binary" in release
    assert "scripts/verify_release.py --tree-mode release" in how_to
    assert "docker compose ps --all" in how_to
    assert "releases/v0.1.0.md" in docs_index
    assert "how-to/verify-v0.1.0-release.md" in docs_index


def test_supported_public_docs_do_not_describe_the_project_as_bootstrap() -> None:
    stale = ("bootstrap stage", "local bootstrap phase", "no released production version")
    for relative in ("SECURITY.md", "CONTRIBUTING.md", "docs/README.md"):
        source = (ROOT / relative).read_text(encoding="utf-8").lower()
        assert all(phrase not in source for phrase in stale), relative
