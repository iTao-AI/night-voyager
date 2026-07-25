from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[3]
SOURCE_URL = "https://example.com/contract-source-1"


def run_rehearsal(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/verify_dra_live_closure.py",
            "rehearse-capture",
            *arguments,
            "--json",
        ],
        cwd=ROOT,
        env={"PATH": os.environ["PATH"]},
        text=True,
        capture_output=True,
        check=False,
    )


def run_command(command: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/verify_dra_live_closure.py",
            command,
            *arguments,
            "--json",
        ],
        cwd=ROOT,
        env={"PATH": os.environ["PATH"]},
        text=True,
        capture_output=True,
        check=False,
    )


def test_fake_capture_resumes_from_copied_bundle_in_fresh_process(
    tmp_path: Path,
) -> None:
    capture_root = tmp_path / "capture"
    captured = run_rehearsal(
        "--receipt-root",
        str(capture_root),
        "--phase",
        "capture",
    )
    assert captured.returncode == 10, captured.stderr
    capture_payload = json.loads(captured.stdout)
    assert capture_payload["exit_class"] == "safe_pause"
    assert capture_payload["permitted_next_command"] == "select-and-import"
    assert capture_payload["provider_create_calls"] == 1

    copied_root = tmp_path / "copied"
    shutil.copytree(capture_root, copied_root)
    resumed = run_rehearsal(
        "--receipt-root",
        str(copied_root),
        "--phase",
        "resume",
        "--declared-raw-url",
        SOURCE_URL,
    )
    assert resumed.returncode == 0, resumed.stderr
    resume_payload = json.loads(resumed.stdout)
    assert resume_payload["exit_class"] == "success"
    assert resume_payload["candidate_authority"] == "untrusted_candidate"
    assert resume_payload["provider_create_calls"] == 0
    assert resume_payload["artifact_present"] is False


def test_orphaned_artifact_blocks_recovery_until_acknowledged_cleanup(
    tmp_path: Path,
) -> None:
    receipt_root = tmp_path / "capture"
    captured = run_rehearsal(
        "--receipt-root",
        str(receipt_root),
        "--phase",
        "capture",
    )
    assert captured.returncode == 10, captured.stderr
    (receipt_root / "inspection-required.json").unlink()

    inspected = run_command(
        "inspect-recovery", "--receipt-root", str(receipt_root)
    )
    assert inspected.returncode == 40, inspected.stderr
    assert json.loads(inspected.stdout)["permitted_next_command"] == "cleanup"

    dry_run = run_command("cleanup", "--receipt-root", str(receipt_root))
    assert dry_run.returncode == 0, dry_run.stderr
    assert json.loads(dry_run.stdout)["retained"] == ["artifact"]

    removed = run_command(
        "cleanup",
        "--receipt-root",
        str(receipt_root),
        "--delete-ack",
        "delete-exact-live-artifact",
    )
    assert removed.returncode == 0, removed.stderr
    assert json.loads(removed.stdout)["removed"] == ["artifact"]
