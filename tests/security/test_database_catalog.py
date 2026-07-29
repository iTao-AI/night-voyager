from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_role_init_creates_separate_least_privilege_roles() -> None:
    script = (ROOT / "docker/postgres/init/001-create-roles.sh").read_text(encoding="utf-8")

    for role in ("night_voyager_migrator", "night_voyager_api", "night_voyager_worker"):
        assert role in script
    assert script.count("NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS") == 3
    assert "GRANT night_voyager_migrator" not in script


def test_compose_separates_migration_and_runtime_credentials() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "NIGHT_VOYAGER_MIGRATION_DATABASE_URL" in compose
    assert "NIGHT_VOYAGER_DATABASE_URL" in compose
    assert "night_voyager_migrator" in compose
    assert "night_voyager_api" in compose
    assert "night_voyager_worker" in compose


def test_api_image_contains_alembic_configuration_and_migrations() -> None:
    dockerfile = (ROOT / "Dockerfile.api").read_text(encoding="utf-8")

    assert "COPY alembic.ini ./" in dockerfile
    assert "COPY migrations ./migrations" in dockerfile
    assert "COPY scripts ./scripts" in dockerfile
    assert "FROM builder AS db-test" in dockerfile
    assert "uv sync --locked" in dockerfile


def test_initial_migration_defines_forced_rls_and_restricted_auth_functions() -> None:
    migration = (ROOT / "migrations/versions/0001_identity_and_rls.py").read_text(encoding="utf-8")

    for table in ("organizations", "actors", "memberships"):
        assert f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY" in migration
        assert f"ALTER TABLE app.{table} FORCE ROW LEVEL SECURITY" in migration
        assert f"CREATE POLICY {table}_tenant_isolation" in migration
    for function in (
        "mint_demo_session",
        "resolve_demo_session",
        "rotate_demo_session",
        "revoke_demo_session",
    ):
        assert f"auth.{function}" in migration
        assert f"REVOKE ALL ON FUNCTION auth.{function}" in migration
        assert f"GRANT EXECUTE ON FUNCTION auth.{function}" in migration
    assert "SET search_path = pg_catalog, pg_temp" in migration
    assert "SECURITY DEFINER" in migration
    assert "auth.rotate_demo_session(bytea, bytea, text" in migration
    assert "auth.revoke_demo_session(bytea, bytea)" in migration
    assert "selected_session.csrf_digest <> p_old_csrf_digest" in migration
    assert "ERRCODE = 'NV001'" in migration
    assert "ERRCODE = 'NV002'" in migration
    assert "csrf_digest = p_csrf_digest" in migration


def test_release_verifier_exposes_database_catalog_gate() -> None:
    verifier = (ROOT / "scripts/verify_release.py").read_text(encoding="utf-8")

    assert '"--check-db-roles"' in verifier
    assert "verify_database_catalog" in verifier
    assert "relforcerowsecurity" in verifier
    assert "rolbypassrls" in verifier
    assert "prosecdef" in verifier
    assert "M3B_TABLES" in verifier
    assert "M4A_TABLES" in verifier
    assert "DRA_TABLES" in verifier
    assert "SKILL_TABLES" in verifier
    assert "load_governed_mixed_planning_snapshot" in verifier
    assert "expected_app_policy_count(alembic_revision)" in verifier


def test_release_verifier_freezes_the_exact_0014_timeline_catalog() -> None:
    verifier = runpy.run_path(str(ROOT / "scripts/verify_release.py"))
    timeline_tables = {
        "timeline_executions",
        "timeline_checkpoints",
        "timeline_checkpoint_attestations",
        "timeline_checkpoint_verifications",
        "timeline_reassessment_requests",
        "timeline_mutation_receipts",
    }
    timeline_function_identities = {
        ("read_plan_execution_context", "uuid, uuid, text, text"),
        ("read_timeline_execution", "uuid, uuid, text, uuid"),
        (
            "start_timeline_execution",
            "uuid, uuid, text, uuid, uuid, integer, uuid, uuid, text, text",
        ),
        (
            "attest_timeline_checkpoint",
            "uuid, uuid, text, uuid, uuid, uuid, integer, integer, text, text, text, "
            "text, uuid, uuid, text, text",
        ),
        (
            "verify_timeline_checkpoint",
            "uuid, uuid, text, uuid, uuid, uuid, uuid, integer, integer, text, text, "
            "uuid, uuid, text, text",
        ),
        (
            "request_timeline_reassessment",
            "uuid, uuid, text, uuid, uuid, uuid, uuid, integer, integer, text, uuid, "
            "uuid, text, text",
        ),
    }

    assert verifier["TIMELINE_EXECUTION_TABLES"] == timeline_tables
    assert (
        verifier["TIMELINE_EXECUTION_FUNCTION_IDENTITIES"]
        == timeline_function_identities
    )
    assert (
        verifier["TIMELINE_EXECUTION_API_FUNCTION_IDENTITIES"]
        == timeline_function_identities
    )
    assert verifier["TIMELINE_EXECUTION_WORKER_FUNCTION_IDENTITIES"] == set()
    assert verifier["expected_app_policy_count"]("0013") == 38
    assert verifier["expected_app_policy_count"]("0014") == 44
    assert verifier["expected_app_policy_count"]("0015") == 44


