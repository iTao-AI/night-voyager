#!/bin/sh
set -eu

mode=${1:-full}
if [ "$#" -gt 1 ]; then
    printf 'compose-proof: unsupported mode argument count\n' >&2
    exit 2
fi
case "$mode" in
    planning-revision) ;;
    full) ;;
    *) printf 'compose-proof: unsupported mode %s\n' "$mode" >&2; exit 2 ;;
esac

COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-night-voyager-compose-proof-$$}
UPDATE_COLLABORATION_SCREENSHOT=${UPDATE_COLLABORATION_SCREENSHOT:-0}
UPDATE_PORTFOLIO_SCREENSHOTS=${UPDATE_PORTFOLIO_SCREENSHOTS:-0}
UPDATE_PLANNING_REVISION_SCREENSHOT=${UPDATE_PLANNING_REVISION_SCREENSHOT:-0}
PLANNING_REVISION_REVIEW_DIR=${PLANNING_REVISION_REVIEW_DIR:-tmp/planning-revision-review}
FACT_TO_PLAN_ZH_PROOF_FILE=docs/assets/.fact-to-plan-zh-CN-proof.json
FACT_TO_PLAN_ZH_WORKER_READY_FILE=docs/assets/.fact-to-plan-zh-CN-worker-ready
FACT_TO_PLAN_EN_PROOF_FILE=docs/assets/.fact-to-plan-en-proof.json
FACT_TO_PLAN_EN_WORKER_READY_FILE=docs/assets/.fact-to-plan-en-worker-ready
FACT_TO_PLAN_PROOF_FILE=
FACT_TO_PLAN_WORKER_READY_FILE=
FACT_TO_PLAN_WORKER_READY_SENTINEL="task accepted and initial SSE observed"
PLANNING_REVISION_ZH_PROOF_FILE=docs/assets/.planning-revision-zh-CN-proof.json
PLANNING_REVISION_ZH_WORKER_READY_FILE=docs/assets/.planning-revision-zh-CN-worker-ready
PLANNING_REVISION_EN_PROOF_FILE=docs/assets/.planning-revision-en-proof.json
PLANNING_REVISION_EN_WORKER_READY_FILE=docs/assets/.planning-revision-en-worker-ready
PLANNING_REVISION_PROOF_FILE=
PLANNING_REVISION_WORKER_READY_FILE=
PLANNING_REVISION_INITIAL_SENTINEL="revised task accepted and initial SSE observed"
PLANNING_REVISION_RESTART_SENTINEL="first revised-task lease observed; restart worker"
PLANNING_REVISION_BARRIER_FIFO=tmp/.planning-revision-barrier-control
PLANNING_REVISION_BARRIER_OUTPUT=tmp/.planning-revision-barrier-output
PLANNING_REVISION_BARRIER_STATE=tmp/.planning-revision-barrier-state
PLANNING_REVISION_PREDECESSOR_STDOUT=tmp/.planning-revision-predecessor-stdout
PLANNING_REVISION_PREDECESSOR_STDERR=tmp/.planning-revision-predecessor-stderr
PLANNING_REVISION_BARRIER_READY="planning revision predecessor lock ready"
PLAN_EXECUTION_PROOF_FILE=
# Review artifacts retained for the required manual inspection:
# planning-revision-zh-CN-1440-happy.png planning-revision-zh-CN-1440-blocked.png
# planning-revision-zh-CN-390-happy.png planning-revision-zh-CN-390-blocked.png
# planning-revision-en-1440-happy.png planning-revision-en-1440-blocked.png
# planning-revision-en-390-happy.png planning-revision-en-390-blocked.png
worker_start_pid=
planning_revision_browser_pid=
barrier_pid=
barrier_fd_open=0
export COMPOSE_PROJECT_NAME

