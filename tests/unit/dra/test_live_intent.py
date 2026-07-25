from __future__ import annotations

import json
from collections.abc import Iterator
from copy import deepcopy
from uuid import UUID

import pytest
from pydantic import ValidationError

from night_voyager.dra.fixtures import load_live_closure_scenario
from night_voyager.dra.live_models import (
    DraCaptureInputV1,
    DraCaptureIntentV1,
    DraFrozenRequestV1,
    DraReceiptIdentityV1,
    DraReconciliationRequiredReceiptV1,
    derive_stage_key,
)

ORGANIZATION_ID = UUID("11111111-1111-4111-8111-111111111111")
CASE_ID = UUID("22222222-2222-4222-8222-222222222222")
ACTOR_HASH = "a" * 64
TENANT_HASH = "b" * 64
REQUEST_HASH = "c" * 64
RECEIPT_HASH = "d" * 64


def capture_input() -> DraCaptureInputV1:
    scenario = load_live_closure_scenario()
    return DraCaptureInputV1(
        scenario_id=scenario.scenario_id,
        producer=scenario.producer,
        organization_id=ORGANIZATION_ID,
        case_id=CASE_ID,
        expected_case_revision=1,
        advisor_actor_identity_sha256=ACTOR_HASH,
        tenant_identity_sha256=TENANT_HASH,
        request=DraFrozenRequestV1(
            logical_name="query.txt",
            encoding="utf-8",
            byte_length=12,
            sha256=REQUEST_HASH,
        ),
        receipt_root_id="dra-live-capture-root",
        one_attempt_authorized=True,
    )


def attempt_ids() -> Iterator[str]:
    yield "attempt-0000000000000001"
    raise AssertionError("attempt id generated more than once")


def test_capture_intent_is_frozen_once_and_byte_stable() -> None:
    identifiers = attempt_ids()
    intent = DraCaptureIntentV1.freeze(
        capture_input(), attempt_id_factory=lambda: next(identifiers)
    )
    reordered = DraCaptureIntentV1.model_validate(
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


def test_stage_keys_are_stable_domain_separated_and_target_bound() -> None:
    intent = DraCaptureIntentV1.freeze(
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
        DraCaptureInputV1.model_validate(payload)


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
        DraCaptureInputV1.model_validate(payload)


def test_capture_input_rejects_missing_and_unknown_request_fields() -> None:
    payload = capture_input().model_dump(mode="json")
    missing = deepcopy(payload)
    del missing["request"]["sha256"]
    with pytest.raises(ValidationError):
        DraCaptureInputV1.model_validate(missing)

    unknown = deepcopy(payload)
    unknown["request"]["body"] = "forbidden"
    with pytest.raises(ValidationError):
        DraCaptureInputV1.model_validate(unknown)


def test_reconciliation_receipt_requires_parent_intent_identity() -> None:
    intent = DraCaptureIntentV1.freeze(
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
    intent = DraCaptureIntentV1.freeze(
        capture_input(), attempt_id_factory=lambda: "attempt-0000000000000001"
    )
    payload = json.loads(intent.canonical_bytes())
    assert payload["capture"]["request"] == {
        "byte_length": 12,
        "encoding": "utf-8",
        "logical_name": "query.txt",
        "sha256": REQUEST_HASH,
    }
    assert payload["capture"]["one_attempt_authorized"] is True
