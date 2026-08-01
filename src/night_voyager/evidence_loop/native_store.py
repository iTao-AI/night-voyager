"""Fail-closed A3 native MKE store preparation and seal contracts."""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import os
import stat
import subprocess
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Never, cast

ToolCaller = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]
STORE_AUTHORITY_BASENAMES = (
    "store.sqlite",
    "store.sqlite-shm",
    "store.sqlite-wal",
)


class NativeStoreValidationError(ValueError):
    """Closed validation failure that exposes only a stable public code."""


@dataclass(frozen=True)
class SearchCollection:
    matches: tuple[dict[str, Any], ...]
    authority_snapshot: dict[str, Any]


@dataclass(frozen=True)
class ReadCollection:
    descriptor: dict[str, Any]
    terminal_sha256: str
    utf8_bytes: int
    authority_snapshot: dict[str, Any]


def _fail(code: str) -> Never:
    raise NativeStoreValidationError(code)


def _object(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(code)
    return cast(dict[str, Any], value)


async def collect_search_pages(
    call_tool: ToolCaller,
    *,
    query: str,
    limit: int = 20,
    max_pages: int = 4,
) -> SearchCollection:
    request: dict[str, Any] = {"query": query, "limit": limit}
    seen_cursors: set[str] = set()
    matches: list[dict[str, Any]] = []
    snapshot: dict[str, Any] | None = None
    for _ in range(max_pages):
        body = _object(
            await call_tool("search_library_v2", {"request": request}),
            "search_response_invalid",
        )
        if body.get("ok") is not True:
            _fail("search_unavailable")
        page_snapshot = _object(body.get("authority_snapshot"), "search_authority_invalid")
        if snapshot is None:
            snapshot = page_snapshot
        elif page_snapshot != snapshot:
            _fail("search_authority_drift")
        page_matches_raw = body.get("matches")
        if not isinstance(page_matches_raw, list):
            _fail("search_response_invalid")
        page_matches = cast(list[object], page_matches_raw)
        selection = _object(body.get("selection"), "search_selection_invalid")
        if selection.get("returned") != len(page_matches):
            _fail("search_selection_invalid")
        for match in page_matches:
            typed_match = _object(match, "search_match_invalid")
            evidence = _object(typed_match.get("evidence"), "search_match_invalid")
            excerpt = _object(typed_match.get("excerpt"), "search_match_invalid")
            read = _object(typed_match.get("read"), "search_match_invalid")
            if (
                excerpt.get("content_trust") != "untrusted_evidence"
                or read.get("tool") != "read_evidence_v1"
                or read.get("evidence_id") != evidence.get("evidence_id")
            ):
                _fail("search_match_invalid")
            matches.append(typed_match)
        status = selection.get("status")
        if status == "complete":
            return SearchCollection(tuple(matches), snapshot)
        if status != "more_available":
            _fail("search_selection_incomplete")
        cursor = selection.get("next_cursor")
        if not isinstance(cursor, str) or not cursor:
            _fail("search_cursor_invalid")
        if cursor in seen_cursors:
            _fail("search_cursor_cycle")
        seen_cursors.add(cursor)
        request = {"cursor": cursor}
    _fail("search_page_limit")


async def collect_read_chunks(
    call_tool: ToolCaller,
    descriptor: Mapping[str, Any],
    *,
    max_reads: int = 32,
) -> ReadCollection:
    evidence_id = descriptor.get("evidence_id")
    if not isinstance(evidence_id, str) or not evidence_id:
        _fail("read_descriptor_invalid")
    request: dict[str, Any] = {"evidence_id": evidence_id, "max_bytes": 16384}
    seen_cursors: set[str] = set()
    content = bytearray()
    snapshot: dict[str, Any] | None = None
    canonical_descriptor = dict(descriptor)
    for _ in range(max_reads):
        body = _object(
            await call_tool("read_evidence_v1", {"request": request}),
            "read_response_invalid",
        )
        if body.get("ok") is not True:
            _fail("read_unavailable")
        page_descriptor = _object(body.get("evidence"), "read_descriptor_invalid")
        if page_descriptor != canonical_descriptor:
            _fail("read_descriptor_drift")
        page_snapshot = _object(body.get("authority_snapshot"), "read_authority_invalid")
        if snapshot is None:
            snapshot = page_snapshot
        elif page_snapshot != snapshot:
            _fail("read_authority_drift")
        chunk = _object(body.get("content"), "read_content_invalid")
        text = chunk.get("text")
        encoded = text.encode("utf-8") if isinstance(text, str) else None
        if encoded is None:
            _fail("read_offset_invalid")
        if (
            chunk.get("content_trust") != "untrusted_evidence"
            or chunk.get("offset_bytes") != len(content)
            or chunk.get("returned_utf8_bytes") != len(encoded)
        ):
            _fail("read_offset_invalid")
        content.extend(encoded)
        complete = body.get("complete")
        cursor = body.get("next_cursor")
        if complete is True:
            if cursor is not None:
                _fail("read_cursor_invalid")
            digest = hashlib.sha256(content).hexdigest()
            expected_digest = descriptor.get("evidence_text_sha256")
            if digest != str(expected_digest).removeprefix("sha256:"):
                _fail("read_terminal_digest_mismatch")
            if len(content) != descriptor.get("original_utf8_bytes"):
                _fail("read_terminal_length_mismatch")
            return ReadCollection(canonical_descriptor, digest, len(content), snapshot)
        if complete is not False or not isinstance(cursor, str) or not cursor:
            _fail("read_cursor_invalid")
        if cursor in seen_cursors:
            _fail("read_cursor_cycle")
        seen_cursors.add(cursor)
        request = {"cursor": cursor}
    _fail("read_limit")


def validate_native_descriptors(
    expected_sources: Sequence[Mapping[str, Any]],
    descriptors: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    if len(expected_sources) != len(descriptors):
        _fail("native descriptor count mismatch")
    validated: list[Mapping[str, Any]] = []
    for expected, descriptor in zip(expected_sources, descriptors, strict=True):
        required = {
            "publication_revision": expected["expected_publication_revision"],
            "content_fingerprint": f"sha256:{expected['content_sha256']}",
            "evidence_text_sha256": (f"sha256:{expected['expected_extracted_text_sha256']}"),
            "original_utf8_bytes": expected["expected_extracted_utf8_bytes"],
            "locator": expected["expected_locator"],
        }
        if any(descriptor.get(key) != value for key, value in required.items()):
            _fail("native descriptor identity mismatch")
        for trace_key in ("source_id", "publication_id"):
            if not isinstance(descriptor.get(trace_key), str) or not descriptor[trace_key]:
                _fail("native descriptor trace identity missing")
        validated.append(descriptor)
    return tuple(validated)


def validate_native_vertical(
    expected_sources: Sequence[Mapping[str, Any]],
    ingest_receipts: Sequence[Mapping[str, Any]],
    descriptors: Sequence[Mapping[str, Any]],
    reads: Mapping[str, Mapping[str, Any]],
    authority_snapshot: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    if len(expected_sources) != 4 or len(descriptors) != 4 or len(ingest_receipts) != 4:
        _fail("native_source_set_mismatch")
    observation = _object(authority_snapshot.get("observation"), "native_authority_invalid")
    if (
        observation.get("library_id") != "local"
        or observation.get("state") != "active"
        or observation.get("source_count") != 4
        or observation.get("active_publication_count") != 4
        or observation.get("active_evidence_count") != 4
    ):
        _fail("native_authority_invalid")
    descriptor_by_digest: dict[str, Mapping[str, Any]] = {}
    trace_sets: dict[str, set[str]] = {
        key: set() for key in ("source_id", "publication_id", "run_id", "evidence_id")
    }
    for descriptor in descriptors:
        fingerprint = descriptor.get("content_fingerprint")
        if not isinstance(fingerprint, str) or fingerprint in descriptor_by_digest:
            _fail("native_source_set_mismatch")
        descriptor_by_digest[fingerprint] = descriptor
        for key, values in trace_sets.items():
            value = descriptor.get(key)
            if not isinstance(value, str) or not value or value in values:
                _fail("native_trace_identity_ambiguous")
            values.add(value)
    ingest_by_path = {str(item.get("relative_path")): item for item in ingest_receipts}
    if len(ingest_by_path) != 4:
        _fail("native_ingest_identity_mismatch")

    mappings: list[dict[str, Any]] = []
    seen_expected: set[str] = set()
    for expected in expected_sources:
        digest = str(expected.get("content_sha256"))
        fingerprint = f"sha256:{digest}"
        if digest in seen_expected or fingerprint not in descriptor_by_digest:
            _fail("native_source_set_mismatch")
        seen_expected.add(digest)
        descriptor = descriptor_by_digest[fingerprint]
        validate_native_descriptors((expected,), (descriptor,))
        path = str(expected.get("relative_path"))
        ingest = ingest_by_path.get(path)
        if (
            ingest is None
            or ingest.get("ok") is not True
            or ingest.get("run_state") != "published"
            or ingest.get("media_type") != "application/pdf"
            or ingest.get("evidence_count") != 1
            or ingest.get("run_id") != descriptor.get("run_id")
        ):
            _fail("native_ingest_identity_mismatch")
        evidence_id = str(descriptor["evidence_id"])
        read = reads.get(evidence_id)
        if (
            read is None
            or read.get("terminal_sha256") != str(expected["expected_extracted_text_sha256"])
            or read.get("utf8_bytes") != expected["expected_extracted_utf8_bytes"]
        ):
            _fail("native_read_identity_mismatch")
        mappings.append(
            {
                "relative_path": path,
                "dataset_source_id": expected["dataset_source_id"],
                "evaluation_canonical_source_id": expected["evaluation_canonical_source_id"],
                "content_sha256": digest,
                "source_id": descriptor["source_id"],
                "publication_id": descriptor["publication_id"],
                "run_id": descriptor["run_id"],
                "evidence_id": evidence_id,
                "publication_revision": descriptor["publication_revision"],
                "evidence_text_sha256": str(descriptor["evidence_text_sha256"]).removeprefix(
                    "sha256:"
                ),
                "original_utf8_bytes": descriptor["original_utf8_bytes"],
                "locator": descriptor["locator"],
                "media_type": "application/pdf",
                "publication_state": "published",
                "content_trust": "untrusted_evidence",
                "selection_status": "complete",
            }
        )
    if len(descriptor_by_digest) != len(seen_expected):
        _fail("native_source_set_mismatch")
    return tuple(mappings)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()


def seal_store(store_root: Path, database: Path) -> dict[str, Any]:
    paths = tuple(store_root / basename for basename in STORE_AUTHORITY_BASENAMES)
    if (
        database != paths[0]
        or database.parent != store_root
        or stat.S_IMODE(store_root.stat().st_mode) != 0o700
        or tuple(path.name for path in sorted(store_root.iterdir())) != STORE_AUTHORITY_BASENAMES
    ):
        _fail("store_artifact_invalid")
    for path in paths:
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            _fail("store_artifact_invalid")
    if paths[1].stat().st_size != 32_768 or paths[2].stat().st_size != 0:
        _fail("store_artifact_invalid")
    for path in paths:
        path.chmod(0o400)
    files = [
        {
            "basename": path.name,
            "byte_length": path.stat().st_size,
            "sha256": _sha256(path),
            "mode": "0400",
        }
        for path in paths
    ]
    tree_sha256 = hashlib.sha256(_canonical_bytes({"files": files})).hexdigest()
    store_root.chmod(0o500)
    return {
        "schema_version": "night-voyager.evidence-loop-store-seal.v1",
        "tree_sha256": tree_sha256,
        "files": files,
        "store_root_mode": "0500",
        "lifecycle_state": "sealed_read_only",
    }


def verify_store_seal(store_root: Path, receipt: Mapping[str, Any]) -> Mapping[str, Any]:
    if (
        receipt.get("schema_version") != "night-voyager.evidence-loop-store-seal.v1"
        or receipt.get("lifecycle_state") != "sealed_read_only"
        or receipt.get("store_root_mode") != "0500"
        or stat.S_IMODE(store_root.stat().st_mode) != 0o500
    ):
        _fail("store_artifact_drift")
    files_raw = receipt.get("files")
    if not isinstance(files_raw, list):
        _fail("store_artifact_drift")
    files = cast(list[object], files_raw)
    if len(files) != len(STORE_AUTHORITY_BASENAMES):
        _fail("store_artifact_drift")
    if tuple(path.name for path in sorted(store_root.iterdir())) != STORE_AUTHORITY_BASENAMES:
        _fail("store_artifact_drift")
    for expected_basename, item in zip(STORE_AUTHORITY_BASENAMES, files, strict=True):
        entry = _object(item, "store_artifact_drift")
        path = store_root / expected_basename
        metadata = path.lstat()
        if (
            entry.get("basename") != expected_basename
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_size != entry.get("byte_length")
            or _sha256(path) != entry.get("sha256")
            or stat.S_IMODE(metadata.st_mode) != 0o400
            or entry.get("mode") != "0400"
        ):
            _fail("store_artifact_drift")
    expected_tree = hashlib.sha256(_canonical_bytes({"files": files})).hexdigest()
    if receipt.get("tree_sha256") != expected_tree:
        _fail("store_artifact_drift")
    return receipt


def _runtime_file_identity(path: Path, *, label: str) -> dict[str, object]:
    try:
        metadata = path.lstat()
    except OSError:
        _fail("native_runtime_artifact_invalid")
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        _fail("native_runtime_artifact_invalid")
    return {
        "path": label,
        "byte_length": metadata.st_size,
        "sha256": _sha256(path),
        "mode": f"{stat.S_IMODE(metadata.st_mode):04o}",
    }


def _record_sha256(value: str) -> str:
    try:
        algorithm, encoded = value.split("=", 1)
        padding = "=" * (-len(encoded) % 4)
        digest = base64.urlsafe_b64decode(encoded + padding).hex()
    except (ValueError, TypeError):
        _fail("native_runtime_artifact_invalid")
    if algorithm != "sha256" or len(digest) != 64:
        _fail("native_runtime_artifact_invalid")
    return digest


def _probe_native_python(python: Path) -> dict[str, object]:
    program = (
        "import importlib.metadata,json,platform,sqlite3;"
        "connection=sqlite3.connect(':memory:');"
        "print(json.dumps({"
        "'python_implementation':platform.python_implementation(),"
        "'python_version':platform.python_version(),"
        "'platform_system':platform.system(),"
        "'platform_machine':platform.machine(),"
        "'sqlite_version':sqlite3.sqlite_version,"
        "'sqlite_source_id':connection.execute('select sqlite_source_id()').fetchone()[0],"
        "'sqlite_threadsafety':sqlite3.threadsafety,"
        "'distribution_version':importlib.metadata.version('multimodal-knowledge-engine')"
        "},separators=(',',':'),sort_keys=True))"
    )
    try:
        result = subprocess.run(
            [str(python), "-c", program],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        value = json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        _fail("native_runtime_probe_invalid")
    if result.returncode != 0 or result.stderr or not isinstance(value, dict):
        _fail("native_runtime_probe_invalid")
    probe = cast(dict[str, object], value)
    expected_keys = {
        "python_implementation",
        "python_version",
        "platform_system",
        "platform_machine",
        "sqlite_version",
        "sqlite_source_id",
        "sqlite_threadsafety",
        "distribution_version",
    }
    if set(probe) != expected_keys or any(
        not isinstance(probe[key], str)
        for key in expected_keys - {"sqlite_threadsafety"}
    ):
        _fail("native_runtime_probe_invalid")
    if not isinstance(probe["sqlite_threadsafety"], int):
        _fail("native_runtime_probe_invalid")
    return probe


def build_native_runtime_identity(
    run_root: Path,
    *,
    wheel_sha256: str,
) -> dict[str, object]:
    """Bind the retained tagged MKE runtime without hashing unrelated venv files."""

    if len(wheel_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in wheel_sha256
    ):
        _fail("native_runtime_identity_drift")
    venv = run_root / "work/venv"
    python = venv / "bin/python"
    entrypoint = venv / "bin/mke"
    try:
        launcher_metadata = python.lstat()
        resolved_python = python.resolve(strict=True)
        resolved_metadata = resolved_python.lstat()
    except OSError:
        _fail("native_runtime_artifact_invalid")
    if (
        not (stat.S_ISREG(launcher_metadata.st_mode) or stat.S_ISLNK(launcher_metadata.st_mode))
        or not stat.S_ISREG(resolved_metadata.st_mode)
        or launcher_metadata.st_nlink != 1
        or resolved_metadata.st_nlink != 1
    ):
        _fail("native_runtime_artifact_invalid")

    site_roots = sorted((venv / "lib").glob("python*/site-packages"))
    distribution_roots = [
        path
        for site_root in site_roots
        for path in site_root.glob("multimodal_knowledge_engine-*.dist-info")
        if path.is_dir() and not path.is_symlink()
    ]
    if len(distribution_roots) != 1:
        _fail("native_runtime_artifact_invalid")
    distribution_root = distribution_roots[0]
    site_root = distribution_root.parent
    record = distribution_root / "RECORD"
    record_identity = _runtime_file_identity(record, label="distribution/RECORD")
    try:
        rows = list(csv.reader(record.read_text(encoding="utf-8").splitlines()))
    except (OSError, UnicodeDecodeError, csv.Error):
        _fail("native_runtime_artifact_invalid")

    distribution_prefix = f"{distribution_root.name}/"
    selected: list[dict[str, object]] = []
    saw_entrypoint = False
    saw_package = False
    saw_metadata = False
    for row in rows:
        if len(row) != 3:
            _fail("native_runtime_artifact_invalid")
        relative, record_digest, record_length = row
        posix = PurePosixPath(relative)
        is_entrypoint = relative == "../../../bin/mke"
        is_package = relative.startswith("mke/") and not (
            relative.endswith(".pyc") or "__pycache__" in posix.parts
        )
        is_distribution = relative.startswith(distribution_prefix) and posix.name != "RECORD"
        if not (is_entrypoint or is_package or is_distribution):
            continue
        if not record_digest or not record_length:
            _fail("native_runtime_artifact_invalid")
        if is_entrypoint:
            path = entrypoint
            label = "entrypoint/mke"
            saw_entrypoint = True
        else:
            if posix.is_absolute() or ".." in posix.parts:
                _fail("native_runtime_artifact_invalid")
            path = site_root.joinpath(*posix.parts)
            label = relative
            saw_package = saw_package or is_package
            saw_metadata = saw_metadata or posix.name == "METADATA"
        identity = _runtime_file_identity(path, label=label)
        try:
            expected_length = int(record_length)
        except ValueError:
            _fail("native_runtime_artifact_invalid")
        if (
            identity["byte_length"] != expected_length
            or identity["sha256"] != _record_sha256(record_digest)
        ):
            _fail("native_runtime_artifact_invalid")
        selected.append(identity)
    selected_labels = [cast(str, item["path"]) for item in selected]
    if (
        not (saw_entrypoint and saw_package and saw_metadata)
        or not selected
        or len(selected_labels) != len(set(selected_labels))
    ):
        _fail("native_runtime_artifact_invalid")
    selected.sort(key=lambda item: cast(str, item["path"]))
    entrypoint_identity = next(
        item for item in selected if item["path"] == "entrypoint/mke"
    )
    probe = _probe_native_python(python)
    if probe["distribution_version"] != "0.1.5":
        _fail("native_runtime_identity_drift")
    python_identity = {
        "launcher_kind": (
            "symlink" if stat.S_ISLNK(launcher_metadata.st_mode) else "regular"
        ),
        "resolved_basename": resolved_python.name,
        "resolved_byte_length": resolved_metadata.st_size,
        "resolved_sha256": _sha256(resolved_python),
        "resolved_mode": f"{stat.S_IMODE(resolved_metadata.st_mode):04o}",
    }
    files_tree_sha256 = hashlib.sha256(
        _canonical_bytes({"files": selected})
    ).hexdigest()
    return {
        "schema_version": "night-voyager.evidence-loop-native-runtime.v1",
        "python": {
            **python_identity,
            "implementation": probe["python_implementation"],
            "version": probe["python_version"],
            "platform_system": probe["platform_system"],
            "platform_machine": probe["platform_machine"],
        },
        "sqlite": {
            "version": probe["sqlite_version"],
            "source_id": probe["sqlite_source_id"],
            "threadsafety": probe["sqlite_threadsafety"],
        },
        "mke": {
            "distribution_name": "multimodal-knowledge-engine",
            "distribution_version": probe["distribution_version"],
            "wheel_sha256": wheel_sha256,
            "entrypoint": {
                key: entrypoint_identity[key]
                for key in ("byte_length", "sha256", "mode")
            },
            "record": {
                key: record_identity[key]
                for key in ("byte_length", "sha256", "mode")
            },
            "record_driven_file_count": len(selected),
            "record_driven_files_tree_sha256": files_tree_sha256,
        },
    }


def validate_native_runtime_identity(
    frozen: Mapping[str, object],
    *,
    run_root: Path,
    wheel_sha256: str,
) -> None:
    try:
        current = build_native_runtime_identity(
            run_root,
            wheel_sha256=wheel_sha256,
        )
    except NativeStoreValidationError:
        raise
    if dict(frozen) != current:
        _fail("native_runtime_identity_drift")


def build_setup_receipt(
    *,
    source_manifest_sha256: str,
    active_set_fingerprint: str,
    store_seal: Mapping[str, Any],
    producer: Mapping[str, Any],
    mappings: Sequence[Mapping[str, Any]],
    sqlite_authority_image: Mapping[str, Any],
    fresh_process_verification_runs: int,
    native_runtime_identity: Mapping[str, Any],
    input_admission: Mapping[str, Any] | None = None,
    sealed_write_rejection: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    receipt = {
        "schema_version": "night-voyager.evidence-loop-store-setup-receipt.v1",
        "preparation_scope": "task_owned_mutation_before_sealed_evaluation_window",
        "sealed_evaluation_window_started": False,
        "source_manifest_sha256": source_manifest_sha256,
        "active_set_fingerprint": active_set_fingerprint,
        "producer": dict(producer),
        "source_mappings": [dict(item) for item in mappings],
        "store_seal": dict(store_seal),
        "sqlite_authority_image": dict(sqlite_authority_image),
        "fresh_process_verification_runs": fresh_process_verification_runs,
        "native_runtime_identity": dict(native_runtime_identity),
        "mutation_capability": "closed_after_preparation",
        "read_only_reopen_verified": True,
    }
    if input_admission is not None:
        receipt["input_admission"] = dict(input_admission)
    if sealed_write_rejection is not None:
        receipt["sealed_write_rejection"] = dict(sealed_write_rejection)
    return receipt


def validate_sealed_write_rejection(
    *,
    response: Mapping[str, Any],
    before_seal: Mapping[str, Any],
    after_seal: Mapping[str, Any],
    before_active_set_fingerprint: str,
    after_active_set_fingerprint: str,
) -> dict[str, Any]:
    problem = response.get("problem")
    if (
        response.get("ok") is not False
        or not isinstance(problem, str)
        or response.get("active_publication_impact") != "unchanged"
        or before_seal != after_seal
        or before_active_set_fingerprint != after_active_set_fingerprint
    ):
        _fail("sealed_mutation_not_closed")
    return {
        "attempted_tool": "ingest_file",
        "rejected": True,
        "problem": problem,
        "active_publication_impact": "unchanged",
        "store_tree_unchanged": True,
        "active_set_unchanged": True,
    }


def write_canonical_json(path: Path, value: Mapping[str, Any], *, mode: int = 0o600) -> None:
    if path.exists():
        _fail("receipt_destination_exists")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(_canonical_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