cleanup() {
    if [ -n "$planning_revision_browser_pid" ]; then
        kill "$planning_revision_browser_pid" 2>/dev/null || true
        wait "$planning_revision_browser_pid" 2>/dev/null || true
    fi
    if [ -n "$worker_start_pid" ]; then
        kill "$worker_start_pid" 2>/dev/null || true
        wait "$worker_start_pid" 2>/dev/null || true
    fi
    if [ "$barrier_fd_open" = "1" ]; then
        printf 'ROLLBACK;\n' >&3 2>/dev/null || true
        exec 3>&-
        barrier_fd_open=0
    fi
    if [ -n "$barrier_pid" ]; then
        kill "$barrier_pid" 2>/dev/null || true
        wait "$barrier_pid" 2>/dev/null || true
    fi
    rm -f \
        "$FACT_TO_PLAN_ZH_PROOF_FILE" "$FACT_TO_PLAN_ZH_WORKER_READY_FILE" \
        "$FACT_TO_PLAN_EN_PROOF_FILE" "$FACT_TO_PLAN_EN_WORKER_READY_FILE" \
        "$PLANNING_REVISION_ZH_PROOF_FILE" "$PLANNING_REVISION_ZH_WORKER_READY_FILE" \
        "$PLANNING_REVISION_EN_PROOF_FILE" "$PLANNING_REVISION_EN_WORKER_READY_FILE" \
        "$PLANNING_REVISION_BARRIER_FIFO" "$PLANNING_REVISION_BARRIER_OUTPUT" \
        "$PLANNING_REVISION_BARRIER_STATE" \
        "$PLANNING_REVISION_PREDECESSOR_STDOUT" \
        "$PLANNING_REVISION_PREDECESSOR_STDERR" \
        docs/assets/.plan-execution-zh-CN-happy-proof.json \
        docs/assets/.plan-execution-zh-CN-blocked-proof.json \
        docs/assets/.plan-execution-en-happy-proof.json \
        docs/assets/.plan-execution-en-blocked-proof.json
    docker compose down --volumes --remove-orphans --rmi local
}

