from __future__ import annotations

import base64
import hashlib
import json
import os
import py_compile
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from night_voyager.evidence_loop import native_store


class FakeCaller:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def __call__(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((tool, arguments))
        return self.responses.pop(0)


def _descriptor(seed: str, *, trace: str = "1") -> dict[str, Any]:
    return {
        "evidence_id": f"ev_{trace}",
        "source_id": f"src_{trace}",
        "publication_id": f"pub_{trace}",
        "run_id": f"run_{trace}",
        "publication_revision": 1,
        "content_fingerprint": f"sha256:{seed * 64}",
        "evidence_text_sha256": f"sha256:{seed.upper() * 64}",
        "original_utf8_bytes": 4,
        "locator": {"kind": "page", "start": 1, "end": 1},
    }


def _snapshot() -> dict[str, Any]:
    return {
        "active_set_fingerprint": f"sha256:{'f' * 64}",
        "observation": {
            "library_id": "local",
            "state": "active",
            "source_count": 4,
            "active_publication_count": 4,
            "active_evidence_count": 4,
        },
    }


def _search(
    status: str,
    matches: list[dict[str, Any]],
    *,
    cursor: str | None = None,
) -> dict[str, Any]:
    selection: dict[str, Any] = {"status": status, "returned": len(matches)}
    if cursor is not None:
        selection["next_cursor"] = cursor
    return {
        "ok": True,
        "authority_snapshot": _snapshot(),
        "matches": matches,
        "selection": selection,
    }


def _match(descriptor: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence": descriptor,
        "excerpt": {"content_trust": "untrusted_evidence"},
        "read": {"tool": "read_evidence_v1", "evidence_id": descriptor["evidence_id"]},
    }


@pytest.mark.asyncio
async def test_search_follows_every_cursor_and_requires_complete() -> None:
    caller = FakeCaller(
        [
            _search("more_available", [_match(_descriptor("a"))], cursor="next"),
            _search("complete", [_match(_descriptor("b", trace="2"))]),
        ]
    )
    result = await native_store.collect_search_pages(caller, query="public source probe")
    assert [item["evidence"]["evidence_id"] for item in result.matches] == ["ev_1", "ev_2"]
    assert caller.calls[1] == ("search_library_v2", {"request": {"cursor": "next"}})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("returned", "search_selection_invalid"),
        ("trust", "search_match_invalid"),
        ("read_tool", "search_match_invalid"),
        ("read_evidence_id", "search_match_invalid"),
    ],
)
async def test_search_rejects_native_match_contradictions(mutation: str, code: str) -> None:
    match = _match(_descriptor("a"))
    response = _search("complete", [match])
    if mutation == "returned":
        response["selection"]["returned"] = 2
    elif mutation == "trust":
        match["excerpt"]["content_trust"] = "trusted"
    elif mutation == "read_tool":
        match["read"]["tool"] = "search_library_v1"
    else:
        match["read"]["evidence_id"] = "ev_other"
    with pytest.raises(native_store.NativeStoreValidationError, match=code):
        await native_store.collect_search_pages(FakeCaller([response]), query="public source probe")


@pytest.mark.asyncio
async def test_search_rejects_intermediate_returned_mismatch() -> None:
    first = _search("more_available", [_match(_descriptor("a"))], cursor="next")
    first["selection"]["returned"] = 2
    with pytest.raises(native_store.NativeStoreValidationError, match="search_selection_invalid"):
        await native_store.collect_search_pages(FakeCaller([first]), query="public source probe")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("responses", "code"),
    [
        ([_search("capped", [])], "search_selection_incomplete"),
        (
            [
                _search("more_available", [], cursor="repeat"),
                _search("more_available", [], cursor="repeat"),
            ],
            "search_cursor_cycle",
        ),
        ([_search("more_available", [])], "search_cursor_invalid"),
    ],
)
async def test_search_rejects_incomplete_or_invalid_cursor_graph(
    responses: list[dict[str, Any]], code: str
) -> None:
    with pytest.raises(native_store.NativeStoreValidationError, match=code):
        await native_store.collect_search_pages(FakeCaller(responses), query="public source probe")


