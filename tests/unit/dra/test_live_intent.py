from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from copy import deepcopy
from uuid import UUID

import pytest
from pydantic import ValidationError

from night_voyager.dra.fixtures import load_live_closure_scenario
from night_voyager.dra.live_models import (
    DRA_LIVE_CITATION_CLAUSE_MARKER_V2,
    DRA_LIVE_CITATION_CLAUSE_V2,
    DraCaptureInputV2,
    DraCaptureIntentV2,
    DraFrozenRequestV2,
    DraReceiptIdentityV1,
    DraReconciliationRequiredReceiptV1,
    compose_effective_query_v2,
    derive_stage_key,
    validate_effective_query_v2,
)

ORGANIZATION_ID = UUID("11111111-1111-4111-8111-111111111111")
CASE_ID = UUID("22222222-2222-4222-8222-222222222222")
ACTOR_HASH = "a" * 64
TENANT_HASH = "b" * 64
REQUEST_HASH = "c" * 64
RECEIPT_HASH = "d" * 64
BASE_QUERY = b"Compare one bounded synthetic source."


def frozen_request() -> DraFrozenRequestV2:
    _, request = compose_effective_query_v2(
        BASE_QUERY,
        logical_name="query.txt",
    )
    return request


def capture_input() -> DraCaptureInputV2:
    scenario = load_live_closure_scenario()
    return DraCaptureInputV2(
        scenario_id=scenario.scenario_id,
        producer=scenario.producer,
        organization_id=ORGANIZATION_ID,
        case_id=CASE_ID,
        expected_case_revision=1,
        advisor_actor_identity_sha256=ACTOR_HASH,
        tenant_identity_sha256=TENANT_HASH,
        request=frozen_request(),
        candidate_readiness_sha256=REQUEST_HASH,
        receipt_root_id="dra-live-capture-root",
        one_attempt_authorized=True,
    )


def attempt_ids() -> Iterator[str]:
    yield "attempt-0000000000000001"
    raise AssertionError("attempt id generated more than once")


def test_capture_intent_is_frozen_once_and_byte_stable() -> None:
    identifiers = attempt_ids()
    intent = DraCaptureIntentV2.freeze(
        capture_input(), attempt_id_factory=lambda: next(identifiers)
    )
    reordered = DraCaptureIntentV2.model_validate(
        dict(
            reversed(
                list(
                    intent.model_dump(
                        mode="json", exclude={"intent_sha256"}
                    ).items()
                )
            )
        )
    )
    assert intent.attempt_id == "attempt-0000000000000001"
    assert intent.intent_sha256 == reordered.intent_sha256
    assert intent.canonical_bytes() == reordered.canonical_bytes()
    assert b"selected_url" not in intent.canonical_bytes()
    assert b"session" not in intent.canonical_bytes()
    restored = DraCaptureIntentV2.model_validate_json(intent.canonical_bytes())
    assert restored.canonical_bytes() == intent.canonical_bytes()


def test_effective_query_is_code_owned_exact_and_byte_stable() -> None:
    effective, identity = compose_effective_query_v2(
        BASE_QUERY,
        logical_name="query.txt",
    )
    assert effective == BASE_QUERY + b"\n\n" + DRA_LIVE_CITATION_CLAUSE_V2
    assert identity.base_byte_length == len(BASE_QUERY)
    assert identity.base_sha256 == hashlib.sha256(BASE_QUERY).hexdigest()
    assert identity.effective_byte_length == len(effective)
    assert identity.effective_sha256 == hashlib.sha256(effective).hexdigest()
    assert identity.citation_clause_sha256 == hashlib.sha256(
        DRA_LIVE_CITATION_CLAUSE_V2
    ).hexdigest()


@pytest.mark.parametrize(
    "base_query",
    (
        b"",
        b"   ",
        b"line one\nline two",
        b"line one\rline two",
        DRA_LIVE_CITATION_CLAUSE_MARKER_V2,
        b"prefix " + DRA_LIVE_CITATION_CLAUSE_MARKER_V2 + b" replacement",
        b"x" * 1_048_576,
    ),
)
def test_effective_query_rejects_empty_line_break_marker_and_oversize(
    base_query: bytes,
) -> None:
    with pytest.raises(ValueError, match="dra_effective_query_invalid"):
        compose_effective_query_v2(base_query, logical_name="query.txt")


def test_effective_query_identity_rejects_wrong_version_hash_and_extra_fields() -> None:
    payload = frozen_request().model_dump(mode="json")
    for field, value in (
        ("schema_version", "night-voyager.dra-live-effective-query.v1"),
        ("citation_clause_sha256", "e" * 64),
    ):
        malformed = deepcopy(payload)
        malformed[field] = value
        with pytest.raises(ValidationError):
            DraFrozenRequestV2.model_validate(malformed)
    wrong_hash = DraFrozenRequestV2.model_validate(
        payload | {"effective_sha256": "f" * 64}
    )
    with pytest.raises(ValueError, match="dra_effective_query_identity_mismatch"):
        validate_effective_query_v2(BASE_QUERY, wrong_hash)
    with pytest.raises(ValidationError):
        DraFrozenRequestV2.model_validate(payload | {"clause": "operator supplied"})


