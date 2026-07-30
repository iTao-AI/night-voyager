from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/prepare_evidence_loop_store.py"
FIXTURES = ROOT / "tests/fixtures/evidence_loop"
FORBIDDEN_DIAGNOSTIC_TEXT = (
    "/Users/",
    "/private/",
    "/tmp/",
    "query",
    "cursor",
    "credential",
)


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("prepare_evidence_loop_store", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _copy_public_sources(target: Path) -> Path:
    target.mkdir()
    for name in ("source-manifest-v1.json", "source-manifest-fragment-v1.json"):
        shutil.copyfile(FIXTURES / name, target / name)
        (target / name).chmod(0o644)
    corpus = target / "mke-corpus"
    corpus.mkdir()
    for source in (FIXTURES / "mke-corpus").iterdir():
        shutil.copyfile(source, corpus / source.name)
        (corpus / source.name).chmod(0o644)
    return target / "source-manifest-v1.json"


def _assert_bounded_failure(
    result: subprocess.CompletedProcess[str],
    *,
    exit_code: int,
    stage: str,
    code: str,
) -> dict[str, Any]:
    assert result.returncode == exit_code
    payload = json.loads(result.stdout)
    assert set(payload) == {"stage", "code", "problem", "cause", "recovery"}
    assert payload["stage"] == stage
    assert payload["code"] == code
    assert result.stderr.splitlines() == [f"recovery: {payload['recovery']}"]
    encoded = result.stdout + result.stderr
    assert all(value not in encoded for value in FORBIDDEN_DIAGNOSTIC_TEXT)
    return payload


def test_native_store_cli_help_matches_approved_archive_contract() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    for flag in (
        "--mke-source-archive",
        "--mke-tag-object",
        "--mke-commit",
        "--dra-source-archive",
        "--dra-tag-object",
        "--dra-commit",
        "--source-manifest",
        "--run-root",
        "--json",
    ):
        assert flag in result.stdout
    assert "--mke-repository" not in result.stdout
    assert "--work-root" not in result.stdout
    assert "custody" not in result.stdout.lower()
    assert result.stderr == ""


def test_native_store_cli_missing_required_input_is_bounded_json() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    _assert_bounded_failure(
        result,
        exit_code=2,
        stage="arguments",
        code="required_argument_missing",
    )


def test_native_store_cli_unknown_argument_is_bounded_json() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--unknown-argument"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    _assert_bounded_failure(
        result,
        exit_code=2,
        stage="arguments",
        code="invalid_cli",
    )


def test_native_store_cli_unreadable_archive_is_exit_2(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir(mode=0o700)
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--mke-source-archive",
            str(tmp_path / "missing-mke.tar"),
            "--mke-tag-object",
            "1ca0a0b348638369e8407270ca5f363b0e551a9e",
            "--mke-commit",
            "d258c10dc40bd9eccd67c858b56f4e4cf5fe4610",
            "--dra-source-archive",
            str(tmp_path / "missing-dra.tar.gz"),
            "--dra-tag-object",
            "f828606741f636bca7ddbb66244ca60019eaa3c8",
            "--dra-commit",
            "cb1f4660ee4ac7d81b04ffea014362e933487e61",
            "--source-manifest",
            str(FIXTURES / "source-manifest-v1.json"),
            "--run-root",
            str(run_root),
            "--json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    _assert_bounded_failure(
        result,
        exit_code=2,
        stage="arguments",
        code="input_unreadable",
    )


