#!/usr/bin/env python3
"""Prepare and seal the provider-free Slice 0 MKE store."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Any, cast

from night_voyager.evidence_loop.native_store import (
    NativeStoreValidationError,
    build_setup_receipt,
    collect_read_chunks,
    collect_search_pages,
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
SOURCE_ARCHIVE_SHA256 = (
    "12e0dc785723bd35e4f1ba40d3935fd4d906ae360b1e99fcecb43d24a009aa5a"
)
DRA_TAG = "v0.1.8"
DRA_TAG_OBJECT = "f828606741f636bca7ddbb66244ca60019eaa3c8"
DRA_PEELED_COMMIT = "cb1f4660ee4ac7d81b04ffea014362e933487e61"
DRA_SOURCE_ARCHIVE_BASENAME = "dra-v0.1.8-source.tar.gz"
DRA_SOURCE_ARCHIVE_SHA256 = (
    "ab9deaf7678571b2dda6e8275fcfe2ff69d6baab04f3ab66f84c6abdcb2a6e7f"
)
DRA_PROFILE_ID = "generic-strict-citation"
DRA_PROFILE_VERSION = "1"
SOURCE_FRAGMENT_SHA256 = (
    "d9926321da8c244e93d93afd4e8a5c4571aa14ceac4a7913644a887f195c0793"
)
SOURCE_FRAGMENT_BYTES = 11549
PYMUPDF_VERSION = "1.27.2.3"
PYMUPDF_WHEEL = "pymupdf-1.27.2.3-cp310-abi3-macosx_11_0_arm64.whl"
PYMUPDF_WHEEL_SHA256 = (
    "660d93cb6da5bbddf11d3982ae27745dd3a9902d9f24cdb69adab83962294b5a"
)
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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
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
) -> str:
    result = subprocess.run(
        argv,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "UV_OFFLINE": "1"},
    )
    if result.returncode != 0:
        raise PreparationFailure(
            "producer",
            "producer_command_failed",
            "The exact producer command did not complete.",
            "A verified local producer step failed.",
            "Inspect the task-owned producer environment.",
            11,
        )
    return result.stdout.strip()


def _verify_cached_pymupdf(uv: str) -> None:
    cache = Path(_run([uv, "cache", "dir"]))
    proof = (
        cache
        / "wheels-v6"
        / "pypi"
        / "pymupdf"
        / "1.27.2.3-cp310-abi3-macosx_11_0_arm64.http"
    )
    if not proof.is_file():
        raise PreparationFailure(
            "producer",
            "producer_dependency_unavailable",
            "The locked cached PDF dependency is unavailable.",
            "The exact cached wheel commitment is absent.",
            "Restore the approved shared package cache.",
            11,
        )
    data = proof.read_bytes()
    if (
        PYMUPDF_WHEEL.encode() not in data
        or PYMUPDF_WHEEL_SHA256.encode() not in data
    ):
        raise PreparationFailure(
            "producer",
            "producer_dependency_mismatch",
            "The cached PDF dependency does not match the frozen contract.",
            "The locked wheel filename or digest differs.",
            "Restore the approved locked wheel cache entry.",
            11,
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
            11,
        )


def _prepare_wheel(
    source_archive: Path, work_root: Path
) -> tuple[Path, str]:
    uv = shutil.which("uv")
    if uv is None:
        raise PreparationFailure(
            "producer",
            "producer_tool_unavailable",
            "The local package runner is unavailable.",
            "The required cached build tool is not on PATH.",
            "Restore the approved local build tool.",
            11,
        )
    _verify_cached_pymupdf(uv)
    if _sha256(source_archive) != SOURCE_ARCHIVE_SHA256:
        raise PreparationFailure(
            "producer",
            "producer_identity_mismatch",
            "The MKE source archive does not match the frozen contract.",
            "The exact source archive digest differs.",
            "Restore the exact task-owned MKE v0.1.5 source archive.",
            11,
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
            11,
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
            11,
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
            ]
        )
    )
    if versions != {"mke": "0.1.5", "pymupdf": "1.27.2.3", "mcp": "1.28.1"}:
        raise PreparationFailure(
            "producer",
            "producer_runtime_mismatch",
            "The isolated producer runtime does not match the frozen contract.",
            "One or more installed producer versions differ.",
            "Restore the approved cached producer dependencies.",
            11,
        )
    return venv / "bin/mke", _sha256(wheels[0])


def _corpus_failure() -> PreparationFailure:
    return PreparationFailure(
        "corpus",
        "corpus_identity_mismatch",
        "The project source manifest does not match Revision 3.",
        "A closed manifest, producer, proof, or source commitment differs.",
        "Restore the committed Revision 3 public package.",
        12,
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
        stable_sources = [
            {key: source[key] for key in stable_keys} for source in sources
        ]
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
            and manifest.get("schema_version")
            == "night-voyager.evidence-loop-source-manifest.v1"
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
                source["producer_native_proof_commitment"] == native_proof
                for source in sources
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


def _copy_exclusive(source: Path, destination: Path) -> dict[str, Any]:
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
        raise
    destination.chmod(0o400)
    if (
        destination.stat().st_size != source.stat().st_size
        or _sha256(destination) != _sha256(source)
    ):
        raise _corpus_failure()
    return {
        "basename": destination.name,
        "byte_length": destination.stat().st_size,
        "sha256": _sha256(destination),
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
            ),
        },
        {
            "logical_name": "dra_source_archive",
            **_copy_exclusive(
                dra_source_archive,
                input_root / DRA_SOURCE_ARCHIVE_BASENAME,
            ),
        },
        {
            "logical_name": "source_manifest",
            **_copy_exclusive(manifest_path, input_root / "source-manifest-v1.json"),
        },
        {
            "logical_name": "source_manifest_fragment",
            **_copy_exclusive(
                manifest_path.parent / "source-manifest-fragment-v1.json",
                input_root / "source-manifest-fragment-v1.json",
            ),
        },
    ]
    for source in sources:
        source_path = manifest_path.parent / source["relative_path"]
        files.append(
            {
                "logical_name": source["relative_path"],
                **_copy_exclusive(source_path, corpus / source_path.name),
            }
        )
    return {
        "schema_version": "night-voyager.evidence-loop-input-admission.v1",
        "root_mode": "0700",
        "corpus_root_mode": "0700",
        "files": files,
    }


def _prepare_run_root(run_root: Path) -> dict[str, Path]:
    if (
        not run_root.is_dir()
        or run_root.stat().st_mode & 0o777 != 0o700
        or any(run_root.iterdir())
    ):
        raise PreparationFailure(
            "arguments",
            "destination_exists",
            "The task-owned run root is not fresh and empty.",
            "A3 preparation is single-use and fail-closed.",
            "Create one fresh mode-0700 run root without child directories.",
            2,
        )
    roots = {
        name: run_root / name for name in ("input", "work", "store", "receipts")
    }
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
    if (
        mke_tag_object != TAG_OBJECT
        or mke_commit != PEELED_COMMIT
        or dra_tag_object != DRA_TAG_OBJECT
        or dra_commit != DRA_PEELED_COMMIT
        or not mke_source_archive.is_file()
        or _sha256(mke_source_archive) != SOURCE_ARCHIVE_SHA256
        or not dra_source_archive.is_file()
        or _sha256(dra_source_archive) != DRA_SOURCE_ARCHIVE_SHA256
    ):
        raise PreparationFailure(
            "producer",
            "producer_identity_mismatch",
            "The supplied producer inputs do not match the frozen A3 contract.",
            "An exact archive, tag object, commit, or digest differs.",
            "Supply the approved MKE v0.1.5 and DRA v0.1.8 inputs.",
            11,
        )


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

                async def call_tool(
                    tool: str, arguments: dict[str, Any]
                ) -> dict[str, Any]:
                    result = await session.call_tool(tool, arguments)
                    if result.isError or not isinstance(result.structuredContent, dict):
                        raise NativeStoreValidationError("native_tool_call_failed")
                    return result.structuredContent

                if ingest:
                    for source in sources:
                        relative = str(source["relative_path"])
                        result = await call_tool(
                            "ingest_file", {"path": Path(relative).name}
                        )
                        ingests.append({"relative_path": relative, **result})
                if sealed_write_probe:
                    write_response = await call_tool(
                        "ingest_file",
                        {"path": Path(str(sources[0]["relative_path"])).name},
                    )
                search = await collect_search_pages(call_tool, query=PROBE_QUERY)
                descriptors = [
                    dict(match["evidence"]) for match in search.matches
                ]
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
                fingerprint = str(
                    search.authority_snapshot["active_set_fingerprint"]
                )
                return mappings, fingerprint, write_response


def _remove_sqlite_runtime_files(database: Path) -> None:
    for suffix in ("-wal", "-shm"):
        candidate = database.with_name(database.name + suffix)
        candidate.unlink(missing_ok=True)


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
    run_root = Path(args.run_root).resolve()
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
    _remove_sqlite_runtime_files(database)
    store_seal = seal_store(store_root, database)
    verify_store_seal(store_root, store_seal)
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
    _remove_sqlite_runtime_files(database)
    after_seal = dict(verify_store_seal(store_root, store_seal))
    if write_response is None:
        raise NativeStoreValidationError("sealed_mutation_not_closed")
    sealed_write_rejection = validate_sealed_write_rejection(
        response=write_response,
        before_seal=store_seal,
        after_seal=after_seal,
        before_active_set_fingerprint=active_set_fingerprint,
        after_active_set_fingerprint=reopened_fingerprint,
    )
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
                "byte_length": (
                    input_root / DRA_SOURCE_ARCHIVE_BASENAME
                ).stat().st_size,
                "sha256": DRA_SOURCE_ARCHIVE_SHA256,
                "mode": "0400",
            },
        },
    }
    setup = build_setup_receipt(
        source_manifest_sha256=_sha256(input_root / "source-manifest-v1.json"),
        active_set_fingerprint=active_set_fingerprint,
        store_seal=store_seal,
        producer=producer,
        mappings=mappings,
        input_admission=input_admission,
        sealed_write_rejection=sealed_write_rejection,
    )
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


def main() -> int:
    args = _parser().parse_args()
    try:
        payload = _prepare(args)
    except PreparationFailure as error:
        print(json.dumps(error.payload, separators=(",", ":"), sort_keys=True))
        return error.exit_code
    except NativeStoreValidationError as error:
        payload = {
            "stage": "native",
            "code": str(error),
            "problem": "The native MKE store did not satisfy the frozen A3 contract.",
            "cause": "A bounded native identity or completeness check failed.",
            "recovery": "Inspect the exact tagged producer and committed public sources.",
        }
        print(json.dumps(payload, separators=(",", ":"), sort_keys=True))
        return 13
    except Exception:
        payload = {
            "stage": "internal",
            "code": "a3_preparation_failed",
            "problem": "A3 store preparation did not complete.",
            "cause": "An internal bounded operation failed.",
            "recovery": "Inspect task-owned runtime diagnostics without changing producer inputs.",
        }
        print(json.dumps(payload, separators=(",", ":"), sort_keys=True))
        return 14
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
