#!/bin/sh
set -eu

if [ "$#" -lt 1 ] || {
  [ "$1" != "test" ] &&
    [ "$1" != "proof" ] &&
    [ "$1" != "evidence-loop-development" ] &&
    [ "$1" != "evidence-loop-holdout" ]
}; then
  echo "usage: scripts/run_mke_lane.sh test|proof|evidence-loop-development|evidence-loop-holdout [args...]" >&2
  exit 2
fi

mode=$1
shift
if [ "$mode" = "evidence-loop-development" ]; then
  exec uv run python scripts/evaluate_evidence_loop.py "$@"
fi
if [ "$mode" = "evidence-loop-holdout" ]; then
  export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}src"
  exec tmp/evidence-loop-a3-native-operator-final/work/venv/bin/python \
    scripts/evaluate_evidence_loop.py "$@"
fi

temp=$(mktemp -d)
trap 'rm -rf -- "$temp"' EXIT HUP INT TERM
export UV_PROJECT_ENVIRONMENT="$temp/venv"
uv sync --locked --extra mke

if [ "$mode" = "test" ]; then
  uv run pytest -q -m mke "$@"
else
  uv run python scripts/verify_mke_consumer.py proof "$@"
fi