start_planning_revision_barrier() {
    mkdir -p "$(dirname "$PLANNING_REVISION_BARRIER_FIFO")"
    rm -f \
        "$PLANNING_REVISION_PREDECESSOR_STDOUT" \
        "$PLANNING_REVISION_PREDECESSOR_STDERR"
    : > "$PLANNING_REVISION_PREDECESSOR_STDOUT"
    : > "$PLANNING_REVISION_PREDECESSOR_STDERR"
    chmod 0600 "$PLANNING_REVISION_PREDECESSOR_STDOUT"
    chmod 0600 "$PLANNING_REVISION_PREDECESSOR_STDERR"

    if ! docker compose exec -T postgres \
        psql -U night_voyager -d night_voyager -Atc \
        "SELECT selected.id::text FROM (SELECT predecessor.id, count(*) OVER () AS match_count FROM app.student_cases case_row JOIN app.student_case_revisions revision_row ON revision_row.organization_id=case_row.organization_id AND revision_row.case_id=case_row.id AND revision_row.revision=case_row.current_revision JOIN app.agent_tasks task ON task.organization_id=revision_row.organization_id AND task.case_id=revision_row.case_id AND task.case_revision=revision_row.revision JOIN app.planning_runs predecessor ON predecessor.organization_id=revision_row.organization_id AND predecessor.case_id=revision_row.case_id AND predecessor.id=revision_row.superseded_planning_run_id WHERE case_row.organization_id='10000000-0000-0000-0000-000000000001' AND case_row.id='49000000-0000-0000-0000-000000000001' AND case_row.current_revision=2 AND case_row.state='planning' AND task.state='queued' AND task.attempt_count=0 AND task.result_planning_run_id IS NULL AND task.predecessor_planning_run_id=revision_row.superseded_planning_run_id AND predecessor.id=task.predecessor_planning_run_id AND predecessor.case_revision=revision_row.revision - 1 AND NOT predecessor.is_current) AS selected WHERE selected.match_count = 1" \
        > "$PLANNING_REVISION_PREDECESSOR_STDOUT" \
        2> "$PLANNING_REVISION_PREDECESSOR_STDERR"; then
        selector_error=$(tail -n 20 "$PLANNING_REVISION_PREDECESSOR_STDERR" \
            | tr '\n' ' ' | cut -c1-1000)
        printf 'compose-proof: planning revision predecessor selector failed: %s\n' \
            "$selector_error" >&2
        exit 1
    fi
    predecessor_id=$(cat "$PLANNING_REVISION_PREDECESSOR_STDOUT")
    if ! printf '%s\n' "$predecessor_id" | grep -Eq "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"; then
        selector_output=$(head -c 100 "$PLANNING_REVISION_PREDECESSOR_STDOUT" \
            | tr '\n' ' ')
        printf 'compose-proof: planning revision predecessor selector was not one UUID: %s\n' \
            "$selector_output" >&2
        exit 1
    fi

    rm -f \
        "$PLANNING_REVISION_BARRIER_FIFO" \
        "$PLANNING_REVISION_BARRIER_OUTPUT" \
        "$PLANNING_REVISION_BARRIER_STATE"
    mkfifo "$PLANNING_REVISION_BARRIER_FIFO"
    : > "$PLANNING_REVISION_BARRIER_OUTPUT"
    : > "$PLANNING_REVISION_BARRIER_STATE"
    chmod 0600 \
        "$PLANNING_REVISION_BARRIER_FIFO" \
        "$PLANNING_REVISION_BARRIER_OUTPUT" \
        "$PLANNING_REVISION_BARRIER_STATE"

    docker compose exec -T postgres \
        psql -v ON_ERROR_STOP=1 -U night_voyager -d night_voyager \
        < "$PLANNING_REVISION_BARRIER_FIFO" \
        > "$PLANNING_REVISION_BARRIER_OUTPUT" 2>&1 &
    barrier_pid=$!
    exec 3> "$PLANNING_REVISION_BARRIER_FIFO"
    barrier_fd_open=1
    printf '%s\n' \
        'BEGIN;' \
        'SELECT pg_backend_pid() AS barrier_backend_pid \gset' \
        "SELECT id FROM app.planning_runs WHERE organization_id='10000000-0000-0000-0000-000000000001' AND case_id='49000000-0000-0000-0000-000000000001' AND id='$predecessor_id' FOR UPDATE;" \
        '\echo barrier-backend-pid=:barrier_backend_pid' \
        "\echo $PLANNING_REVISION_BARRIER_READY:$predecessor_id" \
        >&3

    for attempt in $(seq 1 120); do
        if grep -Fqx \
            "$PLANNING_REVISION_BARRIER_READY:$predecessor_id" \
            "$PLANNING_REVISION_BARRIER_OUTPUT"; then
            break
        fi
        kill -0 "$barrier_pid"
        [ "$attempt" -lt 120 ] || {
            printf 'compose-proof: planning revision barrier lock timeout\n' >&2
            exit 1
        }
        sleep 1
    done
    barrier_backend_pid=$(sed -n \
        's/^barrier-backend-pid=//p' \
        "$PLANNING_REVISION_BARRIER_OUTPUT" | tail -n 1)
    printf '%s\n' "$barrier_backend_pid" | grep -Eq '^[0-9]+$'
    barrier_state=$(docker compose exec -T postgres \
        psql -U night_voyager -d night_voyager -Atc \
        "SELECT state FROM pg_stat_activity WHERE pid=$barrier_backend_pid")
    [ "$barrier_state" = "idle in transaction" ]
    printf 'predecessor=%s backend_pid=%s state=%s\n' \
        "$predecessor_id" "$barrier_backend_pid" "$barrier_state" \
        > "$PLANNING_REVISION_BARRIER_STATE"
}

release_planning_revision_barrier() {
    [ "$barrier_fd_open" = "1" ]
    [ -n "$barrier_pid" ]
    kill -0 "$barrier_pid"
    printf 'COMMIT;\n' >&3
    exec 3>&-
    barrier_fd_open=0
    wait "$barrier_pid"
    barrier_pid=
    grep -Fqx "COMMIT" "$PLANNING_REVISION_BARRIER_OUTPUT"
}

run_plan_execution_minimal_lane() {
    docker compose down --volumes --remove-orphans
    docker compose up --no-build --wait
    printf 'compose-proof: fresh governed plan execution baseline seeded\n'
    docker compose --profile browser-proof run --rm --no-deps \
        -e PLAN_EXECUTION_MINIMAL_PROOF=1 \
        browser-proof npx playwright test \
            --config playwright.compose.config.ts plan-execution-minimal.spec.ts
    docker compose run --rm --no-deps \
        demo-seed python scripts/verify_timeline_execution.py --expect completed
    printf 'compose-proof: governed plan execution minimal browser and database proof passed\n'
}