def _read(
    descriptor: dict[str, Any],
    text: str,
    offset: int,
    *,
    complete: bool,
    cursor: str | None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "authority_snapshot": _snapshot(),
        "evidence": descriptor,
        "content": {
            "text": text,
            "offset_bytes": offset,
            "returned_utf8_bytes": len(text.encode()),
            "content_trust": "untrusted_evidence",
        },
        "complete": complete,
        "next_cursor": cursor,
    }


@pytest.mark.asyncio
async def test_read_follows_every_cursor_and_verifies_terminal_bytes() -> None:
    descriptor = _descriptor("a")
    descriptor["evidence_text_sha256"] = f"sha256:{hashlib.sha256(b'abcd').hexdigest()}"
    caller = FakeCaller(
        [
            _read(descriptor, "ab", 0, complete=False, cursor="next"),
            _read(descriptor, "cd", 2, complete=True, cursor=None),
        ]
    )
    result = await native_store.collect_read_chunks(caller, descriptor)
    assert result.terminal_sha256 == hashlib.sha256(b"abcd").hexdigest()
    assert result.utf8_bytes == 4
    assert caller.calls[1] == ("read_evidence_v1", {"request": {"cursor": "next"}})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("responses", "code"),
    [
        ([_read(_descriptor("a"), "ab", 1, complete=True, cursor=None)], "read_offset_invalid"),
        (
            [
                _read(_descriptor("a"), "ab", 0, complete=False, cursor="same"),
                _read(_descriptor("a"), "cd", 2, complete=False, cursor="same"),
            ],
            "read_cursor_cycle",
        ),
        ([_read(_descriptor("a"), "ab", 0, complete=False, cursor=None)], "read_cursor_invalid"),
    ],
)
async def test_read_rejects_partial_invalid_or_cyclic_chunks(
    responses: list[dict[str, Any]], code: str
) -> None:
    with pytest.raises(native_store.NativeStoreValidationError, match=code):
        await native_store.collect_read_chunks(FakeCaller(responses), _descriptor("a"))


def _expected(seed: str, name: str) -> dict[str, Any]:
    return {
        "relative_path": f"mke-corpus/{name}.pdf",
        "dataset_source_id": f"dataset-{name}",
        "evaluation_canonical_source_id": seed * 64,
        "content_sha256": seed * 64,
        "expected_extracted_text_sha256": seed.upper() * 64,
        "expected_extracted_utf8_bytes": 4,
        "expected_publication_revision": 1,
        "expected_locator": {"kind": "page", "start": 1, "end": 1},
        "media_type": "application/pdf",
    }


def _ingest(name: str, trace: str) -> dict[str, Any]:
    return {
        "relative_path": f"mke-corpus/{name}.pdf",
        "ok": True,
        "run_id": f"run_{trace}",
        "run_state": "published",
        "media_type": "application/pdf",
        "evidence_count": 1,
    }


