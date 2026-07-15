from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_dra_consumer_is_product_owned_and_fixture_bounded() -> None:
    expected = (
        "src/night_voyager/dra/models.py",
        "src/night_voyager/dra/fixtures.py",
        "fixtures/dra/downstream-consumer-contract-v1.json",
        "fixtures/dra/manifest.json",
        "fixtures/dra/sources/australia-program-fit.html",
    )
    assert all((ROOT / relative).is_file() for relative in expected)


def test_dra_consumer_does_not_import_agent_frameworks_or_runtime() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "src/night_voyager/dra").glob("*.py")
    )
    for forbidden in (
        "decision_research_agent",
        "langchain",
        "langgraph",
        "deepagents",
        "langsmith",
    ):
        assert forbidden not in source.lower()


def test_dra_migration_is_seed_free_and_proof_case_is_external() -> None:
    migration = (ROOT / "migrations/versions/0005_dra_candidate_promotion.py").read_text()
    proof_seed = (ROOT / "scripts/seed_dra_proof.py").read_text()
    assert "40000000-0000-0000-0000-000000000003" not in migration
    assert "DRA_PROOF_CASE_ID" in proof_seed
    assert "seed_dra_proof.py" not in migration


def test_required_dra_lane_is_fixture_only() -> None:
    makefile = (ROOT / "Makefile").read_text()
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "verify_dra_consumer.py fixture --json" in makefile
    assert "make dra-check" in workflow
    assert "DRA_LIVE_PROOF_ACK" not in workflow


def test_governed_mixed_planning_public_contract_is_closed() -> None:
    readme = (ROOT / "README.md").read_text()
    docs_index = (ROOT / "docs/README.md").read_text()
    reference = (ROOT / "docs/reference/dra-governed-evidence.md").read_text()
    operations = (ROOT / "docs/operations/dra-consumer-proof.md").read_text()

    for required in (
        "generate_governed_mixed_planning_run_v1",
        "australia_program_fit -> program_fit -> externally_verified",
        "exact copies of the synthetic baseline",
        "generate_planning_run_v1",
    ):
        assert required in reference
    assert "governed mixed PlanningRun generation is implemented" in readme
    assert "existing v0.1.0 synthetic `/demo` remains unchanged" in docs_index
    assert "make compose-proof" in operations
    assert "Live provider proof was not run" in operations
