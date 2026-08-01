from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from night_voyager.evidence_loop.canonicalization import canonical_json_bytes
from night_voyager.evidence_loop.receipt import build_terminal_receipt

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = (
    "evaluate_evidence_loop.py",
    "freeze_evidence_loop.py",
    "reveal_evidence_loop_holdouts.py",
    "verify_evidence_loop.py",
)


def test_lifecycle_scripts_use_an_explicit_external_run_root() -> None:
    for script in (
        "freeze_evidence_loop.py",
        "evaluate_evidence_loop.py",
        "reveal_evidence_loop_holdouts.py",
        "run_mke_lane.sh",
    ):
        source = (ROOT / "scripts" / script).read_text(encoding="utf-8")
        assert "tmp/evidence-loop-a3-native-operator-final" not in source
    assert "--run-root" in (ROOT / "scripts/freeze_evidence_loop.py").read_text(
        encoding="utf-8"
    )
    assert "--run-root" in (ROOT / "scripts/evaluate_evidence_loop.py").read_text(
        encoding="utf-8"
    )
    assert "--run-root" in (ROOT / "scripts/reveal_evidence_loop_holdouts.py").read_text(
        encoding="utf-8"
    )


def test_development_cli_accepts_a_fresh_external_run_root_without_retained_artifacts(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "evidence-loop-run"
    run_root.mkdir(mode=0o700)
    for child in ("input", "work", "store", "receipts"):
        (run_root / child).mkdir(mode=0o700)
    (run_root / "store").chmod(0o500)
    (run_root / "receipts" / "sealed-mke-store-v1.json").write_bytes(
        b'{"mutation_capability":"closed_after_preparation",'
        b'"read_only_reopen_verified":true,'
        b'"store_seal":{"lifecycle_state":"sealed_read_only"}}'
    )
    output = run_root / "receipts" / "development-evaluation-v2.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/evaluate_evidence_loop.py"),
            "--development-dataset",
            str(ROOT / "tests/fixtures/evidence_loop/development-dataset-v1.json"),
            "--store-receipt",
            str(run_root / "receipts" / "sealed-mke-store-v1.json"),
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
    assert output.is_file()


def _ignore_call(*_args: object, **_kwargs: object) -> None:
    return None


def _mock_reveal_destination(*_args: object) -> str:
    return "tests/fixtures/evidence_loop/holdout-dataset-v1.json"


def _mock_frozen_git(_root: Path, *args: str) -> str:
    if args[-1] == "HEAD":
        return "1" * 40
    if args[-1] == "HEAD^{tree}":
        return "2" * 40
    return ""


def _mock_custody_dataset(_root: Path) -> tuple[bytes, dict[str, Any]]:
    return b"{}\n", {}


def _make_run_root(tmp_path: Path) -> Path:
    run_root = tmp_path / "run-root"
    run_root.mkdir(mode=0o700)
    for child in ("input", "work", "store", "receipts"):
        (run_root / child).mkdir(mode=0o700)
    (run_root / "store").chmod(0o500)
    return run_root


def _copy_retained_setup_receipt(run_root: Path) -> Path:
    receipt = run_root / "receipts/sealed-mke-store-v1.json"
    shutil.copyfile(
        ROOT / "tmp/evidence-loop-a3-native-operator-final/receipts/sealed-mke-store-v1.json",
        receipt,
    )
    return receipt


@pytest.mark.parametrize("script", SCRIPTS)
def test_a4_cli_help_is_public_and_successful(script: str) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.startswith("usage:")
    assert result.stderr == ""


@pytest.mark.parametrize("script", SCRIPTS)
def test_a4_cli_unknown_argument_is_one_bounded_diagnostic(script: str) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), "--not-approved"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert set(payload) == {"stage", "code", "problem", "cause", "recovery"}
    assert result.stderr.splitlines() == [f"recovery: {payload['recovery']}"]
    combined = result.stdout + result.stderr
    for forbidden in ("query", "cursor", "credential", str(ROOT), "custody-root"):
        assert forbidden not in combined


