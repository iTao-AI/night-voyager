#!/bin/sh
set -eu

if [ "${1:-}" = "inside" ]; then
    downgrade_output=$(mktemp)
    cleanup_output() {
        rm -f "$downgrade_output"
    }
    trap cleanup_output EXIT INT TERM

    uv run alembic upgrade head
    uv run alembic current | grep '0013'
    uv run alembic downgrade 0007
    uv run alembic current | grep '0007'
    uv run alembic downgrade 0006
    uv run alembic current | grep '0006'
    uv run alembic upgrade head
    uv run alembic current | grep '0013'
    uv run alembic downgrade 0005
    uv run alembic current | grep '0005'
    uv run alembic upgrade 0006
    uv run alembic current | grep '0006'
    uv run alembic upgrade head
    uv run alembic current | grep '0013'
    uv run alembic downgrade 0001
    uv run alembic current | grep '0001'
    uv run alembic upgrade head
    uv run alembic current | grep '0013'
    uv run alembic downgrade 0001
    uv run alembic current | grep '0001'
    uv run python scripts/seed_demo.py --identity-only
    uv run alembic upgrade 0007
    uv run alembic current | grep '0007'
    uv run --no-editable python scripts/seed_demo.py \
        --without-skills --without-planning-revision
    uv run alembic upgrade head
    uv run alembic current | grep '0013'
    uv run --no-editable python scripts/seed_demo.py
    uv run --no-editable python scripts/seed_demo.py
    uv run --no-editable python scripts/verify_release.py --check-db-roles
    NIGHT_VOYAGER_DEMO_SEED_READY=1 PYTEST_ADDOPTS= uv run --no-editable pytest \
        -q -m database \
        tests/security tests/integration/identity tests/integration/planning \
        tests/integration/decision/test_postgres_decision.py tests/integration/tasks \
        tests/integration/connected_demo tests/integration/dra \
        tests/integration/collaboration \
        --ignore=tests/integration/tasks/test_planning_start_migration.py \
        --ignore=tests/integration/dra/test_dra_live_migration.py \
        --ignore=tests/integration/dra/test_dra_strict_migration.py \
        --ignore=tests/integration/tasks/test_mixed_downgrade.py \
        --ignore=tests/integration/collaboration/test_collaboration_downgrade.py \
        --ignore=tests/integration/dra/test_governed_closure.py
    PYTEST_ADDOPTS= uv run --no-editable pytest -q -m database \
        tests/integration/dra/test_governed_closure.py
    PYTEST_ADDOPTS= uv run --no-editable pytest -q -m database \
        tests/integration/decision/test_postgres_decision.py
    PYTEST_ADDOPTS= uv run --no-editable pytest -q -m database \
        tests/integration/decision/test_http_decision.py
    if uv run alembic downgrade 0011 >"$downgrade_output" 2>&1; then
        echo "expected planning revision authority downgrade refusal" >&2
        exit 1
    fi
    grep -q 'refusing downgrade: planning revision lineage exists' "$downgrade_output"
    uv run alembic current | grep '0013'
    uv run --no-editable python scripts/verify_release.py --check-db-roles
    exit 0
fi

if [ "${1:-}" = "inside-mixed-downgrade" ]; then
    uv run alembic upgrade head
    uv run alembic current | grep '0013'
    uv run --no-editable python scripts/seed_demo.py \
        --without-collaboration --without-planning-revision
    PYTEST_ADDOPTS= uv run --no-editable pytest -q -m database \
        tests/integration/tasks/test_mixed_downgrade.py
    uv run alembic current | grep '0013'
    exit 0
fi

if [ "${1:-}" = "inside-planning-start-migration" ]; then
    uv run alembic downgrade base
    uv run alembic upgrade 0008
    uv run alembic current | grep '0008'
    uv run --no-editable python scripts/seed_demo.py --without-planning-revision
    PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database \
        tests/integration/tasks/test_planning_start_migration.py
    uv run alembic current | grep '0009'
    uv run --no-editable python scripts/verify_release.py --check-db-roles
    exit 0
fi

