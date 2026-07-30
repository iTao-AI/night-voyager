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
    archive = os.environ.get("NIGHT_VOYAGER_MKE_SOURCE_ARCHIVE")
    if archive is None:
        pytest.skip("exact MKE source archive was not provided")
    work = tmp_path / "work"
    store = tmp_path / "store"
    receipt = tmp_path / "receipts/sealed-mke-store-v1.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--mke-source-archive",
            archive,
            "--mke-tag-object",
            "1ca0a0b348638369e8407270ca5f363b0e551a9e",
            "--mke-commit",
            "d258c10dc40bd9eccd67c858b56f4e4cf5fe4610",
            "--source-manifest",
            str(ROOT / "tests/fixtures/evidence_loop/source-manifest-v1.json"),
            "--work-root",
            str(work),
            "--store-root",
            str(store),
            "--receipt",
            str(receipt),
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
    assert payload["code"] == "evidence_loop_store_sealed"
    assert payload["source_count"] == 4
    database = store / "store.sqlite"
    assert database.stat().st_mode & 0o777 == 0o400
    setup = receipt.read_text()
    assert "/private/" not in setup
    assert "query" not in setup
    assert "cursor" not in setup
    assert "INERT_RETRIEVED_INSTRUCTION_V1" not in setup
    assert not (store / "store.sqlite-wal").exists()
    assert not (store / "store.sqlite-shm").exists()
    setup_payload = json.loads(setup)
    assert setup_payload["sealed_write_rejection"] == {
        "active_publication_impact": "unchanged",
        "active_set_unchanged": True,
        "attempted_tool": "ingest_file",
        "problem": "internal_error",
        "rejected": True,
        "store_tree_unchanged": True,
    }
    assert setup_payload["input_admission"]["root_mode"] == "0700"
    assert all(
        item["mode"] == "0400"
        for item in setup_payload["input_admission"]["files"]
    )
