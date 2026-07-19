from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations/versions/0007_conversation_and_memory.py"
TABLES = (
    "collaboration_threads",
    "message_events",
    "memory_candidates",
    "memory_candidate_verifications",
    "confirmed_facts",
    "case_revision_confirmed_fact_refs",
)
MUTATIONS = (
    "create_collaboration_thread",
    "append_collaboration_message",
    "propose_memory_candidate",
    "verify_memory_candidate",
)
READS = (
    "read_collaboration_thread",
    "read_collaboration_messages",
    "read_memory_candidates",
    "read_confirmed_facts",
)


def migration_source() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_migration_0007_adds_exactly_six_authority_tables() -> None:
    source = migration_source()
    assert 'revision = "0007"' in source
    assert 'down_revision = "0006"' in source
    assert tuple(
        line.split("app.", 1)[1].split(" ", 1)[0]
        for line in source.splitlines()
        if line.startswith("CREATE TABLE app.")
    ) == TABLES
    assert source.count("CREATE TABLE app.") == 6


def test_six_tables_are_forced_rls_and_immutable() -> None:
    source = migration_source()
    for table in TABLES:
        assert f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY" in source
        assert f"ALTER TABLE app.{table} FORCE ROW LEVEL SECURITY" in source
        assert f"CREATE POLICY {table}_tenant_isolation" in source
        assert f"CREATE TRIGGER {table}_immutable" in source


def test_migration_encodes_exact_tenant_and_case_lineage() -> None:
    source = migration_source()
    for fragment in (
        "UNIQUE (organization_id,case_id,id)",
        "FOREIGN KEY (organization_id,case_id,thread_id)",
        "FOREIGN KEY (organization_id,case_id,message_event_id,proposing_actor_id,proposing_role)",
        "FOREIGN KEY (organization_id,case_id,candidate_id)",
        "FOREIGN KEY (organization_id,case_id,source_candidate_id,"
        "source_message_event_id,subject_actor_id,subject_role)",
        "FOREIGN KEY (organization_id,case_id,fact_key,confirmed_fact_id)",
        "DEFERRABLE INITIALLY DEFERRED",
    ):
        assert fragment in source


def test_collaboration_functions_are_fixed_search_path_and_least_privilege() -> None:
    source = migration_source()
    for function in (*MUTATIONS, *READS, "seed_demo_collaboration"):
        assert f"CREATE FUNCTION app.{function}" in source
        signature_lines = [
            line
            for line in source.splitlines()
            if line.startswith(f"CREATE FUNCTION app.{function}")
        ]
        assert signature_lines
        assert "SECURITY DEFINER SET search_path = pg_catalog, pg_temp" in signature_lines[0]
        assert f"REVOKE ALL ON FUNCTION app.{function}" in source

    for function in (*MUTATIONS, *READS):
        grant_lines = [
            line
            for line in source.splitlines()
            if line.startswith(f"GRANT EXECUTE ON FUNCTION app.{function}")
        ]
        assert grant_lines and all("night_voyager_api" in line for line in grant_lines)
        assert all("night_voyager_worker" not in line for line in grant_lines)

    seed_grants = [
        line
        for line in source.splitlines()
        if line.startswith("GRANT EXECUTE ON FUNCTION app.seed_demo_collaboration")
    ]
    assert not seed_grants


def test_runtime_roles_have_no_direct_table_authority() -> None:
    source = migration_source()
    for table in TABLES:
        assert f"REVOKE ALL ON TABLE app.{table} FROM PUBLIC" in source
        assert f"REVOKE ALL ON TABLE app.{table} FROM night_voyager_api" in source
        assert f"REVOKE ALL ON TABLE app.{table} FROM night_voyager_worker" in source
        assert f"GRANT SELECT ON app.{table}" not in source


def test_demo_seed_function_has_one_closed_fixture_contract() -> None:
    source = migration_source()
    seed = source[
        source.index("CREATE FUNCTION app.seed_demo_collaboration") : source.index(
            'PRIVILEGE_SQL = r"""'
        )
    ]
    signature = "app.seed_demo_collaboration(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text)"
    assert f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC" in source
    assert f"REVOKE ALL ON FUNCTION {signature} FROM night_voyager_api" in source
    assert f"REVOKE ALL ON FUNCTION {signature} FROM night_voyager_worker" in source
    assert f"DROP FUNCTION {signature}" in source
    for fixture_kind in ("primary", "active_task"):
        assert f"p_fixture_kind='{fixture_kind}'" in source
    assert "p_fixture_kind IN ('stale','expired')" in source
    assert "p_fixture_kind IS NULL" in seed
    for record in (
        "existing",
        "existing_task",
        "existing_event",
        "existing_message",
        "existing_candidate",
    ):
        assert f"IF NOT FOUND OR {record}." in seed
    assert seed.count("IS DISTINCT FROM") >= 30


def test_demo_seed_script_uses_only_migrator_owned_collaboration_functions() -> None:
    script = (ROOT / "scripts/seed_demo.py").read_text(encoding="utf-8")
    assert "SELECT app.seed_demo_collaboration(" in script
    assert "SELECT app.seed_demo_pinned_collaboration_task(" in script
    assert "await _seed_collaboration(" in script
    for table in TABLES:
        assert f"INSERT INTO app.{table}" not in script


