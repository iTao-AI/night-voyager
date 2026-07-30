from __future__ import annotations

import pytest
from pydantic import ValidationError

from night_voyager.evidence_loop.mke_v2 import (
    MkeSearchErrorV2,
    MkeSearchInitialV2,
    MkeSearchResponseV2,
    MkeSearchSuccessV2,
)


def search_payload(status: str = "complete") -> dict[str, object]:
    selection: dict[str, object] = {
        "schema_version": "mke.search_selection.v2",
        "status": status,
        "returned": 0,
    }
    if status == "more_available":
        selection["next_cursor"] = "cursor"
    if status == "capped":
        selection["limit_reason"] = "retrieval_strategy_cap"
    return {
        "schema_version": "mke.search_library_response.v2",
        "ok": True,
        "authority_snapshot": {
            "schema_version": "mke.active_authority_snapshot.v1",
            "observation": {
                "schema_version": "mke.active_publication_observation.v1",
                "library_id": "local",
                "state": "active",
                "source_count": 1,
                "active_publication_count": 1,
                "active_evidence_count": 1,
            },
            "active_set_fingerprint": f"sha256:{'a' * 64}",
        },
        "query": "synthetic program requirement",
        "matches": [],
        "selection": selection,
        "output": {
            "schema_version": "mke.search_output_budget.v1",
            "incomplete_excerpt_count": 0,
            "content_budget_bytes": 16384,
            "envelope_budget_bytes": 32768,
        },
    }


def test_mcp_query_cap_is_512_utf8_bytes_not_domain_cap() -> None:
    MkeSearchInitialV2(query="界" * 170, limit=20)
    with pytest.raises(ValidationError):
        MkeSearchInitialV2(query="界" * 171, limit=20)


def test_closed_schema_rejects_unknown_field_and_oversized_limit() -> None:
    with pytest.raises(ValidationError):
        MkeSearchInitialV2.model_validate({"query": "x", "limit": 21})
    with pytest.raises(ValidationError):
        MkeSearchInitialV2.model_validate({"query": "x", "limit": 20, "tool": "other"})


@pytest.mark.parametrize(
    ("status", "exhaustive"),
    (("complete", True), ("more_available", False), ("capped", False)),
)
def test_selection_state_never_treats_capped_as_complete(
    status: str, exhaustive: bool
) -> None:
    result = MkeSearchSuccessV2.model_validate(search_payload(status))
    assert result.is_exhaustive is exhaustive


def test_canonical_success_body_cap_is_32768_bytes() -> None:
    payload = search_payload()
    payload["matches"] = [
        {
            "evidence": {
                "evidence_id": "evidence-1",
                "source_id": "source-1",
                "content_fingerprint": f"sha256:{'b' * 64}",
                "publication_id": "publication-1",
                "publication_revision": 1,
                "run_id": "run-1",
                "locator": {"kind": "page", "start": 1, "end": 1},
                "evidence_text_sha256": f"sha256:{'c' * 64}",
                "original_utf8_bytes": 40_000,
            },
            "excerpt": {
                "kind": "prefix_fallback",
                "text": "x" * 33_000,
                "start_utf8_byte": 0,
                "end_utf8_byte": 33_000,
                "prefix_omitted": False,
                "suffix_omitted": True,
                "complete": False,
                "returned_utf8_bytes": 2048,
                "content_trust": "untrusted_evidence",
            },
            "read": {"tool": "read_evidence_v1", "evidence_id": "evidence-1"},
        }
    ]
    with pytest.raises(ValidationError, match="canonical success body"):
        MkeSearchSuccessV2.model_validate(payload)


@pytest.mark.parametrize("problem", ("invalid_cursor", "cursor_expired"))
def test_cursor_failures_remain_explicit_terminal_errors(problem: str) -> None:
    response = MkeSearchResponseV2.model_validate(
        {
            "schema_version": "mke.search_library_response.v2",
            "ok": False,
            "problem": problem,
            "cause": "cursor is not eligible",
            "active_publication_impact": "unchanged",
            "next_step": "repeat_initial_call",
        }
    )
    assert isinstance(response.root, MkeSearchErrorV2)
    assert response.root.problem == problem


def test_unknown_terminal_state_is_rejected() -> None:
    payload = search_payload()
    selection = payload["selection"]
    assert isinstance(selection, dict)
    selection["status"] = "partial"
    with pytest.raises(ValidationError):
        MkeSearchSuccessV2.model_validate(payload)