if [ "${1:-}" = "inside-dra-live-migration" ]; then
    uv run alembic downgrade base
    uv run alembic upgrade 0009
    uv run alembic current | grep '0009'
    uv run --no-editable python scripts/seed_demo.py --without-planning-revision
    PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database \
        tests/integration/dra/test_dra_live_migration.py
    uv run alembic current | grep '0010'
    exit 0
fi

if [ "${1:-}" = "inside-dra-strict-migration" ]; then
    uv run alembic downgrade base
    uv run alembic upgrade 0009
    uv run alembic current | grep '0009'
    uv run --no-editable python scripts/seed_demo.py --without-planning-revision
    PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database \
        tests/integration/dra/test_dra_live_migration.py \
        tests/integration/dra/test_dra_strict_migration.py \
        tests/security/test_rls_isolation.py
    uv run alembic current | grep '0011'
    exit 0
fi

if [ "${1:-}" = "inside-skill-migration-parity" ]; then
    PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database \
        tests/integration/skills/test_skill_migration_parity.py::test_0008_legacy_seed_helper_has_fresh_upgrade_and_downgrade_parity
    exit 0
fi

if [ "${1:-}" = "inside-skill-seed-replay" ]; then
    export NIGHT_VOYAGER_SKILL_SEED_PATH=fresh_head
    uv run --no-editable python scripts/seed_demo.py
    uv run --no-editable python scripts/seed_demo.py
    PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database \
        tests/integration/skills/test_postgres_skills.py::test_fresh_head_seed_creates_exact_pinned_active_task_fixture \
        tests/integration/skills/test_postgres_skills.py::test_pinned_seed_replay_rejects_task_projection_drift_atomically \
        tests/integration/skills/test_postgres_skills.py::test_pinned_helper_rejects_extra_event_without_partial_history \
        tests/integration/skills/test_postgres_skills.py::test_pinned_seed_replay_rejects_missing_event_without_repair \
        tests/integration/skills/test_postgres_skills.py::test_legacy_seed_replay_rejects_missing_event_without_repair \
        tests/integration/skills/test_postgres_skills.py::test_pinned_helper_rejects_execution_residue_without_partial_history \
        tests/integration/skills/test_postgres_skills.py::test_pinned_helper_rejects_dispatch_residue_without_partial_history \
        tests/integration/skills/test_postgres_skills.py::test_seed_replay_preserves_only_exact_all_null_legacy_task \
        tests/integration/skills/test_postgres_skills.py::test_seed_replay_rejects_all_null_legacy_projection_drift \
        tests/integration/skills/test_postgres_skills.py::test_seed_replay_rejects_partial_pin_classification \
        tests/integration/skills/test_postgres_skills.py::test_pinned_active_task_seed_mismatch_has_no_partial_task_or_event
    exit 0
fi

if [ "${1:-}" = "inside-planning-revision-seed-migration" ]; then
    uv run alembic downgrade base
    uv run alembic upgrade 0012
    uv run alembic current | grep '0012'
    uv run --no-editable python scripts/seed_demo.py --without-planning-revision
    NIGHT_VOYAGER_REVISION_SEED_MIGRATION_PHASE=absent-0012 \
        PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database \
        tests/integration/planning/test_revision_seed_migration.py
    uv run alembic upgrade 0013
    uv run alembic current | grep '0013'
    NIGHT_VOYAGER_REVISION_SEED_MIGRATION_PHASE=authority-0013 \
        PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database \
        tests/integration/planning/test_revision_seed_migration.py
    uv run alembic downgrade 0012
    NIGHT_VOYAGER_REVISION_SEED_MIGRATION_PHASE=safe-downgrade-0012 \
        PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database \
        tests/integration/planning/test_revision_seed_migration.py
    uv run alembic upgrade 0013
    NIGHT_VOYAGER_REVISION_SEED_MIGRATION_PHASE=restored-0013 \
        PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database \
        tests/integration/planning/test_revision_seed_migration.py
    uv run alembic current | grep '0013'
    exit 0
fi

