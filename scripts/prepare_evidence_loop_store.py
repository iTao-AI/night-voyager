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
from typing import Any

from night_voyager.evidence_loop.freeze import validate_public_commitments
from night_voyager.evidence_loop.native_store import (
    NativeStoreValidationError,
    build_setup_receipt,
    collect_read_chunks,
    collect_search_pages,
    seal_store,
    validate_native_vertical,
    verify_store_seal,
    write_canonical_json,
)

TAG = "v0.1.5"
TAG_OBJECT = "1ca0a0b348638369e8407270ca5f363b0e551a9e"
PEELED_COMMIT = "d258c10dc40bd9eccd67c858b56f4e4cf5fe4610"
TREE = "22756fdfa8ef131d3e28fc2a44acc3f2b6fa32f0"
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
    parser.add_argument("--mke-repository")
    parser.add_argument("--workspace-root")
    parser.add_argument("--receipt-root")
    parser.add_argument(
        "--source-root",
        default="tests/fixtures/evidence_loop",
        help="Revision 3 public package root.",
    )
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


def _verify_git_identity(repository: Path) -> None:
    values = (
        _run(["git", "-C", str(repository), "rev-parse", f"refs/tags/{TAG}"]),
        _run(["git", "-C", str(repository), "rev-parse", f"refs/tags/{TAG}^{{}}"]),
        _run(
            ["git", "-C", str(repository), "rev-parse", f"refs/tags/{TAG}^{{}}^{{tree}}"]
        ),
    )
    if values != (TAG_OBJECT, PEELED_COMMIT, TREE):
        raise PreparationFailure(
            "producer",
            "producer_identity_mismatch",
            "The MKE release identity does not match the frozen contract.",
            "The exact tag object, commit, or tree is unavailable.",
            "Restore the exact MKE v0.1.5 Git objects.",
            11,
        )


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


def _prepare_wheel(repository: Path, workspace: Path) -> tuple[Path, str, str]:
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
    archive = workspace / "mke-v0.1.5.tar"
    source = workspace / "source"
    dist = workspace / "dist"
    venv = workspace / "venv"
    source.mkdir(mode=0o700)
    dist.mkdir(mode=0o700)
    _run(
        [
            "git",
            "-C",
            str(repository),
            "archive",
            "--format=tar",
            "--prefix=mke-v0.1.5/",
            f"--output={archive}",
            f"refs/tags/{TAG}^{{}}",
        ]
    )
    with tarfile.open(archive) as package:
        package.extractall(source, filter="data")
    extracted = source / "mke-v0.1.5"
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
    return venv / "bin/mke", _sha256(archive), _sha256(wheels[0])


