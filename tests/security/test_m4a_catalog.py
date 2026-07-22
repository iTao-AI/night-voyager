from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = ROOT / "migrations/versions/0004_agent_tasks_executions_events.py"
PLANNING_START_MIGRATION_PATH = (
    ROOT / "migrations/versions/0009_explicit_planning_start_authority.py"
)
TABLES = ("agent_tasks", "agent_executions", "agent_task_events")
API_FUNCTIONS = ("create_agent_task", "cancel_agent_task")
WORKER_FUNCTIONS = (
    "claim_agent_task",
    "start_agent_task",
    "heartbeat_agent_task",
    "fail_agent_task",
    "finalize_agent_task_result",
)
WORKER_FUNCTION_SIGNATURES = {
    "start_agent_task": "uuid,uuid,text,bigint,text",
    "fail_agent_task": "uuid,uuid,text,bigint,text,boolean,boolean",
}


def migration() -> str:
    assert MIGRATION_PATH.is_file()
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_0009_keeps_task_creation_as_the_single_narrow_runtime_authority() -> None:
    source = PLANNING_START_MIGRATION_PATH.read_text(encoding="utf-8")
    signature = (
        "app.create_agent_task(uuid,uuid,uuid,uuid,text,integer,uuid,integer,"
        "text,jsonb,text,text)"
    )

    assert 'op.execute(f"DROP FUNCTION {CREATE_TASK_SIGNATURE}")' in source
    assert "_replace(CREATE_TASK_SQL)" in source
    assert "_replace(_0008_CREATE_TASK_SQL)" in source
    assert source.count("CREATE FUNCTION app.create_agent_task(") == 2
    assert f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC" in source
    assert f"GRANT EXECUTE ON FUNCTION {signature} TO night_voyager_api" in source
    assert f"GRANT EXECUTE ON FUNCTION {signature} TO night_voyager_worker" not in source
    assert "CREATE TABLE" not in source
    assert "ALTER TABLE" not in source


def test_m4a_migration_has_exact_graph_and_storage() -> None:
    source = migration()
    tree = ast.parse(source)
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"revision", "down_revision"}
    }
    assert assignments == {"revision": "0004", "down_revision": "0003"}
    assert tuple(
        line.split("app.", 1)[1].split(" ", 1)[0]
        for line in source.splitlines()
        if line.startswith("CREATE TABLE app.")
    ) == TABLES
    assert "CREATE TABLE internal.agent_task_dispatch" in source
    assert "CREATE SCHEMA internal AUTHORIZATION night_voyager_migrator" in source
    dispatch = source.split("CREATE TABLE internal.agent_task_dispatch (", 1)[1].split(
        ");", 1
    )[0]
    for column in ("task_id uuid", "organization_id uuid", "available_at timestamptz"):
        assert column in dispatch
    for forbidden in (
        "case_id",
        "actor_id",
        "request_sha256",
        "evidence",
        "adapter",
        "error",
        "result",
        "payload",
    ):
        assert forbidden not in dispatch.lower()


def test_every_m4a_tenant_table_has_forced_rls_and_policy() -> None:
    source = migration()
    for table in TABLES:
        assert f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY" in source
        assert f"ALTER TABLE app.{table} FORCE ROW LEVEL SECURITY" in source
        assert f"CREATE POLICY {table}_tenant_isolation" in source
        assert "organization_id uuid NOT NULL" in source


def test_runtime_authority_is_narrow_function_only() -> None:
    source = migration()
    assert "GRANT INSERT ON app.agent_" not in source
    assert "GRANT UPDATE ON app.agent_" not in source
    assert "GRANT DELETE ON app.agent_" not in source
    assert "GRANT TRUNCATE ON app.agent_" not in source
    assert "GRANT SELECT ON internal.agent_task_dispatch" not in source
    for function in API_FUNCTIONS + WORKER_FUNCTIONS:
        assert f"FUNCTION app.{function}" in source
        assert f"REVOKE ALL ON FUNCTION app.{function}" in source
    assert "SECURITY DEFINER SET search_path = pg_catalog, pg_temp" in source
    assert "GRANT EXECUTE ON FUNCTION app.create_agent_task" in source
    assert "GRANT EXECUTE ON FUNCTION app.cancel_agent_task" in source
    for function in WORKER_FUNCTIONS:
        grant = next(
            line
            for line in source.splitlines()
            if line.startswith(f"GRANT EXECUTE ON FUNCTION app.{function}")
        )
        assert grant.endswith("TO night_voyager_worker;")
    for function, signature in WORKER_FUNCTION_SIGNATURES.items():
        assert f"FUNCTION app.{function}({signature})" in source
    worker_grants = "\n".join(
        line
        for line in source.splitlines()
        if "GRANT EXECUTE" in line and "night_voyager_worker" in line
    )
    assert "review_planning_run" not in worker_grants
    assert "decide_family_brief" not in worker_grants


def test_m4a_events_and_executions_exclude_raw_payloads() -> None:
    source = migration()
    for table in ("agent_executions", "agent_task_events"):
        body = source.split(f"CREATE TABLE app.{table} (", 1)[1].split(");", 1)[0]
        for forbidden in ("raw_prompt", "raw_output", "payload json", "stack_trace", "secret"):
            assert forbidden not in body.lower()
    assert "event_sequence" in source
    assert "PRIMARY KEY (organization_id, task_id, event_sequence)" in source
    assert "lease_generation" in source
    assert "lease_owner" in source
    for audit_field in (
        "fallback_used",
        "input_sha256",
        "output_sha256",
        "duration_ms",
        "cost_status",
    ):
        assert audit_field in source
    assert "invalid fallback audit fact" in source
    assert "invalid execution input hash" in source


def test_m4a_downgrade_drops_only_m4a_authority() -> None:
    source = migration()
    for table in TABLES:
        assert f"DROP TABLE app.{table}" in source
    assert "DROP TABLE internal.agent_task_dispatch" in source
    assert "DROP TABLE app.planning_runs" not in source
    assert "DROP TABLE app.decision_briefs" not in source
