#!/bin/sh
set -eu

if [ "${1:-}" = "fixture" ]; then
  shift
  exec uv run python scripts/verify_dra_consumer.py fixture "$@"
fi

if [ "${1:-}" = "live" ]; then
  shift
  temp=$(mktemp -d)
  trap 'rm -rf -- "$temp"' EXIT HUP INT TERM
  export UV_PROJECT_ENVIRONMENT="$temp/venv"
  uv sync --locked --extra dra
  uv run python scripts/verify_dra_consumer.py live "$@"
  exit
fi

echo "usage: scripts/run_dra_lane.sh fixture|live [args...]" >&2
exit 2
