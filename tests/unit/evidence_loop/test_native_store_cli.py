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
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert set(payload) == {"stage", "code", "problem", "cause", "recovery"}
    assert payload["stage"] == "arguments"
    assert result.stderr == ""


def test_manifest_accepts_fresh_checkout_0644_and_copies_both_archives_0400(
    tmp_path: Path,
) -> None:
    module = _load_script()
    manifest_path = _copy_public_sources(tmp_path / "package")
    mke_archive = tmp_path / "mke.tar"
    mke_archive.write_bytes(b"exact mke archive")
    dra_archive = tmp_path / "dra.tar.gz"
    dra_archive.write_bytes(b"exact dra archive")
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
    ("flag", "value"),
    [
        ("--mke-source-archive", "wrong-mke"),
        ("--mke-tag-object", "0" * 40),
        ("--mke-commit", "0" * 40),
        ("--dra-source-archive", "wrong-dra"),
        ("--dra-tag-object", "0" * 40),
        ("--dra-commit", "0" * 40),
    ],
)
def test_documented_operator_contract_admits_only_exact_producer_inputs(
    tmp_path: Path,
    flag: str,
    value: str,
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

    assert result.returncode == 11
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["stage"] == "producer"
    assert payload["code"] == "producer_identity_mismatch"


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
