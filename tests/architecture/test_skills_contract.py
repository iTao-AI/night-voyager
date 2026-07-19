from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_skill_manifests_are_packaged_at_the_registry_resource_paths() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile.api").read_text(encoding="utf-8")

    assert (
        '"fixtures/skills/runtime-manifest-v1.json" = '
        '"night_voyager/skills/data/runtime-manifest-v1.json"'
    ) in pyproject
    assert (
        '"fixtures/skills/eval-manifest-v1.json" = '
        '"night_voyager/skills/data/eval-manifest-v1.json"'
    ) in pyproject
    assert not (ROOT / "src/night_voyager/skills/data").exists()
    assert "COPY fixtures/skills ./fixtures/skills" in dockerfile


def test_skills_database_runner_is_registered_and_isolated() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    runner_path = ROOT / "scripts/run_skill_db_tests.sh"

    assert "skills-db-check:" in makefile
    assert 'SUITE="$(SUITE)" sh scripts/run_skill_db_tests.sh' in makefile
    assert runner_path.is_file()

    runner = runner_path.read_text(encoding="utf-8")
    assert "catalog|worker|lifecycle" in runner
    assert "-o addopts='' -m database" in runner
    assert "docker compose --profile db-test run --rm --build" in runner
    assert "docker compose --profile db-test \\" in runner
    assert "down --volumes --remove-orphans" in runner
    assert "label=com.docker.compose.project=$active_project" in runner
    assert "docker volume ls --quiet" in runner
    assert "docker network ls --quiet" in runner
    assert "Skill database project was not empty after teardown" in runner
    assert "trap cleanup EXIT INT TERM" in runner
    assert "night-voyager-skills-db-check" in runner
    assert "uv run --no-editable python scripts/seed_demo.py" in runner
    legacy = runner.index("uv run alembic downgrade 0007")
    legacy_seed = runner.index("uv run --no-editable python scripts/seed_demo.py --without-skills")
    head = runner.index("uv run alembic upgrade head")
    assert legacy < legacy_seed < head


def test_skills_database_runner_freezes_the_approved_suite_map() -> None:
    runner = (ROOT / "scripts/run_skill_db_tests.sh").read_text(encoding="utf-8")

    catalog = (
        "tests/security/test_skills_catalog.py",
        "tests/integration/skills/test_postgres_skills.py",
        "tests/integration/skills/test_skill_downgrade.py",
        "tests/integration/skills/test_persisted_planning_materialization.py",
        "tests/unit/identity/test_seed_demo.py",
    )
    worker = (
        "tests/integration/skills/test_task_pins.py",
        "tests/integration/skills/test_persisted_planning_materialization.py",
        "tests/integration/connected_demo/test_postgres_read_models.py",
        "tests/integration/tasks/test_http_tasks.py",
        "tests/integration/tasks/test_postgres_tasks.py",
        "tests/integration/tasks/test_sse.py",
        "tests/integration/tasks/test_worker.py",
        "tests/integration/tasks/test_worker_authority.py",
        "tests/integration/tasks/test_worker_capacity.py",
        "tests/integration/tasks/test_mixed_downgrade.py",
    )
    lifecycle = (
        "tests/integration/skills/test_skill_lifecycle.py",
        "tests/integration/skills/test_http_skills.py",
        "tests/integration/skills/test_persisted_planning_materialization.py",
        "tests/integration/skills/test_postgres_skills.py",
        "tests/integration/skills/test_skill_downgrade.py",
    )

    for suite_name, paths in (
        ("catalog", catalog),
        ("worker", worker),
        ("lifecycle", lifecycle),
    ):
        marker = f"{suite_name})"
        assert marker in runner
        for path in paths:
            assert path in runner, (suite_name, path)


def test_required_db_gate_runs_fresh_head_seed_replay_regressions() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    compose_job = workflow.split("  compose:", maxsplit=1)[1]
    assert "make db-check" in compose_job

    runner = (ROOT / "scripts/run_db_tests.sh").read_text(encoding="utf-8")
    assert "inside-skill-seed-replay" in runner
    assert "NIGHT_VOYAGER_SKILL_SEED_PATH=fresh_head" in runner
    expected_tests = (
        "test_fresh_head_seed_creates_exact_pinned_active_task_fixture",
        "test_pinned_seed_replay_rejects_task_projection_drift_atomically",
        "test_pinned_helper_rejects_extra_event_without_partial_history",
        "test_pinned_seed_replay_rejects_missing_event_without_repair",
        "test_legacy_seed_replay_rejects_missing_event_without_repair",
        "test_pinned_helper_rejects_execution_residue_without_partial_history",
        "test_pinned_helper_rejects_dispatch_residue_without_partial_history",
        "test_seed_replay_preserves_only_exact_all_null_legacy_task",
        "test_seed_replay_rejects_all_null_legacy_projection_drift",
        "test_seed_replay_rejects_partial_pin_classification",
        "test_pinned_active_task_seed_mismatch_has_no_partial_task_or_event",
    )
    replay_lane = runner.split(
        'if [ "${1:-}" = "inside-skill-seed-replay" ]; then', maxsplit=1
    )[1].split("    exit 0", maxsplit=1)[0]
    routed_tests = tuple(
        line.rsplit("::", maxsplit=1)[1].removesuffix(" \\")
        for line in replay_lane.splitlines()
        if "tests/integration/skills/test_postgres_skills.py::" in line
    )
    assert routed_tests == expected_tests


