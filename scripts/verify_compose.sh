#!/bin/sh
set -eu

COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-night-voyager-compose-proof-$$}
export COMPOSE_PROJECT_NAME

cleanup() {
    docker compose down --volumes --remove-orphans
}
trap cleanup EXIT INT TERM

docker compose config --quiet
docker compose up --build --wait

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
docker compose exec -T api python scripts/verify_m4a_flow.py --verify-existing
docker compose exec -T web wget -q --spider http://127.0.0.1:3000
printf 'compose-proof: Web probe passed\n'