def _load_manifest(source_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    validate_public_commitments(source_root)
    manifest_path = source_root / "source-manifest-v1.json"
    fragment_path = source_root / "source-manifest-fragment-v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fragment = json.loads(fragment_path.read_text(encoding="utf-8"))
    if (
        manifest.get("author_revision") != 3
        or manifest.get("source_manifest_fragment", {}).get("sha256")
        != _sha256(fragment_path)
        or manifest.get("sources") != fragment.get("sources")
    ):
        # The project manifest intentionally narrows producer detail, so compare stable sources.
        stable = [
            {
                key: source[key]
                for key in (
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
            }
            for source in fragment["sources"]
        ]
        if manifest.get("sources") != stable:
            raise PreparationFailure(
                "corpus",
                "corpus_identity_mismatch",
                "The project source manifest does not match Revision 3.",
                "A stable source commitment differs.",
                "Restore the committed Revision 3 public package.",
                12,
            )
    for source in manifest["sources"]:
        path = source_root / source["relative_path"]
        if (
            path.stat().st_size != source["byte_length"]
            or _sha256(path) != source["content_sha256"]
            or path.stat().st_mode & 0o777 != 0o600
        ):
            raise PreparationFailure(
                "corpus",
                "corpus_identity_mismatch",
                "An admitted public source does not match its commitment.",
                "Source bytes, length, or mode differ.",
                "Restore the committed Revision 3 public package.",
                12,
            )
    return manifest, manifest["sources"]


async def _native_observation(
    executable: Path,
    database: Path,
    corpus: Path,
    sources: list[dict[str, Any]],
    *,
    ingest: bool,
) -> tuple[tuple[dict[str, Any], ...], str]:
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
                return mappings, fingerprint


def _remove_sqlite_runtime_files(database: Path) -> None:
    for suffix in ("-wal", "-shm"):
        candidate = database.with_name(database.name + suffix)
        candidate.unlink(missing_ok=True)


def _prepare(args: argparse.Namespace) -> dict[str, Any]:
    if not args.mke_repository or not args.workspace_root or not args.receipt_root:
        raise PreparationFailure(
            "arguments",
            "required_argument_missing",
            "Required A3 input is missing.",
            "Producer, workspace, and receipt roots are required.",
            "Provide all documented A3 root arguments.",
            2,
        )
    repository = Path(args.mke_repository).resolve()
    workspace = Path(args.workspace_root).resolve()
    receipt_root = Path(args.receipt_root).resolve()
    source_root = Path(args.source_root).resolve()
    if workspace.exists() or receipt_root.exists():
        raise PreparationFailure(
            "arguments",
            "destination_exists",
            "A task-owned destination already exists.",
            "A3 preparation is single-use and fail-closed.",
            "Choose fresh task-owned destinations.",
            2,
        )
    workspace.mkdir(mode=0o700, parents=True)
    receipt_root.mkdir(mode=0o700, parents=True)
    _verify_git_identity(repository)
    _, sources = _load_manifest(source_root)
    executable, archive_sha256, wheel_sha256 = _prepare_wheel(repository, workspace)
    store_root = workspace / "store"
    store_root.mkdir(mode=0o700)
    database = store_root / "store.sqlite"
    corpus = source_root / "mke-corpus"
    mappings, active_set_fingerprint = asyncio.run(
        _native_observation(executable, database, corpus, sources, ingest=True)
    )
    _remove_sqlite_runtime_files(database)
    store_seal = seal_store(store_root, database)
    verify_store_seal(store_root, store_seal)
    reopened, reopened_fingerprint = asyncio.run(
        _native_observation(executable, database, corpus, sources, ingest=False)
    )
    if reopened != mappings or reopened_fingerprint != active_set_fingerprint:
        raise NativeStoreValidationError("read_only_reopen_drift")
    _remove_sqlite_runtime_files(database)
    verify_store_seal(store_root, store_seal)
    producer = {
        "name": "multimodal-knowledge-engine",
        "version": "0.1.5",
        "tag": TAG,
        "tag_object": TAG_OBJECT,
        "peeled_commit": PEELED_COMMIT,
        "tree": TREE,
        "archive_sha256": archive_sha256,
        "wheel_sha256": wheel_sha256,
        "mcp_version": "1.28.1",
        "pymupdf_version": PYMUPDF_VERSION,
        "pymupdf_wheel_filename": PYMUPDF_WHEEL,
        "pymupdf_wheel_sha256": PYMUPDF_WHEEL_SHA256,
        "tool_inventory": list(TOOLS),
    }
    setup = build_setup_receipt(
        source_manifest_sha256=_sha256(
            source_root / "source-manifest-v1.json"
        ),
        active_set_fingerprint=active_set_fingerprint,
        store_seal=store_seal,
        producer=producer,
        mappings=mappings,
    )
    seal_path = receipt_root / "mke-store-seal-receipt-v1.json"
    setup_path = receipt_root / "mke-store-setup-receipt-v1.json"
    write_canonical_json(seal_path, store_seal)
    write_canonical_json(setup_path, setup)
    return {
        "schema_version": "night-voyager.evidence-loop-store-preparation-response.v1",
        "ok": True,
        "source_count": len(sources),
        "store_state": "sealed_read_only",
        "setup_receipt": {
            "basename": setup_path.name,
            "byte_length": setup_path.stat().st_size,
            "sha256": _sha256(setup_path),
        },
        "store_seal_receipt": {
            "basename": seal_path.name,
            "byte_length": seal_path.stat().st_size,
            "sha256": _sha256(seal_path),
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
            f"source_count={payload['source_count']} "
            f"store_state={payload['store_state']} "
            f"setup_receipt_sha256={payload['setup_receipt']['sha256']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
