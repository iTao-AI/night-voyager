from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from night_voyager.dra.live_models import (
    DraCaptureIntentV1,
    DraPollRecoveryReceiptV1,
    DraPreflightReceiptV1,
    DraReconciliationRequiredReceiptV1,
    derive_stage_key,
)
from night_voyager.dra.live_storage import LiveReceiptStore

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

    capture_inspection = run_command(
        "inspect-recovery", "--receipt-root", str(capture_root)
    )
    assert capture_inspection.returncode == 0, capture_inspection.stderr
    assert json.loads(capture_inspection.stdout)[
        "provider_attempt_consumed"
    ] is True

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

    completed_inspection = run_command(
        "inspect-recovery", "--receipt-root", str(copied_root)
    )
    assert completed_inspection.returncode == 0, completed_inspection.stderr
    assert json.loads(completed_inspection.stdout)[
        "provider_attempt_consumed"
    ] is True


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


def test_recovery_cli_derives_provider_consumption_from_durable_receipts(
    tmp_path: Path,
) -> None:
    root = tmp_path / "receipts"
    query = tmp_path / "query.txt"
    query.write_text("bounded synthetic query", encoding="utf-8")
    frozen = run_command(
        "freeze-intent",
        "--receipt-root",
        str(root),
        "--query-file",
        str(query),
        "--organization-id",
        "10000000-0000-0000-0000-000000000001",
        "--case-id",
        "40000000-0000-0000-0000-000000000003",
        "--expected-case-revision",
        "1",
        "--advisor-actor-id",
        "20000000-0000-0000-0000-000000000001",
        "--one-attempt-ack",
        "separately-authorized-one-attempt",
    )
    assert frozen.returncode == 0, frozen.stderr
    preflight = run_command("preflight-live", "--receipt-root", str(root))
    assert preflight.returncode == 0, preflight.stderr
    inspected = run_command(
        "inspect-recovery", "--receipt-root", str(root)
    )
    assert inspected.returncode == 0, inspected.stderr
    assert json.loads(inspected.stdout)["provider_attempt_consumed"] is False

    with LiveReceiptStore.open(root) as store:
        intent = store.read_receipt("intent.json", DraCaptureIntentV1)
        preflight_receipt = store.read_receipt(
            "preflight.json", DraPreflightReceiptV1
        )
        reconciliation = DraReconciliationRequiredReceiptV1(
            schema_version=(
                "night-voyager.dra-live-reconciliation-required.v1"
            ),
            intent_sha256=intent.intent_sha256,
            attempt_id=intent.attempt_id,
            intent_receipt=preflight_receipt.intent_receipt,
            create_key=derive_stage_key(
                intent.intent_sha256, "create", intent.attempt_id
            ),
            provider_attempt_consumed=True,
            permitted_next_command="reconcile-create",
        )
        store.write_receipt("reconciliation-required.json", reconciliation)
    inspected = run_command(
        "inspect-recovery", "--receipt-root", str(root)
    )
    assert json.loads(inspected.stdout)["provider_attempt_consumed"] is True

    with LiveReceiptStore.open(root) as store:
        preflight_identity = next(
            receipt
            for receipt in store.verify_recovery_bundle().receipts
            if receipt.logical_name == "preflight.json"
        )
        store.write_receipt(
            "poll-recovery.json",
            DraPollRecoveryReceiptV1(
                intent_sha256=intent.intent_sha256,
                attempt_id=intent.attempt_id,
                preflight_receipt=preflight_identity,
                thread_id="thread-1",
                run_id="run-1",
                segment_id="segment-1",
                last_state_version=1,
                provider_attempt_consumed=True,
            ),
        )
    inspected = run_command(
        "inspect-recovery", "--receipt-root", str(root)
    )
    assert json.loads(inspected.stdout)["provider_attempt_consumed"] is True
