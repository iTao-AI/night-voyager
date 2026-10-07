from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]


def run_launcher(
    tmp_path: Path,
    *,
    failure: str = "run",
    diagnostic_failure: bool = False,
    cleanup_failure: bool = False,
    suite: str = "authority",
) -> tuple[subprocess.CompletedProcess[str], list[dict[str, Any]]]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls = tmp_path / "calls.jsonl"
    docker = fake_bin / "docker"
    docker.write_text(
        f"#!{sys.executable}\n"
        + r"""
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
with Path(os.environ["TASK_DOCKER_CALLS"]).open("a") as output:
    record = {"args": args, "project": os.environ.get("COMPOSE_PROJECT_NAME")}
    output.write(json.dumps(record) + "\n")
if args[:3] != ["compose", "--profile", "db-test"]:
    sys.exit(90)
command = args[3:]
failure = os.environ["TASK_DOCKER_FAILURE"]
if command == ["config", "--quiet"]:
    sys.exit(23 if failure == "config" else 0)
if command[:3] == ["run", "--rm", "--build"]:
    sys.exit(37 if failure == "run" else 0)
if command == ["down", "--volumes", "--remove-orphans", "--rmi", "local"]:
    sys.exit(63 if os.environ["TASK_DOCKER_CLEANUP_FAILURE"] == "1" else 0)
if command == ["ps", "--all", "migrator", "postgres"]:
    print("migrator exited 1; postgres running")
elif command == ["logs", "--no-color", "--tail", "80", "migrator", "postgres"]:
    print("migration rejected at revision 0017")
    print("connection postgresql+asyncpg://reader:sample-password@postgres:5432/night_voyager")
    print("TOKEN=session-secret COOKIE=cookie-secret")
    print("Authorization: Bearer bearer-secret", file=sys.stderr)
    print("NIGHT_VOYAGER_DATABASE_URL=private-connection", file=sys.stderr)
    for number in range(500):
        print(f"safe-error-{number:03d} " + "x" * 1200)
else:
    sys.exit(91)
if os.environ["TASK_DOCKER_DIAGNOSTIC_FAILURE"] == "1":
    print("diagnostic command unavailable", file=sys.stderr)
    sys.exit(17)
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    result = subprocess.run(
        ["/bin/sh", "scripts/run_collaboration_db_tests.sh"],
        cwd=ROOT,
        env={
            "PATH": f"{fake_bin}{os.pathsep}/usr/bin{os.pathsep}/bin",
            "COMPOSE_PROJECT_NAME": "diagnostic-test",
            "SUITE": suite,
            "TASK_DOCKER_CALLS": str(calls),
            "TASK_DOCKER_FAILURE": failure,
            "TASK_DOCKER_DIAGNOSTIC_FAILURE": "1" if diagnostic_failure else "0",
            "TASK_DOCKER_CLEANUP_FAILURE": "1" if cleanup_failure else "0",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    records = (
        [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
    )
    return result, records


def test_failed_run_collects_only_owned_startup_diagnostics_before_cleanup(tmp_path: Path) -> None:
    result, calls = run_launcher(tmp_path)

    assert result.returncode == 37
    commands = [call["args"][3] for call in calls]
    assert commands == ["config", "run", "ps", "logs", "down"]
    assert {call["project"] for call in calls} == {"diagnostic-test-authority"}
    assert "migration rejected at revision 0017" in result.stderr


@pytest.mark.parametrize(("failure", "exit_code"), [("config", 23), ("run", 37)])
def test_diagnostic_and_cleanup_errors_do_not_mask_original_failure(
    tmp_path: Path, failure: str, exit_code: int
) -> None:
    result, calls = run_launcher(
        tmp_path, failure=failure, diagnostic_failure=True, cleanup_failure=True
    )

    assert result.returncode == exit_code
    commands = [call["args"][3] for call in calls]
    assert commands[-3:] == ["ps", "logs", "down"]
    assert commands.count("down") == 1
    assert commands.count("run") == (0 if failure == "config" else 1)
    assert {call["project"] for call in calls} == {"diagnostic-test-authority"}


def test_success_preserves_authority_projects_without_diagnostics(tmp_path: Path) -> None:
    result, calls = run_launcher(tmp_path, failure="none")

    assert result.returncode == 0, result.stderr
    expected_projects = [
        "diagnostic-test-authority",
        "diagnostic-test-revision",
        "diagnostic-test-empty",
        "diagnostic-test-unrelated",
        "diagnostic-test-table-history",
        "diagnostic-test-audit-history",
        "diagnostic-test-idempotency-history",
    ]
    assert [call["project"] for call in calls if call["args"][3] == "run"] == expected_projects
    assert [call["project"] for call in calls if call["args"][3] == "down"] == expected_projects
    assert all(call["args"][3] in {"config", "run", "down"} for call in calls)
    assert result.stdout == result.stderr == ""


def test_failed_run_bounds_and_redacts_diagnostic_output(tmp_path: Path) -> None:
    result, _ = run_launcher(tmp_path)
    output = result.stdout + result.stderr

    assert result.returncode == 37
    for value in [
        "sample-password",
        "session-secret",
        "cookie-secret",
        "bearer-secret",
        "private-connection",
    ]:
        assert value not in output
    assert "safe-error-000" in output
    assert "safe-error-499" not in output
    assert len(output) < 100_000
    assert max(map(len, output.splitlines())) <= 500


def test_unknown_suite_exits_before_any_docker_call(tmp_path: Path) -> None:
    result, calls = run_launcher(tmp_path, suite="unknown")

    assert result.returncode == 2
    assert calls == []
