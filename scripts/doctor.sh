#!/bin/sh
set -eu

fail() {
    printf 'FAILED CHECK: %s\nexpected: %s\nobserved: %s\nrecovery: %s\n' "$1" "$2" "$3" "$4"
    exit 1
}

check_ports() {
    ports=${NIGHT_VOYAGER_DOCTOR_PORTS:-"${WEB_PORT:-3000} ${API_PORT:-8000} ${POSTGRES_PORT:-55432}"}
    probe_image=${NIGHT_VOYAGER_DOCTOR_PROBE_IMAGE:-python:3.12.13-slim}
    if ! docker image inspect "$probe_image" >/dev/null 2>&1; then
        docker pull "$probe_image" >/dev/null 2>&1 || fail \
            "port probe image" "$probe_image is locally available" \
            "Docker could not pull the probe image" \
            "run docker pull $probe_image, then rerun make doctor"
    fi
    for port in $ports; do
        probe_name="night-voyager-port-probe-$$-$port"
        if probe_output=$(docker run --detach --rm --name "$probe_name" \
            --publish "127.0.0.1:$port:8000" "$probe_image" \
            python -c "import time; time.sleep(30)" 2>&1); then
            docker rm --force "$probe_name" >/dev/null 2>&1 || true
        else
            fail "port availability" "127.0.0.1:$port is free" \
                "Docker could not bind the port: $probe_output" \
                "stop the process using the port or override WEB_PORT/API_PORT/POSTGRES_PORT"
        fi
        printf 'PASSED CHECK: port 127.0.0.1:%s is free\n' "$port"
    done
}

if [ "${NIGHT_VOYAGER_DOCTOR_ONLY:-}" = "ports" ]; then
    check_ports
    exit 0
fi

command -v docker >/dev/null 2>&1 || fail \
    "Docker CLI" "docker command available" "docker command not found" \
    "install Docker Desktop, then rerun make doctor"
docker info >/dev/null 2>&1 || fail \
    "Docker daemon" "daemon reachable" "docker info failed" \
    "start Docker Desktop, wait until ready, then rerun make doctor"
docker compose version >/dev/null 2>&1 || fail \
    "Docker Compose" "docker compose available" "docker compose version failed" \
    "install or enable the Docker Compose plugin, then rerun make doctor"
docker compose up --help 2>/dev/null | grep -q -- '--wait' || fail \
    "Compose capability" "docker compose up supports --wait" "--wait is unavailable" \
    "upgrade Docker Desktop or Docker Compose, then rerun make doctor"
printf 'PASSED CHECK: Docker daemon and Compose --wait are available\n'

available_kb=$(df -Pk . | awk 'NR == 2 {print $4}')
minimum_kb=5242880
[ "$available_kb" -ge "$minimum_kb" ] || fail \
    "disk space" "at least 5 GiB available" "${available_kb} KiB available" \
    "free at least 5 GiB on the project filesystem, then rerun make doctor"
printf 'PASSED CHECK: disk space %s KiB available\n' "$available_kb"
check_ports

mode=${MODE:-evaluator}
[ "$mode" = "evaluator" ] || [ "$mode" = "dev" ] || fail \
    "doctor mode" "MODE is evaluator or dev" "MODE=$mode" \
    "rerun make doctor or make doctor MODE=dev"

if [ "$mode" = "dev" ]; then
    python_version=$(cat .python-version)
    node_version=$(cat .node-version)
    command -v uv >/dev/null 2>&1 || fail \
        "uv" "uv available" "uv command not found" \
        "install uv, then run uv python install $python_version"
    uv python find "$python_version" >/dev/null 2>&1 || fail \
        "Python" "Python $python_version available through uv" "uv could not find Python $python_version" \
        "run uv python install $python_version"
    command -v node >/dev/null 2>&1 || fail \
        "Node.js" "Node.js $node_version" "node command not found" \
        "run nvm install $node_version && nvm use $node_version"
    observed_node=$(node --version)
    [ "$observed_node" = "v$node_version" ] || fail \
        "Node.js" "v$node_version" "$observed_node" \
        "run nvm install $node_version && nvm use $node_version"
    command -v npm >/dev/null 2>&1 || fail \
        "npm" "npm available with Node.js $node_version" "npm command not found" \
        "reinstall Node.js $node_version with npm"
    printf 'PASSED CHECK: contributor Python/uv/Node/npm toolchain is available\n'
fi

printf 'doctor: %s preflight passed\n' "$mode"
