from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_pytest_and_default_lanes_exclude_optional_mke() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pytest_config = pyproject["tool"]["pytest"]["ini_options"]
    assert pytest_config["addopts"] == '-m "not database and not mke"'
    assert set(pytest_config["markers"]) == {
        "database: requires disposable PostgreSQL 18 roles",
        "mke: requires the optional MKE/MCP process extra",
    }
    assert pyproject["project"]["optional-dependencies"]["mke"] == ["mcp>=1.28.1,<2"]
    assert set(pyproject["tool"]["pyright"]["exclude"]) == {
        "src/night_voyager/adapters/mke_readonly.py",
        "tests/fixtures/m4b/fake_mke_server.py",
        "tests/integration/adapters/test_mke_candidate_wheel.py",
        "tests/integration/adapters/test_mke_readonly_smoke.py",
    }

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    default_check = makefile.split("\ncheck: ##", 1)[1].split("\n\n", 1)[0]
    assert '-m "not database and not mke"' in default_check
    assert "mke-check" not in default_check
    assert "mke-consumer-proof" not in default_check


def test_make_exposes_only_explicit_mke_gates() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    expected = {
        "mke-doctor": "verify_mke_consumer.py doctor",
        "mke-artifact-check": "verify_mke_consumer.py artifact-check",
        "mke-check": "scripts/run_mke_lane.sh test",
        "mke-consumer-proof": "scripts/run_mke_lane.sh proof",
    }
    for target, command in expected.items():
        body = makefile.split(f"\n{target}:", 1)[1].split("\n\n", 1)[0]
        assert command in body


def test_python_ci_has_artifact_free_optional_process_step() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    python_job = workflow.split("  python:", 1)[1].split("  frontend:", 1)[0]
    assert 'uv run pytest -q -m "not database and not mke"' in python_job
    assert (
        "scripts/run_mke_lane.sh test tests/integration/adapters/test_mke_readonly_smoke.py"
        in python_job
    )
    for forbidden in (
        "MKE_WHEEL",
        "MKE_RECEIPT",
        "candidate-artifact-receipt",
        "actions/download-artifact",
        "multimodal-knowledge-engine",
    ):
        assert forbidden not in python_job


def test_m4b_remains_outside_compose_migrations_and_m4a_runtime() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8").lower()
    assert "mke" not in compose
    assert not list((ROOT / "migrations" / "versions").glob("0005_*.py"))
    runtime_paths = [
        ROOT / "src/night_voyager/api.py",
        ROOT / "src/night_voyager/worker.py",
        *(ROOT / "src/night_voyager/tasks").glob("*.py"),
        *(ROOT / "src/night_voyager/interfaces/http").glob("*.py"),
    ]
    for path in runtime_paths:
        assert "mke" not in path.read_text(encoding="utf-8").lower(), path


def test_pure_boundary_has_no_optional_sdk_import_and_public_records_exist() -> None:
    for path in (ROOT / "src/night_voyager/evidence").glob("*.py"):
        content = path.read_text(encoding="utf-8")
        assert "import mcp" not in content
        assert "from mcp" not in content
    for relative in (
        "docs/decisions/0005-mke-readonly-evidence-boundary.md",
        "docs/superpowers/specs/2026-07-13-m4b-mke-readonly-consumer-design.md",
        "docs/superpowers/plans/2026-07-13-m4b-mke-readonly-consumer.md",
        "fixtures/m4b/candidate-artifact-lock.json",
        "fixtures/m4b/manifest.json",
    ):
        assert (ROOT / relative).is_file(), relative
