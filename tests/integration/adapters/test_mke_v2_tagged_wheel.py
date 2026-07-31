from __future__ import annotations

import asyncio
import importlib.util
import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[3]


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
    output = tmp_path / "development-evaluation-v2.json"
    result = subprocess.run(
        [
            str(ROOT / "scripts/run_mke_lane.sh"),
            "evidence-loop-development",
            "--development-dataset",
            str(ROOT / "tests/fixtures/evidence_loop/development-dataset-v1.json"),
            "--store-receipt",
            str(
                ROOT
                / "tmp/evidence-loop-a3-native-operator-final/receipts"
                / "sealed-mke-store-v1.json"
            ),
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
    assert "work/venv/bin/python" in runner


@pytest.mark.mke
def test_tagged_wheel_executes_read_only_mock_capture_lane() -> None:
    script = ROOT / "scripts/evaluate_evidence_loop.py"
    spec = importlib.util.spec_from_file_location("evaluate_native_lane", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
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
                    "mke_request": {
                        "query": expected_value,
                        "limit": 20,
                    },
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
    receipt = json.loads(
        (
            ROOT
            / "tmp/evidence-loop-a3-native-operator-final/receipts"
            / "sealed-mke-store-v1.json"
        ).read_text(encoding="utf-8")
    )

    capture = asyncio.run(
        module._capture_native_dataset(
            dataset={"cases": cases},
            repo_root=ROOT,
            store_root=(ROOT / "tmp/evidence-loop-a3-native-operator-final/store"),
            expected_active_set_fingerprint=receipt["active_set_fingerprint"],
        )
    )

    assert len(capture["cases"]) == 4
    assert all(case["selection"]["status"] == "complete" for case in capture["cases"])
    assert all(case["mke_units"] for case in capture["cases"])
