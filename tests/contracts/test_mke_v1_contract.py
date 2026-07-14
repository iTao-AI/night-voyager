from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from night_voyager.evidence.mke_contract import (
    AskLibraryResponseV1,
    AskLibrarySuccessV1,
    ListLibrariesResponseV1,
    SearchLibraryResponseV1,
    SearchLibrarySuccessV1,
)
from night_voyager.evidence.mke_models import EvidenceQuery, M4BManifestV1

FIXTURE_ROOT = Path(__file__).parents[2] / "fixtures" / "m4b"


def load_fixture(relative_path: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / relative_path).read_text(encoding="utf-8"))


def validate_manifest(payload: dict[str, Any] | None = None) -> M4BManifestV1:
    value = payload if payload is not None else load_fixture("manifest.json")
    return M4BManifestV1.model_validate_json(json.dumps(value))


def test_golden_responses_and_manifest_are_strictly_valid() -> None:
    listed = ListLibrariesResponseV1.model_validate(load_fixture("responses/list-active.json"))
    searched = SearchLibraryResponseV1.model_validate(
        load_fixture("responses/search-match.json")
    )
    asked = AskLibraryResponseV1.model_validate(load_fixture("responses/ask-match.json"))
    manifest = validate_manifest()

    assert listed.root.ok is True
    assert isinstance(searched.root, SearchLibrarySuccessV1)
    assert isinstance(asked.root, AskLibrarySuccessV1)
    assert searched.root.results[0].locator.kind == "page"
    assert asked.root.answer_status == "evidence_found"
    assert manifest.sources[0].media_type == "application/pdf"


def test_golden_no_match_responses_are_valid() -> None:
    search = SearchLibraryResponseV1.model_validate(
        load_fixture("responses/search-no-match.json")
    )
    ask = AskLibraryResponseV1.model_validate(load_fixture("responses/ask-no-match.json"))

    assert isinstance(search.root, SearchLibrarySuccessV1)
    assert isinstance(ask.root, AskLibrarySuccessV1)
    assert search.root.results == []
    assert ask.root.answer_status == "insufficient_evidence"
    assert ask.root.evidence == []


def invalid_response_payloads() -> list[tuple[str, dict[str, Any]]]:
    cases: list[tuple[str, dict[str, Any]]] = []
    for field, value in (("unknown", True), ("ok", "true")):
        payload = load_fixture("responses/list-active.json")
        payload[field] = value
        cases.append(("list", payload))
    payload = load_fixture("responses/list-active.json")
    del payload["observation"]
    cases.append(("list", payload))

    search_mutations: tuple[tuple[str, Any], ...] = (
        ("evidence_id", "source_0123456789abcdef0123456789abcdef"),
        ("content_fingerprint", "sha256:ABC"),
        ("publication_revision", 0),
        ("locator", {"kind": "page", "start": 1, "end": 2}),
        ("locator", {"kind": "timestamp_ms", "start": 10, "end": 10}),
    )
    for field, value in search_mutations:
        payload = load_fixture("responses/search-match.json")
        result = payload["results"]
        assert isinstance(result, list) and isinstance(result[0], dict)
        result[0][field] = value
        cases.append(("search", payload))
    payload = load_fixture("responses/search-match.json")
    observation = payload["observation"]
    assert isinstance(observation, dict)
    observation["active_evidence_count"] = 0
    cases.append(("search", payload))

    payload = load_fixture("responses/list-active.json")
    observation = payload["observation"]
    assert isinstance(observation, dict)
    observation["state"] = "empty"
    observation["source_count"] = 1
    cases.append(("list", payload))

    payload = load_fixture("responses/ask-match.json")
    payload["answer_status"] = "insufficient_evidence"
    cases.append(("ask", payload))
    payload = load_fixture("responses/ask-match.json")
    evidence = payload["evidence"]
    assert isinstance(evidence, list) and isinstance(evidence[0], dict)
    evidence[0]["text"] = "x" * 1_000_001
    cases.append(("ask", payload))
    return cases


@pytest.mark.parametrize(("response_kind", "payload"), invalid_response_payloads())
def test_response_contract_rejects_invalid_payloads(
    response_kind: str, payload: dict[str, Any]
) -> None:

    with pytest.raises(ValidationError):
        if response_kind == "ask":
            AskLibraryResponseV1.model_validate(payload)
        elif response_kind == "search":
            SearchLibraryResponseV1.model_validate(payload)
        else:
            ListLibrariesResponseV1.model_validate(payload)


