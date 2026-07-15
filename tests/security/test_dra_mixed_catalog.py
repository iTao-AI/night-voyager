from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations/versions/0006_governed_mixed_planning.py"


def test_mixed_migration_is_additive_without_a_second_queue_or_table() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "0006"' in source
    assert 'down_revision = "0005"' in source
    assert "CREATE TABLE" not in source
    assert "generate_planning_run_v1" in source
    assert "generate_governed_mixed_planning_run_v1" in source
    assert "deterministic_planning" in source and "m4a-v1" in source
    assert "governed_mixed_planning" in source and "dra-mixed-v1" in source


def test_mixed_migration_has_one_worker_only_snapshot_authority() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    signature = (
        "app.load_governed_mixed_planning_snapshot"
        "(uuid,uuid,integer,uuid,integer,text)"
    )
    assert "SECURITY DEFINER SET search_path = pg_catalog, pg_temp" in source
    assert f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC" in source
    assert f"GRANT EXECUTE ON FUNCTION {signature} TO night_voyager_worker" in source
    assert f"GRANT EXECUTE ON FUNCTION {signature} TO night_voyager_api" not in source
    assert "GRANT EXECUTE ON FUNCTION app.verify_and_promote_dra_candidate" not in source
    assert "GRANT EXECUTE ON FUNCTION app.import_dra_research_candidate" not in source


def test_mixed_migration_downgrade_restores_pr1_contracts() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert "def downgrade() -> None:" in source
    assert "DROP FUNCTION app.load_governed_mixed_planning_snapshot" in source
    assert "CHECK (operation = 'generate_planning_run_v1')" in source
    assert "CHECK (adapter_id = 'deterministic_planning')" in source
    assert "CHECK (adapter_version = 'm4a-v1')" in source
    assert "GRANT EXECUTE ON FUNCTION app.create_agent_task" in source


def test_db_lane_cycles_through_the_mixed_head() -> None:
    source = (ROOT / "scripts/run_db_tests.sh").read_text(encoding="utf-8")
    assert "alembic downgrade 0005" in source
    assert source.count("alembic current | grep '0006'") >= 2
    assert "tests/integration/dra/test_postgres_mixed_snapshot.py" in source
