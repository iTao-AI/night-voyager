#!/bin/sh
set -eu

if [ "$#" -lt 1 ] || { [ "$1" != "test" ] && [ "$1" != "proof" ]; }; then
  echo "usage: scripts/run_mke_lane.sh test|proof [args...]" >&2
  exit 2
fi

mode=$1
shift
temp=$(mktemp -d)
trap 'rm -rf -- "$temp"' EXIT HUP INT TERM
export UV_PROJECT_ENVIRONMENT="$temp/venv"
uv sync --locked --extra mke

if [ "$mode" = "test" ]; then
  uv run pytest -q -m mke "$@"
else
  uv run python scripts/verify_mke_consumer.py proof "$@"
fi
