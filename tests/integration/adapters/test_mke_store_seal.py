from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/prepare_evidence_loop_store.py"


@pytest.mark.mke
def test_exact_tagged_mke_store_is_sealed_and_reopened_read_only(
    tmp_path: Path,
) -> None:
    repository = os.environ.get("NIGHT_VOYAGER_MKE_REPOSITORY")
    if repository is None:
        pytest.skip("exact MKE repository was not provided")
    workspace = tmp_path / "workspace"
    receipts = tmp_path / "receipts"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--mke-repository",
            repository,
            "--workspace-root",
            str(workspace),
            "--receipt-root",
            str(receipts),
            "--json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["source_count"] == 4
    database = workspace / "store/store.sqlite"
    assert database.stat().st_mode & 0o777 == 0o400
    setup = (receipts / "mke-store-setup-receipt-v1.json").read_text()
    assert "/private/" not in setup
    assert "query" not in setup
    assert "cursor" not in setup
    assert "INERT_RETRIEVED_INSTRUCTION_V1" not in setup
    assert not (workspace / "store/store.sqlite-wal").exists()
    assert not (workspace / "store/store.sqlite-shm").exists()