run_plan_execution_lane() {
    lane_locale=$1
    lane_scenario=$2
    case "$lane_locale" in
        zh-CN) set -- ;;
        en) set -- -e PRESENTATION_LOCALE=en ;;
        *) printf 'compose-proof: unsupported plan execution locale %s\n' "$lane_locale" >&2; exit 1 ;;
    esac
    case "$lane_scenario" in
        happy|blocked) ;;
        *) printf 'compose-proof: unsupported plan execution scenario %s\n' "$lane_scenario" >&2; exit 1 ;;
    esac
    PLAN_EXECUTION_PROOF_FILE="docs/assets/.plan-execution-${lane_locale}-${lane_scenario}-proof.json"
    docker compose down --volumes --remove-orphans
    docker compose up --no-build --wait
    rm -f "$PLAN_EXECUTION_PROOF_FILE"
    : > "$PLAN_EXECUTION_PROOF_FILE"
    chmod 0666 "$PLAN_EXECUTION_PROOF_FILE"
    printf 'compose-proof: fresh plan execution baseline locale=%s scenario=%s\n' \
        "$lane_locale" "$lane_scenario"
    docker compose --profile browser-proof run --rm --no-deps "$@" \
        -e PLAN_EXECUTION_SCENARIO="$lane_scenario" \
        -e PLAN_EXECUTION_PROOF_FILE="/workspace/$PLAN_EXECUTION_PROOF_FILE" \
        browser-proof npx playwright test \
            --config playwright.compose.config.ts plan-execution.spec.ts
    test -s "$PLAN_EXECUTION_PROOF_FILE"
    docker compose run --rm --no-deps \
        -v "$PWD/$PLAN_EXECUTION_PROOF_FILE:/tmp/plan-execution-proof.json:ro" \
        demo-seed python scripts/verify_timeline_execution.py \
        --proof-file /tmp/plan-execution-proof.json
    rm -f "$PLAN_EXECUTION_PROOF_FILE"
    printf 'compose-proof: plan execution browser and database proof passed locale=%s scenario=%s\n' \
        "$lane_locale" "$lane_scenario"
}

run_fact_to_plan_lane() {
    lane_locale=$1
    case "$lane_locale" in
        zh-CN) set -- -e UPDATE_PORTFOLIO_SCREENSHOTS="$UPDATE_PORTFOLIO_SCREENSHOTS" ;;
        en) set -- -e PRESENTATION_LOCALE=en ;;
        *) printf 'compose-proof: unsupported presentation locale %s\n' "$lane_locale" >&2; exit 1 ;;
    esac
    if [ "$lane_locale" = "zh-CN" ]; then
        FACT_TO_PLAN_PROOF_FILE=$FACT_TO_PLAN_ZH_PROOF_FILE
        FACT_TO_PLAN_WORKER_READY_FILE=$FACT_TO_PLAN_ZH_WORKER_READY_FILE
    else
        FACT_TO_PLAN_PROOF_FILE=$FACT_TO_PLAN_EN_PROOF_FILE
        FACT_TO_PLAN_WORKER_READY_FILE=$FACT_TO_PLAN_EN_WORKER_READY_FILE
    fi

    docker compose down --volumes --remove-orphans
    docker compose up --no-build --wait
    printf 'compose-proof: fresh fact-to-plan baseline seeded locale=%s\n' "$lane_locale"
    rm -f "$FACT_TO_PLAN_PROOF_FILE" "$FACT_TO_PLAN_WORKER_READY_FILE"
    : > "$FACT_TO_PLAN_PROOF_FILE"
    : > "$FACT_TO_PLAN_WORKER_READY_FILE"
    chmod 0666 "$FACT_TO_PLAN_PROOF_FILE" "$FACT_TO_PLAN_WORKER_READY_FILE"
    docker compose pause worker
    (
        for attempt in $(seq 1 120); do
            if grep -Fqx "$FACT_TO_PLAN_WORKER_READY_SENTINEL" "$FACT_TO_PLAN_WORKER_READY_FILE"; then
                docker compose unpause worker
                exit 0
            fi
            sleep 1
        done
        printf 'compose-proof: timed out waiting for task acceptance and initial SSE locale=%s\n' "$lane_locale" >&2
        exit 1
    ) &
    worker_start_pid=$!
    docker compose --profile browser-proof run --rm --no-deps "$@" \
        -e FACT_TO_PLAN_PROOF_FILE="/workspace/$FACT_TO_PLAN_PROOF_FILE" \
        -e FACT_TO_PLAN_WORKER_READY_FILE="/workspace/$FACT_TO_PLAN_WORKER_READY_FILE" \
        -e FACT_TO_PLAN_WORKER_READY_SENTINEL="$FACT_TO_PLAN_WORKER_READY_SENTINEL" \
        browser-proof npx playwright test --config playwright.compose.config.ts fact-to-plan.spec.ts
    wait "$worker_start_pid"
    worker_start_pid=
    test -s "$FACT_TO_PLAN_PROOF_FILE"
    docker compose run --rm --no-deps \
        -v "$PWD/$FACT_TO_PLAN_PROOF_FILE:/tmp/fact-to-plan-proof.json:ro" \
        demo-seed python scripts/verify_fact_to_plan_flow.py \
        --proof-file /tmp/fact-to-plan-proof.json
    rm -f "$FACT_TO_PLAN_PROOF_FILE" "$FACT_TO_PLAN_WORKER_READY_FILE"
    printf 'compose-proof: governed fact-to-plan browser and database proof passed locale=%s\n' "$lane_locale"
}

