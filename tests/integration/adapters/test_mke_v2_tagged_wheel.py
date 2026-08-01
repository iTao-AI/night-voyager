from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from night_voyager.evidence_loop import native_store

ROOT = Path(__file__).resolve().parents[3]


def _capture_cases() -> list[dict[str, Any]]:
    manifest = cast(
        dict[str, Any],
        json.loads(
            (ROOT / "tests/fixtures/evidence_loop/source-manifest-v1.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    expected_values = [
        "completed semester of statistics",
        "2026-11-15",
        "IELTS 6.5",
        "21 calendar days",
    ]
    sources = cast(list[dict[str, Any]], manifest["sources"])
    cases: list[dict[str, Any]] = []
    for index, (source, expected_value) in enumerate(
        zip(sources, expected_values, strict=True),
        start=1,
    ):
        cases.append(
            {
                "payload": {
                    "identity": {
                        "case_id": f"00000000-0000-4000-8000-{index:012d}",
                        "case_revision": 1,
                        "query_id": f"10000000-0000-4000-8000-{index:012d}",
                        "decision_dimension": (
                            "program_requirements" if index % 2 else "application_timeline"
                        ),
                    },
                    "mke_request": {"query": expected_value, "limit": 20},
                    "pre_registered_gap": {
                        "fact_key": f"mock.fact_{index}",
                        "expected_value": expected_value,
                    },
                    "eligible_mke_sources": [
                        {
                            "dataset_source_id": source["dataset_source_id"],
                            "evaluation_canonical_source_id": source[
                                "evaluation_canonical_source_id"
                            ],
                            "expected_content_fingerprint": (f"sha256:{source['content_sha256']}"),
                            "expected_evidence_text_sha256": (
                                f"sha256:{source['expected_extracted_text_sha256']}"
                            ),
                            "expected_original_utf8_bytes": source["expected_extracted_utf8_bytes"],
                            "expected_locator": source["expected_locator"],
                            "expected_publication_revision": source[
                                "expected_publication_revision"
                            ],
                        }
                    ],
                    "control": {"source_pack_entries": []},
                }
            }
        )
    return cases


def _compact_native_venv_with_system_site_packages(
    tmp_path: Path,
) -> Path:
    retained = ROOT / "tmp/evidence-loop-a3-native-operator-final/work/venv"
    source_python = (retained / "bin/python").resolve()
    base_root = source_python.parent.parent
    target = tmp_path / "venv"
    (target / "bin").mkdir(parents=True)
    (target / "lib").mkdir()
    shutil.copy2(source_python, target / "bin/python", follow_symlinks=True)
    (target / "bin/python3.12").symlink_to("python")
    (target / "lib/libpython3.12.dylib").symlink_to(
        base_root / "lib/libpython3.12.dylib"
    )
    (target / "lib/python3.12").symlink_to(
        retained / "lib/python3.12",
        target_is_directory=True,
    )
    config = (retained / "pyvenv.cfg").read_text(encoding="utf-8").replace(
        "include-system-site-packages = false",
        "include-system-site-packages = true",
    )
    (target / "pyvenv.cfg").write_text(config, encoding="utf-8")
    return target


@pytest.mark.mke
def test_tagged_native_rejects_external_site_packages_from_pyvenv_config(
    tmp_path: Path,
) -> None:
    python = _compact_native_venv_with_system_site_packages(tmp_path) / "bin/python"
    env = native_store.native_mcp_environment()
    probe = subprocess.run(
        [
            str(python),
            "-B",
            "-s",
            "-P",
            "-c",
            (
                "import json,sys;"
                "print(json.dumps({'prefix':sys.prefix,'base_prefix':sys.base_prefix,"
                "'sys_path':sys.path},sort_keys=True))"
            ),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert probe.returncode == 0, probe.stderr
    observed = json.loads(probe.stdout)
    venv_site = str(python.parent.parent / "lib/python3.12/site-packages")
    external = [
        path
        for path in observed["sys_path"]
        if "site-packages" in path and os.path.normpath(path) != os.path.normpath(venv_site)
    ]
    assert external
    probe_native_python = cast(
        Callable[[Path], dict[str, object]],
        native_store.__dict__["_probe_native_python"],
    )
    with pytest.raises(
        native_store.NativeStoreValidationError,
        match="native_runtime_identity_drift",
    ):
        probe_native_python(python)


@pytest.mark.mke
def test_development_lane_binds_the_exact_tagged_wheel_and_sealed_store() -> None:
    locks = json.loads((ROOT / "tests/fixtures/evidence_loop/provider-locks-v1.json").read_text())
    receipt = json.loads(
        (
            ROOT
            / "tmp/evidence-loop-a3-native-operator-final/receipts"
            / "sealed-mke-store-v1.json"
        ).read_text()
    )

    assert receipt["producer"]["tag_object"] == locks["mke"]["tag_object"]
    assert receipt["producer"]["peeled_commit"] == locks["mke"]["commit"]
    assert receipt["producer"]["wheel_sha256"] == locks["mke"]["wheel_sha256"]
    assert receipt["store_seal"]["lifecycle_state"] == "sealed_read_only"
    assert receipt["store_seal"]["store_root_mode"] == "0500"
    assert [item["basename"] for item in receipt["store_seal"]["files"]] == [
        "store.sqlite",
        "store.sqlite-shm",
        "store.sqlite-wal",
    ]
    assert receipt["fresh_process_verification_runs"] == 3
    assert receipt["mutation_capability"] == "closed_after_preparation"
    assert receipt["sealed_write_rejection"] == {
        "active_publication_impact": "unchanged",
        "active_set_unchanged": True,
        "attempted_tool": "ingest_file",
        "problem": "internal_error",
        "rejected": True,
        "store_tree_unchanged": True,
    }


@pytest.mark.mke
def test_tagged_wheel_runner_executes_the_development_structural_lane(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "evidence-loop-run"
    run_root.mkdir(mode=0o700)
    for child in ("input", "work", "store", "receipts"):
        (run_root / child).mkdir(mode=0o700)
    (run_root / "store").chmod(0o500)
    store_receipt = run_root / "receipts" / "sealed-mke-store-v1.json"
    store_receipt.write_bytes(
        b'{"mutation_capability":"closed_after_preparation",'
        b'"read_only_reopen_verified":true,'
        b'"store_seal":{"lifecycle_state":"sealed_read_only"}}'
    )
    output = run_root / "receipts" / "development-evaluation-v2.json"
    result = subprocess.run(
        [
            str(ROOT / "scripts/run_mke_lane.sh"),
            "evidence-loop-development",
            "--development-dataset",
            str(ROOT / "tests/fixtures/evidence_loop/development-dataset-v1.json"),
            "--store-receipt",
            str(store_receipt),
            "--run-root",
            str(run_root),
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
    assert json.loads(result.stdout)["code"] == "evidence_loop_development_evaluated"


@pytest.mark.mke
def test_tagged_wheel_runner_inventories_the_frozen_holdout_lane() -> None:
    runner = (ROOT / "scripts/run_mke_lane.sh").read_text(encoding="utf-8")

    assert '"evidence-loop-holdout"' in runner
    assert "scripts/evaluate_evidence_loop.py" in runner
    assert "EVIDENCE_LOOP_RUN_ROOT" in runner
    assert "work/venv/bin/python" in runner
    assert "PYTHONDONTWRITEBYTECODE=1" in runner
    assert "PYTHONNOUSERSITE=1" in runner
    assert "PYTHONSAFEPATH=1" in runner


@pytest.mark.mke
def test_retained_native_runtime_has_no_unbound_bytecode() -> None:
    venv = ROOT / "tmp/evidence-loop-a3-native-operator-final/work/venv"
    assert not list(venv.rglob("*.pyc"))
    assert not list(venv.rglob("__pycache__"))


@pytest.mark.mke
def test_tagged_wheel_fails_closed_when_v015_creates_sqlite_sidecars(
    tmp_path: Path,
) -> None:
    script = ROOT / "scripts/evaluate_evidence_loop.py"
    spec = importlib.util.spec_from_file_location("evaluate_native_lane", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cases = _capture_cases()
    receipt = json.loads(
        (
            ROOT
            / "tmp/evidence-loop-a3-native-operator-final/receipts"
            / "sealed-mke-store-v1.json"
        ).read_text(encoding="utf-8")
    )
    retained_store = ROOT / "tmp/evidence-loop-a3-native-operator-final/store"
    run_root = tmp_path / "run"
    run_root.mkdir(mode=0o700)
    (run_root / "work").symlink_to(retained_store.parent / "work", target_is_directory=True)
    (run_root / "input").symlink_to(retained_store.parent / "input", target_is_directory=True)
    store_root = run_root / "store"
    store_root.mkdir(mode=0o700)
    shutil.copyfile(retained_store / "store.sqlite", store_root / "store.sqlite")
    (store_root / "store.sqlite").chmod(0o400)
    before_capture = module._capture_state(ROOT, store_root)
    assert (
        cast(list[dict[str, Any]], before_capture["store_files"])[0]
        == (receipt["store_seal"]["files"][0])
    )

    capture = asyncio.run(
        module._capture_native_dataset(
            dataset={"cases": cases},
            repo_root=ROOT,
            store_root=store_root,
            expected_active_set_fingerprint=receipt["active_set_fingerprint"],
        )
    )
    after_capture = module._capture_state(ROOT, store_root)
    assert {item["basename"] for item in after_capture["store_files"]} == {
        "store.sqlite",
        "store.sqlite-shm",
        "store.sqlite-wal",
    }
    with pytest.raises(module.CliFailure) as raised:
        module._seal_observed_capture_guardrails(
            capture,
            before=before_capture,
            after=after_capture,
        )
    assert raised.value.exit_code == 14
    assert raised.value.payload["code"] == "capture_mutation_prohibited"


@pytest.mark.mke
def test_tagged_wheel_reads_sealed_wal_snapshot_without_mutation() -> None:
    script = ROOT / "scripts/evaluate_evidence_loop.py"
    spec = importlib.util.spec_from_file_location("evaluate_native_lane_sealed", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    retained = ROOT / "tmp/evidence-loop-a3-native-operator-final"
    receipt = json.loads((retained / "receipts/sealed-mke-store-v1.json").read_text())
    store_root = retained / "store"
    module._verify_capture_authority(
        store_root=store_root,
        sealed_store=receipt["store_seal"],
        native_runtime_identity=receipt["native_runtime_identity"],
        wheel_sha256=receipt["producer"]["wheel_sha256"],
    )
    before = module._capture_state(ROOT, store_root)
    capture = asyncio.run(
        module._capture_native_dataset(
            dataset={"cases": _capture_cases()},
            repo_root=ROOT,
            store_root=store_root,
            expected_active_set_fingerprint=receipt["active_set_fingerprint"],
        )
    )
    module._verify_capture_authority(
        store_root=store_root,
        sealed_store=receipt["store_seal"],
        native_runtime_identity=receipt["native_runtime_identity"],
        wheel_sha256=receipt["producer"]["wheel_sha256"],
    )
    after = module._capture_state(ROOT, store_root)

    module._seal_observed_capture_guardrails(
        capture,
        before=before,
        after=after,
    )
    assert before == after
    assert before["store_tree_sha256"] == receipt["store_seal"]["tree_sha256"]
    assert all(case["guardrail_proof"]["immutable_readback_verified"] for case in capture["cases"])


@pytest.mark.mke
def test_tagged_wheel_one_file_nonwritable_root_fails_native(
    tmp_path: Path,
) -> None:
    script = ROOT / "scripts/evaluate_evidence_loop.py"
    spec = importlib.util.spec_from_file_location("evaluate_native_lane_locked", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    retained = ROOT / "tmp/evidence-loop-a3-native-operator-final"
    receipt = json.loads((retained / "receipts/sealed-mke-store-v1.json").read_text())
    run_root = tmp_path / "run"
    run_root.mkdir(mode=0o700)
    (run_root / "work").symlink_to(retained / "work", target_is_directory=True)
    (run_root / "input").symlink_to(retained / "input", target_is_directory=True)
    store_root = run_root / "store"
    store_root.mkdir(mode=0o700)
    shutil.copyfile(retained / "store/store.sqlite", store_root / "store.sqlite")
    (store_root / "store.sqlite").chmod(0o400)
    store_root.chmod(0o500)
    try:
        with pytest.raises(BaseExceptionGroup):
            asyncio.run(
                module._capture_native_dataset(
                    dataset={"cases": _capture_cases()},
                    repo_root=ROOT,
                    store_root=store_root,
                    expected_active_set_fingerprint=receipt["active_set_fingerprint"],
                )
            )
        assert [path.name for path in store_root.iterdir()] == ["store.sqlite"]
    finally:
        store_root.chmod(0o700)
