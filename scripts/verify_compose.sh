#!/bin/sh
set -eu

COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-night-voyager-compose-proof-$$}
UPDATE_COLLABORATION_SCREENSHOT=${UPDATE_COLLABORATION_SCREENSHOT:-0}
FACT_TO_PLAN_PROOF_FILE=docs/assets/.fact-to-plan-proof.json
worker_start_pid=
export COMPOSE_PROJECT_NAME

cleanup() {
    if [ -n "$worker_start_pid" ]; then
        kill "$worker_start_pid" 2>/dev/null || true
        wait "$worker_start_pid" 2>/dev/null || true
    fi
    rm -f "$FACT_TO_PLAN_PROOF_FILE"
    docker compose down --volumes --remove-orphans --rmi local
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
docker compose down --volumes --remove-orphans
docker compose up --no-build --wait
rm -f "$FACT_TO_PLAN_PROOF_FILE"
docker compose pause worker
(
    sleep 15
    docker compose unpause worker
) &
worker_start_pid=$!
docker compose --profile browser-proof run --rm --no-deps \
    -e FACT_TO_PLAN_PROOF_FILE=/workspace/docs/assets/.fact-to-plan-proof.json \
    browser-proof npx playwright test --config playwright.compose.config.ts fact-to-plan.spec.ts
wait "$worker_start_pid"
worker_start_pid=
test -f "$FACT_TO_PLAN_PROOF_FILE"
docker compose run --rm --no-deps \
    -v "$PWD/$FACT_TO_PLAN_PROOF_FILE:/tmp/fact-to-plan-proof.json:ro" \
    demo-seed python scripts/verify_fact_to_plan_flow.py \
    --proof-file /tmp/fact-to-plan-proof.json
rm -f "$FACT_TO_PLAN_PROOF_FILE"
printf 'compose-proof: governed fact-to-plan browser and database proof passed\n'
