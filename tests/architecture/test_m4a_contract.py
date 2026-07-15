from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PUBLIC_RECORDS = (
    "docs/superpowers/specs/2026-07-13-m4a-durable-agent-task-sse-design.md",
    "docs/superpowers/plans/2026-07-13-m4a-durable-agent-task-sse.md",
    "docs/decisions/0004-durable-agent-task-authority.md",
)
M4A_TABLES = ("agent_tasks", "agent_executions", "agent_task_events")
M4A_HTTP_PATHS = (
    "/api/v1/cases/{case_id}/agent-tasks",
    "/api/v1/tasks/{task_id}",
    "/api/v1/tasks/{task_id}/cancel",
    "/api/v1/tasks/{task_id}/events",
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


def test_m4a_public_records_exist() -> None:
    for relative in PUBLIC_RECORDS:
        assert (ROOT / relative).is_file(), relative


def test_m4a_public_records_freeze_scope_and_claim_boundaries() -> None:
    source = "\n".join((ROOT / relative).read_text(encoding="utf-8") for relative in PUBLIC_RECORDS)
    for required in (
        "generate_planning_run_v1",
        "m3a-policy-v1",
        "needs_advisor_review",
        "60 seconds",
        "15 seconds",
        "three total attempts",
        "100 durable events",
        "payload-free",
        "M4B",
        "M5",
        "local synthetic",
    ):
        assert required in source
    for private in (
        "/" + "Users/",
        "Developer/" + "Career",
        "." + "sessions/",
        "G" + "Stack",
        "g" + "stack",
    ):
        assert private not in source


def test_migration_graph_extends_0003_with_exact_m4a_storage() -> None:
    migrations = sorted((ROOT / "migrations/versions").glob("*.py"))
    assert [path.name for path in migrations] == [
        "0001_identity_and_rls.py",
        "0002_case_evidence_planning.py",
        "0003_advisor_family_decision.py",
        "0004_agent_tasks_executions_events.py",
        "0005_dra_candidate_promotion.py",
    ]
    migration = migrations[3]
    tree = ast.parse(migration.read_text(encoding="utf-8"))
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"revision", "down_revision"}
    }
    assert assignments == {"revision": "0004", "down_revision": "0003"}
    source = migration.read_text(encoding="utf-8")
    assert tuple(
        line.split("app.", 1)[1].split(" ", 1)[0]
        for line in source.splitlines()
        if line.startswith("CREATE TABLE app.")
    ) == M4A_TABLES
    dispatch = source.split("CREATE TABLE internal.agent_task_dispatch (", 1)[1].split(
        ");", 1
    )[0]
    dispatch_columns = {
        line.strip().split()[0].rstrip(",")
        for line in dispatch.splitlines()
        if line.strip() and not line.lstrip().startswith(("PRIMARY", "FOREIGN"))
    }
    assert dispatch_columns == {
        "task_id",
        "organization_id",
        "available_at",
    }


def test_pure_task_contracts_do_not_import_frameworks_or_concrete_adapters() -> None:
    forbidden = {"fastapi", "sqlalchemy", "asyncpg", "alembic"}
    for relative in (
        "src/night_voyager/tasks/models.py",
        "src/night_voyager/tasks/policy.py",
        "src/night_voyager/tasks/ports.py",
        "src/night_voyager/tasks/application.py",
        "src/night_voyager/tasks/errors.py",
        "src/night_voyager/adapters/protocols.py",
    ):
        path = ROOT / relative
        assert path.is_file(), relative
        assert not (_imports(path) & forbidden), relative


def test_m4a_http_contract_declares_only_the_four_backend_routes() -> None:
    path = ROOT / "src/night_voyager/interfaces/http/tasks.py"
    source = path.read_text(encoding="utf-8")
    for route in M4A_HTTP_PATHS:
        assert route.replace("/api/v1", "") in source
    assert "MKE" not in source
    assert "DecisionBrief" not in source
