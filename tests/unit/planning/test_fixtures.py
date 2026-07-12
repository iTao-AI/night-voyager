from __future__ import annotations

from pathlib import Path

import pytest

from night_voyager.planning.fixtures import (
    EVAL_IDS,
    evaluate_stable_scenarios,
    validate_planning_fixture,
)


def test_synthetic_planning_fixture_validates_offline() -> None:
    fixture = validate_planning_fixture()
    assert fixture.snapshot() == {
        "australia": "recommended_with_condition",
        "japan": "conditional",
        "malaysia": "blocked",
        "run_state": "review_required",
    }
    assert set(fixture.eval_assertions) == EVAL_IDS
    assert len(fixture.manifest_sha256) == 64
    assert len(fixture.evidence_projection_sha256) == 64
    assert len(fixture.output_sha256) == 64
    assert evaluate_stable_scenarios(fixture) == fixture.eval_assertions
    assert fixture.eval_assertions["dra_fallback_ready"] == "failed"


def test_dra_fallback_candidate_fails_closed_on_authority() -> None:
    fixture = validate_planning_fixture()
    assert evaluate_stable_scenarios(fixture)["dra_fallback_ready"] == "failed"


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

    root = tmp_path / "m3a"
    copytree(Path("fixtures/m3a"), root)
    (root / "sources/australia.txt").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        validate_planning_fixture(root / "manifest.json")


def test_database_seed_uses_validated_canonical_fixture() -> None:
    script = Path("scripts/seed_demo.py").read_text(encoding="utf-8")
    assert "fixture = validate_planning_fixture()" in script
    assert "fixture.manifest_sha256" in script
    assert "fixture.evidence_projection_sha256" in script
    assert "fixture.output_sha256" in script
    assert "single_fully_evidenced_recommendation'" not in script
