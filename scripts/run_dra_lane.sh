#!/bin/sh
set -eu

if [ "${1:-}" = "fixture" ]; then
  shift
  exec uv run python scripts/verify_dra_consumer.py fixture "$@"
fi

if [ "${1:-}" = "rehearse" ]; then
  shift
  uv run python -c \
    'from night_voyager.dra.fixtures import load_strict_live_closure_scenario; load_strict_live_closure_scenario()'
  temp=$(mktemp -d)
  trap 'rm -rf -- "$temp"' EXIT HUP INT TERM
  set +e
  uv run python scripts/verify_dra_live_closure.py rehearse-capture \
    --receipt-root "$temp/receipts" --phase capture --json
  capture_status=$?
  set -e
  if [ "$capture_status" -ne 10 ]; then
    exit "$capture_status"
  fi
  uv run python scripts/verify_dra_live_closure.py rehearse-capture \
    --receipt-root "$temp/receipts" --phase resume \
    --declared-raw-url "https://example.com/contract-source-1" --json "$@"
  exit
fi

if [ "${1:-}" = "live" ]; then
  shift
  temp=$(mktemp -d)
  trap 'rm -rf -- "$temp"' EXIT HUP INT TERM
  export UV_PROJECT_ENVIRONMENT="$temp/venv"
  uv sync --locked --extra dra
  uv run python scripts/verify_dra_live_closure.py capture-live "$@"
  exit
fi

echo "usage: scripts/run_dra_lane.sh fixture|rehearse|live [args...]" >&2
exit 2
