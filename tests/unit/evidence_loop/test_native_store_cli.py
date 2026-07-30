from __future__ import annotations

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
        "--source-manifest",
        "--work-root",
        "--store-root",
        "--receipt",
        "--json",
    ):
        assert flag in result.stdout
    assert "--mke-repository" not in result.stdout
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


def test_manifest_accepts_fresh_checkout_0644_and_copies_0400(
    tmp_path: Path,
) -> None:
    module = _load_script()
    manifest_path = _copy_public_sources(tmp_path / "package")
    archive = tmp_path / "mke.tar"
    archive.write_bytes(b"exact archive")
    input_root = tmp_path / "input"
    manifest, sources = module._load_manifest(manifest_path)
    admitted = module._prepare_input_root(
        manifest_path, archive, input_root, sources
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
