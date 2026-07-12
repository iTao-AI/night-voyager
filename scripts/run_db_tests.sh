#!/bin/sh
set -eu

if [ "${1:-}" = "inside" ]; then
    uv run alembic upgrade head
    uv run alembic current
    uv run python scripts/seed_demo.py
    uv run python scripts/seed_demo.py
    uv run python scripts/verify_release.py --check-db-roles
    uv run pytest -q -m database tests/security tests/integration/identity
    uv run alembic downgrade base
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