@pytest.mark.mke
def test_development_cli_emits_canonical_receipt(tmp_path: Path) -> None:
    run_root = _make_run_root(tmp_path)
    store_receipt = run_root / "receipts" / "sealed-mke-store-v1.json"
    store_receipt.write_bytes(
        b'{"mutation_capability":"closed_after_preparation",'
        b'"read_only_reopen_verified":true,'
        b'"store_seal":{"lifecycle_state":"sealed_read_only"}}'
    )
    output = run_root / "receipts" / "development-evaluation-v2.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/evaluate_evidence_loop.py"),
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
    receipt = json.loads(output.read_bytes())
    assert receipt["terminal_disposition"] == "incremental_value_confirmed"
    assert result.stderr == ""


def test_reveal_rejects_invalid_freeze_before_custody_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = ROOT / "scripts/reveal_evidence_loop_holdouts.py"
    spec = importlib.util.spec_from_file_location("reveal_order_test", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    run_root = _make_run_root(tmp_path)
    invalid_freeze = run_root / "receipts/pre-registration-v2.json"
    invalid_freeze.write_text("{}", encoding="utf-8")
    custody_observed = False

    def observe_custody(_root: Path) -> tuple[bytes, dict[str, Any]]:
        nonlocal custody_observed
        custody_observed = True
        return b"", {}

    monkeypatch.setattr(module, "_relative_destination", _mock_reveal_destination)
    monkeypatch.setattr(module, "_read_exact_custody_input", observe_custody)
    args = SimpleNamespace(
        pre_registration=invalid_freeze,
        expected_pre_registration_sha256="0" * 64,
        holdout_manifest=ROOT / "tests/fixtures/evidence_loop/holdout-manifest-v1.json",
        run_root=run_root,
        store_root=run_root / "store",
        custody_root=tmp_path / "must-not-be-read",
        destination=tmp_path / "holdout-dataset-v1.json",
    )

    with pytest.raises(module.CliFailure) as raised:
        module._prepare(args)

    assert raised.value.exit_code == 13
    assert raised.value.payload["code"] == "pre_registration_invalid"
    assert custody_observed is False


def test_reveal_rejects_retired_dataset_reuse_before_custody_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = ROOT / "scripts/reveal_evidence_loop_holdouts.py"
    spec = importlib.util.spec_from_file_location("reveal_retired_dataset_test", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    run_root = _make_run_root(tmp_path)
    invalid_freeze = run_root / "receipts/pre-registration-v2.json"
    invalid_freeze.write_text("{}", encoding="utf-8")
    custody_observed = False

    def observe_custody(_root: Path) -> tuple[bytes, dict[str, Any]]:
        nonlocal custody_observed
        custody_observed = True
        return b"", {}

    monkeypatch.setattr(module, "_read_exact_custody_input", observe_custody)
    args = SimpleNamespace(
        pre_registration=invalid_freeze,
        expected_pre_registration_sha256="0" * 64,
        holdout_manifest=ROOT / "tests/fixtures/evidence_loop/holdout-manifest-v1.json",
        run_root=run_root,
        store_root=run_root / "store",
        custody_root=tmp_path / "must-not-be-read",
        destination=ROOT / "tests/fixtures/evidence_loop/holdout-dataset-v1.json",
    )

    with pytest.raises(module.CliFailure) as raised:
        module._prepare(args)

    assert raised.value.exit_code == 11
    assert raised.value.payload["code"] == "destination_not_fresh"
    assert custody_observed is False


@pytest.mark.parametrize("drift", ["store", "runtime"])
def test_reveal_requires_store_root_and_checks_drift_before_custody_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    script = ROOT / "scripts/reveal_evidence_loop_holdouts.py"
    spec = importlib.util.spec_from_file_location("reveal_store_order_test", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert "--store-root" in module._parser().format_help()

    run_root = _make_run_root(tmp_path)
    preregistration_path = run_root / "receipts/pre-registration-v2.json"
    preregistration_content = b"reviewed\n"
    preregistration_path.write_bytes(preregistration_content)
    destination = tmp_path / "holdout-dataset-v1.json"
    store_root = run_root / "store"
    custody_observed = False
    preregistration = {
        "reveal_procedure_id": "nv.slice0.one-way-reveal.v1",
        "post_reveal_generated_file_allowlist": list(module.POST_REVEAL_ALLOWLIST),
        "pre_reveal_scan": {"passed": True},
        "git": {"head": "1" * 40, "tree": "2" * 40, "clean": True},
        "holdout_manifest": {
            "path": "tests/fixtures/evidence_loop/holdout-manifest-v1.json"
        },
        "native_runtime_identity": {},
        "provider_locks": {"mke": {"wheel_sha256": "4" * 64}},
    }

    def reviewed_receipt(_content: bytes) -> dict[str, Any]:
        return preregistration

    monkeypatch.setattr(
        module,
        "verify_pre_registration_receipt",
        reviewed_receipt,
    )
    monkeypatch.setattr(
        module,
        "_relative_destination",
        _mock_reveal_destination,
    )
    monkeypatch.setattr(module, "_git", _mock_frozen_git)

    def reject_drift(
        _receipt: dict[str, Any],
        *,
        store_root: Path | None,
        **_kwargs: object,
    ) -> None:
        assert store_root == run_root / "store"
        if drift == "store":
            raise ValueError("store_artifact_drift")

    def reject_runtime(*_args: object, **_kwargs: object) -> None:
        if drift == "runtime":
            raise ValueError("native_runtime_identity_drift")

    def observe_custody(_root: Path) -> tuple[bytes, dict[str, Any]]:
        nonlocal custody_observed
        custody_observed = True
        return b"", {}

    monkeypatch.setattr(module, "validate_frozen_checkout", reject_drift)
    monkeypatch.setattr(
        module,
        "validate_native_runtime_identity",
        reject_runtime,
    )
    monkeypatch.setattr(module, "_read_exact_custody_input", observe_custody)
    args = SimpleNamespace(
        pre_registration=preregistration_path,
        expected_pre_registration_sha256=hashlib.sha256(
            preregistration_content
        ).hexdigest(),
        holdout_manifest=ROOT / "tests/fixtures/evidence_loop/holdout-manifest-v1.json",
        run_root=run_root,
        store_root=store_root,
        custody_root=tmp_path / "custody-must-not-be-read",
        destination=destination,
    )

    with pytest.raises(module.CliFailure) as raised:
        module._prepare(args)

    assert raised.value.payload["code"] == "freeze_order_invalid"
    assert custody_observed is False
    assert destination.exists() is False


def test_reveal_rechecks_store_after_validation_before_atomic_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = ROOT / "scripts/reveal_evidence_loop_holdouts.py"
    spec = importlib.util.spec_from_file_location("reveal_store_toctou_test", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    run_root = _make_run_root(tmp_path)
    preregistration_path = run_root / "receipts/pre-registration-v2.json"
    preregistration_content = b"reviewed\n"
    preregistration_path.write_bytes(preregistration_content)
    destination = tmp_path / "holdout-dataset-v1.json"
    store_root = run_root / "store"
    custody_root = tmp_path / "custody"
    custody_root.mkdir(mode=0o700)
    checks = 0
    published = False
    preregistration = {
        "reveal_procedure_id": "nv.slice0.one-way-reveal.v1",
        "post_reveal_generated_file_allowlist": list(module.POST_REVEAL_ALLOWLIST),
        "pre_reveal_scan": {"passed": True},
        "git": {"head": "1" * 40, "tree": "2" * 40, "clean": True},
        "holdout_manifest": {
            "path": "tests/fixtures/evidence_loop/holdout-manifest-v1.json"
        },
        "native_runtime_identity": {},
        "provider_locks": {"mke": {"wheel_sha256": "4" * 64}},
    }

    def reviewed_receipt(_content: bytes) -> dict[str, Any]:
        return preregistration

    monkeypatch.setattr(
        module,
        "verify_pre_registration_receipt",
        reviewed_receipt,
    )
    monkeypatch.setattr(
        module,
        "_relative_destination",
        _mock_reveal_destination,
    )
    monkeypatch.setattr(module, "_git", _mock_frozen_git)

    def check_store(*_args: object, **_kwargs: object) -> None:
        nonlocal checks
        checks += 1
        if checks == 2:
            raise ValueError("store_artifact_drift")

    monkeypatch.setattr(module, "validate_frozen_checkout", check_store)
    monkeypatch.setattr(
        module,
        "validate_native_runtime_identity",
        _ignore_call,
    )
    monkeypatch.setattr(
        module,
        "_read_exact_custody_input",
        _mock_custody_dataset,
    )
    monkeypatch.setattr(module, "validate_revealed_dataset", _ignore_call)

    def publish(_destination: Path, _content: bytes) -> None:
        nonlocal published
        published = True

    monkeypatch.setattr(module, "_publish_exclusive", publish)
    args = SimpleNamespace(
        pre_registration=preregistration_path,
        expected_pre_registration_sha256=hashlib.sha256(
            preregistration_content
        ).hexdigest(),
        holdout_manifest=ROOT / "tests/fixtures/evidence_loop/holdout-manifest-v1.json",
        run_root=run_root,
        store_root=store_root,
        custody_root=custody_root,
        destination=destination,
    )

    with pytest.raises(module.CliFailure) as raised:
        module._prepare(args)

    assert raised.value.payload["code"] == "freeze_order_invalid"
    assert checks == 2
    assert published is False


def test_authoritative_holdout_cli_rejects_prebuilt_capture() -> None:
    script = ROOT / "scripts/evaluate_evidence_loop.py"
    spec = importlib.util.spec_from_file_location("evaluate_capture_contract", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    with pytest.raises(module.CliFailure) as raised:
        module._parser().parse_args(["--capture", "prebuilt.json"])

    assert raised.value.exit_code == 2
    assert raised.value.payload["code"] == "invalid_cli"


def test_terminal_verifier_rejects_self_hashed_malformed_bound_artifacts(
    tmp_path: Path,
) -> None:
    pre_registration = tmp_path / "pre-registration.json"
    dataset = tmp_path / "dataset.json"
    capture = tmp_path / "capture.json"
    receipt = tmp_path / "receipt.json"
    pre_registration.write_bytes(canonical_json_bytes({"self": "consistent"}))
    empty_cases: list[dict[str, Any]] = [{}, {}, {}, {}]
    dataset.write_bytes(canonical_json_bytes({"cases": empty_cases}))
    capture.write_bytes(canonical_json_bytes({"cases": empty_cases}))
    receipt.write_bytes(
        build_terminal_receipt(
            {
                "schema_version": "night-voyager.evidence-loop-evaluation.v2",
                "terminal_disposition": "no_incremental_value",
                "case_results": [{}, {}, {}, {}],
            },
            run_kind="holdout",
            artifact_bindings={
                "pre_registration_sha256": hashlib.sha256(
                    pre_registration.read_bytes()
                ).hexdigest(),
                "holdout_dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
                "mke_capture_sha256": hashlib.sha256(capture.read_bytes()).hexdigest(),
            },
        )
    )

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/verify_evidence_loop.py"),
            "--pre-registration",
            str(pre_registration),
            "--dataset",
            str(dataset),
            "--capture",
            str(capture),
            "--receipt",
            str(receipt),
            "--json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 13
    assert json.loads(result.stdout)["code"] == "receipt_invalid"


def test_capture_state_drift_is_a_mutation_veto() -> None:
    script = ROOT / "scripts/evaluate_evidence_loop.py"
    spec = importlib.util.spec_from_file_location("capture_mutation_contract", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    capture = {
        "cases": [
            {
                "guardrail_observations": {
                    "allowed_read_tools_only": True,
                    "retrieved_content_treated_as_untrusted_data": True,
                    "authority_actions_emitted": 0,
                }
            }
        ]
    }

    with pytest.raises(module.CliFailure) as raised:
        module._seal_observed_capture_guardrails(
            capture,
            before={"store_tree_sha256": "a" * 64},
            after={"store_tree_sha256": "b" * 64},
        )

    assert raised.value.exit_code == 14
    assert "guardrails" not in capture["cases"][0]


def test_capture_state_binds_sealed_store_root_mode_and_three_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = ROOT / "scripts/evaluate_evidence_loop.py"
    spec = importlib.util.spec_from_file_location("capture_state_contract", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    store_root = tmp_path / "store"
    store_root.mkdir(mode=0o700)
    for basename, content in {
        "store.sqlite": b"sealed",
        "store.sqlite-shm": b"s" * 32_768,
        "store.sqlite-wal": b"",
    }.items():
        path = store_root / basename
        path.write_bytes(content)
        path.chmod(0o400)
    store_root.chmod(0o500)

    def empty_git_identity(*args: object) -> str:
        return ""

    monkeypatch.setattr(module, "_git", empty_git_identity)

    try:
        state = module._capture_state(tmp_path, store_root)
    finally:
        store_root.chmod(0o700)

    assert state["store_root_mode"] == "0500"
    assert [item["basename"] for item in state["store_files"]] == [
        "store.sqlite",
        "store.sqlite-shm",
        "store.sqlite-wal",
    ]


def test_capture_authority_rejects_same_byte_hardlink_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from night_voyager.evidence_loop.native_store import seal_store

    script = ROOT / "scripts/evaluate_evidence_loop.py"
    spec = importlib.util.spec_from_file_location("capture_link_contract", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    store_root = tmp_path / "store"
    store_root.mkdir(mode=0o700)
    database = store_root / "store.sqlite"
    database.write_bytes(b"sealed")
    (store_root / "store.sqlite-shm").write_bytes(b"s" * 32_768)
    (store_root / "store.sqlite-wal").write_bytes(b"")
    seal = seal_store(store_root, database)
    replacement = tmp_path / "same-bytes"
    replacement.write_bytes((store_root / "store.sqlite-shm").read_bytes())
    replacement.chmod(0o400)
    store_root.chmod(0o700)
    (store_root / "store.sqlite-shm").unlink()
    (store_root / "store.sqlite-shm").hardlink_to(replacement)
    store_root.chmod(0o500)
    monkeypatch.setattr(
        module,
        "validate_native_runtime_identity",
        _ignore_call,
        raising=False,
    )

    with pytest.raises(module.CliFailure) as raised:
        module._verify_capture_authority(
            store_root=store_root,
            sealed_store=seal,
            native_runtime_identity={},
            wheel_sha256="4" * 64,
        )

    assert raised.value.exit_code == 14
    assert raised.value.payload["code"] == "capture_mutation_prohibited"
    store_root.chmod(0o700)


@pytest.mark.parametrize(
    ("mutation", "exit_code", "code"),
    [
        (("selection", "status", "capped"), 12, "evaluation_inconclusive"),
        (("guardrails", "filesystem_mutation", True), 14, "mutation_prohibited"),
    ],
)
@pytest.mark.mke
def test_development_cli_persists_each_terminal_disposition(
    tmp_path: Path,
    mutation: tuple[str, str, object],
    exit_code: int,
    code: str,
) -> None:
    dataset = json.loads(
        (ROOT / "tests/fixtures/evidence_loop/development-dataset-v1.json").read_text()
    )
    parent, key, value = mutation
    dataset["cases"][0][parent][key] = value
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(json.dumps(dataset), encoding="utf-8")
    run_root = _make_run_root(tmp_path)
    store_receipt = _copy_retained_setup_receipt(run_root)
    output = run_root / "receipts/development-evaluation-v2.json"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/evaluate_evidence_loop.py"),
            "--development-dataset",
            str(dataset_path),
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

    assert result.returncode == exit_code
    assert json.loads(result.stdout)["code"] == code
    assert result.stderr.startswith("recovery: ")
    receipt = json.loads(output.read_bytes())
    assert receipt["terminal_disposition"] in {
        "inconclusive",
        "evaluation_invalid",
    }


@pytest.mark.parametrize(
    ("condition", "exit_code", "code"),
    [
        ("producer", 10, "store_receipt_invalid"),
        ("order", 11, "output_not_fresh"),
        ("validation", 13, "evaluation_invalid"),
    ],
)
@pytest.mark.mke
def test_development_cli_completes_the_a4_failure_taxonomy(
    tmp_path: Path,
    condition: str,
    exit_code: int,
    code: str,
) -> None:
    dataset = ROOT / "tests/fixtures/evidence_loop/development-dataset-v1.json"
    run_root = _make_run_root(tmp_path)
    store_receipt = _copy_retained_setup_receipt(run_root)
    output = run_root / "receipts/development-evaluation-v2.json"
    if condition == "producer":
        store_receipt.write_text("{}", encoding="utf-8")
    elif condition == "order":
        output.write_text("occupied", encoding="utf-8")
    else:
        dataset = tmp_path / "dataset.json"
        dataset.write_text("{}", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/evaluate_evidence_loop.py"),
            "--development-dataset",
            str(dataset),
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

    assert result.returncode == exit_code
    assert json.loads(result.stdout)["code"] == code
    assert result.stderr.startswith("recovery: ")
