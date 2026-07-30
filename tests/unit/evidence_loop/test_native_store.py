from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

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
        await native_store.collect_search_pages(
            FakeCaller(responses), query="public source probe"
        )


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
def test_vertical_rejects_missing_extra_duplicate_and_wrong_media(
    mutation: str, code: str
) -> None:
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
        native_store.validate_native_vertical(
            expected, ingests, descriptors, reads, _snapshot()
        )


def test_seal_is_byte_stable_read_only_and_detects_drift(tmp_path: Path) -> None:
    store = tmp_path / "store"
    store.mkdir(mode=0o700)
    database = store / "store.sqlite"
    database.write_bytes(b"sealed")
    receipt = native_store.seal_store(store, database)
    assert database.stat().st_mode & 0o777 == 0o400
    assert native_store.verify_store_seal(store, receipt) == receipt
    with pytest.raises(PermissionError):
        database.open("ab")
    database.chmod(0o600)
    database.write_bytes(b"drift")
    with pytest.raises(
        native_store.NativeStoreValidationError, match="store_artifact_drift"
    ):
        native_store.verify_store_seal(store, receipt)


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
    )
    encoded = str(receipt)
    for forbidden in ("/private/", "query", "cursor", "raw_evidence", "text"):
        assert forbidden not in encoded
