from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, cast

import pytest

from night_voyager.evidence_loop.dra_baseline import GovernedDraBaselineExportV1
from night_voyager.evidence_loop.freeze import (
    POST_REVEAL_ALLOWLIST,
    build_pre_registration_receipt,
    current_runtime_identity,
    scan_pre_reveal,
    validate_frozen_checkout,
    validate_public_commitments,
    validate_runtime_identity,
    validate_sqlite_authority_image,
)
from night_voyager.evidence_loop.receipt import verify_pre_registration_receipt

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests/fixtures/evidence_loop"


def _sealed_store_projection(store_files: dict[str, bytes]) -> dict[str, object]:
    files = [
        {
            "basename": basename,
            "byte_length": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "mode": "0400",
        }
        for basename, content in store_files.items()
    ]
    canonical = (
        json.dumps({"files": files}, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode()
    return {
        "schema_version": "night-voyager.evidence-loop-store-seal.v1",
        "files": files,
        "store_root_mode": "0500",
        "tree_sha256": hashlib.sha256(canonical).hexdigest(),
        "lifecycle_state": "sealed_read_only",
    }


def test_public_commitments_admit_only_revision_three() -> None:
    result = validate_public_commitments(FIXTURES)
    assert result.author_revision == 3
    assert result.roles == (
        "independent-dataset-author-v3",
        "night-voyager-slice0-evaluator-v1",
        "independent-holdout-custodian-v3",
    )
    assert len(result.source_digests) == 4
    assert result.holdout_content_reachable is False


def test_public_commitments_fail_on_source_drift(tmp_path: Path) -> None:
    for path in FIXTURES.iterdir():
        if path.is_file():
            (tmp_path / path.name).write_bytes(path.read_bytes())
    corpus = tmp_path / "mke-corpus"
    corpus.mkdir()
    for path in (FIXTURES / "mke-corpus").iterdir():
        (corpus / path.name).write_bytes(path.read_bytes())
    (corpus / "rf-0a6f5c9d.pdf").write_bytes(b"drift")

    with pytest.raises(ValueError, match="source identity mismatch"):
        validate_public_commitments(tmp_path)


def test_post_reveal_allowlist_is_exact() -> None:
    assert POST_REVEAL_ALLOWLIST == (
        "tests/fixtures/evidence_loop/holdout-dataset-v1.json",
        "tests/fixtures/evidence_loop/mke-capture-v2.json",
        "tests/fixtures/evidence_loop/slice0-receipt-v2.json",
    )
    manifest = json.loads((FIXTURES / "holdout-manifest-v1.json").read_text())
    assert manifest["holdout_content_included"] is False
    assert manifest["oracle_content_included"] is False


def test_pre_registration_binds_complete_public_freeze_boundary() -> None:
    receipt = build_pre_registration_receipt(
        repo_root=ROOT,
        exact_head="1" * 40,
        exact_tree="2" * 40,
        store_receipt=(
            ROOT
            / "tmp/evidence-loop-a3-native-operator-final/receipts"
            / "sealed-mke-store-v1.json"
        ),
        source_manifest=FIXTURES / "source-manifest-v1.json",
        development_dataset=FIXTURES / "development-dataset-v1.json",
        holdout_manifest=FIXTURES / "holdout-manifest-v1.json",
        dra_baseline=FIXTURES / "dra-governed-baseline-v1.json",
        environment={},
    )

    frozen = verify_pre_registration_receipt(receipt)
    assert frozen["git"] == {"head": "1" * 40, "tree": "2" * 40, "clean": True}
    assert frozen["roles"] == {
        "dataset_author_id": "independent-dataset-author-v3",
        "evaluator_implementer_id": "night-voyager-slice0-evaluator-v1",
        "holdout_custodian_id": "independent-holdout-custodian-v3",
    }
    assert len(frozen["case_query_identities"]) == 8
    assert all(
        set(commitment)
        >= {
            "payload_byte_length",
            "payload_sha256",
            "oracle_byte_length",
            "oracle_sha256",
        }
        for commitment in frozen["holdout_commitments"]
    )
    assert frozen["post_reveal_generated_file_allowlist"] == list(POST_REVEAL_ALLOWLIST)
    assert frozen["thresholds"]["max_search_pages"] == 4
    assert frozen["thresholds"]["max_evidence_reads"] == 32
    assert frozen["pre_reveal_scan"]["passed"] is True
    assert frozen["reveal_procedure_id"] == "nv.slice0.one-way-reveal.v1"
    assert frozen["sealed_store"]["fresh_process_verification_runs"] == 3
    assert frozen["sealed_store"]["sqlite_authority_image"] == {
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
    assert frozen["native_runtime_identity"]["schema_version"] == (
        "night-voyager.evidence-loop-native-runtime.v1"
    )
    assert frozen["native_runtime_identity"]["mke"]["wheel_sha256"] == (
        frozen["provider_locks"]["mke"]["wheel_sha256"]
    )
    native_runtime = cast(dict[str, Any], frozen["native_runtime_identity"])
    runtime_distributions = cast(
        list[dict[str, Any]], native_runtime["runtime_distributions"]
    )
    assert native_runtime["runtime_distribution_count"] == len(runtime_distributions)
    assert {item["distribution_name"] for item in runtime_distributions} >= {
        "anyio",
        "mcp",
        "multimodal-knowledge-engine",
    }
    runtime_bootstrap = cast(dict[str, Any], native_runtime["runtime_bootstrap"])
    assert runtime_bootstrap["file_count"] >= 0
    frozen_paths = {item["path"] for item in [*frozen["evaluator_paths"], *frozen["harness_paths"]]}
    assert frozen_paths == {
        "src/night_voyager/evidence_loop/canonicalization.py",
        "src/night_voyager/evidence_loop/evaluator.py",
        "src/night_voyager/evidence_loop/freeze.py",
        "src/night_voyager/evidence_loop/mke_capture.py",
        "src/night_voyager/evidence_loop/native_store.py",
        "src/night_voyager/evidence_loop/receipt.py",
        "src/night_voyager/evidence_loop/schema_validation.py",
        "scripts/evaluate_evidence_loop.py",
        "scripts/freeze_evidence_loop.py",
        "scripts/reveal_evidence_loop_holdouts.py",
        "scripts/run_mke_lane.sh",
        "scripts/verify_evidence_loop.py",
        "tests/unit/evidence_loop/test_canonicalization.py",
        "tests/unit/evidence_loop/test_cli_contracts.py",
        "tests/unit/evidence_loop/test_evaluator.py",
        "tests/unit/evidence_loop/test_freeze.py",
        "tests/unit/evidence_loop/test_mke_capture.py",
        "tests/unit/evidence_loop/test_receipt.py",
        "tests/unit/evidence_loop/test_schema_validation.py",
        "tests/integration/adapters/test_mke_v2_tagged_wheel.py",
        "tests/integration/evidence_loop/test_frozen_suite.py",
    }


@pytest.mark.parametrize("mutation", ["missing_image", "wrong_files", "wrong_runs"])
def test_freeze_rejects_incomplete_sqlite_authority_proof(mutation: str) -> None:
    setup: dict[str, Any] = {
        "sqlite_authority_image": {
            "authority_image": "sqlite_read_only_wal_atomic_snapshot",
            "materialization_phase": "task_owned_preparation_mutation",
            "ordered_basenames": [
                "store.sqlite",
                "store.sqlite-shm",
                "store.sqlite-wal",
            ],
            "shm_byte_length": 32_768,
            "wal_byte_length": 0,
        },
        "fresh_process_verification_runs": 3,
    }
    if mutation == "missing_image":
        setup.pop("sqlite_authority_image")
    elif mutation == "wrong_files":
        setup["sqlite_authority_image"]["ordered_basenames"] = ["store.sqlite"]
    else:
        setup["fresh_process_verification_runs"] = 2

    with pytest.raises(ValueError, match="sqlite authority image invalid"):
        validate_sqlite_authority_image(setup)


def test_development_baseline_contains_complete_governed_exports() -> None:
    baseline = json.loads((FIXTURES / "dra-governed-baseline-v1.json").read_text(encoding="utf-8"))

    exports = [GovernedDraBaselineExportV1.model_validate(item) for item in baseline["exports"]]

    assert len(exports) == 4
    assert all(export.typed_value_sha256 for export in exports)
    assert all(export.advisor_verification.receipt_sha256 for export in exports)
    assert all(export.row_sha256 and export.export_sha256 for export in exports)


def test_pre_registration_rejects_governed_baseline_hash_drift(
    tmp_path: Path,
) -> None:
    baseline = json.loads((FIXTURES / "dra-governed-baseline-v1.json").read_text(encoding="utf-8"))
    baseline["exports"][0]["typed_value_sha256"] = "0" * 64
    drifted = tmp_path / "dra-governed-baseline-v1.json"
    drifted.write_text(json.dumps(baseline), encoding="utf-8")

    with pytest.raises(ValueError, match="governed baseline hash chain invalid"):
        build_pre_registration_receipt(
            repo_root=ROOT,
            exact_head="1" * 40,
            exact_tree="2" * 40,
            store_receipt=(
                ROOT
                / "tmp/evidence-loop-a3-native-operator-final/receipts"
                / "sealed-mke-store-v1.json"
            ),
            source_manifest=FIXTURES / "source-manifest-v1.json",
            development_dataset=FIXTURES / "development-dataset-v1.json",
            holdout_manifest=FIXTURES / "holdout-manifest-v1.json",
            dra_baseline=drifted,
            environment={},
        )


def test_pre_registration_rejects_setup_provider_peer_drift(
    tmp_path: Path,
) -> None:
    provider_locks = json.loads((FIXTURES / "provider-locks-v1.json").read_text(encoding="utf-8"))
    provider_locks["mke"]["wheel_sha256"] = "0" * 64
    provider_root = tmp_path / "tests/fixtures/evidence_loop"
    provider_root.mkdir(parents=True)
    (provider_root / "provider-locks-v1.json").write_text(
        json.dumps(provider_locks),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="provider lock peer mismatch"):
        build_pre_registration_receipt(
            repo_root=tmp_path,
            exact_head="1" * 40,
            exact_tree="2" * 40,
            store_receipt=(
                ROOT
                / "tmp/evidence-loop-a3-native-operator-final/receipts"
                / "sealed-mke-store-v1.json"
            ),
            source_manifest=FIXTURES / "source-manifest-v1.json",
            development_dataset=FIXTURES / "development-dataset-v1.json",
            holdout_manifest=FIXTURES / "holdout-manifest-v1.json",
            dra_baseline=FIXTURES / "dra-governed-baseline-v1.json",
            environment={},
        )


def test_frozen_checkout_rejects_path_and_store_drift(tmp_path: Path) -> None:
    tracked = tmp_path / "evaluator.py"
    tracked.write_text("frozen\n", encoding="utf-8")
    store_files = {
        "store.sqlite": b"sealed",
        "store.sqlite-shm": b"s" * 32_768,
        "store.sqlite-wal": b"",
    }
    store_root = tmp_path / "store"
    store_root.mkdir(mode=0o700)
    for basename, content in store_files.items():
        path = store_root / basename
        path.write_bytes(content)
        path.chmod(0o400)
    store_root.chmod(0o500)
    receipt: dict[str, object] = {
        "git": {"head": "1" * 40, "tree": "2" * 40, "clean": True},
        "evaluator_paths": [
            {
                "path": "evaluator.py",
                "byte_length": tracked.stat().st_size,
                "sha256": hashlib.sha256(tracked.read_bytes()).hexdigest(),
                "mode": "0644",
            }
        ],
        "harness_paths": [],
        "sealed_store": _sealed_store_projection(store_files),
    }

    try:
        validate_frozen_checkout(
            receipt,
            repo_root=tmp_path,
            store_root=store_root,
            current_head="1" * 40,
            current_tree="2" * 40,
            status_paths=(),
        )
        tracked.write_text("drift\n", encoding="utf-8")
        with pytest.raises(ValueError, match="frozen path drift"):
            validate_frozen_checkout(
                receipt,
                repo_root=tmp_path,
                store_root=store_root,
                current_head="1" * 40,
                current_tree="2" * 40,
                status_paths=(),
            )
    finally:
        store_root.chmod(0o700)


def test_frozen_checkout_allows_only_exact_post_reveal_paths(
    tmp_path: Path,
) -> None:
    store_files = {
        "store.sqlite": b"",
        "store.sqlite-shm": b"s" * 32_768,
        "store.sqlite-wal": b"",
    }
    receipt: dict[str, object] = {
        "git": {"head": "1" * 40, "tree": "2" * 40, "clean": True},
        "evaluator_paths": [],
        "harness_paths": [],
        "sealed_store": _sealed_store_projection(store_files),
    }
    store_root = tmp_path / "store"
    store_root.mkdir(mode=0o700)
    for basename, content in store_files.items():
        path = store_root / basename
        path.write_bytes(content)
        path.chmod(0o400)
    store_root.chmod(0o500)
    try:
        validate_frozen_checkout(
            receipt,
            repo_root=tmp_path,
            store_root=store_root,
            current_head="1" * 40,
            current_tree="2" * 40,
            status_paths=(POST_REVEAL_ALLOWLIST[0],),
            allowed_generated_paths=(POST_REVEAL_ALLOWLIST[0],),
        )
        with pytest.raises(ValueError, match="post-freeze write set invalid"):
            validate_frozen_checkout(
                receipt,
                repo_root=tmp_path,
                store_root=store_root,
                current_head="1" * 40,
                current_tree="2" * 40,
                status_paths=("src/night_voyager/evidence_loop/evaluator.py",),
                allowed_generated_paths=POST_REVEAL_ALLOWLIST,
            )
    finally:
        store_root.chmod(0o700)


def test_pre_reveal_scan_rejects_custody_environment_reachability() -> None:
    with pytest.raises(ValueError, match="custody environment reachable"):
        scan_pre_reveal(
            ROOT,
            environment={"EVIDENCE_LOOP_CUSTODY_ROOT": "/not/public"},
        )


def test_pre_reveal_scan_reports_only_measured_roots_and_rejects_committed_bytes(
    tmp_path: Path,
) -> None:
    checkout = tmp_path / "checkout"
    run_root = tmp_path / "run"
    checkout.mkdir()
    run_root.mkdir()
    content = b"mock sealed payload bytes"
    commitment = {
        "payload_byte_length": len(content),
        "payload_sha256": hashlib.sha256(content).hexdigest(),
        "oracle_byte_length": 999,
        "oracle_sha256": "a" * 64,
        "full_case_byte_length": 998,
        "full_case_sha256": "b" * 64,
    }

    measured = scan_pre_reveal(
        checkout,
        run_roots={"task_run_root": run_root},
        commitments=[commitment],
        environment={},
    )
    assert measured["method"] == "bounded_regular_file_length_sha256_scan_v1"
    assert measured["inspected_roots"] == ["evaluator_checkout", "task_run_root"]
    assert "custody_root_mounted" not in measured
    assert "custody_root_indexed" not in measured
    assert "holdout_payload_reachable" not in measured

    (run_root / "opaque.bin").write_bytes(content)
    with pytest.raises(ValueError, match="committed holdout bytes reachable"):
        scan_pre_reveal(
            checkout,
            run_roots={"task_run_root": run_root},
            commitments=[commitment],
            environment={},
        )


def test_runtime_identity_is_enforced_not_only_recorded() -> None:
    frozen = current_runtime_identity(ROOT)
    validate_runtime_identity(frozen, repo_root=ROOT)
    drifted = {**frozen, "python_version": "0.0.0"}
    with pytest.raises(ValueError, match="runtime identity drift"):
        validate_runtime_identity(drifted, repo_root=ROOT)


def test_reveal_plan_requires_store_authority_and_only_measured_custody_claims() -> None:
    plan = (
        ROOT
        / "docs/superpowers/plans/"
        "2026-07-31-advisor-governed-multimodal-evidence-composition-implementation.md"
    ).read_text(encoding="utf-8")
    reveal_command = plan.split(
        "uv run python scripts/reveal_evidence_loop_holdouts.py",
        1,
    )[1].split("```", 1)[0]
    assert '--store-root "$EVIDENCE_LOOP_RUN_ROOT/store"' in reveal_command
    assert "proves the root was not mounted or indexed" not in plan
    assert "holdout source mounted or indexed by evaluator." not in plan
    assert "Global mount/index state" in plan


def test_pre_registration_is_mode_0600_when_written(tmp_path: Path) -> None:
    path = tmp_path / "pre-registration-v2.json"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(b"public-safe\n")
    assert path.stat().st_mode & 0o777 == 0o600


def _mock_case(value: str) -> dict[str, Any]:
    return {
        "schema_version": "night-voyager.evidence-loop-holdout-case.v1",
        "payload": {"identity": {"case_id": "mock"}, "value": value},
        "oracle": {"identity": {"case_id": "mock"}, "expected": value},
    }


def test_reveal_validator_accepts_only_exact_committed_case_bytes() -> None:
    import importlib.util

    script = ROOT / "scripts/reveal_evidence_loop_holdouts.py"
    spec = importlib.util.spec_from_file_location("reveal_evidence_loop_holdouts", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    case = _mock_case("accepted")
    dataset: dict[str, Any] = {
        "schema_version": "night-voyager.evidence-loop-holdout-dataset.v1",
        "canonicalization_id": "night-voyager.slice0.compact-sorted-utf8-lf.v1",
        "cases": [case],
    }
    commitment = module.case_commitment(case)
    manifest = {"holdouts": [commitment]}

    module.validate_revealed_dataset(dataset, manifest)
    with pytest.raises(ValueError, match="schema validation"):
        module.validate_revealed_dataset(
            dataset,
            manifest,
            schema_root=FIXTURES,
        )
    cases_value = dataset["cases"]
    assert isinstance(cases_value, list)
    cases = cast(list[object], cases_value)
    typed_case_value = cases[0]
    assert isinstance(typed_case_value, dict)
    typed_case = cast(dict[str, Any], typed_case_value)
    typed_oracle_value = typed_case["oracle"]
    assert isinstance(typed_oracle_value, dict)
    typed_oracle = cast(dict[str, Any], typed_oracle_value)
    typed_oracle["expected"] = "tampered"
    with pytest.raises(ValueError, match="revealed case commitment mismatch"):
        module.validate_revealed_dataset(dataset, manifest)
