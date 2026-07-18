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
    uv run alembic downgrade 0007
    uv run --no-editable python scripts/seed_demo.py --without-skills
    uv run alembic upgrade head
    case "$suite" in
        catalog)
            uv run --no-editable python scripts/seed_demo.py --without-collaboration
            echo "Skill database suite: catalog"
            PYTEST_ADDOPTS= uv run --no-editable pytest -q \
                tests/security/test_skills_catalog.py \
                tests/unit/identity/test_seed_demo.py
            PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database \
                tests/integration/skills/test_postgres_skills.py \
                tests/integration/skills/test_skill_downgrade.py \
                tests/integration/skills/test_persisted_planning_materialization.py
            ;;
        worker)
            uv run --no-editable python scripts/seed_demo.py
            echo "Skill database suite: worker"
            PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database \
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
            uv run --no-editable python scripts/seed_demo.py
            echo "Skill database suite: lifecycle"
            PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database \
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
        cleanup_status=0
        COMPOSE_PROJECT_NAME="$active_project" docker compose --profile db-test \
            down --volumes --remove-orphans || cleanup_status=$?
        resource_ids=$(
            {
                docker ps --all --quiet \
                    --filter "label=com.docker.compose.project=$active_project"
                docker volume ls --quiet \
                    --filter "label=com.docker.compose.project=$active_project"
                docker network ls --quiet \
                    --filter "label=com.docker.compose.project=$active_project"
            } | sed '/^$/d'
        )
        if [ -n "$resource_ids" ]; then
            echo "Skill database project was not empty after teardown: $active_project" >&2
            return 1
        fi
        active_project=
        return "$cleanup_status"
    fi
}
trap cleanup EXIT INT TERM

active_project="${base_project}-${suite}"
export COMPOSE_PROJECT_NAME="$active_project"
docker compose --profile db-test config --quiet
docker compose --profile db-test run --rm --build db-test \
    sh scripts/run_skill_db_tests.sh inside "$suite"
cleanup
trap - EXIT INT TERM
