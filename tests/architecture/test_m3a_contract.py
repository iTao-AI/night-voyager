from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

M3A_TABLES = (
    "student_cases",
    "student_case_revisions",
    "source_packs",
    "source_pack_entries",
    "evidence_refs",
    "planning_runs",
    "planning_routes",
    "comparison_dimensions",
    "comparison_dimension_evidence_refs",
    "cost_evidence",
    "ranking_evidence",
)


def test_m3a_public_contract_records_exist() -> None:
    for relative in (
        "docs/decisions/0002-deterministic-planning-and-evidence-authority.md",
        "docs/superpowers/specs/2026-07-12-m3a-deterministic-planning-design.md",
        "docs/superpowers/plans/2026-07-12-m3a-deterministic-planning.md",
    ):
        assert (ROOT / relative).is_file(), relative


def test_migration_graph_is_exactly_0001_to_0002_with_eleven_tables() -> None:
    migrations = sorted((ROOT / "migrations/versions").glob("*.py"))
    assert [path.name for path in migrations] == [
        "0001_identity_and_rls.py",
        "0002_case_evidence_planning.py",
    ]
    tree = ast.parse(migrations[1].read_text(encoding="utf-8"))
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"revision", "down_revision"}
    }
    assert assignments == {"revision": "0002", "down_revision": "0001"}
    migration = migrations[1].read_text(encoding="utf-8")
    assert tuple(
        line.split("app.", 1)[1].split(" ", 1)[0]
        for line in migration.splitlines()
        if line.startswith("CREATE TABLE app.")
    ) == M3A_TABLES


def test_pure_planning_modules_do_not_import_framework_or_adapter_packages() -> None:
    forbidden = {"fastapi", "sqlalchemy", "asyncpg", "alembic"}
    pure_modules = ("models.py", "policy.py", "transitions.py", "hashing.py", "ports.py")
    for module in pure_modules:
        path = ROOT / "src/night_voyager/planning" / module
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            (node.module or "").split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        assert not (imported & forbidden), path


def test_m3a_excludes_later_authority_and_execution_artifacts() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "src/night_voyager").rglob("*.py")
    )
    for forbidden in ("AdvisorReview", "DecisionBrief", "FamilyDecision", "AgentTask"):
        assert forbidden not in source
