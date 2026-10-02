#!/bin/sh
# Sequential, provider-free, task-owned customer revision/recovery acceptance.
set -eu
COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-night-voyager-customer-recovery-$$}
CUSTOMER_RECOVERY_REVIEW_DIR=${CUSTOMER_RECOVERY_REVIEW_DIR:-tmp/customer-revision-recovery-review}
export COMPOSE_PROJECT_NAME
browser_pid=
cleanup() {
    task_status=$?
    trap - EXIT INT TERM
    if [ -n "$browser_pid" ]; then
        kill "$browser_pid" 2>/dev/null || true
        wait "$browser_pid" 2>/dev/null || true
    fi
    for browser_container in $(docker ps --all --quiet \
        --filter "label=com.docker.compose.project=$COMPOSE_PROJECT_NAME" \
        --filter "label=com.docker.compose.service=browser-proof"); do
        docker rm --force "$browser_container" >/dev/null 2>&1 || task_status=1
    done
    docker compose down --volumes --remove-orphans --rmi local || task_status=1
    exit "$task_status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
# Build once before entering this runner; the explicit --no-build keeps provenance stable.
docker compose config --quiet
producer_hash=$(python3 -c 'import hashlib; print(hashlib.sha256(open("scripts/produce_customer_recovery_terminal.py","rb").read()).hexdigest())')
for locale in zh-CN en; do
    lane_dir="$CUSTOMER_RECOVERY_REVIEW_DIR/$locale"
    mkdir -p "$lane_dir"
    chmod 0777 "$lane_dir"
    mkdir -p "$lane_dir/trace"
    chmod 0777 "$lane_dir/trace"
    rm -f "$lane_dir/control.json" "$lane_dir/ack"
    docker compose down --volumes --remove-orphans
    docker compose up --no-build --wait
    docker compose images --format json
    docker compose run --rm --no-deps \
        -e CUSTOMER_RECOVERY_PRODUCER_SHA256="$producer_hash" \
        demo-seed python -c "import hashlib,os; from pathlib import Path; path=Path('scripts/produce_customer_recovery_terminal.py'); actual=hashlib.sha256(path.read_bytes()).hexdigest(); assert actual==os.environ['CUSTOMER_RECOVERY_PRODUCER_SHA256']; print('native producer image hash:',actual)"
    docker compose stop worker
    docker compose --profile browser-proof run --rm --no-deps \
        -e PRESENTATION_LOCALE="$locale" \
        -e CUSTOMER_RECOVERY_REVIEW_ROOT=/workspace/customer-review \
        -v "$PWD/$lane_dir:/workspace/customer-review" \
        -v "$PWD/$lane_dir/trace:/workspace/web/test-results" \
        browser-proof npx playwright test --config playwright.compose.config.ts \
        customer-revision-recovery.spec.ts &
    browser_pid=$!
    previous_stage=
    for attempt in $(seq 1 360); do
        if ! kill -0 "$browser_pid" 2>/dev/null; then break; fi
        if [ -s "$lane_dir/control.json" ]; then
            stage=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["stage"])' "$lane_dir/control.json")
            if [ "$stage" != "$previous_stage" ]; then
                case "$stage" in
                    fail-happy|fail-hard)
                        task_id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["task_id"])' "$lane_dir/control.json")
                        code=deadline_exceeded
                        [ "$stage" != fail-hard ] || code=invalid_schema
                        docker compose run --rm --no-deps \
                            -e NIGHT_VOYAGER_WORKER_DATABASE_URL="postgresql+asyncpg://night_voyager_worker:${NIGHT_VOYAGER_WORKER_PASSWORD:-worker-local-only}@postgres:5432/night_voyager" \
                            -v "$PWD/$lane_dir:/tmp/customer-review" \
                            demo-seed python scripts/produce_customer_recovery_terminal.py \
                            --task "$task_id" --code "$code" --proof "/tmp/customer-review/$stage-native.json"
                        ;;
                    # start also restarts completed seed dependencies; evolved Cases must fail closed.
                    start-worker) docker compose up --no-deps --no-build -d worker ;;
                    stop-worker) docker compose stop worker ;;
                    unknown-negative)
                        task_id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["task_id"])' "$lane_dir/control.json")
                        docker compose run --rm --no-deps \
                            -v "$PWD/$lane_dir:/tmp/customer-review" \
                            demo-seed python scripts/produce_customer_recovery_terminal.py \
                            --task "$task_id" --action unknown-negative --proof /tmp/customer-review/fail-hard-native.json
                        ;;
                    verify-source)
                        task_id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["source_task_id"])' "$lane_dir/control.json")
                        docker compose run --rm --no-deps \
                            -v "$PWD/$lane_dir:/tmp/customer-review" \
                            demo-seed python scripts/produce_customer_recovery_terminal.py \
                            --task "$task_id" --action verify-source --proof /tmp/customer-review/fail-happy-native.json
                        ;;
                    *) printf 'unknown customer proof stage: %s\n' "$stage" >&2; exit 1 ;;
                esac
                printf '%s\n' "$stage" > "$lane_dir/ack"
                previous_stage=$stage
            fi
        fi
        sleep 1
    done
    wait "$browser_pid"
    browser_pid=
    [ "$previous_stage" = verify-source ]
    printf 'customer-revision-recovery: native producer, browser consent, fresh review, receipt and negatives passed locale=%s\n' "$locale"
done