def test_vertical_maps_exactly_four_sources_in_manifest_order() -> None:
    expected = [_expected(seed, str(index)) for index, seed in enumerate("abcd", start=1)]
    descriptors = [_descriptor(seed, trace=str(index)) for index, seed in enumerate("abcd", 1)]
    ingests = [_ingest(str(index), str(index)) for index in range(1, 5)]
    reads = {
        descriptor["evidence_id"]: {
            "terminal_sha256": descriptor["evidence_text_sha256"].removeprefix("sha256:"),
            "utf8_bytes": 4,
        }
        for descriptor in descriptors
    }
    result = native_store.validate_native_vertical(
        expected, ingests, descriptors[::-1], reads, _snapshot()
    )
    assert [item["relative_path"] for item in result] == [
        "mke-corpus/1.pdf",
        "mke-corpus/2.pdf",
        "mke-corpus/3.pdf",
        "mke-corpus/4.pdf",
    ]
    assert result[0]["source_id"] == "src_1"


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("missing", "native_source_set_mismatch"),
        ("extra", "native_source_set_mismatch"),
        ("duplicate", "native_trace_identity_ambiguous"),
        ("wrong_media", "native_ingest_identity_mismatch"),
    ],
)
def test_vertical_rejects_missing_extra_duplicate_and_wrong_media(mutation: str, code: str) -> None:
    expected = [_expected(seed, str(index)) for index, seed in enumerate("abcd", start=1)]
    descriptors = [_descriptor(seed, trace=str(index)) for index, seed in enumerate("abcd", 1)]
    ingests = [_ingest(str(index), str(index)) for index in range(1, 5)]
    reads = {
        descriptor["evidence_id"]: {
            "terminal_sha256": descriptor["evidence_text_sha256"].removeprefix("sha256:"),
            "utf8_bytes": 4,
        }
        for descriptor in descriptors
    }
    if mutation == "missing":
        descriptors.pop()
    elif mutation == "extra":
        descriptors.append(_descriptor("e", trace="5"))
    elif mutation == "duplicate":
        descriptors[1]["source_id"] = descriptors[0]["source_id"]
    else:
        ingests[0]["media_type"] = "text/plain"
    with pytest.raises(native_store.NativeStoreValidationError, match=code):
        native_store.validate_native_vertical(expected, ingests, descriptors, reads, _snapshot())


def _write_wal_store(store: Path) -> Path:
    store.mkdir(mode=0o700)
    database = store / "store.sqlite"
    database.write_bytes(b"sealed")
    (store / "store.sqlite-shm").write_bytes(b"s" * 32_768)
    (store / "store.sqlite-wal").write_bytes(b"")
    return database


def test_seal_is_exact_three_file_read_only_wal_authority(tmp_path: Path) -> None:
    store = tmp_path / "store"
    database = _write_wal_store(store)
    try:
        receipt = native_store.seal_store(store, database)
        assert store.stat().st_mode & 0o777 == 0o500
        assert [item["basename"] for item in receipt["files"]] == [
            "store.sqlite",
            "store.sqlite-shm",
            "store.sqlite-wal",
        ]
        assert [item["mode"] for item in receipt["files"]] == ["0400"] * 3
        assert receipt["store_root_mode"] == "0500"
        assert native_store.verify_store_seal(store, receipt) == receipt
    finally:
        store.chmod(0o700)


@pytest.mark.parametrize(
    "mutation",
    ["missing", "extra", "tampered", "writable", "root_mode"],
)
def test_verify_store_seal_rejects_every_wal_authority_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    store = tmp_path / "store"
    database = _write_wal_store(store)
    receipt = native_store.seal_store(store, database)
    store.chmod(0o700)
    if mutation == "missing":
        (store / "store.sqlite-wal").unlink()
    elif mutation == "extra":
        (store / "extra").write_bytes(b"extra")
    elif mutation == "tampered":
        peer = store / "store.sqlite-shm"
        peer.chmod(0o600)
        peer.write_bytes(b"t" * 32_768)
        peer.chmod(0o400)
    elif mutation == "writable":
        (store / "store.sqlite-shm").chmod(0o600)
    else:
        pass
    if mutation != "root_mode":
        store.chmod(0o500)
    with pytest.raises(native_store.NativeStoreValidationError, match="store_artifact_drift"):
        native_store.verify_store_seal(store, receipt)
    store.chmod(0o700)


@pytest.mark.parametrize("invalid_kind", ["symlink", "hardlink"])
def test_seal_rejects_linked_wal_authority_peers(
    tmp_path: Path,
    invalid_kind: str,
) -> None:
    store = tmp_path / "store"
    database = _write_wal_store(store)
    peer = store / "store.sqlite-shm"
    peer.unlink()
    if invalid_kind == "symlink":
        peer.symlink_to(database.name)
    else:
        peer.hardlink_to(database)
    with pytest.raises(native_store.NativeStoreValidationError, match="store_artifact_invalid"):
        native_store.seal_store(store, database)


