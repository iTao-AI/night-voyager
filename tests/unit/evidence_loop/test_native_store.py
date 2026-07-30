from __future__ import annotations

from night_voyager.evidence_loop.native_store import validate_native_descriptors


def test_native_descriptor_binds_every_required_field() -> None:
    expected = {
        "content_sha256": "a" * 64,
        "expected_extracted_text_sha256": "b" * 64,
        "expected_extracted_utf8_bytes": 4,
        "expected_publication_revision": 1,
        "expected_locator": {"kind": "page", "start": 1, "end": 1},
    }
    descriptor = {
        "source_id": "src_trace",
        "publication_id": "pub_trace",
        "publication_revision": 1,
        "content_fingerprint": f"sha256:{'a' * 64}",
        "evidence_text_sha256": f"sha256:{'b' * 64}",
        "original_utf8_bytes": 4,
        "locator": {"kind": "page", "start": 1, "end": 1},
        "content_trust": "untrusted_evidence",
        "selection_status": "complete",
    }
    validated = validate_native_descriptors((expected,), (descriptor,))
    assert validated[0]["source_id"] == "src_trace"