run_planning_revision_lane() {
    lane_locale=$1
    case "$lane_locale" in
        zh-CN) set -- -e UPDATE_PLANNING_REVISION_SCREENSHOT="$UPDATE_PLANNING_REVISION_SCREENSHOT" ;;
        en) set -- -e PRESENTATION_LOCALE=en -e UPDATE_PLANNING_REVISION_SCREENSHOT=0 ;;
        *) printf 'compose-proof: unsupported planning revision locale %s\n' "$lane_locale" >&2; exit 1 ;;
    esac
    if [ "$lane_locale" = "zh-CN" ]; then
        PLANNING_REVISION_PROOF_FILE=$PLANNING_REVISION_ZH_PROOF_FILE
        PLANNING_REVISION_WORKER_READY_FILE=$PLANNING_REVISION_ZH_WORKER_READY_FILE
    else
        PLANNING_REVISION_PROOF_FILE=$PLANNING_REVISION_EN_PROOF_FILE
        PLANNING_REVISION_WORKER_READY_FILE=$PLANNING_REVISION_EN_WORKER_READY_FILE
    fi

    docker compose down --volumes --remove-orphans
    docker compose up --no-build --wait
    printf 'compose-proof: fresh planning revision baseline seeded locale=%s\n' "$lane_locale"
    rm -f "$PLANNING_REVISION_PROOF_FILE" "$PLANNING_REVISION_WORKER_READY_FILE"
    : > "$PLANNING_REVISION_PROOF_FILE"
    : > "$PLANNING_REVISION_WORKER_READY_FILE"
    chmod 0666 "$PLANNING_REVISION_PROOF_FILE" "$PLANNING_REVISION_WORKER_READY_FILE"
    mkdir -p "$PLANNING_REVISION_REVIEW_DIR"
    for viewport in 1440 390; do
        for state in happy blocked; do
            review_file="$PLANNING_REVISION_REVIEW_DIR/planning-revision-$lane_locale-$viewport-$state.png"
            rm -f "$review_file"
            : > "$review_file"
            chmod 0666 "$review_file"
        done
    done
    docker compose pause worker
    docker compose --profile browser-proof run --rm --no-deps "$@" \
        -e PLANNING_REVISION_PROOF_FILE="/workspace/$PLANNING_REVISION_PROOF_FILE" \
        -e PLANNING_REVISION_WORKER_READY_FILE="/workspace/$PLANNING_REVISION_WORKER_READY_FILE" \
        -e PLANNING_REVISION_INITIAL_SENTINEL="$PLANNING_REVISION_INITIAL_SENTINEL" \
        -e PLANNING_REVISION_RESTART_SENTINEL="$PLANNING_REVISION_RESTART_SENTINEL" \
        -e PLANNING_REVISION_REVIEW_ROOT="/workspace/tmp/planning-revision-review" \
        -v "$PWD/$PLANNING_REVISION_REVIEW_DIR:/workspace/tmp/planning-revision-review" \
        browser-proof npx playwright test \
            --config playwright.compose.config.ts planning-revision.spec.ts &
    planning_revision_browser_pid=$!

    for attempt in $(seq 1 120); do
        if grep -Fqx \
            "$PLANNING_REVISION_INITIAL_SENTINEL" \
            "$PLANNING_REVISION_WORKER_READY_FILE"; then
            break
        fi
        kill -0 "$planning_revision_browser_pid"
        [ "$attempt" -lt 120 ] || {
            printf 'compose-proof: timed out waiting for revised task SSE locale=%s\n' \
                "$lane_locale" >&2
            exit 1
        }
        sleep 1
    done

    start_planning_revision_barrier
    docker compose unpause worker
    task_identity=
    for attempt in $(seq 1 120); do
        task_identity=$(docker compose exec -T postgres \
            psql -U night_voyager -d night_voyager -Atc \
            "SELECT task.id::text || ':' || task.state || ':' || task.attempt_count::text || ':' || task.lease_generation::text || ':' || execution.id::text || ':' || execution.attempt_no::text || ':' || execution.lease_generation::text || ':' || execution.status FROM app.agent_tasks task JOIN app.agent_executions execution ON execution.organization_id=task.organization_id AND execution.task_id=task.id AND execution.lease_generation=task.lease_generation WHERE task.organization_id='10000000-0000-0000-0000-000000000001' AND task.case_id='49000000-0000-0000-0000-000000000001' AND task.case_revision=2 AND task.state='running' AND task.attempt_count=1 AND task.lease_generation=1 AND execution.attempt_no=1 AND execution.lease_generation=1 AND execution.status='running'")
        if printf '%s\n' "$task_identity" | grep -Eq \
            '^[0-9a-f-]{36}:running:1:1:[0-9a-f-]{36}:1:1:running$'; then
            break
        fi
        kill -0 "$planning_revision_browser_pid"
        kill -0 "$barrier_pid"
        [ "$attempt" -lt 120 ] || {
            printf 'compose-proof: durable running identity timeout locale=%s\n' \
                "$lane_locale" >&2
            exit 1
        }
        sleep 1
    done
    printf '%s\n' "$task_identity" >> "$PLANNING_REVISION_BARRIER_STATE"

    for attempt in $(seq 1 120); do
        if grep -Fqx \
            "$PLANNING_REVISION_RESTART_SENTINEL" \
            "$PLANNING_REVISION_WORKER_READY_FILE"; then
            break
        fi
        kill -0 "$planning_revision_browser_pid"
        kill -0 "$barrier_pid"
        [ "$attempt" -lt 120 ] || {
            printf 'compose-proof: restart sentinel timeout locale=%s\n' \
                "$lane_locale" >&2
            exit 1
        }
        sleep 1
    done

    for attempt in $(seq 1 120); do
        lock_waiters=$(docker compose exec -T postgres \
            psql -U night_voyager -d night_voyager -Atc \
            "SELECT count(*) FROM pg_stat_activity WHERE usename='night_voyager_worker' AND wait_event_type='Lock'")
        [ "$lock_waiters" = "1" ] && break
        kill -0 "$barrier_pid"
        [ "$attempt" -lt 120 ] || {
            printf 'compose-proof: worker did not reach planning-run lock locale=%s\n' \
                "$lane_locale" >&2
            exit 1
        }
        sleep 1
    done
    barrier_backend_pid=$(sed -n \
        's/^barrier-backend-pid=//p' \
        "$PLANNING_REVISION_BARRIER_OUTPUT" | tail -n 1)
    barrier_state=$(docker compose exec -T postgres \
        psql -U night_voyager -d night_voyager -Atc \
        "SELECT state FROM pg_stat_activity WHERE pid=$barrier_backend_pid")
    [ "$barrier_state" = "idle in transaction" ]

    worker_container=$(docker compose ps -q worker)
    old_worker_pid=$(docker inspect --format '{{.State.Pid}}' "$worker_container")
    [ "$old_worker_pid" -gt 0 ]
    docker compose restart worker
    worker_container=$(docker compose ps -q worker)
    new_worker_pid=$(docker inspect --format '{{.State.Pid}}' "$worker_container")
    [ "$new_worker_pid" -gt 0 ]
    [ "$new_worker_pid" != "$old_worker_pid" ]
    release_planning_revision_barrier

    wait "$planning_revision_browser_pid"
    planning_revision_browser_pid=
    grep -Fqx "$PLANNING_REVISION_INITIAL_SENTINEL" "$PLANNING_REVISION_WORKER_READY_FILE"
    grep -Fqx "$PLANNING_REVISION_RESTART_SENTINEL" "$PLANNING_REVISION_WORKER_READY_FILE"
    test -s "$PLANNING_REVISION_PROOF_FILE"
    docker compose run --rm --no-deps \
        -v "$PWD/$PLANNING_REVISION_PROOF_FILE:/tmp/planning-revision-proof.json:ro" \
        demo-seed python scripts/verify_planning_revision_flow.py \
        --proof-file /tmp/planning-revision-proof.json
    rm -f "$PLANNING_REVISION_PROOF_FILE" "$PLANNING_REVISION_WORKER_READY_FILE"
    printf 'compose-proof: planning revision browser and database proof passed locale=%s\n' "$lane_locale"
}

