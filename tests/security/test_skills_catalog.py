from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations/versions/0008_versioned_skills.py"
REGISTRATION = ROOT / "scripts/register_skill_version.py"
SEED = ROOT / "scripts/seed_demo.py"
TABLES = (
    "skill_definitions",
    "skill_versions",
    "skill_change_candidates",
    "skill_evaluation_results",
    "skill_activation_events",
)
MUTATIONS = (
    "create_skill_change_candidate",
    "record_skill_candidate_evaluation",
    "promote_skill_change_candidate",
    "rollback_skill_activation",
)


def migration_source() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_migration_0008_adds_exactly_five_skill_tables() -> None:
    source = migration_source()

    assert 'revision = "0008"' in source
    assert 'down_revision = "0007"' in source
    assert (
        tuple(
            line.split("app.", 1)[1].split(" ", 1)[0]
            for line in source.splitlines()
            if line.startswith("CREATE TABLE app.skill_")
        )
        == TABLES
    )
    assert source.count("CREATE TABLE app.skill_") == 5


def test_skill_tables_are_forced_rls_immutable_and_migrator_owned() -> None:
    source = migration_source()

    for table in TABLES:
        assert f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY" in source
        assert f"ALTER TABLE app.{table} FORCE ROW LEVEL SECURITY" in source
        assert f"CREATE POLICY {table}_tenant_isolation" in source
        assert f"CREATE TRIGGER {table}_immutable" in source
        assert f"REVOKE ALL ON TABLE app.{table} FROM PUBLIC" in source
        assert f"REVOKE ALL ON TABLE app.{table} FROM night_voyager_api" in source
        assert f"REVOKE ALL ON TABLE app.{table} FROM night_voyager_worker" in source


def test_skill_runtime_functions_have_fixed_search_path_and_least_privilege() -> None:
    source = migration_source()

    for function in (*MUTATIONS, "seed_demo_skill_registry"):
        line = next(
            item
            for item in source.splitlines()
            if item.startswith(f"CREATE FUNCTION app.{function}")
        )
        assert "SECURITY DEFINER SET search_path = pg_catalog, pg_temp" in line
        assert f"REVOKE ALL ON FUNCTION app.{function}" in source

    for function in MUTATIONS:
        grants = tuple(
            line
            for line in source.splitlines()
            if line.startswith(f"GRANT EXECUTE ON FUNCTION app.{function}")
        )
        assert grants and all("night_voyager_api" in line for line in grants)
        assert all("night_voyager_worker" not in line for line in grants)
    assert not any(
        line.startswith("GRANT EXECUTE ON FUNCTION app.seed_demo_skill_registry")
        for line in source.splitlines()
    )


def test_task_and_execution_pins_are_exactly_five_fields_and_all_or_none() -> None:
    source = migration_source()
    fields = (
        "skill_definition_id",
        "skill_version_id",
        "skill_activation_event_id",
        "skill_activation_sequence",
        "runtime_binding_sha256",
    )

    for table in ("agent_tasks", "agent_executions"):
        for field in fields:
            assert f"ALTER TABLE app.{table} ADD COLUMN {field}" in source
        assert f"{table}_skill_pin_all_or_none" in source
    assert "agent_tasks_one_effective_operation" in source
    assert all(field in source for field in fields)


def test_upgrade_and_downgrade_freeze_legacy_task_authority() -> None:
    source = migration_source()
    downgrade = source.split("def downgrade() -> None:", 1)[1]

    assert "legacy_unpinned" in source
    assert "refusing downgrade: Skill governance or runtime pin history exists" in source
    assert "0007_CREATE_TASK_SQL" in source
    assert "0007_CLAIM_TASK_SQL" in source
    assert "DROP TABLE app.skill_activation_events" in downgrade
    assert "DROP TABLE app.skill_definitions" in downgrade


def test_supported_version_registration_is_explicit_migrator_only_and_not_seeded() -> None:
    registration = REGISTRATION.read_text(encoding="utf-8")
    migration = migration_source()
    seed = SEED.read_text(encoding="utf-8")

    assert "NIGHT_VOYAGER_MIGRATION_DATABASE_URL" in registration
    assert "SkillRuntimeRegistry.load_packaged()" in registration
    assert "INSERT INTO app.skill_versions(" in registration
    assert "manifest_projection" in registration
    assert "ON CONFLICT (organization_id,definition_id,semantic_version) DO NOTHING" in (
        registration
    )
    assert "Skill version registration failed closed" in registration
    assert "NIGHT_VOYAGER_API_DATABASE_URL" not in registration
    assert "NIGHT_VOYAGER_WORKER_DATABASE_URL" not in registration
    assert "register_skill_version.py" not in migration
    assert "register_skill_version.py" not in seed
    assert 'registry.get(key, "1.0.0")' in (
        ROOT / "src/night_voyager/identity/demo_seed.py"
    ).read_text(encoding="utf-8")
    assert 'registry.get(key, "1.0.1")' not in (
        ROOT / "src/night_voyager/identity/demo_seed.py"
    ).read_text(encoding="utf-8")


def test_default_seed_orders_skill_authority_before_every_task_ready_case() -> None:
    seed = SEED.read_text(encoding="utf-8")

    skill_seed = seed.index("await _seed_skills(connection)")
    planning_seed = seed.index("await _seed_planning(connection, fixture)")
    task_case_seed = seed.index("await _seed_task_case(connection, fixture)")
    collaboration_seed = seed.index("await _seed_collaboration(connection, fixture)")
    assert skill_seed < planning_seed < task_case_seed < collaboration_seed
