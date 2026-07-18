#!/bin/sh
set -eu

mode=${1:-outside}
suite=${SUITE:-${2:-}}

case "$suite" in
    catalog|worker|lifecycle) ;;
    *)
        echo "unknown Skill database suite: ${suite:-<missing>}" >&2
        exit 2
        ;;
esac

if [ "$mode" = "inside" ]; then
    case "$suite" in
        catalog)
            echo "Skill database suite: catalog"
            PYTEST_ADDOPTS= uv run pytest -q \
                tests/security/test_skills_catalog.py \
                tests/unit/identity/test_seed_demo.py
            PYTEST_ADDOPTS= uv run pytest -q -o addopts='' -m database \
                tests/integration/skills/test_postgres_skills.py \
                tests/integration/skills/test_skill_downgrade.py \
                tests/integration/skills/test_persisted_planning_materialization.py
            ;;
        worker)
            echo "Skill database suite: worker"
            PYTEST_ADDOPTS= uv run pytest -q -o addopts='' -m database \
                tests/integration/skills/test_task_pins.py \
                tests/integration/skills/test_persisted_planning_materialization.py \
                tests/integration/connected_demo/test_postgres_read_models.py \
                tests/integration/tasks/test_http_tasks.py \
                tests/integration/tasks/test_postgres_tasks.py \
                tests/integration/tasks/test_sse.py \
                tests/integration/tasks/test_worker.py \
                tests/integration/tasks/test_worker_authority.py \
                tests/integration/tasks/test_worker_capacity.py \
                tests/integration/tasks/test_mixed_downgrade.py
            ;;
        lifecycle)
            echo "Skill database suite: lifecycle"
            PYTEST_ADDOPTS= uv run pytest -q -o addopts='' -m database \
                tests/integration/skills/test_skill_lifecycle.py \
                tests/integration/skills/test_http_skills.py \
                tests/integration/skills/test_persisted_planning_materialization.py \
                tests/integration/skills/test_postgres_skills.py \
                tests/integration/skills/test_skill_downgrade.py
            ;;
    esac
    exit 0
fi

base_project=${COMPOSE_PROJECT_NAME:-night-voyager-skills-db-check-$$}
active_project=

cleanup() {
    if [ -n "$active_project" ]; then
        COMPOSE_PROJECT_NAME="$active_project" docker compose --profile db-test \
            down --volumes --remove-orphans
    fi
}
trap cleanup EXIT INT TERM

active_project="${base_project}-${suite}"
export COMPOSE_PROJECT_NAME="$active_project"
docker compose --profile db-test config --quiet
docker compose --profile db-test run --rm --build db-test \
    sh scripts/run_skill_db_tests.sh inside "$suite"
docker compose --profile db-test down --volumes --remove-orphans
active_project=
