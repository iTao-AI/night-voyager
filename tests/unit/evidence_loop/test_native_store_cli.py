from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/prepare_evidence_loop_store.py"


def test_native_store_cli_help_is_public_safe() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--json" in result.stdout
    assert "custody" not in result.stdout.lower()
    assert result.stderr == ""


def test_native_store_cli_missing_required_input_is_bounded_json() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert set(payload) == {"stage", "code", "problem", "cause", "recovery"}
    assert payload["stage"] == "arguments"
    assert result.stderr == ""
