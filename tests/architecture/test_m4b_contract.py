from __future__ import annotations

import ast
import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[2]

MKE_ARTIFACT_TESTS = {
    "tests/unit/evidence_loop/test_cli_contracts.py": {
        "test_development_cli_emits_canonical_receipt",
        "test_development_cli_persists_each_terminal_disposition",
        "test_development_cli_completes_the_a4_failure_taxonomy",
    },
    "tests/unit/evidence_loop/test_freeze.py": {
        "test_pre_registration_binds_complete_public_freeze_boundary",
        "test_pre_registration_rejects_post_reveal_checkout",
        "test_pre_registration_rejects_governed_baseline_hash_drift",
        "test_pre_registration_rejects_setup_provider_peer_drift",
        "test_runtime_identity_is_enforced_not_only_recorded",
    },
    "tests/integration/evidence_loop/test_frozen_suite.py": {
        "test_three_fresh_development_processes_are_byte_identical",
    },
}


def _mke_marked_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    marked: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Attribute)
                and decorator.attr == "mke"
                and isinstance(decorator.value, ast.Attribute)
                and decorator.value.attr == "mark"
            ):
                marked.add(node.name)
    return marked


def test_sdist_excludes_only_task_local_tmp_boundary() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    sdist = pyproject["tool"]["hatch"]["build"]["targets"]["sdist"]
    assert sdist["exclude"] == ["/tmp"]


def test_task_local_native_evidence_tests_are_explicitly_mke_marked() -> None:
    for relative, expected in MKE_ARTIFACT_TESTS.items():
        marked = _mke_marked_functions(ROOT / relative)
        assert expected <= marked, (relative, sorted(expected - marked))


def test_pytest_and_default_lanes_exclude_optional_mke() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pytest_config = pyproject["tool"]["pytest"]["ini_options"]
    assert pytest_config["addopts"] == '-m "not database and not mke"'
    assert set(pytest_config["markers"]) == {
        "database: requires disposable PostgreSQL 18 roles",
        "mke: requires the optional MKE/MCP process extra",
    }
    assert pyproject["project"]["optional-dependencies"]["mke"] == ["mcp>=1.28.1,<2"]
    assert set(pyproject["tool"]["pyright"]["exclude"]) == {
        "src/night_voyager/adapters/mke_readonly.py",
        "tests/fixtures/m4b/fake_mke_server.py",
        "tests/integration/adapters/test_mke_candidate_wheel.py",
        "tests/integration/adapters/test_mke_readonly_smoke.py",
    }

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    default_check = makefile.split("\ncheck: ##", 1)[1].split("\n\n", 1)[0]
    assert '-m "not database and not mke"' in default_check
    assert "mke-check" not in default_check
    assert "mke-consumer-proof" not in default_check


def test_make_exposes_only_explicit_mke_gates() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    expected = {
        "mke-doctor": "verify_mke_consumer.py doctor",
        "mke-artifact-check": "verify_mke_consumer.py artifact-check",
        "mke-check": "scripts/run_mke_lane.sh test",
        "mke-consumer-proof": "scripts/run_mke_lane.sh proof",
    }
    for target, command in expected.items():
        body = makefile.split(f"\n{target}:", 1)[1].split("\n\n", 1)[0]
        assert command in body


def test_python_ci_has_artifact_free_optional_process_step() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    python_job = workflow.split("  python:", 1)[1].split("  frontend:", 1)[0]
    assert "uv sync --locked --extra mke" in python_job
    assert 'uv run pytest -q -m "not database and not mke"' in python_job
    assert (
        "scripts/run_mke_lane.sh test tests/integration/adapters/test_mke_readonly_smoke.py"
        in python_job
    )
    for forbidden in (
        "MKE_WHEEL",
        "MKE_RECEIPT",
        "candidate-artifact-receipt",
        "actions/download-artifact",
        "multimodal-knowledge-engine",
    ):
        assert forbidden not in python_job