@pytest.mark.parametrize("invalid_kind", ["symlink", "hardlink"])
def test_verify_store_seal_rejects_post_seal_link_replacement(
    tmp_path: Path,
    invalid_kind: str,
) -> None:
    store = tmp_path / "store"
    database = _write_wal_store(store)
    receipt = native_store.seal_store(store, database)
    external = tmp_path / "replacement"
    external.write_bytes((store / "store.sqlite-shm").read_bytes())
    external.chmod(0o400)
    store.chmod(0o700)
    peer = store / "store.sqlite-shm"
    peer.unlink()
    if invalid_kind == "symlink":
        peer.symlink_to(external)
    else:
        peer.hardlink_to(external)
    store.chmod(0o500)

    with pytest.raises(native_store.NativeStoreValidationError, match="store_artifact_drift"):
        native_store.verify_store_seal(store, receipt)
    store.chmod(0o700)


def _record_hash(content: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=")
    return f"sha256={digest.decode()}"


def _write_synthetic_native_runtime(run_root: Path) -> None:
    venv = run_root / "work/venv"
    executable_root = venv / "bin"
    site_root = venv / "lib/python3.12/site-packages"
    package_root = site_root / "mke"
    dist_root = site_root / "multimodal_knowledge_engine-0.1.5.dist-info"
    executable_root.mkdir(parents=True, exist_ok=True)
    package_root.mkdir(parents=True, exist_ok=True)
    dist_root.mkdir(exist_ok=True)
    (venv / "pyvenv.cfg").write_text(
        "home = /synthetic/base/bin\n"
        "implementation = CPython\n"
        "uv = 0.11.7\n"
        "version_info = 3.12.13\n"
        "include-system-site-packages = false\n",
        encoding="utf-8",
    )
    probe = {
        "python_implementation": "CPython",
        "python_version": "3.12.13",
        "platform_system": "Darwin",
        "platform_machine": "arm64",
        "sqlite_version": "3.50.4",
        "sqlite_source_id": "mock-source-id",
        "sqlite_threadsafety": 3,
        "distribution_version": "0.1.5",
        "sys_prefix_is_venv": True,
        "venv_site_packages_relative": "lib/python3.12/site-packages",
        "active_site_packages_count": 1,
        "external_site_packages_count": 0,
        "external_site_packages_present": False,
        "base_site_packages_present": False,
        "only_frozen_venv_site": True,
    }
    python = executable_root / "python"
    python.write_text(
        "#!/bin/sh\n"
        + "printf '%s\\n' "
        + repr(json.dumps(probe, separators=(",", ":"), sort_keys=True))
        + "\n",
        encoding="utf-8",
    )
    python.chmod(0o755)
    files = {
        "../../../bin/mke": b"#!/bin/sh\nexit 0\n",
        "mke/__init__.py": b'__version__ = "0.1.5"\n',
        "multimodal_knowledge_engine-0.1.5.dist-info/METADATA": (
            b"Metadata-Version: 2.4\nName: multimodal-knowledge-engine\nVersion: 0.1.5\n"
        ),
        "multimodal_knowledge_engine-0.1.5.dist-info/entry_points.txt": (
            b"[console_scripts]\nmke = mke.cli:main\n"
        ),
    }
    for relative, content in files.items():
        path = site_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        path.chmod(0o755 if relative == "../../../bin/mke" else 0o644)
    record_lines = [
        f"{relative},{_record_hash(content)},{len(content)}"
        for relative, content in sorted(files.items())
    ]
    record_lines.append(
        "multimodal_knowledge_engine-0.1.5.dist-info/RECORD,,"
    )
    (dist_root / "RECORD").write_text("\n".join(record_lines) + "\n", encoding="utf-8")


def _write_synthetic_runtime_dependency(run_root: Path) -> None:
    site_root = run_root / "work/venv/lib/python3.12/site-packages"
    package_root = site_root / "mcp"
    dist_root = site_root / "mcp-1.28.1.dist-info"
    package_root.mkdir(parents=True, exist_ok=True)
    dist_root.mkdir(exist_ok=True)
    files = {
        "mcp/runtime.py": b"RUNTIME_VERSION = '1.28.1'\n",
        "mcp-1.28.1.dist-info/METADATA": (
            b"Metadata-Version: 2.4\nName: mcp\nVersion: 1.28.1\n"
        ),
    }
    for relative, content in files.items():
        path = site_root / relative
        path.write_bytes(content)
        path.chmod(0o644)
    record_lines = [
        f"{relative},{_record_hash(content)},{len(content)}"
        for relative, content in sorted(files.items())
    ]
    record_lines.append("mcp-1.28.1.dist-info/RECORD,,")
    (dist_root / "RECORD").write_text("\n".join(record_lines) + "\n", encoding="utf-8")


def test_native_runtime_identity_closes_executable_package_and_runtime_drift(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run"
    _write_synthetic_native_runtime(run_root)
    frozen = native_store.build_native_runtime_identity(
        run_root,
        wheel_sha256="4" * 64,
    )
    native_store.validate_native_runtime_identity(
        frozen,
        run_root=run_root,
        wheel_sha256="4" * 64,
    )

    python = run_root / "work/venv/bin/python"
    python.write_bytes(python.read_bytes() + b"\n")
    with pytest.raises(
        native_store.NativeStoreValidationError,
        match="native_runtime_identity_drift",
    ):
        native_store.validate_native_runtime_identity(
            frozen,
            run_root=run_root,
            wheel_sha256="4" * 64,
        )

    _write_synthetic_native_runtime(run_root)
    entrypoint = run_root / "work/venv/bin/mke"
    entrypoint.write_bytes(entrypoint.read_bytes() + b"# drift\n")
    with pytest.raises(
        native_store.NativeStoreValidationError,
        match="native_runtime_artifact_invalid",
    ):
        native_store.validate_native_runtime_identity(
            frozen,
            run_root=run_root,
            wheel_sha256="4" * 64,
        )

    _write_synthetic_native_runtime(run_root)
    package = run_root / "work/venv/lib/python3.12/site-packages/mke/__init__.py"
    package.write_bytes(package.read_bytes() + b"# drift\n")
    with pytest.raises(
        native_store.NativeStoreValidationError,
        match="native_runtime_artifact_invalid",
    ):
        native_store.validate_native_runtime_identity(
            frozen,
            run_root=run_root,
            wheel_sha256="4" * 64,
        )

    _write_synthetic_native_runtime(run_root)
    with pytest.raises(
        native_store.NativeStoreValidationError,
        match="native_runtime_identity_drift",
    ):
        native_store.validate_native_runtime_identity(
            frozen,
            run_root=run_root,
            wheel_sha256="5" * 64,
        )


def test_native_runtime_identity_rejects_pyvenv_system_site_drift(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run"
    _write_synthetic_native_runtime(run_root)
    frozen = native_store.build_native_runtime_identity(
        run_root,
        wheel_sha256="4" * 64,
    )
    cfg = run_root / "work/venv/pyvenv.cfg"
    cfg.write_text(
        cfg.read_text(encoding="utf-8").replace(
            "include-system-site-packages = false",
            "include-system-site-packages = true",
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        native_store.NativeStoreValidationError,
        match="native_runtime_identity_drift",
    ):
        native_store.validate_native_runtime_identity(
            frozen,
            run_root=run_root,
            wheel_sha256="4" * 64,
        )


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("missing", "native_runtime_artifact_invalid"),
        ("symlink", "native_runtime_artifact_invalid"),
        ("hardlink", "native_runtime_artifact_invalid"),
        ("malformed", "native_runtime_artifact_invalid"),
        ("unknown", "native_runtime_artifact_invalid"),
        ("include_true", "native_runtime_identity_drift"),
    ],
)
def test_native_runtime_identity_rejects_pyvenv_cfg_boundaries(
    tmp_path: Path,
    mutation: str,
    expected_code: str,
) -> None:
    run_root = tmp_path / "run"
    _write_synthetic_native_runtime(run_root)
    frozen = native_store.build_native_runtime_identity(
        run_root,
        wheel_sha256="4" * 64,
    )
    cfg = run_root / "work/venv/pyvenv.cfg"
    if mutation == "missing":
        cfg.unlink()
    elif mutation == "symlink":
        replacement = tmp_path / "pyvenv-replacement.cfg"
        replacement.write_bytes(cfg.read_bytes())
        cfg.unlink()
        cfg.symlink_to(replacement)
    elif mutation == "hardlink":
        replacement = tmp_path / "pyvenv-hardlink.cfg"
        replacement.write_bytes(cfg.read_bytes())
        cfg.unlink()
        cfg.hardlink_to(replacement)
    elif mutation == "malformed":
        cfg.write_text("not-a-key-value-line\n", encoding="utf-8")
    elif mutation == "unknown":
        cfg.write_text(cfg.read_text(encoding="utf-8") + "unknown = value\n", encoding="utf-8")
    else:
        cfg.write_text(
            cfg.read_text(encoding="utf-8").replace(
                "include-system-site-packages = false",
                "include-system-site-packages = true",
            ),
            encoding="utf-8",
        )

    with pytest.raises(
        native_store.NativeStoreValidationError,
        match=expected_code,
    ):
        native_store.validate_native_runtime_identity(
            frozen,
            run_root=run_root,
            wheel_sha256="4" * 64,
        )


@pytest.mark.parametrize("mutation", ["file", "record", "version"])
def test_native_runtime_identity_rejects_transitive_dependency_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    run_root = tmp_path / "run"
    _write_synthetic_native_runtime(run_root)
    _write_synthetic_runtime_dependency(run_root)
    frozen = native_store.build_native_runtime_identity(
        run_root,
        wheel_sha256="4" * 64,
    )
    assert frozen["runtime_distribution_count"] == 2
    distributions = cast(list[dict[str, Any]], frozen["runtime_distributions"])
    assert [item["distribution_name"] for item in distributions] == [
        "mcp",
        "multimodal-knowledge-engine",
    ]
    bootstrap = cast(dict[str, Any], frozen["runtime_bootstrap"])
    assert bootstrap["file_count"] == 0
    assert frozen["child_environment_policy"] == {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONSAFEPATH": "1",
    }
    pyvenv_identity = cast(dict[str, Any], frozen["pyvenv_cfg"])
    pyvenv_file = cast(dict[str, Any], pyvenv_identity["file"])
    assert pyvenv_file["path"] == "pyvenv.cfg"
    assert pyvenv_file["byte_length"] == (
        run_root / "work/venv/pyvenv.cfg"
    ).stat().st_size
    assert pyvenv_file["sha256"] == hashlib.sha256(
        (run_root / "work/venv/pyvenv.cfg").read_bytes()
    ).hexdigest()
    assert pyvenv_file["mode"] == "0644"
    assert pyvenv_identity["include_system_site_packages"] is False
    assert "/synthetic/base" not in json.dumps(frozen, sort_keys=True)
    assert frozen["site_packages"] == {
        "venv_relative": "lib/python3.12/site-packages",
        "active_count": 1,
        "external_present": False,
        "external_count": 0,
        "base_present": False,
        "only_frozen_venv_site": True,
    }

    site_root = run_root / "work/venv/lib/python3.12/site-packages"
    runtime_file = site_root / "mcp/runtime.py"
    metadata_file = site_root / "mcp-1.28.1.dist-info/METADATA"
    record_file = site_root / "mcp-1.28.1.dist-info/RECORD"
    if mutation == "file":
        runtime_file.write_bytes(runtime_file.read_bytes() + b"# drift\n")
    elif mutation == "record":
        record_file.write_text(
            record_file.read_text(encoding="utf-8").replace("sha256=", "sha256=" + "A"),
            encoding="utf-8",
        )
    else:
        metadata_file.write_bytes(
            metadata_file.read_bytes().replace(b"1.28.1", b"1.28.2")
        )

    with pytest.raises(
        native_store.NativeStoreValidationError,
        match="native_runtime_(identity_drift|artifact_invalid)",
    ):
        native_store.validate_native_runtime_identity(
            frozen,
            run_root=run_root,
            wheel_sha256="4" * 64,
        )


def test_native_runtime_identity_rejects_unrecorded_runtime_file(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    _write_synthetic_native_runtime(run_root)
    _write_synthetic_runtime_dependency(run_root)
    extra = run_root / "work/venv/lib/python3.12/site-packages/mcp/extra.py"
    extra.write_bytes(b"UNRECORDED = True\n")

    with pytest.raises(
        native_store.NativeStoreValidationError,
        match="native_runtime_artifact_invalid",
    ):
        native_store.build_native_runtime_identity(run_root, wheel_sha256="4" * 64)


def test_native_runtime_identity_rejects_auto_executed_sitecustomize_pyc(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run"
    _write_synthetic_native_runtime(run_root)
    _write_synthetic_runtime_dependency(run_root)
    frozen = native_store.build_native_runtime_identity(
        run_root,
        wheel_sha256="4" * 64,
    )
    site_root = run_root / "work/venv/lib/python3.12/site-packages"
    source = tmp_path / "sitecustomize.py"
    source.write_text(
        "import builtins\n"
        "builtins.PYC_AUTHORITY_MARKER = 'mutated-unbound-code'\n",
        encoding="utf-8",
    )
    pyc = site_root / "sitecustomize.pyc"
    py_compile.compile(str(source), cfile=str(pyc), doraise=True)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import builtins; print(getattr(builtins, 'PYC_AUTHORITY_MARKER', 'absent'))",
        ],
        env={"PATH": os.environ["PATH"], "PYTHONPATH": str(site_root)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "mutated-unbound-code"
    with pytest.raises(
        native_store.NativeStoreValidationError,
        match="native_runtime_artifact_invalid",
    ):
        native_store.validate_native_runtime_identity(
            frozen,
            run_root=run_root,
            wheel_sha256="4" * 64,
        )


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unhashed"])
def test_native_runtime_identity_rejects_dependency_inventory_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    run_root = tmp_path / "run"
    _write_synthetic_native_runtime(run_root)
    _write_synthetic_runtime_dependency(run_root)
    site_root = run_root / "work/venv/lib/python3.12/site-packages"
    dist_root = site_root / "mcp-1.28.1.dist-info"
    if mutation == "missing":
        shutil.rmtree(dist_root)
    elif mutation == "duplicate":
        shutil.copytree(dist_root, site_root / "mcp-1.28.2.dist-info")
    else:
        record = dist_root / "RECORD"
        record.write_text(
            record.read_text(encoding="utf-8").replace(
                "mcp/runtime.py,",
                "mcp/runtime.py,,",
            ),
            encoding="utf-8",
        )

    with pytest.raises(
        native_store.NativeStoreValidationError,
        match="native_runtime_artifact_invalid",
    ):
        native_store.build_native_runtime_identity(run_root, wheel_sha256="4" * 64)


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_native_runtime_identity_rejects_dependency_link_replacement(
    tmp_path: Path,
    link_kind: str,
) -> None:
    run_root = tmp_path / "run"
    _write_synthetic_native_runtime(run_root)
    _write_synthetic_runtime_dependency(run_root)
    site_root = run_root / "work/venv/lib/python3.12/site-packages"
    runtime_file = site_root / "mcp/runtime.py"
    replacement = tmp_path / "replacement.py"
    replacement.write_bytes(runtime_file.read_bytes())
    runtime_file.unlink()
    if link_kind == "symlink":
        runtime_file.symlink_to(replacement)
    else:
        runtime_file.hardlink_to(replacement)

    with pytest.raises(
        native_store.NativeStoreValidationError,
        match="native_runtime_artifact_invalid",
    ):
        native_store.build_native_runtime_identity(run_root, wheel_sha256="4" * 64)


def test_native_mcp_environment_does_not_forward_python_import_redirectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTHONPATH", "/untrusted/import/root")
    environment = native_store.native_mcp_environment()
    assert "PYTHONPATH" not in environment
    assert environment["PYTHONDONTWRITEBYTECODE"] == "1"
    assert environment["PYTHONNOUSERSITE"] == "1"
    assert environment["PYTHONSAFEPATH"] == "1"
    assert set(environment) <= {
        "HOME",
        "LOGNAME",
        "PATH",
        "SHELL",
        "TERM",
        "USER",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONNOUSERSITE",
        "PYTHONSAFEPATH",
    }


def test_tagged_mcp_default_stdio_environment_excludes_pythonpath() -> None:
    pytest.importorskip("mcp")
    from importlib import metadata

    from mcp.client.stdio import get_default_environment

    assert metadata.version("mcp") == "1.28.1"
    assert "PYTHONPATH" not in get_default_environment()


def test_setup_receipt_excludes_paths_queries_cursors_and_raw_evidence() -> None:
    receipt = native_store.build_setup_receipt(
        source_manifest_sha256="a" * 64,
        active_set_fingerprint=f"sha256:{'b' * 64}",
        store_seal={"tree_sha256": "c" * 64, "files": []},
        producer={
            "tag_object": "d" * 40,
            "peeled_commit": "e" * 40,
            "tree": "f" * 40,
            "wheel_sha256": "1" * 64,
            "pymupdf_wheel_sha256": "2" * 64,
        },
        mappings=(
            {
                "relative_path": "mke-corpus/source.pdf",
                "evaluation_canonical_source_id": "3" * 64,
                "source_id": "src_trace",
                "publication_id": "pub_trace",
                "run_id": "run_trace",
                "evidence_id": "ev_trace",
            },
        ),
        sqlite_authority_image={
            "authority_image": "sqlite_read_only_wal_atomic_snapshot",
            "materialization_phase": "task_owned_preparation_mutation",
            "ordered_basenames": [
                "store.sqlite",
                "store.sqlite-shm",
                "store.sqlite-wal",
            ],
            "wal_byte_length": 0,
            "shm_byte_length": 32_768,
        },
        fresh_process_verification_runs=3,
        native_runtime_identity={
            "schema_version": "night-voyager.evidence-loop-native-runtime.v1"
        },
    )
    assert receipt["sqlite_authority_image"]["materialization_phase"] == (
        "task_owned_preparation_mutation"
    )
    assert receipt["fresh_process_verification_runs"] == 3
    assert receipt["sealed_evaluation_window_started"] is False
    encoded = str(receipt)
    for forbidden in ("/private/", "query", "cursor", "raw_evidence", "text"):
        assert forbidden not in encoded


def test_sealed_write_rejection_binds_unchanged_store_and_authority() -> None:
    seal: dict[str, Any] = {"tree_sha256": "a" * 64, "files": []}
    response = {
        "ok": False,
        "problem": "internal_error",
        "cause": "operation failed; details were redacted",
        "active_publication_impact": "unchanged",
        "next_step": "check_server_logs",
    }
    result = native_store.validate_sealed_write_rejection(
        response=response,
        before_seal=seal,
        after_seal=seal,
        before_active_set_fingerprint=f"sha256:{'b' * 64}",
        after_active_set_fingerprint=f"sha256:{'b' * 64}",
    )
    assert result == {
        "attempted_tool": "ingest_file",
        "rejected": True,
        "problem": "internal_error",
        "active_publication_impact": "unchanged",
        "store_tree_unchanged": True,
        "active_set_unchanged": True,
    }


@pytest.mark.parametrize(
    "mutation",
    ["accepted", "store", "authority"],
)
def test_sealed_write_rejection_fails_closed_on_any_mutation(mutation: str) -> None:
    response = {
        "ok": False,
        "problem": "internal_error",
        "active_publication_impact": "unchanged",
    }
    before: dict[str, Any] = {"tree_sha256": "a" * 64, "files": []}
    after: dict[str, Any] = dict(before)
    before_fingerprint = f"sha256:{'b' * 64}"
    after_fingerprint = before_fingerprint
    if mutation == "accepted":
        response["ok"] = True
    elif mutation == "store":
        after["tree_sha256"] = "c" * 64
    else:
        after_fingerprint = f"sha256:{'d' * 64}"
    with pytest.raises(native_store.NativeStoreValidationError, match="sealed_mutation_not_closed"):
        native_store.validate_sealed_write_rejection(
            response=response,
            before_seal=before,
            after_seal=after,
            before_active_set_fingerprint=before_fingerprint,
            after_active_set_fingerprint=after_fingerprint,
        )
