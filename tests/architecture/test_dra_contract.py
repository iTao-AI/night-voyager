from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_dra_consumer_is_product_owned_and_fixture_bounded() -> None:
    expected = (
        "src/night_voyager/dra/models.py",
        "src/night_voyager/dra/fixtures.py",
        "src/night_voyager/dra/live_models.py",
        "fixtures/dra/downstream-consumer-contract-v1.json",
        "fixtures/dra/live-closure-scenario-v1.json",
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
        assert f"import {forbidden}" not in source.lower()
        assert f"from {forbidden}" not in source.lower()


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
    for node in (
        "tests/contracts/test_dra_live_models.py",
        "tests/contracts/test_dra_live_projection.py",
        "tests/contracts/test_dra_transport.py",
        "tests/unit/dra/test_live_evaluation.py",
    ):
        assert node in makefile
    assert "make dra-check" in workflow
    assert "DRA_LIVE_PROOF_ACK" not in workflow
    assert "dra-consumer-proof" not in workflow


def test_required_dra_lane_includes_provider_free_live_capture_rehearsal() -> None:
    makefile = (ROOT / "Makefile").read_text()
    script = (ROOT / "scripts/verify_dra_live_closure.py")
    assert script.is_file()
    assert "scripts/run_dra_lane.sh rehearse" in makefile
    assert "verify_dra_live_closure.py rehearse-capture" in (
        ROOT / "scripts/run_dra_lane.sh"
    ).read_text()
    assert "capture-live" not in (
        ROOT / ".github/workflows/ci.yml"
    ).read_text()


def test_live_contracts_are_provider_free_and_content_bounded() -> None:
    live_models = (ROOT / "src/night_voyager/dra/live_models.py").read_text()
    scenario = (ROOT / "fixtures/dra/live-closure-scenario-v1.json").read_text()
    assert "httpx" not in live_models
    assert "DECISION_RESEARCH_AGENT_API_KEY" not in scenario
    assert '"content"' not in scenario
    assert '"provider_payload"' not in scenario


def test_dra_live_foundation_is_release_verified_without_live_execution() -> None:
    verifier = (ROOT / "scripts/verify_release.py").read_text()
    governed_flow = (ROOT / "scripts/verify_dra_governed_flow.py").read_text()
    fixture_verifier = (ROOT / "scripts/verify_dra_consumer.py").read_text()
    for required in (
        "migrations/versions/0010_dra_v0_1_6_live_consumer.py",
        "src/night_voyager/dra/live_projection.py",
        "src/night_voyager/dra/live_evaluation.py",
        "src/night_voyager/dra/live_outcome.py",
        "src/night_voyager/dra/live_outcome_postgres.py",
        "docs/decisions/0011-dra-v0-1-6-live-consumer-boundary.md",
    ):
        assert required in verifier
    assert "build_v0_1_6_scenario_candidate_import" in governed_flow
    assert "build_fixture_candidate_import" not in governed_flow
    assert "load_dra_fixture" in fixture_verifier
    assert "verify_dra_consumer.py fixture --json" in (
        ROOT / "Makefile"
    ).read_text()


def test_dra_candidate_freeze_is_executable_and_live_lane_stays_optional() -> None:
    cli = (ROOT / "scripts/verify_dra_live_closure.py").read_text()
    makefile = (ROOT / "Makefile").read_text()
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    for required in (
        '"freeze-candidate"',
        "INCOMPLETE_PENDING_LIVE_ACCEPTANCE",
        "required_hosted_checks",
        "docker_inventory_sha256",
        "authorization_placeholder",
    ):
        assert required in cli
    assert "dra-consumer-proof" not in workflow
    assert "make dra-check" in workflow
    assert "dra-consumer-proof:" in makefile


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
    assert (
        "existing connected synthetic `/demo` remains unchanged by DRA integration"
        in docs_index
    )
    assert "make compose-proof" in operations
    assert "Live provider proof was not run" in operations