def test_v2_intent_rejects_legacy_v1_identity() -> None:
    intent = DraCaptureIntentV2.freeze(
        capture_input(), attempt_id_factory=lambda: "attempt-0000000000000001"
    )
    payload = intent.model_dump(mode="json", exclude={"intent_sha256"})
    payload["schema_version"] = "night-voyager.dra-live-capture-intent.v1"
    payload["capture"]["schema_version"] = (
        "night-voyager.dra-live-capture-input.v1"
    )
    payload["capture"]["request"]["schema_version"] = (
        "night-voyager.dra-live-effective-query.v1"
    )
    with pytest.raises(ValidationError):
        DraCaptureIntentV2.model_validate(payload)


def test_stage_keys_are_stable_domain_separated_and_target_bound() -> None:
    intent = DraCaptureIntentV2.freeze(
        capture_input(), attempt_id_factory=lambda: "attempt-0000000000000001"
    )
    first = derive_stage_key(intent.intent_sha256, "create", intent.attempt_id)
    assert first == derive_stage_key(
        intent.intent_sha256, "create", intent.attempt_id
    )
    assert first != derive_stage_key(
        intent.intent_sha256, "candidate-import", str(CASE_ID)
    )
    assert first != derive_stage_key(
        intent.intent_sha256, "create", "attempt-0000000000000002"
    )


@pytest.mark.parametrize(
    "field,value",
    (
        ("receipt_root_id", "has whitespace"),
        ("receipt_root_id", "../escape"),
    ),
)
def test_capture_input_rejects_unsafe_identity_values(
    field: str, value: object
) -> None:
    payload = capture_input().model_dump(mode="json")
    payload[field] = value
    with pytest.raises(ValidationError):
        DraCaptureInputV2.model_validate(payload)


@pytest.mark.parametrize(
    "forbidden",
    (
        "selected_url",
        "content",
        "prompt",
        "credential",
        "session",
        "headers",
        "environment",
    ),
)
def test_capture_input_rejects_content_and_session_fields(forbidden: str) -> None:
    payload = capture_input().model_dump(mode="json")
    payload[forbidden] = "forbidden"
    with pytest.raises(ValidationError):
        DraCaptureInputV2.model_validate(payload)


def test_capture_input_rejects_missing_and_unknown_request_fields() -> None:
    payload = capture_input().model_dump(mode="json")
    missing = deepcopy(payload)
    del missing["request"]["effective_sha256"]
    with pytest.raises(ValidationError):
        DraCaptureInputV2.model_validate(missing)

    unknown = deepcopy(payload)
    unknown["request"]["body"] = "forbidden"
    with pytest.raises(ValidationError):
        DraCaptureInputV2.model_validate(unknown)


def test_reconciliation_receipt_requires_parent_intent_identity() -> None:
    intent = DraCaptureIntentV2.freeze(
        capture_input(), attempt_id_factory=lambda: "attempt-0000000000000001"
    )
    payload = {
        "schema_version": "night-voyager.dra-live-reconciliation-required.v1",
        "intent_sha256": intent.intent_sha256,
        "attempt_id": intent.attempt_id,
        "intent_receipt": DraReceiptIdentityV1(
            logical_name="intent.json",
            byte_length=len(intent.canonical_bytes()),
            sha256=RECEIPT_HASH,
        ).model_dump(mode="json"),
        "create_key": derive_stage_key(
            intent.intent_sha256, "create", intent.attempt_id
        ),
        "provider_attempt_consumed": True,
        "permitted_next_command": "reconcile-create",
    }
    assert (
        DraReconciliationRequiredReceiptV1.model_validate(payload).intent_sha256
        == intent.intent_sha256
    )
    del payload["intent_receipt"]
    with pytest.raises(ValidationError):
        DraReconciliationRequiredReceiptV1.model_validate(payload)


def test_intent_json_contains_only_closed_identity_fields() -> None:
    intent = DraCaptureIntentV2.freeze(
        capture_input(), attempt_id_factory=lambda: "attempt-0000000000000001"
    )
    payload = json.loads(intent.canonical_bytes())
    assert payload["capture"]["request"] == {
        "base_byte_length": len(BASE_QUERY),
        "base_sha256": hashlib.sha256(BASE_QUERY).hexdigest(),
        "citation_clause_sha256": hashlib.sha256(
            DRA_LIVE_CITATION_CLAUSE_V2
        ).hexdigest(),
        "encoding": "utf-8",
        "effective_byte_length": len(
            BASE_QUERY + b"\n\n" + DRA_LIVE_CITATION_CLAUSE_V2
        ),
        "effective_sha256": hashlib.sha256(
            BASE_QUERY + b"\n\n" + DRA_LIVE_CITATION_CLAUSE_V2
        ).hexdigest(),
        "logical_name": "query.txt",
        "schema_version": "night-voyager.dra-live-effective-query.v2",
    }
    assert payload["capture"]["one_attempt_authorized"] is True