def test_skills_database_runner_rejects_unknown_suite_before_docker() -> None:
    runner = (ROOT / "scripts/run_skill_db_tests.sh").read_text(encoding="utf-8")

    validation = runner.index('case "$suite" in')
    docker = runner.index("docker compose")
    assert validation < docker
    assert "unknown Skill database suite" in runner


def test_skills_offline_lane_and_ci_routing_are_registered() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "skills-check:" in makefile
    lane = makefile[makefile.index("skills-check:") : makefile.index("mke-doctor:")]
    for path in (
        "tests/unit/skills",
        "tests/unit/identity/test_seed_demo.py",
        "tests/contracts/test_skill_runtime_registry.py",
        "tests/architecture/test_skills_contract.py",
        "tests/unit/test_release_surface.py",
        "tests/security/test_database_catalog.py",
    ):
        assert path in lane
    assert "-m database" not in lane
    assert workflow.count("make skills-check") == 1
    python_job = workflow[workflow.index("  python:") : workflow.index("  frontend:")]
    assert "make skills-check" in python_job


def test_versioned_skill_public_contract_is_accepted_and_discoverable() -> None:
    required = (
        "docs/decisions/0009-versioned-skill-runtime-pinning.md",
        "docs/reference/versioned-skills-and-runtime-pins.md",
        "docs/operations/skill-governance.md",
    )
    assert all((ROOT / relative).is_file() for relative in required)

    adr = (ROOT / required[0]).read_text(encoding="utf-8")
    docs_index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    readmes = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8") for relative in ("README.md", "README_CN.md")
    )
    assert "- Status: Accepted" in adr
    assert "Implementation status: Implemented by migration `0008`" in adr
    assert "versioned-skills-and-runtime-pins.md" in docs_index
    assert "skill-governance.md" in docs_index
    assert "0009-versioned-skill-runtime-pinning.md" in docs_index
    assert "PR B" in readmes and "implemented" in readmes and "已实现" in readmes
    assert "PR C" in readmes and "deferred" in readmes


def test_versioned_skill_reference_freezes_runtime_and_pin_boundaries() -> None:
    reference = (ROOT / "docs/reference/versioned-skills-and-runtime-pins.md").read_text(
        encoding="utf-8"
    )
    http = (ROOT / "docs/reference/http-api-v1.md").read_text(encoding="utf-8")
    tasks = (ROOT / "docs/reference/agent-tasks-and-events.md").read_text(encoding="utf-8")

    for token in (
        "student-profile-intake",
        "study-destination-compare",
        "evidence-research",
        "document-evidence-retrieval",
        "family-decision-brief",
        "application-timeline-guard",
        "five-field pin",
        "catalog_only",
        "planning_runtime",
        "legacy_unpinned",
    ):
        assert token in reference
    for path in (
        "/api/v1/skills",
        "/api/v1/skills/{skill_key}",
        "/api/v1/skills/{skill_key}/change-candidates",
        "/api/v1/skill-change-candidates/{candidate_id}/evaluations",
        "/api/v1/skill-change-candidates/{candidate_id}/activations",
        "/api/v1/skills/{skill_key}/rollbacks",
        "/api/v1/cases/{case_id}/planning-skill-inspector",
    ):
        assert path in http
    for field in (
        "skill_definition_id",
        "skill_version_id",
        "skill_activation_event_id",
        "skill_activation_sequence",
        "runtime_binding_sha256",
        "{request, five_field_pin}",
        "skill_pin_invalid",
    ):
        assert field in tasks


def test_versioned_skill_plan_and_design_status_match_implementation() -> None:
    spec = (
        ROOT / "docs/superpowers/specs/2026-07-16-governed-collaboration-core-design.md"
    ).read_text(encoding="utf-8")
    plan = (
        ROOT / "docs/superpowers/plans/2026-07-16-versioned-skill-runtime-pinning.md"
    ).read_text(encoding="utf-8")

    assert "PR A and PR B are implemented" in spec
    assert "PR C has not started" in spec
    assert "**Implementation status:** Implemented locally" in plan
    assert "FastAPI 0.139.2" in plan
    assert "fastapi>=0.139,<0.140" in plan
