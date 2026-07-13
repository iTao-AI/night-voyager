from __future__ import annotations

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
    migration = (ROOT / "migrations/versions/0001_identity_and_rls.py").read_text(
        encoding="utf-8"
    )

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
    assert "policy_count != 25" in verifier
