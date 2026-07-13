from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
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


def test_m3b_public_records_exist() -> None:
    for relative in (
        "docs/decisions/0003-advisor-family-decision-authority.md",
        "docs/superpowers/specs/2026-07-13-m3b-advisor-family-decision-design.md",
        "docs/superpowers/plans/2026-07-13-m3b-advisor-family-decision.md",
    ):
        assert (ROOT / relative).is_file()


def test_m3b_migration_remains_0003_with_exact_tables() -> None:
    migrations = sorted((ROOT / "migrations/versions").glob("*.py"))
    assert [path.name for path in migrations[:3]] == [
        "0001_identity_and_rls.py",
        "0002_case_evidence_planning.py",
        "0003_advisor_family_decision.py",
    ]
    tree = ast.parse(migrations[2].read_text(encoding="utf-8"))
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"revision", "down_revision"}
    }
    assert assignments == {"revision": "0003", "down_revision": "0002"}
    source = migrations[2].read_text(encoding="utf-8")
    assert tuple(
        line.split("app.", 1)[1].split(" ", 1)[0]
        for line in source.splitlines()
        if line.startswith("CREATE TABLE app.")
    ) == TABLES


def test_pure_decision_modules_do_not_import_frameworks() -> None:
    forbidden = {"fastapi", "sqlalchemy", "asyncpg", "alembic"}
    for module in ("models.py", "policy.py", "hashing.py"):
        path = ROOT / "src/night_voyager/decision" / module
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            (node.module or "").split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        assert not imports & forbidden
