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
    assert "ENABLE ROW LEVEL SECURITY" in MIGRATION
    assert "FORCE ROW LEVEL SECURITY" in MIGRATION
    assert "CREATE POLICY" in MIGRATION


def test_worker_has_no_write_and_api_has_only_column_updates() -> None:
    assert "TO night_voyager_worker" not in "\n".join(
        line for line in MIGRATION.splitlines() if "GRANT INSERT" in line or "GRANT UPDATE" in line
    )
    assert "GRANT UPDATE (current_revision)" in MIGRATION
    assert "GRANT UPDATE (state, reason_code, output_sha256)" in MIGRATION
    assert "GRANT DELETE" not in MIGRATION
