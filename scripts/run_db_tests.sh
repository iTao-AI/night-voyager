#!/bin/sh
set -eu

if [ "${1:-}" = "inside" ]; then
    uv run alembic upgrade head
    uv run alembic current
    uv run python scripts/seed_demo.py
    uv run python scripts/seed_demo.py
    uv run python scripts/verify_release.py --check-db-roles
    PYTEST_ADDOPTS= uv run pytest -q -m database \
        tests/security tests/integration/identity tests/integration/planning \
        tests/integration/decision/test_postgres_decision.py \
        tests/integration/decision/test_http_decision.py
    uv run alembic downgrade 0001
    uv run alembic current | grep '0001'
    uv run python scripts/seed_demo.py --identity-only
    uv run alembic upgrade head
    uv run python scripts/verify_release.py --check-db-roles
    exit 0
fi

COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-night-voyager-db-check-$$}
export COMPOSE_PROJECT_NAME

cleanup() {
    docker compose --profile db-test down --volumes --remove-orphans
}
trap cleanup EXIT INT TERM

docker compose --profile db-test config --quiet
docker compose --profile db-test run --rm --build db-test
