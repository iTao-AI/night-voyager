from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "migrations/versions/0003_advisor_family_decision.py"
).read_text(encoding="utf-8")

TABLES = (
    "student_case_participants",
    "advisor_reviews",
    "evidence_risk_acceptances",
    "decision_briefs",
    "family_decisions",
    "timeline_plans",
    "audit_events",
    "idempotency_records",
)


def test_every_m3b_table_has_forced_rls_and_tenant_policy() -> None:
    for table in TABLES:
        assert f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY" in MIGRATION
        assert f"ALTER TABLE app.{table} FORCE ROW LEVEL SECURITY" in MIGRATION
        assert f"CREATE POLICY {table}_tenant_isolation" in MIGRATION
        assert "organization_id uuid NOT NULL" in MIGRATION


def test_runtime_authority_is_only_narrow_functions() -> None:
    assert "GRANT INSERT ON app." not in MIGRATION
    assert "GRANT UPDATE ON app." not in MIGRATION
    assert "GRANT DELETE" not in MIGRATION
    for function in ("seed_case_participants", "review_planning_run", "decide_family_brief"):
        assert f"FUNCTION app.{function}" in MIGRATION
        assert f"REVOKE ALL ON FUNCTION app.{function}" in MIGRATION
        assert f"GRANT EXECUTE ON FUNCTION app.{function}" in MIGRATION
    assert "TO night_voyager_worker" not in "\n".join(
        line for line in MIGRATION.splitlines() if "GRANT EXECUTE" in line
    )
    assert "SECURITY DEFINER SET search_path = pg_catalog, pg_temp" in MIGRATION


def test_authority_guards_are_append_only_and_typed() -> None:
    assert "CREATE TRIGGER advisor_reviews_immutable" in MIGRATION
    assert "CREATE TRIGGER decision_briefs_immutable" in MIGRATION
    assert "CREATE TRIGGER family_decisions_immutable" in MIGRATION
    assert "CREATE TRIGGER timeline_plans_immutable" in MIGRATION
    assert "CREATE TRIGGER audit_events_immutable" in MIGRATION
    for sqlstate in ("NV003", "NV006", "NV007", "NV008"):
        assert f"ERRCODE='{sqlstate}'" in MIGRATION
    assert "CREATE UNIQUE INDEX decision_briefs_one_current" in MIGRATION
    assert "CREATE UNIQUE INDEX family_decisions_one_per_brief" in MIGRATION


def test_m3b_downgrade_restores_m3a_case_states_and_drops_only_m3b() -> None:
    assert "DROP CONSTRAINT student_cases_state_check" in MIGRATION
    assert "CHECK (state IN ('intake','planning','advisor_review'))" in MIGRATION
    assert "DROP TABLE app.organizations" not in MIGRATION
    assert "DROP TABLE app.planning_runs" not in MIGRATION
