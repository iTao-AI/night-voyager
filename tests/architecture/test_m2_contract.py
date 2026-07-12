from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_m2_dependencies_and_alembic_head_are_declared() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert "sqlalchemy>=2.0.51,<2.1" in pyproject["project"]["dependencies"]
    assert "alembic>=1.18.5,<1.19" in pyproject["project"]["dependencies"]
    assert "asyncpg>=0.31,<0.32" in pyproject["project"]["dependencies"]
    assert "pytest-asyncio>=1.4,<2" in pyproject["dependency-groups"]["dev"]
    assert (ROOT / "alembic.ini").is_file()
    migrations = list((ROOT / "migrations/versions").glob("*.py"))
    assert [path.name for path in migrations] == ["0001_identity_and_rls.py"]


def test_m2_role_init_and_public_records_exist() -> None:
    required = (
        "docker/postgres/init/001-create-roles.sh",
        "docs/decisions/0001-identity-session-and-rls-boundary.md",
        "docs/reference/http-api-v1.md",
        "docs/operations/database-roles.md",
        "docs/superpowers/specs/2026-07-12-m2-identity-session-rls-design.md",
        "docs/superpowers/plans/2026-07-12-m2-identity-session-rls.md",
    )

    for relative in required:
        assert (ROOT / relative).is_file(), relative


def test_m2_does_not_create_later_milestone_artifacts() -> None:
    assert not list((ROOT / "migrations/versions").glob("000[234]_*.py"))
    for forbidden in ("case", "evidence", "planning", "brief", "decision", "agent_task"):
        assert not list((ROOT / "src/night_voyager").rglob(f"*{forbidden}*.py"))


def test_database_gate_is_mandatory_locally_and_in_existing_ci_job() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    script = (ROOT / "scripts/run_db_tests.sh").read_text(encoding="utf-8")

    assert "db-check:" in makefile
    assert pyproject["tool"]["pytest"]["ini_options"]["addopts"] == '-m "not database"'
    check_target = makefile.split("\ncheck: ##", 1)[1].split("\n\n", 1)[0]
    assert '-m "not database"' in check_target
    assert "$(MAKE) db-check" in check_target
    assert set(("python", "frontend", "compose")) <= {
        line.strip().removesuffix(":")
        for line in workflow.splitlines()
        if line.startswith("  ") and not line.startswith("    ") and line.strip().endswith(":")
    }
    compose_job = workflow.split("  compose:", 1)[1]
    assert "make db-check" in compose_job
    python_job = workflow.split("  python:", 1)[1].split("  frontend:", 1)[0]
    assert 'uv run pytest -q -m "not database"' in python_job
    assert "COMPOSE_PROJECT_NAME" in script
    assert "down --volumes" in script


def test_local_demo_runs_explicit_seed_and_identity_probe() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    proof = (ROOT / "scripts/verify_compose.sh").read_text(encoding="utf-8")

    assert "demo-seed:" in compose
    assert 'command: ["python", "scripts/seed_demo.py"]' in compose
    assert "demo-seed:\n        condition: service_completed_successfully" in compose
    assert "verify_demo_identity.py" in proof


def test_public_docs_preserve_fixture_only_demo_boundary() -> None:
    for relative in ("README.md", "README_CN.md", "CONTRIBUTING.md", "docs/README.md"):
        content = (ROOT / relative).read_text(encoding="utf-8")
        assert "db-check" in content, relative
        assert "fixture-only" in content, relative
