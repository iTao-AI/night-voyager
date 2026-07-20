from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def fake_docker_path(tmp_path: Path) -> Path:
    docker = tmp_path / "docker"
    docker.write_text(
        """#!/bin/sh
if [ "$1 $2" = "image inspect" ]; then exit 0; fi
if [ "$1" = "run" ]; then
    case "$*" in
        *"--network none"*)
            printf '%s\n' "${FAKE_DOCKER_AVAILABLE_KB:-16777216}"
            exit "${FAKE_DOCKER_SPACE_EXIT:-0}"
            ;;
    esac
    if [ "${FAKE_DOCKER_PORT_OCCUPIED:-}" = "1" ]; then
        echo "bind: address already in use" >&2
        exit 1
    fi
    echo port-probe-container
    exit 0
fi
if [ "$1" = "rm" ]; then exit 0; fi
exit 2
""",
        encoding="utf-8",
    )
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
    return tmp_path


def run_ports_probe(tmp_path: Path, *, occupied: bool) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PATH"] = str(fake_docker_path(tmp_path))
    environment["NIGHT_VOYAGER_DOCTOR_PORTS"] = "34567"
    environment["NIGHT_VOYAGER_DOCTOR_ONLY"] = "ports"
    if occupied:
        environment["FAKE_DOCKER_PORT_OCCUPIED"] = "1"
    return subprocess.run(
        ["/bin/sh", "scripts/doctor.sh"],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_port_probe_needs_no_netcat(tmp_path: Path) -> None:
    result = run_ports_probe(tmp_path, occupied=False)

    assert result.returncode == 0
    assert "PASSED CHECK: port 127.0.0.1:34567 is free" in result.stdout


def test_occupied_port_failure_is_structured(tmp_path: Path) -> None:
    result = run_ports_probe(tmp_path, occupied=True)

    assert result.returncode == 1
    assert "FAILED CHECK: port availability" in result.stdout
    assert "expected: 127.0.0.1:34567 is free" in result.stdout
    assert "observed: Docker could not bind the port" in result.stdout
    assert "recovery: stop the process using the port" in result.stdout


def run_docker_space_probe(
    tmp_path: Path, *, available_kb: str, minimum_kb: str = "8388608", exit_code: int = 0
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PATH"] = str(fake_docker_path(tmp_path))
    environment["NIGHT_VOYAGER_DOCTOR_ONLY"] = "docker-space"
    environment["NIGHT_VOYAGER_DOCKER_MINIMUM_KB"] = minimum_kb
    environment["FAKE_DOCKER_AVAILABLE_KB"] = available_kb
    environment["FAKE_DOCKER_SPACE_EXIT"] = str(exit_code)
    return subprocess.run(
        ["/bin/sh", "scripts/doctor.sh"],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_docker_space_probe_reports_vm_filesystem_separately(tmp_path: Path) -> None:
    result = run_docker_space_probe(tmp_path, available_kb="8388608")

    assert result.returncode == 0
    assert "PASSED CHECK: Docker VM filesystem 8388608 KiB available" in result.stdout


def test_docker_space_probe_fails_closed_when_space_is_low(tmp_path: Path) -> None:
    result = run_docker_space_probe(tmp_path, available_kb="4194304")

    assert result.returncode == 1
    assert "FAILED CHECK: Docker VM filesystem space" in result.stdout
    assert "expected: at least 8388608 KiB available" in result.stdout
    assert "observed: 4194304 KiB available" in result.stdout
    assert "does not delete Docker resources automatically" in result.stdout


def test_docker_space_probe_fails_closed_on_malformed_output(tmp_path: Path) -> None:
    result = run_docker_space_probe(tmp_path, available_kb="not-a-number")

    assert result.returncode == 1
    assert "FAILED CHECK: Docker VM filesystem probe" in result.stdout
    assert "observed: malformed probe output: not-a-number" in result.stdout
