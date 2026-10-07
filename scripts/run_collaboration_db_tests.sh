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

if [ "$mode" = "inside-revision" ]; then
    uv run alembic downgrade base
    uv run alembic upgrade 0011
    uv run alembic current | grep '0011'
    uv run --no-editable python scripts/seed_demo.py --without-planning-revision --without-plan-execution
    uv run alembic upgrade 0012
    uv run alembic current | grep '0012'
    uv run alembic downgrade 0011
    NIGHT_VOYAGER_REVISION_MIGRATION_PHASE=safe-0011 PYTEST_ADDOPTS= \
        uv run --no-editable pytest -q -o addopts='' -m database \
        tests/integration/planning/test_revision_migration.py::test_safe_downgrade_restores_exact_0011_surface
    uv run alembic upgrade 0012
    uv run --no-editable python scripts/seed_demo.py --without-planning-revision --without-plan-execution
    PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database \
        tests/integration/planning/test_revision_migration.py \
        tests/integration/planning/test_revision_authority.py
    NIGHT_VOYAGER_REVISION_MIGRATION_PHASE=refusal PYTEST_ADDOPTS= \
        uv run --no-editable pytest -q -o addopts='' -m database \
        tests/integration/planning/test_revision_migration.py::test_refused_downgrade_preserves_exact_catalog_and_rows
    uv run alembic current | grep '0012'
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
            uv run --no-editable python scripts/seed_demo.py \
                --without-skills --without-planning-revision --without-plan-execution
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
            uv run --no-editable python scripts/seed_demo.py \
                --without-skills --without-planning-revision --without-plan-execution
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

bounded_diagnostic_output() {
    sed -E 's#([[:alpha:]][[:alnum:]+.-]*://)[^/@[:space:]]+@#\1[redacted]@#g' |
        awk 'NR <= 160 {
            if (tolower($0) ~ /password|passwd|secret|token|cookie|authorization|credential|api[ _-]?key|database[ _-]?url/) {
                print "[redacted sensitive diagnostic line]"
            } else {
                print substr($0, 1, 500)
            }
        }'
}

failure_diagnostics() {
    printf '%s\n' 'collaboration-db-check: startup diagnostics before teardown' >&2
    {
        COMPOSE_PROJECT_NAME="$active_project" docker compose --profile db-test \
            ps --all migrator postgres || printf '%s\n' 'service state unavailable'
    } 2>&1 | bounded_diagnostic_output >&2 || true
    {
        COMPOSE_PROJECT_NAME="$active_project" docker compose --profile db-test \
            logs --no-color --tail 80 migrator postgres || printf '%s\n' 'service logs unavailable'
    } 2>&1 | bounded_diagnostic_output >&2 || true
}

cleanup() {
    original_status=$?
    trap - EXIT INT TERM
    if [ -n "$active_project" ]; then
        if [ "$original_status" -ne 0 ]; then
            failure_diagnostics || true
        fi
        COMPOSE_PROJECT_NAME="$active_project" docker compose --profile db-test \
            down --volumes --remove-orphans --rmi local || true
    fi
    exit "$original_status"
}
trap cleanup EXIT INT TERM

run_project() {
    active_project=$1
    shift
    export COMPOSE_PROJECT_NAME="$active_project"
    docker compose --profile db-test config --quiet
    docker compose --profile db-test run --rm --build "$@"
    docker compose --profile db-test down --volumes --remove-orphans --rmi local
    active_project=
}

if [ "$suite" = "authority" ]; then
    run_project "${base_project}-authority" db-test \
        sh scripts/run_collaboration_db_tests.sh inside authority
    run_project "${base_project}-revision" db-test \
        sh scripts/run_collaboration_db_tests.sh inside-revision
    for scenario in empty unrelated table-history audit-history idempotency-history; do
        run_project "${base_project}-${scenario}" \
            --env "NIGHT_VOYAGER_COLLABORATION_DOWNGRADE_SCENARIO=$scenario" \
            db-test sh scripts/run_collaboration_db_tests.sh inside-downgrade "$scenario"
    done
else
    run_project "$base_project" db-test \
        sh scripts/run_collaboration_db_tests.sh inside "$suite"
fi
