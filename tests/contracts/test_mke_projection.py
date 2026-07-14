from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid5

import pytest

from night_voyager.evidence.mke_contract import (
    AskLibraryResponseV1,
    AskLibrarySuccessV1,
    SearchLibraryResponseV1,
    SearchLibrarySuccessV1,
)
from night_voyager.evidence.mke_models import (
    CandidateEvidence,
    CandidateStoreNoMatch,
    EvidenceQuery,
    M4BManifestV1,
    MkeConsumerError,
)
from night_voyager.evidence.mke_projection import (
    M4B_EVIDENCE_NAMESPACE,
    project_ask_candidate,
    project_search_candidate,
    require_paired_candidate,
)
from night_voyager.evidence.ports import EvidenceConsumer
from night_voyager.planning.models import EvidenceAuthority, EvidenceRole

FIXTURE_ROOT = Path(__file__).parents[2] / "fixtures" / "m4b"
EXPECTED_NAMESPACE = UUID("bb82fb65-face-585c-90df-ec155d9580f3")


def load(relative_path: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / relative_path).read_text(encoding="utf-8"))


def manifest() -> M4BManifestV1:
    return M4BManifestV1.model_validate_json(
        (FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8")
    )


def query(**changes: object) -> EvidenceQuery:
    source_manifest = manifest()
    source = source_manifest.sources[0]
    payload: dict[str, object] = {
        "schema_version": 1,
        "organization_id": source_manifest.organization_id,
        "source_pack_id": source_manifest.source_pack_id,
        "source_pack_version": source_manifest.source_pack_version,
        "claim": source.claim,
        "evidence_role": source.evidence_role,
        "query": "synthetic australia program fit advisor evidence review",
        "allowed_locator_kinds": ("page",),
        "limit": 1,
    }
    payload.update(changes)
    return EvidenceQuery.model_validate(payload)


def search(relative_path: str = "responses/search-match.json") -> SearchLibrarySuccessV1:
    response = SearchLibraryResponseV1.model_validate(load(relative_path)).root
    assert isinstance(response, SearchLibrarySuccessV1)
    return response


def ask(relative_path: str = "responses/ask-match.json") -> AskLibrarySuccessV1:
    response = AskLibraryResponseV1.model_validate(load(relative_path)).root
    assert isinstance(response, AskLibrarySuccessV1)
    return response


def search_with(mutator: str, value: object) -> SearchLibrarySuccessV1:
    payload = load("responses/search-match.json")
    results = payload["results"]
    assert isinstance(results, list) and isinstance(results[0], dict)
    results[0][mutator] = value
    response = SearchLibraryResponseV1.model_validate(payload).root
    assert isinstance(response, SearchLibrarySuccessV1)
    return response


def ask_with(mutator: str, value: object) -> AskLibrarySuccessV1:
    payload = load("responses/ask-match.json")
    evidence = payload["evidence"]
    assert isinstance(evidence, list) and isinstance(evidence[0], dict)
    evidence[0][mutator] = value
    response = AskLibraryResponseV1.model_validate(payload).root
    assert isinstance(response, AskLibrarySuccessV1)
    return response


def test_search_projection_uses_night_voyager_identity_and_untrusted_authority() -> None:
    source_manifest = manifest()
    evidence_query = query()
    response = search()

    candidate = project_search_candidate(evidence_query, source_manifest, response)

    assert isinstance(candidate, CandidateEvidence)
    assert candidate.evidence_ref.authority is EvidenceAuthority.UNTRUSTED_CANDIDATE
    expected_identity = {
        "organization_id": str(evidence_query.organization_id),
        "source_pack_id": str(evidence_query.source_pack_id),
        "source_pack_version": evidence_query.source_pack_version,
        "source_entry_id": str(source_manifest.sources[0].entry_id),
        "source_sha256": source_manifest.sources[0].sha256,
        "claim": evidence_query.claim,
        "evidence_role": evidence_query.evidence_role.value,
        "locator": {"kind": "page", "start": 1, "end": 1},
        "selected_text_sha256": hashlib.sha256(
            response.results[0].text.encode("utf-8")
        ).hexdigest(),
    }
    expected_name = json.dumps(
        expected_identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    assert M4B_EVIDENCE_NAMESPACE == EXPECTED_NAMESPACE
    assert candidate.evidence_ref.evidence_id == uuid5(EXPECTED_NAMESPACE, expected_name)
    assert candidate.trace.publication_revision == 1


def test_ask_projection_pairs_only_an_identical_snapshot() -> None:
    evidence_query = query()
    source_manifest = manifest()
    candidate = project_search_candidate(evidence_query, source_manifest, search())
    asked = project_ask_candidate(evidence_query, source_manifest, ask())

    assert isinstance(candidate, CandidateEvidence)
    assert isinstance(asked, CandidateEvidence)
    assert require_paired_candidate(candidate, asked) == candidate


@pytest.mark.parametrize(
    "changes",
    [
        {"organization_id": UUID("99999999-9999-4999-8999-999999999999")},
        {"source_pack_id": UUID("99999999-9999-4999-8999-999999999999")},
        {"source_pack_version": 2},
        {"claim": "Different claim"},
        {"evidence_role": EvidenceRole.TUITION},
    ],
)
def test_projection_rejects_query_manifest_policy_mismatch(changes: dict[str, object]) -> None:
    with pytest.raises(MkeConsumerError) as captured:
        project_search_candidate(query(**changes), manifest(), search())

    assert captured.value.failure.code in {
        "mke_manifest_mapping_failed",
        "mke_evidence_role_mismatch",
    }


@pytest.mark.parametrize(
    ("fingerprint", "expected"),
    [
        (
            "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "mke_manifest_mapping_failed",
        ),
    ],
)
def test_projection_rejects_missing_fingerprint_mapping(
    fingerprint: str, expected: str
) -> None:
    with pytest.raises(MkeConsumerError) as captured:
        project_search_candidate(
            query(), manifest(), search_with("content_fingerprint", fingerprint)
        )
    assert captured.value.failure.code == expected


def test_projection_rejects_duplicate_evidence_and_ambiguous_manifest_mapping() -> None:
    payload = load("responses/search-match.json")
    results = cast(list[dict[str, Any]], payload["results"])
    observation = cast(dict[str, Any], payload["observation"])
    results.append(copy.deepcopy(results[0]))
    observation["active_evidence_count"] = 2
    duplicate_response = SearchLibraryResponseV1.model_validate(payload).root
    assert isinstance(duplicate_response, SearchLibrarySuccessV1)
    with pytest.raises(MkeConsumerError) as captured:
        project_search_candidate(query(), manifest(), duplicate_response)
    assert captured.value.failure.code == "mke_manifest_mapping_failed"

    source_manifest = manifest()
    duplicate_source = source_manifest.sources[0].model_copy(
        update={"entry_id": UUID("88888888-8888-4888-8888-888888888888")}
    )
    ambiguous = source_manifest.model_copy(
        update={"sources": (source_manifest.sources[0], duplicate_source)}
    )
    with pytest.raises(MkeConsumerError) as captured:
        project_search_candidate(query(), ambiguous, search())
    assert captured.value.failure.code == "mke_manifest_mapping_failed"


def test_projection_rejects_locator_kind_and_range_mismatch() -> None:
    timestamp = {"kind": "timestamp_ms", "start": 0, "end": 1000}
    with pytest.raises(MkeConsumerError) as captured:
        project_search_candidate(query(), manifest(), search_with("locator", timestamp))
    assert captured.value.failure.code == "mke_locator_mismatch"

    source_manifest = manifest()
    changed_source = source_manifest.sources[0].model_copy(
        update={
            "allowed_locators": (
                source_manifest.sources[0].allowed_locators[0].model_copy(
                    update={"start": 2, "end": 2}
                ),
            )
        }
    )
    changed_manifest = source_manifest.model_copy(update={"sources": (changed_source,)})
    with pytest.raises(MkeConsumerError) as captured:
        project_search_candidate(query(), changed_manifest, search())
    assert captured.value.failure.code == "mke_locator_mismatch"


def test_empty_and_no_active_fail_but_active_zero_is_typed_success() -> None:
    active_no_match = project_search_candidate(
        query(query="absent-token"), manifest(), search("responses/search-no-match.json")
    )
    assert isinstance(active_no_match, CandidateStoreNoMatch)
    assert active_no_match.projection_status == "active_store_no_match"
    assert "proof_pack_no_match" not in active_no_match.model_dump_json()

    for state, counts, expected in (
        ("empty", (0, 0, 0), "mke_store_empty"),
        ("no_active_publication", (1, 0, 0), "mke_no_active_publication"),
    ):
        payload = load("responses/search-no-match.json")
        observation = cast(dict[str, Any], payload["observation"])
        observation.update(
            {
                "state": state,
                "source_count": counts[0],
                "active_publication_count": counts[1],
                "active_evidence_count": counts[2],
            }
        )
        response = SearchLibraryResponseV1.model_validate(payload).root
        assert isinstance(response, SearchLibrarySuccessV1)
        with pytest.raises(MkeConsumerError) as captured:
            project_search_candidate(query(), manifest(), response)
        assert captured.value.failure.code == expected


def test_identity_ignores_opaque_mke_ids_but_changes_for_owned_inputs() -> None:
    baseline = project_search_candidate(query(), manifest(), search())
    changed_ids = project_search_candidate(
        query(),
        manifest(),
        search_with("evidence_id", "ev_eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"),
    )
    changed_text = project_search_candidate(
        query(), manifest(), search_with("text", "Changed selected text.")
    )
    assert isinstance(baseline, CandidateEvidence)
    assert isinstance(changed_ids, CandidateEvidence)
    assert isinstance(changed_text, CandidateEvidence)
    assert changed_ids.evidence_ref.evidence_id == baseline.evidence_ref.evidence_id
    assert changed_text.evidence_ref.evidence_id != baseline.evidence_ref.evidence_id


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "content_fingerprint",
            "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        ),
        ("publication_id", "pub_eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"),
        ("publication_revision", 2),
        ("run_id", "run_eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"),
        ("locator", {"kind": "page", "start": 2, "end": 2}),
        ("text", "Changed selected text."),
    ],
)
def test_pairing_rejects_search_ask_snapshot_mismatch(field: str, value: object) -> None:
    searched = project_search_candidate(query(), manifest(), search())
    try:
        asked = project_ask_candidate(query(), manifest(), ask_with(field, value))
    except MkeConsumerError:
        return
    assert isinstance(searched, CandidateEvidence)
    assert isinstance(asked, CandidateEvidence)
    with pytest.raises(MkeConsumerError) as captured:
        require_paired_candidate(searched, asked)
    assert captured.value.failure.code == "mke_snapshot_pair_mismatch"


def test_consumer_port_is_runtime_checkable_only_by_shape() -> None:
    assert hasattr(EvidenceConsumer, "initialize")
    assert hasattr(EvidenceConsumer, "search")
    assert hasattr(EvidenceConsumer, "ask")
    assert hasattr(EvidenceConsumer, "aclose")
