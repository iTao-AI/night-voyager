#!/bin/sh
set -eu

mode=${1:-outside}
suite=${SUITE:-${2:-}}

if [ "$mode" = "inside-downgrade" ]; then
    scenario=${2:-}
    case "$scenario" in
        empty|unrelated|table-history|audit-history|idempotency-history) ;;
        *)
            echo "unknown collaboration downgrade scenario: ${scenario:-<missing>}" >&2
            exit 2
            ;;
    esac
    if [ "${NIGHT_VOYAGER_COLLABORATION_DOWNGRADE_SCENARIO:-}" != "$scenario" ]; then
        echo "collaboration downgrade scenario environment mismatch" >&2
        exit 2
    fi
    uv run alembic downgrade 0007
    uv run alembic current | grep '0007'
    PYTEST_ADDOPTS= uv run --no-editable pytest -q -m database \
        tests/integration/collaboration/test_collaboration_downgrade.py
    exit 0
fi

case "$suite" in
    repository|http|authority) ;;
    *)
        echo "unknown collaboration database suite: ${suite:-<missing>}" >&2
        exit 2
        ;;
esac

if [ "$mode" = "inside" ]; then
    case "$suite" in
        repository)
            PYTEST_ADDOPTS= uv run --no-editable pytest -q -m database \
                tests/integration/collaboration/test_postgres_collaboration.py
            ;;
        http)
            uv run alembic downgrade 0007
            uv run --no-editable python scripts/seed_demo.py --without-skills
            uv run alembic upgrade head
            uv run --no-editable python scripts/seed_demo.py
            uv run --no-editable python scripts/seed_demo.py
            NIGHT_VOYAGER_DEMO_SEED_READY=1 PYTEST_ADDOPTS= \
                uv run --no-editable pytest -q -m database \
                tests/integration/collaboration/test_http_collaboration.py
            ;;
        authority)
            PYTEST_ADDOPTS= uv run --no-editable pytest -q \
                tests/security/test_collaboration_catalog.py \
                tests/security/test_database_catalog.py \
                tests/architecture/test_collaboration_contract.py
            uv run alembic downgrade 0007
            uv run --no-editable python scripts/seed_demo.py --without-skills
            uv run alembic upgrade head
            uv run --no-editable python scripts/seed_demo.py
            uv run --no-editable python scripts/seed_demo.py
            NIGHT_VOYAGER_DEMO_SEED_READY=1 PYTEST_ADDOPTS= \
                uv run --no-editable pytest -q -m database \
                tests/integration/collaboration/test_postgres_collaboration.py \
                tests/integration/collaboration/test_collaboration_concurrency.py \
                tests/integration/collaboration/test_collaboration_rollback.py \
                tests/integration/collaboration/test_http_collaboration.py
            ;;
    esac
    exit 0
fi

base_project=${COMPOSE_PROJECT_NAME:-night-voyager-collaboration-db-check-$$}
active_project=

cleanup() {
    if [ -n "$active_project" ]; then
        COMPOSE_PROJECT_NAME="$active_project" docker compose --profile db-test \
            down --volumes --remove-orphans
    fi
}
trap cleanup EXIT INT TERM

run_project() {
    active_project=$1
    shift
    export COMPOSE_PROJECT_NAME="$active_project"
    docker compose --profile db-test config --quiet
    docker compose --profile db-test run --rm --build "$@"
    docker compose --profile db-test down --volumes --remove-orphans
    active_project=
}

if [ "$suite" = "authority" ]; then
    run_project "${base_project}-authority" db-test \
        sh scripts/run_collaboration_db_tests.sh inside authority
    for scenario in empty unrelated table-history audit-history idempotency-history; do
        run_project "${base_project}-${scenario}" \
            --env "NIGHT_VOYAGER_COLLABORATION_DOWNGRADE_SCENARIO=$scenario" \
            db-test sh scripts/run_collaboration_db_tests.sh inside-downgrade "$scenario"
    done
else
    run_project "$base_project" db-test \
        sh scripts/run_collaboration_db_tests.sh inside "$suite"
fi
