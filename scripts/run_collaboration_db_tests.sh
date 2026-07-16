#!/bin/sh
set -eu

mode=${1:-outside}
suite=${SUITE:-${2:-}}

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
            PYTEST_ADDOPTS= uv run pytest -q -m database \
                tests/integration/collaboration/test_postgres_collaboration.py
            ;;
        http)
            PYTEST_ADDOPTS= uv run pytest -q -m database \
                tests/integration/collaboration/test_http_collaboration.py
            ;;
        authority)
            PYTEST_ADDOPTS= uv run pytest -q \
                tests/security/test_collaboration_catalog.py \
                tests/architecture/test_collaboration_contract.py
            PYTEST_ADDOPTS= uv run pytest -q -m database \
                tests/security/test_database_catalog.py \
                tests/integration/collaboration/test_postgres_collaboration.py \
                tests/integration/collaboration/test_collaboration_concurrency.py \
                tests/integration/collaboration/test_collaboration_rollback.py \
                tests/integration/collaboration/test_collaboration_downgrade.py \
                tests/integration/collaboration/test_http_collaboration.py
            ;;
    esac
    exit 0
fi

COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-night-voyager-collaboration-db-check-$$}
export COMPOSE_PROJECT_NAME

cleanup() {
    docker compose --profile db-test down --volumes --remove-orphans
}
trap cleanup EXIT INT TERM

docker compose --profile db-test config --quiet
docker compose --profile db-test run --rm --build db-test \
    sh scripts/run_collaboration_db_tests.sh inside "$suite"
