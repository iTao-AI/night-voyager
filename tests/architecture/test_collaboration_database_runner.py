from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_make_exposes_the_bounded_collaboration_database_runner() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "collaboration-db-check:" in makefile
    assert 'SUITE="$(SUITE)" scripts/run_collaboration_db_tests.sh' in makefile


def test_collaboration_database_runner_is_disposable_and_suite_bounded() -> None:
    source = (ROOT / "scripts/run_collaboration_db_tests.sh").read_text(
        encoding="utf-8"
    )
    for suite in ("repository", "http", "authority"):
        assert suite in source
    assert source.index("unknown collaboration database suite") < source.index(
        "docker compose"
    )
    assert "PYTEST_ADDOPTS=" in source
    assert "-m database" in source
    assert "uv run --no-editable python scripts/seed_demo.py" in source
    assert "PYTEST_ADDOPTS= uv run --no-editable pytest" in source
    assert source.count(
        "uv run --no-editable python scripts/seed_demo.py \\\n"
        "                --without-skills --without-planning-revision "
        "--without-plan-execution"
    ) == 2
    assert source.count("down --volumes --remove-orphans --rmi local") == 2


def test_0007_skill_migration_parity_seed_excludes_revision_fixtures() -> None:
    source = (
        ROOT / "tests/integration/skills/test_skill_migration_parity.py"
    ).read_text(encoding="utf-8")
    seed_helper = source[
        source.index("def _seed_0007_demo()") : source.index(
            "\n\nasync def _function_definition"
        )
    ]
    assert '"--without-skills",' in seed_helper
    assert '"--without-planning-revision",' in seed_helper
    assert '"--without-plan-execution",' in seed_helper


def test_collaboration_historical_seeds_explicitly_exclude_plan_execution() -> None:
    source = (ROOT / "scripts/run_collaboration_db_tests.sh").read_text(
        encoding="utf-8"
    )
    revision_lane = source[
        source.index('if [ "$mode" = "inside-revision" ]') :
        source.index('case "$suite" in')
    ]
    assert revision_lane.count(
        "scripts/seed_demo.py --without-planning-revision "
        "--without-plan-execution"
    ) == 2

    legacy_seed = (
        "uv run --no-editable python scripts/seed_demo.py \\\n"
        "                --without-skills --without-planning-revision "
        "--without-plan-execution"
    )
    assert source.count(legacy_seed) == 2
    assert source.count("--without-plan-execution") == 4

    for suite_name in ("http", "authority"):
        lane = source[
            source.index(f"        {suite_name})") :
        ]
        lane = lane.split("            ;;", maxsplit=1)[0]
        head = lane.index("uv run alembic upgrade head")
        full_seed = lane[head:]
        assert "--without-plan-execution" not in full_seed


def test_required_local_and_hosted_gates_execute_the_authority_suite() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    check_target = makefile.split("\ncheck:", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]
    assert "$(MAKE) collaboration-db-check SUITE=authority" in check_target

    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    compose_job = workflow.split("  compose:", maxsplit=1)[1]
    assert "make collaboration-db-check SUITE=authority" in compose_job