def test_0014_inherits_planning_revision_and_api_only_timeline_authority() -> None:
    verifier = runpy.run_path(str(ROOT / "scripts/verify_release.py"))

    assert verifier["PLANNING_REVISION_PENDING_REVISIONS"] == {
        "0012",
        "0013",
        "0014",
        "0015",
    }
    assert verifier["PLANNING_REVISION_SEED_REVISIONS"] == {
        "0013",
        "0014",
        "0015",
    }
    assert verifier["timeline_execution_function_identities"]("0013") == set()
    assert verifier["timeline_execution_function_identities"]("0014") == verifier[
        "TIMELINE_EXECUTION_FUNCTION_IDENTITIES"
    ]
    assert verifier["timeline_execution_function_identities"]("0015") == verifier[
        "TIMELINE_EXECUTION_FUNCTION_IDENTITIES"
    ]


def test_database_gate_requires_0010_head_and_isolated_migration_lanes() -> None:
    script = (ROOT / "scripts/run_db_tests.sh").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "inside-planning-start-migration" in script
    assert "tests/integration/tasks/test_planning_start_migration.py" in script
    assert 'run_lane "${BASE_PROJECT_NAME}-planning-start-migration"' in script
    assert "inside-dra-live-migration" in script
    assert "tests/integration/dra/test_dra_live_migration.py" in script
    assert 'run_lane "${BASE_PROJECT_NAME}-dra-live-migration"' in script
    assert "uv run alembic upgrade head" in script
    assert "uv run alembic current | grep '0010'" in script
    planning_lane = script.split(
        'if [ "${1:-}" = "inside-planning-start-migration" ]; then', 1
    )[1].split("fi", 1)[0]
    assert "uv run alembic current | grep '0009'" in planning_lane
    assert "fact-to-plan-db-check:" in makefile
    assert "scripts/run_db_tests.sh fact-to-plan" in makefile
    assert "scripts/run_db_tests.sh" in makefile.split("db-check:", 1)[1]


def test_release_verifier_includes_collaboration_roles_and_legacy_revocation() -> None:
    verifier = (ROOT / "scripts/verify_release.py").read_text(encoding="utf-8")

    for token in (
        "COLLABORATION_TABLES",
        "COLLABORATION_API_FUNCTIONS",
        "collaboration_runtime_grants",
        "collaboration_signatures",
        "seed_demo_collaboration",
        "public_execute",
        "api_execute",
        "worker_execute",
    ):
        assert token in verifier
    assert "runtime roles must not access collaboration authority tables" in verifier
    assert "legacy Case revision writer must not be executable by the API" in verifier
    assert "legacy Case transition must not be executable by runtime roles" in verifier
    assert "expected_app_policy_count(alembic_revision)" in verifier


def test_release_verifier_includes_skill_role_and_pin_authority() -> None:
    verifier = (ROOT / "scripts/verify_release.py").read_text(encoding="utf-8")

    for token in (
        "SKILL_TABLES",
        "SKILL_API_FUNCTIONS",
        "SKILL_WORKER_FUNCTIONS",
        "skill_runtime_grants",
        "skill_signatures",
        "seed_demo_skill_registry",
        "load_agent_task_skill_pin",
        "load_persisted_synthetic_planning_snapshot",
        "runtime roles must not access Skill authority tables",
        "Skill function grants violate API/worker separation",
        "five-field task pin catalog drift",
    ):
        assert token in verifier
