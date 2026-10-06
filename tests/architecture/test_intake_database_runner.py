from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_TESTS = (
    "tests/integration/planning/test_intake_revision_source_pins.py",
    "tests/integration/planning/test_intake_revision_authority.py",
    "tests/integration/connected_demo/test_http_intake_read_models.py",
    "tests/integration/connected_demo/test_intake_read_models.py",
    "tests/integration/connected_demo/test_intake_revision_flow.py",
)
MIGRATION_TEST = "tests/integration/planning/test_intake_revision_migration.py"


def run_runner(
    tmp_path: Path, *arguments: str, fail_pytest: bool = False, collect_pytest: bool = False
) -> tuple[subprocess.CompletedProcess[str], list[dict[str, Any]]]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls = tmp_path / "calls.jsonl"
    state = tmp_path / "revision.txt"
    fake_tool = (
        f"#!{sys.executable}\n"
        + r"""
import json
import os
import subprocess
import sys
from pathlib import Path

args = sys.argv[1:]
record = {
    "tool": Path(sys.argv[0]).name,
    "arguments": args,
    "project": os.environ.get("COMPOSE_PROJECT_NAME"),
    "migration_phase": os.environ.get("NIGHT_VOYAGER_INTAKE_MIGRATION_TEST"),
}
with Path(os.environ["TASK_RUNNER_CALLS"]).open("a") as output:
    output.write(json.dumps(record) + "\n")
if record["tool"] == "uv":
    if "alembic" in args:
        command = args[args.index("alembic") + 1:]
        state = Path(os.environ["TASK_RUNNER_REVISION"])
        if command[0] == "current":
            print(state.read_text() if state.exists() else "0017")
        elif command == ["downgrade", "0014"]:
            print("terminal task recovery history exists", file=sys.stderr)
            sys.exit(1)
        else:
            state.write_text("0017" if command[1] == "head" else command[1])
    if "pytest" in args and os.environ.get("TASK_RUNNER_FAIL_PYTEST") == "1":
        sys.exit(3)
    if "pytest" in args and os.environ.get("TASK_RUNNER_COLLECT_PYTEST") == "1":
        index = args.index("pytest")
        launcher = (
            [sys.executable, "-m", "pytest"]
            if args[index - 2:index] == ["python", "-m"]
            else [str(Path(sys.executable).with_name("pytest"))]
        )
        # Keep the runner's actual entrypoint and arguments; collect without DB I/O.
        collection = subprocess.run([*launcher, *args[index + 1:], "--collect-only"])
        if collection.returncode:
            sys.exit(collection.returncode)
    if "pytest" in args and record["migration_phase"] == "true":
        # The four migration tests leave their isolated database at current head.
        Path(os.environ["TASK_RUNNER_REVISION"]).write_text("0017")
"""
    )
    for name in ("uv", "docker"):
        path = fake_bin / name
        path.write_text(fake_tool)
        path.chmod(0o755)
    inherited = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "PYTEST_ADDOPTS", "NIGHT_VOYAGER_INTAKE_MIGRATION_TEST"}
    }
    environment = {
        **inherited,
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "TASK_RUNNER_CALLS": str(calls),
        "TASK_RUNNER_REVISION": str(state),
        "TASK_RUNNER_FAIL_PYTEST": "1" if fail_pytest else "0",
        "TASK_RUNNER_COLLECT_PYTEST": "1" if collect_pytest else "0",
        "COMPOSE_PROJECT_NAME": "intake-runner-test",
    }
    result = subprocess.run(
        ["sh", "scripts/run_db_tests.sh", *arguments],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    records = (
        [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
    )
    return result, records


def test_fixed_demo_baseline_is_isolated_from_intake_fixtures(tmp_path: Path) -> None:
    result, calls = run_runner(tmp_path, "inside")
    assert result.returncode == 0, result.stderr
    baseline = next(call["arguments"] for call in calls if "tests/security" in call["arguments"])
    for path in (*RUNTIME_TESTS, MIGRATION_TEST):
        assert f"--ignore={path}" in baseline
    assert "tests/integration/planning" in baseline
    assert "tests/integration/identity" in baseline


def test_intake_runtime_registers_source_before_all_owned_regressions(tmp_path: Path) -> None:
    result, calls = run_runner(tmp_path, "inside-intake-revision")
    assert result.returncode == 0, result.stderr
    seed = next(i for i, call in enumerate(calls) if "--with-intake-revision" in call["arguments"])
    test = next(i for i, call in enumerate(calls) if "pytest" in call["arguments"])
    assert seed < test
    selected = [arg for arg in calls[test]["arguments"] if arg.startswith("tests/")]
    assert selected == list(RUNTIME_TESTS)
    assert "--no-editable" in calls[test]["arguments"]
    assert calls[test]["arguments"][:5] == ["run", "--no-editable", "python", "-m", "pytest"]


def test_intake_migration_starts_at_unseeded_predecessor_and_enables_all_cases(
    tmp_path: Path,
) -> None:
    result, calls = run_runner(tmp_path, "inside-intake-revision-migration")
    assert result.returncode == 0, result.stderr
    downgrade = next(
        i for i, call in enumerate(calls) if call["arguments"][-2:] == ["downgrade", "0016"]
    )
    test = next(i for i, call in enumerate(calls) if "pytest" in call["arguments"])
    assert downgrade < test
    assert not any("scripts/seed_demo.py" in call["arguments"] for call in calls[:test])
    assert calls[test]["migration_phase"] == "true"
    assert calls[test]["arguments"][:5] == ["run", "--no-editable", "python", "-m", "pytest"]
    assert [arg for arg in calls[test]["arguments"] if arg.startswith("tests/")] == [MIGRATION_TEST]


def test_required_default_database_gate_runs_both_intake_lanes_once(tmp_path: Path) -> None:
    result, calls = run_runner(tmp_path)
    assert result.returncode == 0, result.stderr
    runs = [call for call in calls if "--build" in call["arguments"]]
    owned = [
        call
        for call in runs
        if call["arguments"][-1] in {"inside-intake-revision", "inside-intake-revision-migration"}
    ]
    assert {call["arguments"][-1] for call in owned} == {
        "inside-intake-revision",
        "inside-intake-revision-migration",
    }
    assert len(owned) == 2
    assert len({call["project"] for call in owned}) == 2
    for call in owned:
        assert any(
            item["project"] == call["project"] and "--volumes" in item["arguments"]
            for item in calls
        )


@pytest.mark.parametrize("mode", ("inside-intake-revision", "inside-intake-revision-migration"))
def test_intake_database_failures_propagate_to_required_gate(tmp_path: Path, mode: str) -> None:
    result, calls = run_runner(tmp_path, mode, fail_pytest=True)
    assert result.returncode == 3
    assert "pytest" in calls[-1]["arguments"]
    assert not any("scripts/verify_release.py" in call["arguments"] for call in calls)


@pytest.mark.parametrize(
    "mode,expected",
    (
        ("inside-intake-revision-migration", {MIGRATION_TEST: 4}),
        ("inside-intake-revision", dict(zip(RUNTIME_TESTS, (4, 9, 1, 1, 4), strict=True))),
    ),
)
def test_actual_intake_runner_entrypoint_collects_every_owned_node(
    tmp_path: Path, mode: str, expected: dict[str, int]
) -> None:
    result, calls = run_runner(tmp_path, mode, collect_pytest=True)
    assert result.returncode == 0, result.stdout + result.stderr
    nodes = [
        line for line in result.stdout.splitlines() if line.startswith("tests/") and "::" in line
    ]
    assert len(nodes) == len(set(nodes))
    assert Counter(node.split("::", 1)[0] for node in nodes) == expected
    selected = next(call for call in calls if "pytest" in call["arguments"])
    assert selected["arguments"][:5] == ["run", "--no-editable", "python", "-m", "pytest"]
    assert selected["migration_phase"] == ("true" if mode.endswith("migration") else None)