if [ "${1:-}" = "inside-planning-revision" ]; then
    suite=${2:-}
    case "$suite" in
        authority|worker|projection) ;;
        *)
            echo "unknown planning revision suite: ${suite:-<missing>}" >&2
            exit 2
            ;;
    esac
    uv run alembic upgrade head
    uv run alembic current
    uv run --no-editable python scripts/seed_demo.py
    case "$suite" in
        authority)
            PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database \
                tests/integration/planning/test_revision_migration.py \
                tests/integration/planning/test_revision_authority.py \
                tests/integration/collaboration/test_postgres_collaboration.py \
                tests/integration/collaboration/test_collaboration_concurrency.py \
                tests/integration/collaboration/test_collaboration_rollback.py \
                tests/integration/decision/test_postgres_decision.py \
                tests/integration/decision/test_http_decision.py \
                tests/integration/tasks/test_planning_start_authority.py \
                tests/integration/tasks/test_postgres_tasks.py \
                tests/integration/tasks/test_worker_authority.py \
                tests/integration/planning/test_revision_query_plan.py \
                tests/security/test_rls_isolation.py
            ;;
        worker)
            PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database \
                tests/integration/tasks/test_planning_start_authority.py \
                tests/integration/tasks/test_postgres_tasks.py \
                tests/integration/tasks/test_worker.py \
                tests/integration/tasks/test_worker_authority.py
            ;;
        projection)
            PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database \
                tests/integration/connected_demo/test_postgres_read_models.py \
                tests/integration/connected_demo/test_http_read_models.py \
                tests/integration/planning/test_revision_query_plan.py
            ;;
    esac
    uv run alembic current | grep '0013'
    exit 0
fi

if [ "${1:-}" = "inside-planning-revision-journey" ]; then
    uv run alembic upgrade head
    uv run alembic current | grep '0013'
    uv run --no-editable python scripts/seed_demo.py
    PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database \
        tests/integration/connected_demo/test_postgres_read_models.py \
        tests/integration/connected_demo/test_http_read_models.py \
        tests/integration/connected_demo/test_planning_revision_flow.py
    uv run alembic current | grep '0013'
    exit 0
fi

if [ "${1:-}" = "inside-timeline-execution-migration" ]; then
    uv run alembic downgrade base
    uv run alembic upgrade 0013
    uv run alembic current | grep '0013'
    uv run --no-editable python scripts/seed_demo.py
    uv run alembic upgrade head
    uv run alembic current | grep '0014'
    PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database \
        tests/security/test_timeline_execution_catalog.py \
        tests/integration/timeline_execution/test_migration.py \
        tests/integration/timeline_execution/test_query_plan.py
    NIGHT_VOYAGER_TIMELINE_MIGRATION_PHASE=empty \
        PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database \
        tests/integration/timeline_execution/test_downgrade.py
    uv run --no-editable python scripts/seed_demo.py
    NIGHT_VOYAGER_TIMELINE_MIGRATION_PHASE=history \
        PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database \
        tests/integration/timeline_execution/test_downgrade.py
    exit 0
fi

if [ "${1:-}" = "inside-timeline-execution-authority" ]; then
    uv run alembic upgrade head
    uv run alembic current | grep '0014'
    uv run --no-editable python scripts/seed_demo.py
    PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database \
        tests/integration/timeline_execution/test_authority.py \
        tests/integration/timeline_execution/test_repository.py \
        tests/integration/timeline_execution/test_query_plan.py \
        tests/security/test_timeline_execution_catalog.py
    uv run alembic current | grep '0014'
    exit 0
fi

if [ "${1:-}" = "inside-timeline-execution-http" ]; then
    uv run alembic upgrade head
    uv run alembic current | grep '0014'
    PYTEST_ADDOPTS= uv run --no-editable pytest -q -o addopts='' -m database \
        tests/integration/timeline_execution/test_http.py
    exit 0
fi

BASE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-night-voyager-db-check-$$}
ACTIVE_PROJECT_NAME=

cleanup() {
    if [ -n "$ACTIVE_PROJECT_NAME" ]; then
        COMPOSE_PROJECT_NAME=$ACTIVE_PROJECT_NAME docker compose --profile db-test down --volumes --remove-orphans --rmi local
    fi
}
trap cleanup EXIT INT TERM

