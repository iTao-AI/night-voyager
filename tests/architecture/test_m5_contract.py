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
M5_SCREENSHOTS = (
    "docs/assets/m5-advisor-ledger.png",
    "docs/assets/m5-family-receipt-timeline.png",
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
    for private in ("/" + "Users/", "." + "sessions/"):
        assert private not in source


def test_m5_does_not_own_the_later_dra_migration() -> None:
    assert [path.name for path in sorted((ROOT / "migrations/versions").glob("*.py"))] == [
        "0001_identity_and_rls.py",
        "0002_case_evidence_planning.py",
        "0003_advisor_family_decision.py",
        "0004_agent_tasks_executions_events.py",
        "0005_dra_candidate_promotion.py",
    ]
    migration = (ROOT / "migrations/versions/0005_dra_candidate_promotion.py").read_text(
        encoding="utf-8"
    )
    assert "connected_demo" not in migration


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


def test_m5_bff_has_only_explicit_route_handlers() -> None:
    route_root = ROOT / "web/app/api/demo"
    routes = sorted(
        route.relative_to(route_root).as_posix() for route in route_root.rglob("route.ts")
    )
    assert len(routes) == 11
    assert not any("[..." in route for route in routes)
    assert all('dynamic = "force-dynamic"' in (route_root / route).read_text() for route in routes)


def test_m5_browser_proof_keeps_locked_runtime_and_dependencies() -> None:
    dockerfile = (ROOT / "web/Dockerfile.e2e").read_text(encoding="utf-8")
    package = (ROOT / "web/package.json").read_text(encoding="utf-8")
    assert "node:24.18.0-bookworm-slim" in dockerfile
    assert "npm ci" in dockerfile
    assert "playwright install --with-deps chromium" in dockerfile
    assert "PLAYWRIGHT_BROWSERS_PATH=/ms-playwright" in dockerfile
    assert "TCP-LISTEN:3000" in dockerfile
    assert "TCP:web:3000" in dockerfile
    assert '"@playwright/test": "1.58.2"' in package


def test_m5_connected_demo_public_docs_and_screenshots_are_current() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_cn = (ROOT / "README_CN.md").read_text(encoding="utf-8")
    docs_index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    combined = "\n".join((readme, readme_cn, docs_index))
    connected_demo_entries = [
        line
        for line in docs_index.splitlines()
        if line.startswith("- Connected-demo reviewers:")
    ]
    assert len(connected_demo_entries) == 1
    connected_demo_entry = connected_demo_entries[0]

    assert "docs/operations/connected-demo.md" in readme
    assert "docs/operations/connected-demo.md" in readme_cn
    assert "operations/connected-demo.md" in docs_index
    assert "M5" in readme and "implemented" in readme
    assert "M5" in readme_cn and "已实现" in readme_cn
    assert "M5 is implemented" in connected_demo_entry
    assert "implementation has not started" not in connected_demo_entry
    assert "fixture-only `/demo`" not in combined

    for relative in M5_SCREENSHOTS:
        asset = ROOT / relative
        assert asset.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"), relative
        assert readme.count(relative) == 1, relative
        assert readme_cn.count(relative) == 1, relative
