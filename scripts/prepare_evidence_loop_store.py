#!/usr/bin/env python3
"""Prepare and seal the provider-free Slice 0 MKE store."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any, NoReturn, cast

from night_voyager.evidence_loop.native_store import (
    STORE_AUTHORITY_BASENAMES,
    NativeStoreValidationError,
    build_native_runtime_identity,
    build_setup_receipt,
    collect_read_chunks,
    collect_search_pages,
    native_mcp_environment,
    remove_runtime_bytecode,
    seal_store,
    validate_native_vertical,
    validate_sealed_write_rejection,
    verify_store_seal,
    write_canonical_json,
)

TAG = "v0.1.5"
TAG_OBJECT = "1ca0a0b348638369e8407270ca5f363b0e551a9e"
PEELED_COMMIT = "d258c10dc40bd9eccd67c858b56f4e4cf5fe4610"
TREE = "22756fdfa8ef131d3e28fc2a44acc3f2b6fa32f0"
MKE_SOURCE_ARCHIVE_BASENAME = "mke-v0.1.5.tar"
SOURCE_ARCHIVE_BYTES = 14_643_200
SOURCE_ARCHIVE_SHA256 = "12e0dc785723bd35e4f1ba40d3935fd4d906ae360b1e99fcecb43d24a009aa5a"
DRA_TAG = "v0.1.8"
DRA_TAG_OBJECT = "f828606741f636bca7ddbb66244ca60019eaa3c8"
DRA_PEELED_COMMIT = "cb1f4660ee4ac7d81b04ffea014362e933487e61"
DRA_SOURCE_ARCHIVE_BASENAME = "dra-v0.1.8-source.tar.gz"
DRA_SOURCE_ARCHIVE_BYTES = 1_687_802
DRA_SOURCE_ARCHIVE_SHA256 = "ab9deaf7678571b2dda6e8275fcfe2ff69d6baab04f3ab66f84c6abdcb2a6e7f"
DRA_PROFILE_ID = "generic-strict-citation"
DRA_PROFILE_VERSION = "1"
SOURCE_FRAGMENT_SHA256 = "d9926321da8c244e93d93afd4e8a5c4571aa14ceac4a7913644a887f195c0793"
SOURCE_FRAGMENT_BYTES = 11549
SOURCE_MANIFEST_SHA256 = "8d6559feb891f5509fe25f034b97c77ed825a60d3ba682f110bfa50517ba8e75"
SOURCE_MANIFEST_BYTES = 3992
PYMUPDF_VERSION = "1.27.2.3"
PYMUPDF_WHEEL = "pymupdf-1.27.2.3-cp310-abi3-macosx_11_0_arm64.whl"
PYMUPDF_WHEEL_SHA256 = "660d93cb6da5bbddf11d3982ae27745dd3a9902d9f24cdb69adab83962294b5a"
TOOLS = (
    "list_libraries",
    "ingest_file",
    "get_run",
    "search_library",
    "ask_library",
    "list_libraries_v1",
    "search_library_v1",
    "ask_library_v1",
    "search_library_v2",
    "read_evidence_v1",
)
PROBE_QUERY = "synthetic public-safe material"


class PreparationFailure(RuntimeError):
    def __init__(
        self,
        stage: str,
        code: str,
        problem: str,
        cause: str,
        recovery: str,
        exit_code: int,
    ) -> None:
        self.payload = {
            "stage": stage,
            "code": code,
            "problem": problem,
            "cause": cause,
            "recovery": recovery,
        }
        self.exit_code = exit_code
        super().__init__(code)


class BoundedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        del message
        raise PreparationFailure(
            "arguments",
            "invalid_cli",
            "The A3 command line is invalid.",
            "An unknown or malformed argument was supplied.",
            "Use --help and supply only the documented A3 arguments.",
            2,
        )


def _parser() -> argparse.ArgumentParser:
    parser = BoundedArgumentParser(
        description="Prepare the exact tagged MKE v0.1.5 Slice 0 store and close mutation."
    )
    parser.add_argument("--mke-source-archive")
    parser.add_argument("--mke-tag-object")
    parser.add_argument("--mke-commit")
    parser.add_argument("--dra-source-archive")
    parser.add_argument("--dra-tag-object")
    parser.add_argument("--dra-commit")
    parser.add_argument("--source-manifest")
    parser.add_argument("--run-root")
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> str:
    result = subprocess.run(
        argv,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        env=env if env is not None else {**os.environ, "UV_OFFLINE": "1"},
    )
    if result.returncode != 0:
        raise PreparationFailure(
            "producer",
            "producer_command_failed",
            "The exact producer command did not complete.",
            "A verified local producer step failed.",
            "Inspect the task-owned producer environment.",
            10,
        )
    return result.stdout.strip()


def _verify_cached_pymupdf(uv: str) -> None:
    cache = Path(_run([uv, "cache", "dir"]))
    proof = cache / "wheels-v6" / "pypi" / "pymupdf" / "1.27.2.3-cp310-abi3-macosx_11_0_arm64.http"
    if not proof.is_file():
        raise PreparationFailure(
            "producer",
            "producer_dependency_unavailable",
            "The locked cached PDF dependency is unavailable.",
            "The exact cached wheel commitment is absent.",
            "Restore the approved shared package cache.",
            10,
        )
    data = proof.read_bytes()
    if PYMUPDF_WHEEL.encode() not in data or PYMUPDF_WHEEL_SHA256.encode() not in data:
        raise PreparationFailure(
            "producer",
            "producer_dependency_mismatch",
            "The cached PDF dependency does not match the frozen contract.",
            "The locked wheel filename or digest differs.",
            "Restore the approved locked wheel cache entry.",
            10,
        )


def _verify_archive_tree(extracted: Path) -> None:
    _run(["git", "init", "--quiet"], cwd=extracted)
    _run(["git", "config", "core.autocrlf", "false"], cwd=extracted)
    _run(["git", "config", "core.filemode", "true"], cwd=extracted)
    _run(["git", "add", "--force", "."], cwd=extracted)
    if _run(["git", "write-tree"], cwd=extracted) != TREE:
        raise PreparationFailure(
            "producer",
            "producer_identity_mismatch",
            "The MKE source archive tree does not match the frozen contract.",
            "The extracted Git tree identity differs.",
            "Restore the exact task-owned MKE v0.1.5 source archive.",
            10,
        )


def _prepare_wheel(source_archive: Path, work_root: Path) -> tuple[Path, str]:
    uv = shutil.which("uv")
    if uv is None:
        raise PreparationFailure(
            "producer",
            "producer_tool_unavailable",
            "The local package runner is unavailable.",
            "The required cached build tool is not on PATH.",
            "Restore the approved local build tool.",
            10,
        )
    _verify_cached_pymupdf(uv)
    if _sha256(source_archive) != SOURCE_ARCHIVE_SHA256:
        raise PreparationFailure(
            "producer",
            "producer_identity_mismatch",
            "The MKE source archive does not match the frozen contract.",
            "The exact source archive digest differs.",
            "Restore the exact task-owned MKE v0.1.5 source archive.",
            10,
        )
    source = work_root / "source"
    dist = work_root / "dist"
    venv = work_root / "venv"
    source.mkdir(mode=0o700)
    dist.mkdir(mode=0o700)
    with tarfile.open(source_archive) as package:
        package.extractall(source, filter="data")
    extracted = source / "mke-v0.1.5"
    if not extracted.is_dir():
        raise PreparationFailure(
            "producer",
            "producer_archive_invalid",
            "The MKE source archive layout is invalid.",
            "The expected source root is absent.",
            "Restore the exact task-owned MKE v0.1.5 source archive.",
            10,
        )
    _verify_archive_tree(extracted)
    _run(
        [
            uv,
            "build",
            "--offline",
            "--wheel",
            "--no-create-gitignore",
            "--out-dir",
            str(dist),
            str(extracted),
        ]
    )
    wheels = list(dist.glob("multimodal_knowledge_engine-0.1.5-*.whl"))
    if len(wheels) != 1:
        raise PreparationFailure(
            "producer",
            "producer_wheel_invalid",
            "The exact MKE wheel was not produced uniquely.",
            "The local build output was missing or ambiguous.",
            "Inspect the exact tagged archive build.",
            10,
        )
    _run([uv, "venv", "--python", "3.12", str(venv)])
    _run(
        [
            uv,
            "pip",
            "install",
            "--offline",
            "--python",
            str(venv / "bin/python"),
            str(wheels[0]),
        ]
    )
    _run(
        [
            uv,
            "pip",
            "install",
            "--offline",
            "--python",
            str(venv / "bin/python"),
            f"pymupdf=={PYMUPDF_VERSION}",
        ]
    )
    versions = json.loads(
        _run(
            [
                str(venv / "bin/python"),
                "-c",
                (
                    "import importlib.metadata as m,json;"
                    "print(json.dumps({'mke':m.version('multimodal-knowledge-engine'),"
                    "'pymupdf':m.version('PyMuPDF'),'mcp':m.version('mcp')}))"
                ),
            ],
            env={**native_mcp_environment(), "UV_OFFLINE": "1"},
        )
    )
    if versions != {"mke": "0.1.5", "pymupdf": "1.27.2.3", "mcp": "1.28.1"}:
        raise PreparationFailure(
            "producer",
            "producer_runtime_mismatch",
            "The isolated producer runtime does not match the frozen contract.",
            "One or more installed producer versions differ.",
            "Restore the approved cached producer dependencies.",
            10,
        )
    remove_runtime_bytecode(venv)
    return venv / "bin/mke", _sha256(wheels[0])


def _corpus_failure() -> PreparationFailure:
    return PreparationFailure(
        "corpus",
        "corpus_identity_mismatch",
        "The project source manifest does not match Revision 3.",
        "A closed manifest, producer, proof, or source commitment differs.",
        "Restore the committed Revision 3 public package.",
        10,
    )


def _load_manifest(
    manifest_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        manifest = cast(
            dict[str, Any],
            json.loads(manifest_path.read_text(encoding="utf-8")),
        )
        fragment_path = manifest_path.parent / "source-manifest-fragment-v1.json"
        fragment_bytes = fragment_path.read_bytes()
        fragment = cast(dict[str, Any], json.loads(fragment_bytes))
        sources = cast(list[dict[str, Any]], fragment["sources"])
        producer = sources[0]["producer"]
        expected_producer_lock = {
            key: producer[key] for key in ("release", "pymupdf", "wheel", "profile")
        }
        stable_keys = (
            "relative_path",
            "dataset_source_id",
            "evaluation_canonical_source_id",
            "canonical_url",
            "byte_length",
            "content_sha256",
            "media_type",
            "redistribution_class",
            "expected_publication_revision",
            "expected_extracted_text_sha256",
            "expected_extracted_utf8_bytes",
            "expected_locator",
        )
        stable_sources = [{key: source[key] for key in stable_keys} for source in sources]
        native_proof = sources[0]["producer_native_proof_commitment"]
        exact_top_keys = {
            "schema_version",
            "author_revision",
            "canonicalization_id",
            "source_manifest_fragment",
            "producer_lock",
            "producer_native_proof_commitment",
            "sources",
        }
        valid = (
            set(manifest) == exact_top_keys
            and manifest.get("schema_version") == "night-voyager.evidence-loop-source-manifest.v1"
            and manifest.get("author_revision") == 3
            and manifest.get("canonicalization_id")
            == "night-voyager.slice0.compact-sorted-utf8-lf.v1"
            and manifest.get("source_manifest_fragment")
            == {
                "basename": "source-manifest-fragment-v1.json",
                "byte_length": SOURCE_FRAGMENT_BYTES,
                "sha256": SOURCE_FRAGMENT_SHA256,
            }
            and len(fragment_bytes) == SOURCE_FRAGMENT_BYTES
            and hashlib.sha256(fragment_bytes).hexdigest() == SOURCE_FRAGMENT_SHA256
            and len(sources) == 4
            and all(
                {key: source["producer"][key] for key in expected_producer_lock}
                == expected_producer_lock
                for source in sources
            )
            and all(
                source["producer_native_proof_commitment"] == native_proof for source in sources
            )
            and manifest.get("producer_lock") == expected_producer_lock
            and manifest.get("producer_native_proof_commitment") == native_proof
            and manifest.get("sources") == stable_sources
        )
    except (
        AttributeError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        raise _corpus_failure() from None
    if not valid:
        raise _corpus_failure()
    for source in stable_sources:
        path = manifest_path.parent / source["relative_path"]
        if (
            not path.is_file()
            or path.stat().st_size != source["byte_length"]
            or _sha256(path) != source["content_sha256"]
        ):
            raise _corpus_failure()
    return manifest, stable_sources


def _admission_copy_failure() -> PreparationFailure:
    return PreparationFailure(
        "producer",
        "admitted_input_identity_mismatch",
        "An admitted A3 input does not match its frozen commitment.",
        "The copied bytes, length, or mode differ from the approved identity.",
        "Restore the exact committed or producer input and use a fresh run root.",
        10,
    )


def _copy_exclusive(
    source: Path,
    destination: Path,
    *,
    expected_sha256: str,
    expected_byte_length: int,
) -> dict[str, Any]:
    descriptor = os.open(
        destination,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o400,
    )
    try:
        with source.open("rb") as reader, os.fdopen(descriptor, "wb") as writer:
            shutil.copyfileobj(reader, writer)
            writer.flush()
            os.fsync(writer.fileno())
    except Exception:
        destination.unlink(missing_ok=True)
        raise _admission_copy_failure() from None
    destination.chmod(0o400)
    if (
        destination.stat().st_size != expected_byte_length
        or _sha256(destination) != expected_sha256
        or destination.stat().st_mode & 0o777 != 0o400
    ):
        destination.unlink(missing_ok=True)
        raise _admission_copy_failure()
    return {
        "basename": destination.name,
        "byte_length": expected_byte_length,
        "sha256": expected_sha256,
        "mode": "0400",
    }


def _prepare_input_root(
    manifest_path: Path,
    mke_source_archive: Path,
    dra_source_archive: Path,
    input_root: Path,
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    corpus = input_root / "corpus"
    corpus.mkdir(mode=0o700)
    files = [
        {
            "logical_name": "mke_a3_source_tree_archive",
            **_copy_exclusive(
                mke_source_archive,
                input_root / MKE_SOURCE_ARCHIVE_BASENAME,
                expected_sha256=SOURCE_ARCHIVE_SHA256,
                expected_byte_length=SOURCE_ARCHIVE_BYTES,
            ),
        },
        {
            "logical_name": "dra_source_archive",
            **_copy_exclusive(
                dra_source_archive,
                input_root / DRA_SOURCE_ARCHIVE_BASENAME,
                expected_sha256=DRA_SOURCE_ARCHIVE_SHA256,
                expected_byte_length=DRA_SOURCE_ARCHIVE_BYTES,
            ),
        },
        {
            "logical_name": "source_manifest",
            **_copy_exclusive(
                manifest_path,
                input_root / "source-manifest-v1.json",
                expected_sha256=SOURCE_MANIFEST_SHA256,
                expected_byte_length=SOURCE_MANIFEST_BYTES,
            ),
        },
        {
            "logical_name": "source_manifest_fragment",
            **_copy_exclusive(
                manifest_path.parent / "source-manifest-fragment-v1.json",
                input_root / "source-manifest-fragment-v1.json",
                expected_sha256=SOURCE_FRAGMENT_SHA256,
                expected_byte_length=SOURCE_FRAGMENT_BYTES,
            ),
        },
    ]
    for source in sources:
        source_path = manifest_path.parent / source["relative_path"]
        files.append(
            {
                "logical_name": source["relative_path"],
                **_copy_exclusive(
                    source_path,
                    corpus / source_path.name,
                    expected_sha256=str(source["content_sha256"]),
                    expected_byte_length=int(source["byte_length"]),
                ),
            }
        )
    return {
        "schema_version": "night-voyager.evidence-loop-input-admission.v1",
        "root_mode": "0700",
        "corpus_root_mode": "0700",
        "files": files,
    }


def _prepare_run_root(run_root: Path) -> dict[str, Path]:
    try:
        metadata = run_root.lstat()
        fresh = not any(run_root.iterdir())
    except OSError:
        fresh = False
        metadata = None
    if (
        metadata is None
        or stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o700
        or not fresh
    ):
        raise PreparationFailure(
            "arguments",
            "destination_exists",
            "The task-owned run root is not fresh and empty.",
            "A3 preparation is single-use and fail-closed.",
            "Create one fresh mode-0700 run root without child directories.",
            11,
        )
    roots = {name: run_root / name for name in ("input", "work", "store", "receipts")}
    for root in roots.values():
        root.mkdir(mode=0o700)
    return roots


def _validate_producer_inputs(
    *,
    mke_source_archive: Path,
    mke_tag_object: str,
    mke_commit: str,
    dra_source_archive: Path,
    dra_tag_object: str,
    dra_commit: str,
) -> None:
    if not mke_source_archive.is_file() or not dra_source_archive.is_file():
        raise PreparationFailure(
            "arguments",
            "input_unreadable",
            "A required A3 producer input is unreadable.",
            "One or more declared source archives are unavailable.",
            "Restore readable exact producer archives and retry.",
            2,
        )
    try:
        mke_bytes = mke_source_archive.stat().st_size
        mke_sha256 = _sha256(mke_source_archive)
        dra_bytes = dra_source_archive.stat().st_size
        dra_sha256 = _sha256(dra_source_archive)
    except OSError:
        raise PreparationFailure(
            "arguments",
            "input_unreadable",
            "A required A3 producer input is unreadable.",
            "One or more declared source archives cannot be read.",
            "Restore readable exact producer archives and retry.",
            2,
        ) from None
    if (
        mke_tag_object != TAG_OBJECT
        or mke_commit != PEELED_COMMIT
        or dra_tag_object != DRA_TAG_OBJECT
        or dra_commit != DRA_PEELED_COMMIT
        or mke_bytes != SOURCE_ARCHIVE_BYTES
        or mke_sha256 != SOURCE_ARCHIVE_SHA256
        or dra_bytes != DRA_SOURCE_ARCHIVE_BYTES
        or dra_sha256 != DRA_SOURCE_ARCHIVE_SHA256
    ):
        raise PreparationFailure(
            "producer",
            "producer_identity_mismatch",
            "The supplied producer inputs do not match the frozen A3 contract.",
            "An exact archive, tag object, commit, or digest differs.",
            "Supply the approved MKE v0.1.5 and DRA v0.1.8 inputs.",
            10,
        )


def _validate_receipt_archive_peers(receipt: dict[str, Any]) -> None:
    expected_mke = {
        "basename": MKE_SOURCE_ARCHIVE_BASENAME,
        "byte_length": SOURCE_ARCHIVE_BYTES,
        "sha256": SOURCE_ARCHIVE_SHA256,
        "mode": "0400",
    }
    expected_dra = {
        "basename": DRA_SOURCE_ARCHIVE_BASENAME,
        "byte_length": DRA_SOURCE_ARCHIVE_BYTES,
        "sha256": DRA_SOURCE_ARCHIVE_SHA256,
        "mode": "0400",
    }
    try:
        producer = cast(dict[str, Any], receipt["producer"])
        dra = cast(dict[str, Any], producer["dra_admission"])
        native_runtime = cast(dict[str, Any], receipt["native_runtime_identity"])
        native_mke = cast(dict[str, Any], native_runtime["mke"])
        admission = cast(dict[str, Any], receipt["input_admission"])
        files = cast(list[dict[str, Any]], admission["files"])
        by_logical_name = {
            str(entry["logical_name"]): {
                key: entry[key] for key in ("basename", "byte_length", "sha256", "mode")
            }
            for entry in files
        }
        valid = (
            producer["source_archive"] == expected_mke
            and dra["source_archive"] == expected_dra
            and native_mke["wheel_sha256"] == producer["wheel_sha256"]
            and by_logical_name["mke_a3_source_tree_archive"] == expected_mke
            and by_logical_name["dra_source_archive"] == expected_dra
        )
    except (KeyError, TypeError):
        valid = False
    if not valid:
        raise NativeStoreValidationError("receipt_archive_identity_mismatch")


async def _native_observation(
    executable: Path,
    database: Path,
    corpus: Path,
    sources: list[dict[str, Any]],
    *,
    ingest: bool,
    sealed_write_probe: bool = False,
) -> tuple[tuple[dict[str, Any], ...], str, dict[str, Any] | None]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=str(executable),
        args=[
            "--db",
            str(database),
            "mcp",
            "--allowed-root",
            str(corpus),
        ],
        env=native_mcp_environment(),
    )
    ingests: list[dict[str, Any]] = []
    write_response: dict[str, Any] | None = None
    with Path(os.devnull).open("w") as errlog:
        async with stdio_client(params, errlog=errlog) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                inventory = tuple(tool.name for tool in (await session.list_tools()).tools)
                if inventory != TOOLS:
                    raise NativeStoreValidationError("producer_tool_inventory_mismatch")

                async def call_tool(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
                    result = await session.call_tool(tool, arguments)
                    if result.isError or not isinstance(result.structuredContent, dict):
                        raise NativeStoreValidationError("native_tool_call_failed")
                    return result.structuredContent

                if ingest:
                    for source in sources:
                        relative = str(source["relative_path"])
                        result = await call_tool("ingest_file", {"path": Path(relative).name})
                        ingests.append({"relative_path": relative, **result})
                if sealed_write_probe:
                    write_response = await call_tool(
                        "ingest_file",
                        {"path": Path(str(sources[0]["relative_path"])).name},
                    )
                search = await collect_search_pages(call_tool, query=PROBE_QUERY)
                descriptors = [dict(match["evidence"]) for match in search.matches]
                reads: dict[str, dict[str, Any]] = {}
                for descriptor in descriptors:
                    read_result = await collect_read_chunks(call_tool, descriptor)
                    reads[str(descriptor["evidence_id"])] = {
                        "terminal_sha256": read_result.terminal_sha256,
                        "utf8_bytes": read_result.utf8_bytes,
                    }
                if not ingest:
                    ingests = [
                        {
                            "relative_path": source["relative_path"],
                            "ok": True,
                            "run_id": next(
                                descriptor["run_id"]
                                for descriptor in descriptors
                                if descriptor["content_fingerprint"]
                                == f"sha256:{source['content_sha256']}"
                            ),
                            "run_state": "published",
                            "media_type": "application/pdf",
                            "evidence_count": 1,
                        }
                        for source in sources
                    ]
                mappings = validate_native_vertical(
                    sources,
                    ingests,
                    descriptors,
                    reads,
                    search.authority_snapshot,
                )
                fingerprint = str(search.authority_snapshot["active_set_fingerprint"])
                return mappings, fingerprint, write_response


def _remove_sqlite_runtime_files(database: Path) -> None:
    for suffix in ("-wal", "-shm"):
        candidate = database.with_name(database.name + suffix)
        candidate.unlink(missing_ok=True)


def _validate_materialized_wal_peers(database: Path) -> dict[str, Any]:
    store_root = database.parent
    paths = tuple(store_root / basename for basename in STORE_AUTHORITY_BASENAMES)
    if (
        database != paths[0]
        or tuple(path.name for path in sorted(store_root.iterdir())) != STORE_AUTHORITY_BASENAMES
    ):
        raise NativeStoreValidationError("store_artifact_invalid")
    for path in paths:
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise NativeStoreValidationError("store_artifact_invalid")
    if paths[1].stat().st_size != 32_768 or paths[2].stat().st_size != 0:
        raise NativeStoreValidationError("store_artifact_invalid")
    return {
        "authority_image": "sqlite_read_only_wal_atomic_snapshot",
        "materialization_phase": "task_owned_preparation_mutation",
        "ordered_basenames": list(STORE_AUTHORITY_BASENAMES),
        "wal_byte_length": 0,
        "shm_byte_length": 32_768,
    }


def _materialize_wal_authority(
    executable: Path,
    database: Path,
    corpus: Path,
    sources: list[dict[str, Any]],
    *,
    expected_mappings: tuple[dict[str, Any], ...],
    expected_active_set_fingerprint: str,
) -> dict[str, Any]:
    _remove_sqlite_runtime_files(database)
    database.chmod(0o400)
    reopened, reopened_fingerprint, _ = asyncio.run(
        _native_observation(
            executable,
            database,
            corpus,
            sources,
            ingest=False,
        )
    )
    if reopened != expected_mappings or reopened_fingerprint != expected_active_set_fingerprint:
        raise NativeStoreValidationError("read_only_reopen_drift")
    return _validate_materialized_wal_peers(database)


def _prepare(args: argparse.Namespace) -> dict[str, Any]:
    required = (
        args.mke_source_archive,
        args.mke_tag_object,
        args.mke_commit,
        args.dra_source_archive,
        args.dra_tag_object,
        args.dra_commit,
        args.source_manifest,
        args.run_root,
    )
    if not all(required):
        raise PreparationFailure(
            "arguments",
            "required_argument_missing",
            "Required A3 input is missing.",
            "Archive, producer identities, manifest, work, store, and receipt are required.",
            "Provide all documented A3 root arguments.",
            2,
        )
    mke_source_archive = Path(args.mke_source_archive).resolve()
    dra_source_archive = Path(args.dra_source_archive).resolve()
    manifest_path = Path(args.source_manifest).resolve()
    run_root = Path(args.run_root)
    _validate_producer_inputs(
        mke_source_archive=mke_source_archive,
        mke_tag_object=args.mke_tag_object,
        mke_commit=args.mke_commit,
        dra_source_archive=dra_source_archive,
        dra_tag_object=args.dra_tag_object,
        dra_commit=args.dra_commit,
    )
    if not manifest_path.is_file():
        raise PreparationFailure(
            "arguments",
            "required_argument_missing",
            "The Revision 3 source manifest is unavailable.",
            "The declared source manifest is not a file.",
            "Supply the committed Revision 3 source manifest.",
            2,
        )
    _, sources = _load_manifest(manifest_path)
    roots = _prepare_run_root(run_root)
    input_root = roots["input"]
    work_root = roots["work"]
    store_root = roots["store"]
    receipt_path = roots["receipts"] / "sealed-mke-store-v1.json"
    input_admission = _prepare_input_root(
        manifest_path,
        mke_source_archive,
        dra_source_archive,
        input_root,
        sources,
    )
    admitted_archive = input_root / MKE_SOURCE_ARCHIVE_BASENAME
    executable, wheel_sha256 = _prepare_wheel(admitted_archive, work_root)
    database = store_root / "store.sqlite"
    corpus = input_root / "corpus"
    mappings, active_set_fingerprint, _ = asyncio.run(
        _native_observation(executable, database, corpus, sources, ingest=True)
    )
    sqlite_authority_image = _materialize_wal_authority(
        executable,
        database,
        corpus,
        sources,
        expected_mappings=mappings,
        expected_active_set_fingerprint=active_set_fingerprint,
    )
    store_seal = seal_store(store_root, database)
    verify_store_seal(store_root, store_seal)
    sealed_write_rejection: dict[str, Any] | None = None
    for _ in range(3):
        before_seal = dict(verify_store_seal(store_root, store_seal))
        reopened, reopened_fingerprint, write_response = asyncio.run(
            _native_observation(
                executable,
                database,
                corpus,
                sources,
                ingest=False,
                sealed_write_probe=True,
            )
        )
        if reopened != mappings or reopened_fingerprint != active_set_fingerprint:
            raise NativeStoreValidationError("read_only_reopen_drift")
        after_seal = dict(verify_store_seal(store_root, store_seal))
        if write_response is None:
            raise NativeStoreValidationError("sealed_mutation_not_closed")
        sealed_write_rejection = validate_sealed_write_rejection(
            response=write_response,
            before_seal=before_seal,
            after_seal=after_seal,
            before_active_set_fingerprint=active_set_fingerprint,
            after_active_set_fingerprint=reopened_fingerprint,
        )
    if sealed_write_rejection is None:
        raise NativeStoreValidationError("sealed_mutation_not_closed")
    producer = {
        "name": "multimodal-knowledge-engine",
        "version": "0.1.5",
        "tag": TAG,
        "tag_object": TAG_OBJECT,
        "peeled_commit": PEELED_COMMIT,
        "tree": TREE,
        "source_archive": {
            "basename": admitted_archive.name,
            "byte_length": admitted_archive.stat().st_size,
            "sha256": SOURCE_ARCHIVE_SHA256,
            "mode": "0400",
        },
        "wheel_sha256": wheel_sha256,
        "mcp_version": "1.28.1",
        "pymupdf_version": PYMUPDF_VERSION,
        "pymupdf_wheel_filename": PYMUPDF_WHEEL,
        "pymupdf_wheel_sha256": PYMUPDF_WHEEL_SHA256,
        "tool_inventory": list(TOOLS),
        "dra_admission": {
            "name": "decision-research-agent",
            "version": "0.1.8",
            "tag": DRA_TAG,
            "tag_object": DRA_TAG_OBJECT,
            "peeled_commit": DRA_PEELED_COMMIT,
            "profile_id": DRA_PROFILE_ID,
            "profile_version": DRA_PROFILE_VERSION,
            "execution": "not_executed_admission_only",
            "source_archive": {
                "basename": DRA_SOURCE_ARCHIVE_BASENAME,
                "byte_length": (input_root / DRA_SOURCE_ARCHIVE_BASENAME).stat().st_size,
                "sha256": DRA_SOURCE_ARCHIVE_SHA256,
                "mode": "0400",
            },
        },
    }
    native_runtime_identity = build_native_runtime_identity(
        run_root,
        wheel_sha256=wheel_sha256,
    )
    setup = build_setup_receipt(
        source_manifest_sha256=_sha256(input_root / "source-manifest-v1.json"),
        active_set_fingerprint=active_set_fingerprint,
        store_seal=store_seal,
        producer=producer,
        mappings=mappings,
        sqlite_authority_image=sqlite_authority_image,
        fresh_process_verification_runs=3,
        native_runtime_identity=native_runtime_identity,
        input_admission=input_admission,
        sealed_write_rejection=sealed_write_rejection,
    )
    _validate_receipt_archive_peers(setup)
    write_canonical_json(receipt_path, setup)
    return {
        "schema_version": "night-voyager.evidence-loop-store-preparation-response.v1",
        "ok": True,
        "code": "evidence_loop_store_sealed",
        "source_count": len(sources),
        "store_state": "sealed_read_only",
        "receipt": {
            "basename": receipt_path.name,
            "byte_length": receipt_path.stat().st_size,
            "sha256": _sha256(receipt_path),
        },
    }


def _emit_failure(payload: dict[str, Any], exit_code: int) -> int:
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))
    print(f"recovery: {payload['recovery']}", file=sys.stderr)
    return exit_code


def _native_failure_exit_code(code: str) -> int:
    if code in {"sealed_mutation_not_closed", "store_artifact_drift"}:
        return 14
    if code.startswith(("search_", "read_", "native_")) or code in {
        "native descriptor count mismatch",
        "native descriptor identity mismatch",
        "native descriptor trace identity missing",
        "producer_tool_inventory_mismatch",
        "store_artifact_invalid",
    }:
        return 10
    return 13


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        payload = _prepare(args)
    except PreparationFailure as error:
        return _emit_failure(error.payload, error.exit_code)
    except NativeStoreValidationError as error:
        code = str(error)
        payload = {
            "stage": "native",
            "code": code,
            "problem": "The native MKE store did not satisfy the frozen A3 contract.",
            "cause": "A bounded native identity or completeness check failed.",
            "recovery": "Inspect the exact tagged producer and committed public sources.",
        }
        return _emit_failure(payload, _native_failure_exit_code(code))
    except Exception:
        payload = {
            "stage": "internal",
            "code": "a3_preparation_failed",
            "problem": "A3 store preparation did not complete.",
            "cause": "An internal bounded operation failed.",
            "recovery": "Inspect task-owned runtime diagnostics without changing producer inputs.",
        }
        return _emit_failure(payload, 13)
    if args.json_output:
        print(json.dumps(payload, separators=(",", ":"), sort_keys=True))
    else:
        print(
            "status=passed "
            f"code={payload['code']} "
            f"source_count={payload['source_count']} "
            f"store_state={payload['store_state']} "
            f"receipt_sha256={payload['receipt']['sha256']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
