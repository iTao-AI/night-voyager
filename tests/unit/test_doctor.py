from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_occupied_port_failure_is_structured() -> None:
    port = "34567"
    environment = os.environ.copy()
    environment["NIGHT_VOYAGER_DOCTOR_PORTS"] = port
    environment["NIGHT_VOYAGER_DOCTOR_ONLY"] = "ports"
    environment["NIGHT_VOYAGER_DOCTOR_ASSUME_PORT_IN_USE"] = port

    result = subprocess.run(
        ["sh", "scripts/doctor.sh"],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "FAILED CHECK: port availability" in result.stdout
    assert "expected: 127.0.0.1:" in result.stdout
    assert "observed: port is already in use" in result.stdout
    assert "recovery: stop the process using the port" in result.stdout
