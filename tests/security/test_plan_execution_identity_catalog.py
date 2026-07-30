from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations/versions/0015_plan_execution_demo_identity.py"


def test_0015_is_identity_only_and_keeps_a_closed_principal_allowlist() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "0015"' in source
    assert 'down_revision = "0014"' in source
    assert "CREATE TABLE" not in source
    assert "app.timeline_" not in source
    assert "CREATE OR REPLACE FUNCTION auth.rotate_demo_session" in source
    for demo_key in (
        "advisor",
        "student",
        "parent",
        "plan_execution_happy_advisor",
        "plan_execution_happy_student",
        "plan_execution_happy_parent",
        "plan_execution_blocked_advisor",
        "plan_execution_blocked_student",
        "plan_execution_blocked_parent",
    ):
        assert f"'{demo_key}'" in source
    for forbidden in (" LIKE ", " SIMILAR TO ", "CREATE POLICY", "night_voyager_worker"):
        assert forbidden not in source


def test_0015_rotation_checks_scope_before_revoking_the_old_session() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    scope_check = source.index("old_scope IS DISTINCT FROM new_scope")
    revoke = source.index("UPDATE auth.demo_sessions SET revoked_at")
    assert scope_check < revoke
    assert "ERRCODE = 'NV002'" in source
    assert "SECURITY DEFINER SET search_path = pg_catalog, pg_temp" in source
    assert "GRANT EXECUTE ON FUNCTION" in source
    assert "TO night_voyager_api" in source
    assert "0015 plan execution demo identity exists" in source
