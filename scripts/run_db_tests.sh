#!/bin/sh
set -eu

if [ "${1:-}" = "inside" ]; then
    downgrade_output=$(mktemp)
    cleanup_output() {
        rm -f "$downgrade_output"
    }
    trap cleanup_output EXIT INT TERM

    uv run alembic upgrade head
    uv run alembic current | grep '0008'
    uv run alembic downgrade 0007
    uv run alembic current | grep '0007'
    uv run alembic downgrade 0006
    uv run alembic current | grep '0006'
    uv run alembic upgrade head
    uv run alembic current | grep '0008'
    uv run alembic downgrade 0005
    uv run alembic current | grep '0005'
    uv run alembic upgrade 0006
    uv run alembic current | grep '0006'
    uv run alembic upgrade head
    uv run alembic current | grep '0008'
    uv run alembic downgrade 0001
    uv run alembic current | grep '0001'
    uv run alembic upgrade head
    uv run alembic current | grep '0008'
    uv run alembic downgrade 0001
    uv run alembic current | grep '0001'
    uv run python scripts/seed_demo.py --identity-only
    uv run alembic upgrade head
    uv run alembic current | grep '0008'
    uv run python scripts/seed_demo.py
    uv run python scripts/seed_demo.py
    uv run python scripts/verify_release.py --check-db-roles
    NIGHT_VOYAGER_DEMO_SEED_READY=1 PYTEST_ADDOPTS= uv run pytest -q -m database \
        tests/security tests/integration/identity tests/integration/planning \
        tests/integration/decision/test_postgres_decision.py tests/integration/tasks \
        tests/integration/connected_demo tests/integration/dra \
        tests/integration/collaboration \
        --ignore=tests/integration/tasks/test_mixed_downgrade.py \
        --ignore=tests/integration/collaboration/test_collaboration_downgrade.py \
        --ignore=tests/integration/dra/test_governed_closure.py
    PYTEST_ADDOPTS= uv run pytest -q -m database \
        tests/integration/dra/test_governed_closure.py
    PYTEST_ADDOPTS= uv run pytest -q -m database \
        tests/integration/decision/test_postgres_decision.py
    PYTEST_ADDOPTS= uv run pytest -q -m database \
        tests/integration/decision/test_http_decision.py
    if uv run alembic downgrade 0007 >"$downgrade_output" 2>&1; then
        echo "expected Skill authority downgrade refusal" >&2
        exit 1
    fi
    grep -q 'refusing downgrade: Skill governance or runtime pin history exists' "$downgrade_output"
    uv run alembic current | grep '0008'
    uv run python scripts/verify_release.py --check-db-roles
    exit 0
fi

if [ "${1:-}" = "inside-mixed-downgrade" ]; then
    uv run alembic upgrade head
    uv run alembic current | grep '0008'
    uv run python scripts/seed_demo.py --without-collaboration
    PYTEST_ADDOPTS= uv run pytest -q -m database \
        tests/integration/tasks/test_mixed_downgrade.py
    uv run alembic current | grep '0008'
    exit 0
fi

BASE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-night-voyager-db-check-$$}
ACTIVE_PROJECT_NAME=

cleanup() {
    if [ -n "$ACTIVE_PROJECT_NAME" ]; then
        COMPOSE_PROJECT_NAME=$ACTIVE_PROJECT_NAME docker compose --profile db-test down --volumes --remove-orphans
    fi
}
trap cleanup EXIT INT TERM

run_lane() {
    ACTIVE_PROJECT_NAME=$1
    mode=$2
    export ACTIVE_PROJECT_NAME
    COMPOSE_PROJECT_NAME=$ACTIVE_PROJECT_NAME docker compose --profile db-test config --quiet
    COMPOSE_PROJECT_NAME=$ACTIVE_PROJECT_NAME docker compose --profile db-test run --rm --build db-test \
        sh scripts/run_db_tests.sh "$mode"
    COMPOSE_PROJECT_NAME=$ACTIVE_PROJECT_NAME docker compose --profile db-test down --volumes --remove-orphans
    ACTIVE_PROJECT_NAME=
}

run_lane "${BASE_PROJECT_NAME}-main" inside
run_lane "${BASE_PROJECT_NAME}-mixed-downgrade" inside-mixed-downgrade
