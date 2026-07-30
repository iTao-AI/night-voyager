from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def validate_native_descriptors(
    expected_sources: Sequence[Mapping[str, Any]],
    descriptors: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    if len(expected_sources) != len(descriptors):
        raise ValueError("native descriptor count mismatch")
    validated: list[Mapping[str, Any]] = []
    for expected, descriptor in zip(expected_sources, descriptors, strict=True):
        required = {
            "publication_revision": expected["expected_publication_revision"],
            "content_fingerprint": f"sha256:{expected['content_sha256']}",
            "evidence_text_sha256": (
                f"sha256:{expected['expected_extracted_text_sha256']}"
            ),
            "original_utf8_bytes": expected["expected_extracted_utf8_bytes"],
            "locator": expected["expected_locator"],
            "content_trust": "untrusted_evidence",
            "selection_status": "complete",
        }
        if any(descriptor.get(key) != value for key, value in required.items()):
            raise ValueError("native descriptor identity mismatch")
        for trace_key in ("source_id", "publication_id"):
            if not isinstance(descriptor.get(trace_key), str) or not descriptor[trace_key]:
                raise ValueError("native descriptor trace identity missing")
        validated.append(descriptor)
    return tuple(validated)
