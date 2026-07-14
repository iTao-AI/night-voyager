from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_RECORDS = (
    "docs/superpowers/specs/2026-07-14-m5-connected-advisor-family-demo-design.md",
    "docs/superpowers/plans/2026-07-14-m5-connected-advisor-family-demo.md",
    "docs/decisions/0006-connected-demo-bff-authority.md",
)
BACKEND_PATHS = (
    "/api/v1/cases/{case_id}/advisor-ledger",
    "/api/v1/cases/{case_id}/current-decision-brief",
)
BFF_PATHS = (
    "/api/demo/session-bootstrap",
    "/api/demo/sessions",
    "/api/demo/session",
    "/api/demo/cases/{case_id}/advisor-ledger",
    "/api/demo/cases/{case_id}/agent-tasks",
    "/api/demo/tasks/{task_id}",
    "/api/demo/tasks/{task_id}/cancel",
    "/api/demo/tasks/{task_id}/events",
    "/api/demo/cases/{case_id}/advisor-reviews",
    "/api/demo/cases/{case_id}/current-decision-brief",
    "/api/demo/decision-briefs/{brief_id}/family-decisions",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }


def test_m5_public_records_exist_and_are_public_neutral() -> None:
    source = ""
    for relative in PUBLIC_RECORDS:
        path = ROOT / relative
        assert path.is_file(), relative
        source += path.read_text(encoding="utf-8")
    for private in ("/" + "Users/", "Developer/" + "Career", "." + "sessions/"):
        assert private not in source


def test_m5_keeps_the_existing_database_graph() -> None:
    assert [path.name for path in sorted((ROOT / "migrations/versions").glob("*.py"))] == [
        "0001_identity_and_rls.py",
        "0002_case_evidence_planning.py",
        "0003_advisor_family_decision.py",
        "0004_agent_tasks_executions_events.py",
    ]


def test_m5_freezes_exact_backend_and_bff_paths() -> None:
    source = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8") for relative in PUBLIC_RECORDS
    )
    for path in (*BACKEND_PATHS, *BFF_PATHS):
        assert path in source
    assert len(BACKEND_PATHS) == 2
    assert len(BFF_PATHS) == 11


def test_pure_connected_demo_contracts_do_not_import_frameworks() -> None:
    forbidden = {"fastapi", "sqlalchemy", "asyncpg", "alembic"}
    for module in ("models.py", "fixtures.py", "errors.py", "ports.py", "application.py"):
        path = ROOT / "src/night_voyager/connected_demo" / module
        if path.exists():
            assert not (_imports(path) & forbidden), module


def test_m5_adds_no_database_ddl_or_grants() -> None:
    migration_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "migrations/versions").glob("*.py"))
    )
    assert "connected_demo" not in migration_source
    assert "advisor_ledger" not in migration_source
