from __future__ import annotations

import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from night_voyager.dra.fixtures import load_live_closure_scenario
from night_voyager.dra.live_models import (
    DraArtifactIdentityV1,
    DraCaptureReceiptV1,
    DraFailureReceiptV1,
    DraLiveFailurePhase,
    DraLiveRunIntentV1,
    DraLiveScenarioV1,
    DraSelectedEvidenceV1,
)
from night_voyager.dra.models import DRA_FIXTURE_SHA256, DRA_LIVE_COMMIT

EXPECTED_FAILURE_PHASES = {
    "preflight_invalid",
    "producer_identity_invalid",
    "producer_unavailable",
    "run_acceptance_ambiguous",
    "run_poll_deadline_exhausted",
    "terminal_state_invalid",
    "artifact_contract_invalid",
    "evidence_ownership_invalid",
    "evidence_projection_invalid",
    "source_selection_invalid",
    "candidate_import_conflict",
    "candidate_authority_denied",
    "source_attestation_invalid",
    "promotion_conflict",
    "planning_task_conflict",
    "planning_execution_failed",
    "advisor_review_conflict",
    "family_decision_conflict",
    "outcome_projection_invalid",
    "cleanup_incomplete",
}


def test_failure_taxonomy_is_closed() -> None:
    assert {item.value for item in DraLiveFailurePhase} == EXPECTED_FAILURE_PHASES


def test_versioned_scenario_freezes_exact_producer_and_provider_safe_envelopes() -> None:
    scenario = load_live_closure_scenario()
    assert scenario.schema_version == "night-voyager.dra-live-closure-scenario.v1"
    assert scenario.scenario_id == "dra-v0-1-6-live-closure-v1"
    assert scenario.producer.release == "v0.1.6"
    assert scenario.producer.commit == DRA_LIVE_COMMIT
    assert scenario.producer.tag_object == "9e0b0b443c435cf636dfce932c3c77d91d0a43e4"
    assert scenario.producer.fixture_sha256 == DRA_FIXTURE_SHA256
    assert scenario.profile_id == "generic"
    assert scenario.max_attempts == 1
    assert scenario.status.profile_id == "generic"
    assert scenario.status.failure_cause is None
    assert scenario.status.run_id == scenario.result.run_id
    assert scenario.status.segment_id == scenario.evidence[0].segment_id
    assert scenario.status.run_id == scenario.evidence[0].run_id
    assert scenario.result.artifact.byte_length == 56
    assert scenario.expected_non_claims == (
        "provider_quality",
        "source_truth",
        "production_readiness",
        "admissions_outcome",
    )
    dumped = scenario.model_dump(mode="json")
    for forbidden in ("credential", "provider_payload", "prompt", "headers", "content"):
        assert forbidden not in dumped


def test_scenario_rejects_unknown_fields_and_malformed_sha256() -> None:
    payload = json.loads(
        DraLiveScenarioV1.model_validate(
            load_live_closure_scenario().model_dump(mode="json")
        ).model_dump_json()
    )
    with_unknown = deepcopy(payload)
    with_unknown["unexpected"] = True
    with pytest.raises(ValidationError):
        DraLiveScenarioV1.model_validate(with_unknown)

    bad_hash = deepcopy(payload)
    bad_hash["request_sha256"] = "A" * 64
    with pytest.raises(ValidationError):
        DraLiveScenarioV1.model_validate(bad_hash)

    bad_evidence = deepcopy(payload)
    bad_evidence["evidence"][0]["unexpected"] = "raw upstream field"
    with pytest.raises(ValidationError):
        DraLiveScenarioV1.model_validate(bad_evidence)


def test_intent_hash_is_canonical_and_frozen() -> None:
    scenario = load_live_closure_scenario()
    first = DraLiveRunIntentV1.from_scenario(
        scenario, attempt_id="attempt-0000000000000001"
    )
    reordered = DraLiveRunIntentV1.model_validate(
        dict(reversed(list(first.model_dump(exclude={"intent_sha256"}).items())))
    )
    assert first.intent_sha256 == reordered.intent_sha256


def test_selected_evidence_preserves_exact_raw_url() -> None:
    selected = DraSelectedEvidenceV1.model_validate(
        {
            "evidence_id": "evidence-1",
            "run_id": "run-1",
            "segment_id": "segment-1",
            "source_url": "https://example.com/%7Eprogram?b=2&a=1#exact",
            "source_identity": "https://example.com/%7Eprogram?b=2&a=1#exact",
            "retrieved_at": "2026-07-25T00:00:00Z",
            "citation_status": "cited",
            "verification_status": "unverified",
        }
    )
    assert selected.source_url == "https://example.com/%7Eprogram?b=2&a=1#exact"

    with pytest.raises(ValidationError, match="dra_source_identity_mismatch"):
        DraSelectedEvidenceV1.model_validate(
            selected.model_dump()
            | {"source_identity": "https://example.com/~program?b=2&a=1#exact"}
        )


def test_receipts_are_content_free_and_stage_names_are_unique() -> None:
    scenario = load_live_closure_scenario()
    intent = DraLiveRunIntentV1.from_scenario(
        scenario, attempt_id="attempt-0000000000000001"
    )
    artifact = DraArtifactIdentityV1.model_validate(
        scenario.result.artifact.model_dump(exclude={"content"})
    )
    receipt_payload = {
        "schema_version": "night-voyager.dra-live-capture-receipt.v1",
        "intent_sha256": intent.intent_sha256,
        "attempt_id": intent.attempt_id,
        "producer": scenario.producer,
        "run_id": scenario.status.run_id,
        "segment_id": scenario.status.segment_id,
        "artifact": artifact,
        "selected_evidence": None,
        "stage_states": [
            {"stage": "capture-live", "status": "completed"},
            {"stage": "capture-live", "status": "failed"},
        ],
        "provider_attempt_consumed": True,
    }
    with pytest.raises(ValidationError, match="dra_receipt_stage_duplicate"):
        DraCaptureReceiptV1.model_validate(receipt_payload)
    with pytest.raises(ValidationError):
        DraCaptureReceiptV1.model_validate(receipt_payload | {"content": "forbidden"})
    with pytest.raises(ValidationError):
        DraArtifactIdentityV1.model_validate(
            artifact.model_dump() | {"content": "forbidden"}
        )

    failure_payload = {
        "schema_version": "night-voyager.dra-live-failure-receipt.v1",
        "intent_sha256": intent.intent_sha256,
        "attempt_id": intent.attempt_id,
        "phase": "producer_unavailable",
        "public_code": "producer_unavailable",
        "retryability": "separate_authorization_required",
        "provider_attempt_consumed": False,
        "known_identity_hashes": [],
        "last_completed_stage": None,
        "permitted_next_action": "stop",
    }
    DraFailureReceiptV1.model_validate(failure_payload)
    with pytest.raises(ValidationError):
        DraFailureReceiptV1.model_validate(
            failure_payload | {"provider_payload": {"secret": "forbidden"}}
        )