run_planning_revision_proof() {
    run_planning_revision_lane "zh-CN"
    run_planning_revision_lane "en"
}
trap cleanup EXIT INT TERM

docker compose config --quiet
docker compose --profile browser-proof build
docker compose up --no-build --wait

for service in postgres api web; do
    container=$(docker compose ps -q "$service")
    status=$(docker inspect --format '{{.State.Health.Status}}' "$container")
    [ "$status" = "healthy" ]
    printf 'compose-proof: %s health=%s\n' "$service" "$status"
done

worker=$(docker compose ps -q worker)
worker_status=$(docker inspect --format '{{.State.Status}}' "$worker")
[ "$worker_status" = "running" ]
printf 'compose-proof: worker status=%s\n' "$worker_status"

migrator=$(docker compose ps -aq migrator)
migrator_exit=$(docker inspect --format '{{.State.ExitCode}}' "$migrator")
[ "$migrator_exit" = "0" ]
printf 'compose-proof: migrator exit=%s\n' "$migrator_exit"

demo_seed=$(docker compose ps -aq demo-seed)
demo_seed_exit=$(docker inspect --format '{{.State.ExitCode}}' "$demo_seed")
[ "$demo_seed_exit" = "0" ]
printf 'compose-proof: demo-seed exit=%s\n' "$demo_seed_exit"

