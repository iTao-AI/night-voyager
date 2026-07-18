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
    assert "docker compose --profile db-test down --volumes --remove-orphans" in runner
    assert "trap cleanup EXIT INT TERM" in runner
    assert "night-voyager-skills-db-check" in runner
    assert "uv run --no-editable python scripts/seed_demo.py" in runner


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


def test_skills_database_runner_rejects_unknown_suite_before_docker() -> None:
    runner = (ROOT / "scripts/run_skill_db_tests.sh").read_text(encoding="utf-8")

    validation = runner.index('case "$suite" in')
    docker = runner.index("docker compose")
    assert validation < docker
    assert "unknown Skill database suite" in runner
