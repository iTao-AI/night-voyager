from __future__ import annotations

from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2] / "migrations/versions/0002_case_evidence_planning.py"
).read_text(encoding="utf-8")


def test_every_m3a_table_has_forced_rls_and_explicit_policy() -> None:
    tables = tuple(
        line.split("app.", 1)[1].split(" ", 1)[0]
        for line in MIGRATION.splitlines()
        if line.startswith("CREATE TABLE app.")
    )
    assert len(tables) == 11
    for table in tables:
        assert f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY" in MIGRATION
        assert f"ALTER TABLE app.{table} FORCE ROW LEVEL SECURITY" in MIGRATION
        assert f"CREATE POLICY {table}_tenant_isolation" in MIGRATION


def test_runtime_mutation_is_function_only() -> None:
    assert "GRANT INSERT ON app." not in MIGRATION
    assert "GRANT UPDATE (" not in MIGRATION
    assert "GRANT DELETE" not in MIGRATION
    for function in (
        "publish_case_revision",
        "transition_case",
        "persist_source_pack",
        "persist_evidence_ref",
        "persist_planning_result",
    ):
        assert f"FUNCTION app.{function}" in MIGRATION
        assert f"REVOKE ALL ON FUNCTION app.{function}" in MIGRATION
        assert f"GRANT EXECUTE ON FUNCTION app.{function}" in MIGRATION
    assert "SECURITY DEFINER SET search_path = pg_catalog, pg_temp" in MIGRATION


def test_terminal_and_provenance_guards_are_database_enforced() -> None:
    assert "CREATE TRIGGER planning_runs_transition_guard" in MIGRATION
    assert "CREATE TRIGGER planning_routes_terminal_guard" in MIGRATION
    assert "CREATE TRIGGER comparison_dimensions_terminal_guard" in MIGRATION
    assert "CREATE TRIGGER comparison_links_terminal_guard" in MIGRATION
    assert "CREATE TRIGGER cost_evidence_terminal_guard" in MIGRATION
    assert "CREATE TRIGGER ranking_evidence_terminal_guard" in MIGRATION
    assert "CREATE TRIGGER evidence_refs_provenance_guard" in MIGRATION
    assert "CREATE TRIGGER student_cases_current_revision_guard" in MIGRATION
    assert "CREATE TRIGGER student_cases_state_guard" in MIGRATION
    assert "CREATE TRIGGER planning_runs_handoff" in MIGRATION
    assert "NEW.state='review_required' AND NEW.is_current" in MIGRATION
    assert "CREATE TRIGGER cost_evidence_provenance_guard" in MIGRATION
    assert "CREATE TRIGGER ranking_evidence_provenance_guard" in MIGRATION
    assert "evidence_role" in MIGRATION
    assert "source_sha256" in MIGRATION and "entry.sha256" in MIGRATION


def test_planning_run_pins_policy_inputs_hashes_and_currentness() -> None:
    for column in (
        "policy_version",
        "evidence_projection_sha256",
        "output_sha256",
        "supersedes_run_id",
        "is_current",
    ):
        assert column in MIGRATION