docker compose exec -T api python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
printf 'compose-proof: API probe passed\n'
docker compose exec -T api python scripts/verify_demo_identity.py
docker compose exec -T api python scripts/verify_collaboration_flow.py
docker compose run --rm demo-seed python scripts/seed_dra_proof.py
docker compose exec -T api python scripts/verify_dra_governed_flow.py --fixture
docker compose exec -T api python scripts/verify_m3b_flow.py
docker compose exec -T api python scripts/verify_m4a_flow.py
docker compose restart api worker
for attempt in $(seq 1 30); do
    if docker compose exec -T api python -c \
        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"; then
        break
    fi
    [ "$attempt" -lt 30 ] || exit 1
    sleep 1
done
worker=$(docker compose ps -q worker)
worker_status=$(docker inspect --format '{{.State.Status}}' "$worker")
[ "$worker_status" = "running" ]
printf 'compose-proof: API and worker restart probe passed\n'
docker compose exec -T api python scripts/verify_collaboration_flow.py --verify-existing
docker compose exec -T api python scripts/verify_m4a_flow.py --verify-existing
docker compose exec -T web wget -q --spider http://127.0.0.1:3000
printf 'compose-proof: Web probe passed\n'
if [ "$mode" = "planning-revision" ]; then
    run_planning_revision_proof
    exit 0
fi
# The M4A proof intentionally leaves the canonical task case at review_required.
# Recreate the synthetic proof volume so the browser lane proves task creation too.
docker compose down --volumes --remove-orphans
docker compose up --no-build --wait
printf 'compose-proof: fresh browser stack seeded\n'
docker compose stop worker
docker compose --profile browser-proof run --rm --no-deps -e M5_TERMINAL_PROOF=1 browser-proof
printf 'compose-proof: native reconnect and terminal browser proof passed\n'
docker compose down --volumes --remove-orphans
docker compose up --no-build --wait
docker compose --profile browser-proof run --rm --no-deps \
    -e UPDATE_COLLABORATION_SCREENSHOT="$UPDATE_COLLABORATION_SCREENSHOT" browser-proof
printf 'compose-proof: connected browser proof passed\n'
run_plan_execution_minimal_lane
run_plan_execution_lane "zh-CN" "happy"
run_plan_execution_lane "zh-CN" "blocked"
run_plan_execution_lane "en" "happy"
run_plan_execution_lane "en" "blocked"
run_fact_to_plan_lane "zh-CN"
run_fact_to_plan_lane "en"
run_planning_revision_proof
