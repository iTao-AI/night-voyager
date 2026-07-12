from __future__ import annotations

from pathlib import Path

from night_voyager.planning.fixtures import validate_planning_fixture


def test_synthetic_planning_fixture_validates_offline() -> None:
    snapshot = validate_planning_fixture()
    assert snapshot == {
        "australia": "recommended_with_condition",
        "japan": "conditional",
        "malaysia": "blocked",
        "run_state": "review_required",
    }


def test_validate_only_does_not_require_database_url() -> None:
    import os
    import subprocess
    import sys

    environment = dict(os.environ)
    environment.pop("NIGHT_VOYAGER_MIGRATION_DATABASE_URL", None)
    result = subprocess.run(
        [sys.executable, "scripts/seed_demo.py", "--validate-only"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode == 0, result.stderr
    assert "planning fixture valid" in result.stdout


def test_manifest_rejects_changed_source(tmp_path: Path) -> None:
    from shutil import copytree

    import pytest

    root = tmp_path / "m3a"
    copytree(Path("fixtures/m3a"), root)
    (root / "sources/australia.txt").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        validate_planning_fixture(root / "manifest.json")
