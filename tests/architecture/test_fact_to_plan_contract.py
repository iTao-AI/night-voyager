from __future__ import annotations

import hashlib
from pathlib import Path

from night_voyager.interfaces.http.tasks import CreateAgentTaskRequest

ROOT = Path(__file__).resolve().parents[2]
MIGRATION_0008 = ROOT / "migrations/versions/0008_versioned_skills.py"
MIGRATION_0009 = ROOT / "migrations/versions/0009_explicit_planning_start_authority.py"
CREATE_TASK_SIGNATURE = (
    "app.create_agent_task(uuid,uuid,uuid,uuid,text,integer,uuid,integer,"
    "text,jsonb,text,text)"
)


def test_http_create_contract_remains_exact() -> None:
    assert tuple(CreateAgentTaskRequest.model_fields) == (
        "schema_version",
        "operation",
        "expected_case_revision",
        "source_pack_id",
        "source_pack_version",
        "policy_version",
    )


def test_0008_remains_immutable_at_the_approved_pr_base() -> None:
    assert hashlib.sha256(MIGRATION_0008.read_bytes()).hexdigest() == (
        "67fe8d46f6d101e4f5dbfc32c77513fe9311842edd3262b34bdd9b297504120a"
    )


def test_0009_owns_only_the_explicit_first_planning_transition() -> None:
    migration = MIGRATION_0009.read_text(encoding="utf-8")

    assert 'revision = "0009"' in migration
    assert 'down_revision = "0008"' in migration
    assert "CREATE_TASK_SQL" in migration
    assert "_0008_CREATE_TASK_SQL" in migration
    assert "FOR UPDATE" in migration
    assert "current_case.state='intake'" in migration
    assert "p_operation='generate_planning_run_v1'" in migration
    assert "generate_governed_mixed_planning_run_v1" in migration
    assert "starts_planning" in migration
    assert CREATE_TASK_SIGNATURE in migration
    assert f"REVOKE ALL ON FUNCTION {CREATE_TASK_SIGNATURE} FROM PUBLIC" in migration
    assert (
        f"GRANT EXECUTE ON FUNCTION {CREATE_TASK_SIGNATURE} TO night_voyager_api"
        in migration
    )


def test_0009_does_not_add_schema_or_public_contract_surface() -> None:
    migration = MIGRATION_0009.read_text(encoding="utf-8")

    for forbidden in (
        "op.create_table",
        "CREATE TABLE",
        "CREATE TYPE",
        "CREATE SCHEMA",
        "ALTER TABLE",
        "CREATE INDEX",
        "GRANT INSERT",
        "GRANT UPDATE",
        "GRANT DELETE",
        "TO night_voyager_worker",
        "TO PUBLIC",
    ):
        assert forbidden not in migration
