from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
DATASET = ROOT / "tests/fixtures/evidence_loop/development-dataset-v1.json"
STORE_RECEIPT = (
    ROOT / "tmp/evidence-loop-a3-native-operator-final/receipts/sealed-mke-store-v1.json"
)


@pytest.mark.mke
def test_three_fresh_development_processes_are_byte_identical(
    tmp_path: Path,
) -> None:
    outputs: list[bytes] = []
    for index in range(3):
        output = tmp_path / f"evaluation-{index}.json"
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/evaluate_evidence_loop.py"),
                "--development-dataset",
                str(DATASET),
                "--store-receipt",
                str(STORE_RECEIPT),
                "--output",
                str(output),
                "--json",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        outputs.append(output.read_bytes())

    assert outputs[0] == outputs[1] == outputs[2]

    verified = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/verify_evidence_loop.py"),
            "--receipt",
            str(tmp_path / "evaluation-0.json"),
            "--json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["code"] == "evidence_loop_receipt_verified"


def test_internal_holdout_worker_is_three_process_byte_identical() -> None:
    request = json.dumps(
        {
            "dataset": json.loads(DATASET.read_text(encoding="utf-8")),
            "artifact_bindings": {
                "pre_registration_sha256": "a" * 64,
                "holdout_dataset_sha256": "b" * 64,
                "mke_capture_sha256": "c" * 64,
            },
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    receipts = [
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/evaluate_evidence_loop.py"),
                "--fresh-worker",
            ],
            cwd=ROOT,
            input=request,
            check=False,
            capture_output=True,
            text=True,
        )
        for _ in range(3)
    ]

    assert all(result.returncode == 0 for result in receipts)
    assert all(result.stderr == "" for result in receipts)
    assert receipts[0].stdout == receipts[1].stdout == receipts[2].stdout