def test_public_error_union_accepts_only_its_exact_shape() -> None:
    error = {
        "schema_version": "mke.search_library_response.v1",
        "ok": False,
        "problem": "query_invalid",
        "cause": "query must not be empty",
        "active_publication_impact": "unchanged",
        "next_step": "provide_query",
    }
    assert SearchLibraryResponseV1.model_validate(error).root.ok is False

    with pytest.raises(ValidationError):
        SearchLibraryResponseV1.model_validate({**error, "debug": "/private/path"})


@pytest.mark.parametrize(
    ("response_model", "schema_version"),
    [
        (ListLibrariesResponseV1, "mke.list_libraries_response.v1"),
        (SearchLibraryResponseV1, "mke.search_library_response.v1"),
        (AskLibraryResponseV1, "mke.ask_library_response.v1"),
    ],
)
@pytest.mark.parametrize(
    "cause",
    [
        "Traceback: synthetic failure",
        "root/private/config.env",
        "token=synthetic-secret",
    ],
)
def test_public_error_unions_reject_non_approved_sensitive_causes(
    response_model: type[
        ListLibrariesResponseV1 | SearchLibraryResponseV1 | AskLibraryResponseV1
    ],
    schema_version: str,
    cause: str,
) -> None:
    with pytest.raises(ValidationError):
        response_model.model_validate(
            {
                "schema_version": schema_version,
                "ok": False,
                "problem": "operation_failed",
                "cause": cause,
                "active_publication_impact": "unchanged",
                "next_step": "retry_operation",
            }
        )


@pytest.mark.parametrize(
    ("response_model", "schema_version", "cause"),
    [
        (
            ListLibrariesResponseV1,
            "mke.list_libraries_response.v1",
            "operation failed; details were redacted",
        ),
        (
            SearchLibraryResponseV1,
            "mke.search_library_response.v1",
            "query must not be empty",
        ),
        (
            AskLibraryResponseV1,
            "mke.ask_library_response.v1",
            "question must not be empty",
        ),
    ],
)
def test_public_error_unions_accept_selected_producer_public_causes(
    response_model: type[
        ListLibrariesResponseV1 | SearchLibraryResponseV1 | AskLibraryResponseV1
    ],
    schema_version: str,
    cause: str,
) -> None:
    parsed = response_model.model_validate(
        {
            "schema_version": schema_version,
            "ok": False,
            "problem": "operation_failed",
            "cause": cause,
            "active_publication_impact": "unchanged",
            "next_step": "retry_operation",
        }
    )
    assert parsed.root.ok is False
    assert parsed.root.cause == cause


def test_manifest_rejects_duplicate_identity_fingerprint_and_locator_kind() -> None:
    payload = load_fixture("manifest.json")
    duplicate = copy.deepcopy(payload["sources"][0])
    payload["sources"].append(duplicate)
    with pytest.raises(ValidationError):
        validate_manifest(payload)

    payload = load_fixture("manifest.json")
    duplicate = copy.deepcopy(payload["sources"][0])
    duplicate["entry_id"] = "88888888-8888-4888-8888-888888888888"
    payload["sources"].append(duplicate)
    with pytest.raises(ValidationError):
        validate_manifest(payload)

    payload = load_fixture("manifest.json")
    payload["sources"][0]["allowed_locators"].append(
        {"kind": "page", "start": 2, "end": 2}
    )
    with pytest.raises(ValidationError):
        validate_manifest(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("path", "../private.pdf"),
        ("path", "/tmp/private.pdf"),
        ("sha256", "not-a-sha"),
        ("media_type", "video/mp4"),
    ],
)
def test_manifest_rejects_invalid_source_fields(field: str, value: str) -> None:
    payload = load_fixture("manifest.json")
    payload["sources"][0][field] = value

    with pytest.raises(ValidationError):
        validate_manifest(payload)


def test_query_is_strict_and_bound_to_manifest_identity() -> None:
    manifest = validate_manifest()
    source = manifest.sources[0]
    query = {
        "schema_version": 1,
        "organization_id": manifest.organization_id,
        "source_pack_id": manifest.source_pack_id,
        "source_pack_version": manifest.source_pack_version,
        "claim": source.claim,
        "evidence_role": source.evidence_role,
        "query": "synthetic australia program fit advisor evidence review",
        "allowed_locator_kinds": ("page",),
        "limit": 1,
    }
    assert EvidenceQuery.model_validate(query).limit == 1

    for invalid in (
        {**query, "limit": 2},
        {**query, "allowed_locator_kinds": ("page", "page")},
        {**query, "organization_id": manifest.source_pack_id},
        {**query, "claim": "A different claim"},
    ):
        with pytest.raises(ValidationError):
            EvidenceQuery.model_validate_for_manifest(invalid, manifest)

    assert EvidenceQuery.model_validate_for_manifest(query, manifest).claim == source.claim