def test_legacy_whole_revision_writer_is_removed_from_runtime_authority() -> None:
    migration = migration_source()
    signature = "app.publish_case_revision(uuid,uuid,integer,integer,jsonb,jsonb)"
    assert f"REVOKE EXECUTE ON FUNCTION {signature} FROM night_voyager_api" in migration
    assert f"GRANT EXECUTE ON FUNCTION {signature} TO night_voyager_api" in migration
    assert migration.index(f"REVOKE EXECUTE ON FUNCTION {signature}") < migration.index(
        "def downgrade() -> None:"
    )
    assert migration.rindex(f"GRANT EXECUTE ON FUNCTION {signature}") > migration.index(
        "def downgrade() -> None:"
    )

    assert "publish_case_revision" not in (
        ROOT / "src/night_voyager/planning/postgres.py"
    ).read_text(encoding="utf-8")
    assert "publish_revision" not in (
        ROOT / "src/night_voyager/planning/application.py"
    ).read_text(encoding="utf-8")
    assert "create_revision" not in (
        ROOT / "src/night_voyager/planning/ports.py"
    ).read_text(encoding="utf-8")


def test_agent_task_creation_serializes_with_confirmation_case_lock() -> None:
    source = migration_source()
    assert "CREATE FUNCTION app.serialize_agent_task_case_revision()" in source
    assert "CREATE TRIGGER agent_tasks_collaboration_case_revision" in source
    assert "FOR SHARE" in source
    assert "selected_case.current_revision IS DISTINCT FROM NEW.case_revision" in source
    assert "DROP TRIGGER agent_tasks_collaboration_case_revision" in source


def test_confirmation_validates_and_materializes_the_complete_strict_revision() -> None:
    source = migration_source()
    verification = source.split("CREATE FUNCTION app.verify_memory_candidate", 1)[1].split(
        "END; $$;", 1
    )[0]
    assert verification.count("candidate.proposed_value,true") == 6
    for fragment in (
        "current_revision.student_preferences->'intended_field'",
        "current_revision.student_preferences->'preferred_countries'",
        "current_revision.student_preferences->'intake'",
        "current_revision.family_preferences->'risk_tolerance'",
        "current_revision.family_preferences->'japan_risk_accepted'",
        "current_revision.family_preferences->'budget'",
    ):
        assert fragment in verification


def test_mutations_and_reads_fail_closed_on_null_or_changed_canonical_inputs() -> None:
    source = migration_source()
    assert "selected.request_sha256 IS DISTINCT FROM p_request_sha256" in source
    for fragment in (
        "p_decision IS NULL",
        "p_reason IS NULL",
        "p_after_sequence IS NULL",
        "p_limit IS NULL",
        "jsonb_typeof(p_value->'schema_version')<>'number'",
        "jsonb_typeof(p_value->'elasticity_bps')<>'number'",
    ):
        assert fragment in source


def test_fact_and_revision_validation_rejects_sql_null_and_string_schema_versions() -> None:
    source = migration_source()
    validation = source.split(
        "CREATE FUNCTION app.validate_collaboration_fact", 1
    )[1].split("END; $$;", 1)[0]
    verification = source.split(
        "CREATE FUNCTION app.verify_memory_candidate", 1
    )[1].split("END; $$;", 1)[0]

    assert "p_role IS NULL OR p_fact_key IS NULL OR p_value IS NULL" in validation
    assert (
        "jsonb_typeof(current_revision.student_preferences->'schema_version')"
        "<>'number'"
    ) in verification
    assert (
        "jsonb_typeof(current_revision.family_preferences->'schema_version')"
        "<>'number'"
    ) in verification
    assert "(p_value->>'elasticity_bps')::numeric NOT BETWEEN 0 AND 2500" in validation
    assert "(p_value->>'elasticity_bps')::integer" not in validation


def test_existing_candidate_projection_uses_terminal_stale_expired_precedence() -> None:
    source = migration_source()
    proposal = source.split(
        "CREATE FUNCTION app.propose_memory_candidate", 1
    )[1].split("END; $$;", 1)[0]

    assert proposal.count(
        "selected.fact_key,selected.proposed_value,projected_state"
    ) == 2


def test_message_path_guard_does_not_treat_url_path_segments_as_local_paths() -> None:
    source = migration_source()
    validation = source.split(
        "CREATE FUNCTION app.validate_collaboration_message", 1
    )[1].split("END; $$;", 1)[0]

    assert (
        "p_body ~ '(^|[[:space:]])(/(Users|home|etc|private|var|tmp)/"
        in validation
    )


def test_downgrade_is_guarded_by_exact_pr_a_history() -> None:
    source = migration_source()
    downgrade = source.split("def downgrade() -> None:", 1)[1]
    for table in TABLES:
        assert table in downgrade
    for discriminator in (
        "collaboration_thread_create",
        "collaboration_message_append",
        "memory_candidate_propose",
        "memory_candidate_verify",
        "memory_candidate_confirmed",
        "memory_candidate_rejected",
    ):
        assert discriminator in downgrade
    assert "refusing downgrade: collaboration authority history exists" in downgrade