run_lane() {
    ACTIVE_PROJECT_NAME=$1
    shift
    export ACTIVE_PROJECT_NAME
    COMPOSE_PROJECT_NAME=$ACTIVE_PROJECT_NAME docker compose --profile db-test config --quiet
    COMPOSE_PROJECT_NAME=$ACTIVE_PROJECT_NAME docker compose --profile db-test run --rm --build db-test \
        sh scripts/run_db_tests.sh "$@"
    COMPOSE_PROJECT_NAME=$ACTIVE_PROJECT_NAME docker compose --profile db-test down --volumes --remove-orphans --rmi local
    ACTIVE_PROJECT_NAME=
}

if [ "${1:-}" = "fact-to-plan" ]; then
    run_lane "${BASE_PROJECT_NAME}-planning-start-migration" inside-planning-start-migration
    exit 0
fi

if [ "${1:-}" = "dra-live-migration" ]; then
    run_lane "${BASE_PROJECT_NAME}-dra-live-migration" inside-dra-live-migration
    exit 0
fi

if [ "${1:-}" = "dra-strict-migration" ]; then
    run_lane "${BASE_PROJECT_NAME}-dra-strict-migration" inside-dra-strict-migration
    exit 0
fi

if [ "${1:-}" = "planning-revision-seed-migration" ]; then
    run_lane "${BASE_PROJECT_NAME}-planning-revision-seed-migration" \
        inside-planning-revision-seed-migration
    exit 0
fi

if [ "${1:-}" = "planning-revision" ]; then
    suite=${2:-}
    case "$suite" in
        authority|projection)
            run_lane "${BASE_PROJECT_NAME}-${suite}" inside-planning-revision "$suite"
            ;;
        worker)
            run_lane "${BASE_PROJECT_NAME}-worker" inside-planning-revision worker
            run_lane "${BASE_PROJECT_NAME}-mixed-downgrade" inside-mixed-downgrade
            ;;
        all)
            run_lane "${BASE_PROJECT_NAME}-authority" inside-planning-revision authority
            run_lane "${BASE_PROJECT_NAME}-worker" inside-planning-revision worker
            run_lane "${BASE_PROJECT_NAME}-mixed-downgrade" inside-mixed-downgrade
            run_lane "${BASE_PROJECT_NAME}-projection" inside-planning-revision projection
            ;;
        journey)
            run_lane "${BASE_PROJECT_NAME}-journey" inside-planning-revision-journey
            ;;
        *)
            echo "unknown planning revision suite: ${suite:-<missing>}" >&2
            exit 2
            ;;
    esac
    exit 0
fi

if [ "${1:-}" = "timeline-execution" ]; then
    suite=${2:-}
    case "$suite" in
        migration)
            run_lane "${BASE_PROJECT_NAME}-migration" \
                inside-timeline-execution-migration
            ;;
        authority)
            run_lane "${BASE_PROJECT_NAME}-authority" \
                inside-timeline-execution-authority
            ;;
        http)
            run_lane "${BASE_PROJECT_NAME}-http" \
                inside-timeline-execution-http
            ;;
        *)
            echo "unknown timeline execution suite: ${suite:-<missing>}" >&2
            exit 2
            ;;
    esac
    exit 0
fi

if [ -n "${1:-}" ]; then
    echo "unknown database test mode: $1" >&2
    exit 2
fi

run_lane "${BASE_PROJECT_NAME}-planning-start-migration" inside-planning-start-migration
run_lane "${BASE_PROJECT_NAME}-dra-live-migration" inside-dra-live-migration
run_lane "${BASE_PROJECT_NAME}-dra-strict-migration" inside-dra-strict-migration
run_lane "${BASE_PROJECT_NAME}-planning-revision-seed-migration" \
    inside-planning-revision-seed-migration
run_lane "${BASE_PROJECT_NAME}-skill-seed-replay" inside-skill-seed-replay
run_lane "${BASE_PROJECT_NAME}-skill-migration-parity" inside-skill-migration-parity
run_lane "${BASE_PROJECT_NAME}-main" inside
run_lane "${BASE_PROJECT_NAME}-mixed-downgrade" inside-mixed-downgrade