def test_m4b_remains_outside_compose_migrations_and_m4a_runtime() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8").lower()
    assert "mke" not in compose
    migration_texts = {
        path.name: path.read_text(encoding="utf-8")
        for path in (ROOT / "migrations" / "versions").glob("*.py")
    }
    skill_seed_line = next(
        line
        for line in migration_texts["0008_versioned_skills.py"].splitlines()
        if line.startswith("CANONICAL_DEMO_SKILL_SEED = ")
    )
    skill_seed = json.loads(ast.literal_eval(skill_seed_line.split("=", 1)[1].strip()))
    document_skill = next(
        entry
        for entry in skill_seed["entries"]
        if entry["manifest"]["skill_key"] == "document-evidence-retrieval"
    )
    assert document_skill["manifest"]["binding_kind"] == "catalog_only"
    assert document_skill["manifest"]["tool_ids"] == ["mke_readonly"]
    migrations = "\n".join(
        line.lower()
        for content in migration_texts.values()
        for line in content.splitlines()
        if not line.startswith("CANONICAL_DEMO_SKILL_SEED = ")
    )
    assert "mke" not in migrations
    runtime_paths = [
        ROOT / "src/night_voyager/api.py",
        ROOT / "src/night_voyager/worker.py",
        *(ROOT / "src/night_voyager/tasks").glob("*.py"),
        *(ROOT / "src/night_voyager/interfaces/http").glob("*.py"),
    ]
    for path in runtime_paths:
        assert "mke" not in path.read_text(encoding="utf-8").lower(), path


def test_pure_boundary_has_no_optional_sdk_import_and_public_records_exist() -> None:
    for path in (ROOT / "src/night_voyager/evidence").glob("*.py"):
        content = path.read_text(encoding="utf-8")
        assert "import mcp" not in content
        assert "from mcp" not in content
    for relative in (
        "docs/decisions/0005-mke-readonly-evidence-boundary.md",
        "docs/superpowers/specs/2026-07-13-m4b-mke-readonly-consumer-design.md",
        "docs/superpowers/plans/2026-07-13-m4b-mke-readonly-consumer.md",
        "fixtures/m4b/candidate-artifact-lock.json",
        "fixtures/m4b/manifest.json",
    ):
        assert (ROOT / relative).is_file(), relative


def test_m4b_documentation_routes_roles_and_preserves_authority_boundary() -> None:
    index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    reference = (ROOT / "docs/reference/mke-readonly-consumer.md").read_text(
        encoding="utf-8"
    )
    runbook = (ROOT / "docs/operations/mke-candidate-proof.md").read_text(
        encoding="utf-8"
    )
    for text in (index, reference, runbook):
        assert "UNTRUSTED_CANDIDATE" in text
        assert "read-only" in text
        assert "synthetic" in text
        assert "PlanningAdapter" in text
    assert "Evaluators do not need MKE" in index
    assert "make mke-check" in index
    assert "make mke-artifact-check" in index
    assert "make mke-consumer-proof" in index

    quick_path = runbook.split("## Quick path", 1)[1].split("##", 1)[0]
    assert len([line for line in quick_path.splitlines() if line.startswith("make ")]) == 4
    assert "MKE_WHEEL=" in quick_path
    assert "operator_supplied" in runbook
    assert "Do not rebuild" in runbook
    assert "stop" in runbook.lower()
    failure_codes = {
        line.strip().strip('",')
        for line in (ROOT / "src/night_voyager/evidence/mke_models.py")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip().startswith('"mke_')
    }
    assert failure_codes
    assert all(code in runbook for code in failure_codes)


def test_bilingual_readme_m4b_boundary_is_in_parity() -> None:
    for relative in ("README.md", "README_CN.md"):
        content = (ROOT / relative).read_text(encoding="utf-8")
        for token in (
            "M4B",
            "MKE",
            "optional",
            "read-only",
            "synthetic",
            "UNTRUSTED_CANDIDATE",
            "make mke-check",
            "docs/operations/mke-candidate-proof.md",
        ):
            assert token in content, (relative, token)
