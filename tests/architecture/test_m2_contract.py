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