def test_manifest_accepts_fresh_checkout_0644_and_copies_both_archives_0400(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script()
    manifest_path = _copy_public_sources(tmp_path / "package")
    mke_archive = tmp_path / "mke.tar"
    mke_archive.write_bytes(b"exact mke archive")
    dra_archive = tmp_path / "dra.tar.gz"
    dra_archive.write_bytes(b"exact dra archive")
    monkeypatch.setattr(
        module,
        "SOURCE_ARCHIVE_SHA256",
        hashlib.sha256(mke_archive.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(module, "SOURCE_ARCHIVE_BYTES", len(mke_archive.read_bytes()))
    monkeypatch.setattr(
        module,
        "DRA_SOURCE_ARCHIVE_SHA256",
        hashlib.sha256(dra_archive.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(
        module,
        "DRA_SOURCE_ARCHIVE_BYTES",
        len(dra_archive.read_bytes()),
    )
    input_root = tmp_path / "input"
    input_root.mkdir(mode=0o700)
    manifest, sources = module._load_manifest(manifest_path)
    admitted = module._prepare_input_root(
        manifest_path, mke_archive, dra_archive, input_root, sources
    )
    assert manifest["author_revision"] == 3
    committed_corpus = manifest_path.parent / "mke-corpus"
    assert all(
        (path.stat().st_mode & 0o777) == 0o644
        for path in committed_corpus.iterdir()
    )
    assert input_root.stat().st_mode & 0o777 == 0o700
    assert all(item["mode"] == "0400" for item in admitted["files"])
    assert all(
        (path.stat().st_mode & 0o777) == 0o400
        for path in (input_root / "corpus").iterdir()
    )
    assert {
        item["basename"]
        for item in admitted["files"]
        if item["logical_name"].endswith("_archive")
    } == {"mke-v0.1.5.tar", "dra-v0.1.8-source.tar.gz"}


def test_fresh_run_root_exclusively_creates_children(tmp_path: Path) -> None:
    module = _load_script()
    run_root = tmp_path / "run"
    run_root.mkdir(mode=0o700)

    roots = module._prepare_run_root(run_root)

    assert set(roots) == {"input", "work", "store", "receipts"}
    assert all(path.parent == run_root for path in roots.values())
    assert all(path.stat().st_mode & 0o777 == 0o700 for path in roots.values())


def test_precreated_run_child_fails_closed(tmp_path: Path) -> None:
    module = _load_script()
    run_root = tmp_path / "run"
    run_root.mkdir(mode=0o700)
    (run_root / "input").mkdir(mode=0o700)

    with pytest.raises(module.PreparationFailure) as captured:
        module._prepare_run_root(run_root)

    assert captured.value.payload["code"] == "destination_exists"
    assert captured.value.exit_code == 11


@pytest.mark.parametrize(
    "mutation",
    [
        "mke_tag",
        "mke_commit",
        "mke_hash",
        "dra_tag",
        "dra_commit",
        "dra_hash",
    ],
)
def test_producer_input_validation_rejects_each_identity_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    module = _load_script()
    mke_archive = tmp_path / "mke-v0.1.5.tar"
    mke_archive.write_bytes(b"exact mke")
    dra_archive = tmp_path / "dra-v0.1.8-source.tar.gz"
    dra_archive.write_bytes(b"exact dra")
    monkeypatch.setattr(
        module,
        "SOURCE_ARCHIVE_SHA256",
        hashlib.sha256(mke_archive.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(
        module,
        "DRA_SOURCE_ARCHIVE_SHA256",
        hashlib.sha256(dra_archive.read_bytes()).hexdigest(),
    )
    values = {
        "mke_source_archive": mke_archive,
        "mke_tag_object": module.TAG_OBJECT,
        "mke_commit": module.PEELED_COMMIT,
        "dra_source_archive": dra_archive,
        "dra_tag_object": module.DRA_TAG_OBJECT,
        "dra_commit": module.DRA_PEELED_COMMIT,
    }
    if mutation == "mke_tag":
        values["mke_tag_object"] = "0" * 40
    elif mutation == "mke_commit":
        values["mke_commit"] = "0" * 40
    elif mutation == "mke_hash":
        mke_archive.write_bytes(b"drift")
    elif mutation == "dra_tag":
        values["dra_tag_object"] = "0" * 40
    elif mutation == "dra_commit":
        values["dra_commit"] = "0" * 40
    else:
        dra_archive.write_bytes(b"drift")

    with pytest.raises(module.PreparationFailure) as captured:
        module._validate_producer_inputs(**values)

    assert captured.value.payload["code"] == "producer_identity_mismatch"


@pytest.mark.parametrize(
    ("flag", "value", "exit_code", "stage", "code"),
    [
        ("--mke-source-archive", "wrong-mke", 2, "arguments", "input_unreadable"),
        ("--mke-tag-object", "0" * 40, 10, "producer", "producer_identity_mismatch"),
        ("--mke-commit", "0" * 40, 10, "producer", "producer_identity_mismatch"),
        ("--dra-source-archive", "wrong-dra", 2, "arguments", "input_unreadable"),
        ("--dra-tag-object", "0" * 40, 10, "producer", "producer_identity_mismatch"),
        ("--dra-commit", "0" * 40, 10, "producer", "producer_identity_mismatch"),
    ],
)
def test_documented_operator_contract_admits_only_exact_producer_inputs(
    tmp_path: Path,
    flag: str,
    value: str,
    exit_code: int,
    stage: str,
    code: str,
) -> None:
    mke_archive = tmp_path / "mke-v0.1.5.tar"
    mke_archive.write_bytes(b"wrong-mke")
    dra_archive = tmp_path / "dra-v0.1.8-source.tar.gz"
    dra_archive.write_bytes(b"wrong-dra")
    run_root = tmp_path / "run"
    run_root.mkdir(mode=0o700)
    arguments = [
        sys.executable,
        str(SCRIPT),
        "--mke-source-archive",
        str(mke_archive),
        "--mke-tag-object",
        "1ca0a0b348638369e8407270ca5f363b0e551a9e",
        "--mke-commit",
        "d258c10dc40bd9eccd67c858b56f4e4cf5fe4610",
        "--dra-source-archive",
        str(dra_archive),
        "--dra-tag-object",
        "f828606741f636bca7ddbb66244ca60019eaa3c8",
        "--dra-commit",
        "cb1f4660ee4ac7d81b04ffea014362e933487e61",
        "--source-manifest",
        str(FIXTURES / "source-manifest-v1.json"),
        "--run-root",
        str(run_root),
        "--json",
    ]
    index = arguments.index(flag)
    arguments[index + 1] = value

    result = subprocess.run(
        arguments,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    _assert_bounded_failure(
        result,
        exit_code=exit_code,
        stage=stage,
        code=code,
    )


@pytest.mark.parametrize(
    ("exception", "exit_code"),
    [
        ("native_source_set_mismatch", 10),
        ("store_artifact_invalid", 10),
        ("sealed_mutation_not_closed", 14),
        ("store_artifact_drift", 14),
        ("receipt_destination_exists", 13),
    ],
)
def test_native_failure_codes_have_explicit_a3_exit_ownership(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    exception: str,
    exit_code: int,
) -> None:
    module = _load_script()

    def fail(_: Any) -> None:
        raise module.NativeStoreValidationError(exception)

    monkeypatch.setattr(module, "_prepare", fail)

    assert module.main([]) == exit_code
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["code"] == exception
    assert captured.err.splitlines() == [f"recovery: {payload['recovery']}"]
    assert exit_code != 12


def test_internal_validation_failure_is_exit_13_and_public_safe(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script()

    def fail(_: Any) -> None:
        raise RuntimeError("sensitive physical path")

    monkeypatch.setattr(module, "_prepare", fail)

    assert module.main([]) == 13
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["code"] == "a3_preparation_failed"
    assert "sensitive" not in captured.out + captured.err
    assert captured.err.splitlines() == [f"recovery: {payload['recovery']}"]


def test_copy_time_archive_swap_fails_before_native_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script()
    manifest_path = _copy_public_sources(tmp_path / "package")
    mke_archive = tmp_path / "mke-v0.1.5.tar"
    mke_archive.write_bytes(b"exact mke")
    dra_archive = tmp_path / "dra-v0.1.8-source.tar.gz"
    dra_archive.write_bytes(b"exact dra")
    monkeypatch.setattr(
        module,
        "SOURCE_ARCHIVE_SHA256",
        hashlib.sha256(mke_archive.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(module, "SOURCE_ARCHIVE_BYTES", len(mke_archive.read_bytes()))
    monkeypatch.setattr(
        module,
        "DRA_SOURCE_ARCHIVE_SHA256",
        hashlib.sha256(dra_archive.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(
        module,
        "DRA_SOURCE_ARCHIVE_BYTES",
        len(dra_archive.read_bytes()),
    )
    module._validate_producer_inputs(
        mke_source_archive=mke_archive,
        mke_tag_object=module.TAG_OBJECT,
        mke_commit=module.PEELED_COMMIT,
        dra_source_archive=dra_archive,
        dra_tag_object=module.DRA_TAG_OBJECT,
        dra_commit=module.DRA_PEELED_COMMIT,
    )
    dra_archive.write_bytes(b"post-validation swap")
    input_root = tmp_path / "input"
    input_root.mkdir(mode=0o700)
    _, sources = module._load_manifest(manifest_path)

    with pytest.raises(module.PreparationFailure) as captured:
        module._prepare_input_root(
            manifest_path,
            mke_archive,
            dra_archive,
            input_root,
            sources,
        )

    assert captured.value.payload["code"] == "admitted_input_identity_mismatch"
    assert not (input_root / "dra-v0.1.8-source.tar.gz").exists()


@pytest.mark.parametrize("swapped", ["manifest", "fragment", "corpus"])
def test_copy_time_public_input_swap_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    swapped: str,
) -> None:
    module = _load_script()
    manifest_path = _copy_public_sources(tmp_path / "package")
    mke_archive = tmp_path / "mke-v0.1.5.tar"
    mke_archive.write_bytes(b"exact mke")
    dra_archive = tmp_path / "dra-v0.1.8-source.tar.gz"
    dra_archive.write_bytes(b"exact dra")
    monkeypatch.setattr(
        module,
        "SOURCE_ARCHIVE_SHA256",
        hashlib.sha256(mke_archive.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(module, "SOURCE_ARCHIVE_BYTES", len(mke_archive.read_bytes()))
    monkeypatch.setattr(
        module,
        "DRA_SOURCE_ARCHIVE_SHA256",
        hashlib.sha256(dra_archive.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(
        module,
        "DRA_SOURCE_ARCHIVE_BYTES",
        len(dra_archive.read_bytes()),
    )
    _, sources = module._load_manifest(manifest_path)
    if swapped == "manifest":
        manifest_path.write_bytes(b"swapped")
    elif swapped == "fragment":
        (manifest_path.parent / "source-manifest-fragment-v1.json").write_bytes(
            b"swapped"
        )
    else:
        (manifest_path.parent / sources[0]["relative_path"]).write_bytes(b"swapped")
    input_root = tmp_path / "input"
    input_root.mkdir(mode=0o700)

    with pytest.raises(module.PreparationFailure) as captured:
        module._prepare_input_root(
            manifest_path,
            mke_archive,
            dra_archive,
            input_root,
            sources,
        )

    assert captured.value.payload["code"] == "admitted_input_identity_mismatch"


def test_receipt_archive_entries_must_equal_provider_and_admission_peers() -> None:
    module = _load_script()
    receipt: dict[str, Any] = {
        "producer": {
            "source_archive": {
                "basename": "mke-v0.1.5.tar",
                "byte_length": 14_643_200,
                "sha256": module.SOURCE_ARCHIVE_SHA256,
                "mode": "0400",
            },
            "dra_admission": {
                "source_archive": {
                    "basename": "dra-v0.1.8-source.tar.gz",
                    "byte_length": 1_687_802,
                    "sha256": module.DRA_SOURCE_ARCHIVE_SHA256,
                    "mode": "0400",
                }
            },
        },
        "input_admission": {
            "files": [
                {
                    "logical_name": "mke_a3_source_tree_archive",
                    "basename": "mke-v0.1.5.tar",
                    "byte_length": 14_643_200,
                    "sha256": module.SOURCE_ARCHIVE_SHA256,
                    "mode": "0400",
                },
                {
                    "logical_name": "dra_source_archive",
                    "basename": "dra-v0.1.8-source.tar.gz",
                    "byte_length": 1_687_802,
                    "sha256": module.DRA_SOURCE_ARCHIVE_SHA256,
                    "mode": "0400",
                },
            ]
        },
    }
    module._validate_receipt_archive_peers(receipt)
    receipt["producer"]["dra_admission"]["source_archive"]["sha256"] = "0" * 64

    with pytest.raises(
        module.NativeStoreValidationError,
        match="receipt_archive_identity_mismatch",
    ):
        module._validate_receipt_archive_peers(receipt)


@pytest.mark.parametrize(
    "mutation",
    [
        "author_revision",
        "fragment_basename",
        "fragment_bytes",
        "fragment_sha256",
        "producer_lock",
        "native_proof",
        "source_list",
    ],
)
def test_manifest_rejects_each_closed_identity_drift(
    tmp_path: Path, mutation: str
) -> None:
    module = _load_script()
    manifest_path = _copy_public_sources(tmp_path / "package")
    manifest: dict[str, Any] = json.loads(manifest_path.read_text())
    if mutation == "author_revision":
        manifest["author_revision"] = 2
    elif mutation == "fragment_basename":
        manifest["source_manifest_fragment"]["basename"] = "other.json"
    elif mutation == "fragment_bytes":
        manifest["source_manifest_fragment"]["byte_length"] += 1
    elif mutation == "fragment_sha256":
        manifest["source_manifest_fragment"]["sha256"] = "0" * 64
    elif mutation == "producer_lock":
        manifest["producer_lock"]["release"]["peeled_commit"] = "0" * 40
    elif mutation == "native_proof":
        manifest["producer_native_proof_commitment"]["sha256"] = "0" * 64
    else:
        manifest["sources"] = manifest["sources"][:-1]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(module.PreparationFailure) as captured:
        module._load_manifest(manifest_path)
    assert captured.value.payload["code"] == "corpus_identity_mismatch"
