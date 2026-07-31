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
    dra_archive = os.environ.get("NIGHT_VOYAGER_DRA_SOURCE_ARCHIVE")
    if archive is None or dra_archive is None:
        pytest.skip("exact producer source archives were not provided")
    run_root = tmp_path / "run"
    run_root.mkdir(mode=0o700)
    receipt = run_root / "receipts/sealed-mke-store-v1.json"
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
            "--dra-source-archive",
            dra_archive,
            "--dra-tag-object",
            "f828606741f636bca7ddbb66244ca60019eaa3c8",
            "--dra-commit",
            "cb1f4660ee4ac7d81b04ffea014362e933487e61",
            "--source-manifest",
            str(ROOT / "tests/fixtures/evidence_loop/source-manifest-v1.json"),
            "--run-root",
            str(run_root),
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
    database = run_root / "store/store.sqlite"
    assert database.stat().st_mode & 0o777 == 0o400
    assert (run_root / "store").stat().st_mode & 0o777 == 0o500
    setup = receipt.read_text()
    assert "/private/" not in setup
    assert "query" not in setup
    assert "cursor" not in setup
    assert "INERT_RETRIEVED_INSTRUCTION_V1" not in setup
    assert [path.name for path in sorted((run_root / "store").iterdir())] == [
        "store.sqlite",
        "store.sqlite-shm",
        "store.sqlite-wal",
    ]
    assert (run_root / "store/store.sqlite-shm").stat().st_size == 32_768
    assert (run_root / "store/store.sqlite-wal").stat().st_size == 0
    assert all(path.stat().st_mode & 0o777 == 0o400 for path in (run_root / "store").iterdir())
    setup_payload = json.loads(setup)
    assert setup_payload["fresh_process_verification_runs"] == 3
    assert setup_payload["sqlite_authority_image"] == {
        "authority_image": "sqlite_read_only_wal_atomic_snapshot",
        "materialization_phase": "task_owned_preparation_mutation",
        "ordered_basenames": [
            "store.sqlite",
            "store.sqlite-shm",
            "store.sqlite-wal",
        ],
        "shm_byte_length": 32_768,
        "wal_byte_length": 0,
    }
    assert setup_payload["sealed_write_rejection"] == {
        "active_publication_impact": "unchanged",
        "active_set_unchanged": True,
        "attempted_tool": "ingest_file",
        "problem": "internal_error",
        "rejected": True,
        "store_tree_unchanged": True,
    }
    assert setup_payload["input_admission"]["root_mode"] == "0700"
    assert all(item["mode"] == "0400" for item in setup_payload["input_admission"]["files"])
    admitted = {item["logical_name"]: item for item in setup_payload["input_admission"]["files"]}
    assert admitted["mke_a3_source_tree_archive"]["basename"] == "mke-v0.1.5.tar"
    assert admitted["dra_source_archive"]["basename"] == "dra-v0.1.8-source.tar.gz"
