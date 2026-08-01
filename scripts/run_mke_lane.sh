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
  : "${EVIDENCE_LOOP_RUN_ROOT:?set the validated external evidence-loop run root}"
  native_python="$EVIDENCE_LOOP_RUN_ROOT/work/venv/bin/python"
  if [ ! -x "$native_python" ]; then
    echo "evidence-loop native runtime is unavailable under the validated run root" >&2
    exit 11
  fi
  export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}src"
  export PYTHONDONTWRITEBYTECODE=1
  export PYTHONNOUSERSITE=1
  export PYTHONSAFEPATH=1
  exec "$native_python" \
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
