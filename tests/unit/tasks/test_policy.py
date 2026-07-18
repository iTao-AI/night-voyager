from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, cast
from uuid import UUID

import pytest

from night_voyager.adapters.protocols import (
    AdapterFailure,
    AdapterFailureCode,
    AdapterPayload,
    PlanningAdapterRequest,
)
from night_voyager.planning.fixtures import validate_planning_fixture
from night_voyager.tasks.models import AgentTaskState, TaskRuntimePolicy, TaskViewStatus
from night_voyager.tasks.policy import (
    AdapterPayloadError,
    classify_adapter_outcome,
    project_task_status,
    validate_adapter_payload,
)

ORG = UUID("10000000-0000-0000-0000-000000000001")
CASE = UUID("40000000-0000-0000-0000-000000000010")
PACK = UUID("50000000-0000-0000-0000-000000000001")


def request() -> PlanningAdapterRequest:
    return PlanningAdapterRequest(
        schema_version=1,
        operation="generate_planning_run_v1",
        organization_id=ORG,
        case_id=CASE,
        case_revision=1,
        source_pack_id=PACK,
        source_pack_version=1,
        policy_version="m3a-policy-v1",
    )


@pytest.mark.parametrize(
    ("state", "current", "expected"),
    (
        (AgentTaskState.QUEUED, True, TaskViewStatus.PREPARING),
        (AgentTaskState.LEASED, True, TaskViewStatus.PREPARING),
        (AgentTaskState.RUNNING, True, TaskViewStatus.PREPARING),
        (AgentTaskState.WAITING_REVIEW, True, TaskViewStatus.NEEDS_ADVISOR_REVIEW),
        (AgentTaskState.SUCCEEDED, True, TaskViewStatus.READY),
        (AgentTaskState.BLOCKED, True, TaskViewStatus.NEEDS_EVIDENCE),
        (AgentTaskState.TIMED_OUT, True, TaskViewStatus.TIMED_OUT),
        (AgentTaskState.FAILED, True, TaskViewStatus.FAILED),
        (AgentTaskState.CANCELLED, True, TaskViewStatus.CANCELLED),
        (AgentTaskState.WAITING_REVIEW, False, TaskViewStatus.OUTDATED),
        (AgentTaskState.SUCCEEDED, False, TaskViewStatus.OUTDATED),
    ),
)
def test_public_projection_is_total_and_currentness_aware(
    state: AgentTaskState, current: bool, expected: TaskViewStatus
) -> None:
    assert project_task_status(state, result_is_current=current) is expected


def test_runtime_policy_freezes_all_approved_bounds() -> None:
    policy = TaskRuntimePolicy()
    assert policy.lease_seconds == 60
    assert policy.heartbeat_seconds == 15
    assert policy.poll_seconds == 1
    assert policy.sse_heartbeat_seconds == 15
    assert policy.max_attempts == 3
    assert policy.sse_page_size == 100
    assert policy.max_payload_bytes == 1024 * 1024
    assert policy.max_narrative_bytes == 64 * 1024
    assert policy.max_evidence_refs == 20


@pytest.mark.parametrize(
    ("code", "attempt", "retryable", "terminal"),
    (
        (AdapterFailureCode.TRANSIENT_UNAVAILABLE, 1, True, None),
        (AdapterFailureCode.TRANSPORT_INTERRUPTED, 2, True, None),
        (AdapterFailureCode.LEASE_EXPIRED, 1, True, None),
        (AdapterFailureCode.TRANSIENT_UNAVAILABLE, 3, False, AgentTaskState.FAILED),
        (AdapterFailureCode.DEADLINE_EXCEEDED, 1, False, AgentTaskState.TIMED_OUT),
        (AdapterFailureCode.REQUIRED_EVIDENCE_GAP, 1, False, AgentTaskState.BLOCKED),
        (AdapterFailureCode.INVALID_SCHEMA, 1, False, AgentTaskState.FAILED),
        (AdapterFailureCode.PIN_MISMATCH, 1, False, AgentTaskState.FAILED),
        (AdapterFailureCode.FALLBACK_AUTHORITY, 1, False, AgentTaskState.FAILED),
        (AdapterFailureCode.OVERSIZE, 1, False, AgentTaskState.FAILED),
        (AdapterFailureCode.POLICY_REJECTED, 1, False, AgentTaskState.FAILED),
        (AdapterFailureCode.UNKNOWN, 1, False, AgentTaskState.FAILED),
    ),
)
def test_retry_is_allowlisted_bounded_and_unknown_fails_closed(
    code: AdapterFailureCode,
    attempt: int,
    retryable: bool,
    terminal: AgentTaskState | None,
) -> None:
    decision = classify_adapter_outcome(AdapterFailure(code=code), attempt_no=attempt)
    assert decision.retryable is retryable
    assert decision.terminal_state is terminal
    assert decision.public_code == code.value


def valid_payload() -> bytes:
    fixture = validate_planning_fixture()
    planning_input = fixture.planning_input.model_copy(
        update={
            "organization_id": ORG,
            "case": fixture.planning_input.case.model_copy(
                update={"organization_id": ORG, "case_id": CASE, "revision": 1}
            ),
            "source_pack": fixture.planning_input.source_pack.model_copy(
                update={"organization_id": ORG}
            ),
            "evidence": tuple(
                item.model_copy(update={"organization_id": ORG})
                for item in fixture.planning_input.evidence
            ),
            "costs": tuple(
                item.model_copy(update={"organization_id": ORG})
                for item in fixture.planning_input.costs
            ),
            "rankings": tuple(
                item.model_copy(update={"organization_id": ORG})
                for item in fixture.planning_input.rankings
            ),
        }
    )
    return planning_input.model_dump_json().encode()


def test_adapter_payload_validates_schema_pins_authority_and_country_scope() -> None:
    result = validate_adapter_payload(AdapterPayload(payload=valid_payload()), request())
    assert result.organization_id == ORG
    assert result.case.case_id == CASE
    assert result.case.revision == 1
    assert result.source_pack.pack_id == PACK
    assert {country.value for country in result.case.student.preferred_countries} == {
        "australia",
        "japan",
        "malaysia",
    }
    assert all(item.authority.value == "accepted_synthetic_demo" for item in result.evidence)


def set_invalid_schema(data: dict[str, Any]) -> None:
    data["schema_version"] = 2


def set_wrong_organization(data: dict[str, Any]) -> None:
    data["organization_id"] = "10000000-0000-0000-0000-000000000099"


def set_wrong_revision(data: dict[str, Any]) -> None:
    cast(dict[str, Any], data["case"])["revision"] = 2


def set_wrong_pack_version(data: dict[str, Any]) -> None:
    cast(dict[str, Any], data["source_pack"])["version"] = 2


def set_wrong_country_scope(data: dict[str, Any]) -> None:
    case = cast(dict[str, Any], data["case"])
    student = cast(dict[str, Any], case["student"])
    student["preferred_countries"] = ["japan", "australia"]


def set_untrusted_authority(data: dict[str, Any]) -> None:
    evidence = cast(list[dict[str, Any]], data["evidence"])
    evidence[0]["authority"] = "untrusted_candidate"


@pytest.mark.parametrize(
    ("mutation", "code"),
    (
        (set_invalid_schema, "invalid_schema"),
        (set_wrong_organization, "pin_mismatch"),
        (set_wrong_revision, "pin_mismatch"),
        (set_wrong_pack_version, "pin_mismatch"),
        (set_wrong_country_scope, "country_scope_invalid"),
        (set_untrusted_authority, "fallback_authority"),
    ),
)
def test_adapter_payload_rejects_invalid_schema_pins_scope_and_authority(
    mutation: Callable[[dict[str, Any]], None], code: str
) -> None:
    data = cast(dict[str, Any], json.loads(valid_payload()))
    mutation(data)
    with pytest.raises(AdapterPayloadError) as captured:
        validate_adapter_payload(AdapterPayload(payload=json.dumps(data).encode()), request())
    assert captured.value.code == code


def test_adapter_payload_accepts_a_selected_country_subset_without_product_leakage() -> None:
    data = cast(dict[str, Any], json.loads(valid_payload()))
    case = cast(dict[str, Any], data["case"])
    student = cast(dict[str, Any], case["student"])
    student["preferred_countries"] = ["japan"]
    data["costs"] = []
    data["rankings"] = []

    result = validate_adapter_payload(
        AdapterPayload(payload=json.dumps(data).encode()), request()
    )

    assert tuple(country.value for country in result.case.student.preferred_countries) == (
        "japan",
    )
    assert result.costs == ()
    assert result.rankings == ()


def test_adapter_payload_rejects_unselected_country_product_rows() -> None:
    data = cast(dict[str, Any], json.loads(valid_payload()))
    case = cast(dict[str, Any], data["case"])
    student = cast(dict[str, Any], case["student"])
    student["preferred_countries"] = ["japan"]

    with pytest.raises(AdapterPayloadError) as captured:
        validate_adapter_payload(
            AdapterPayload(payload=json.dumps(data).encode()), request()
        )

    assert captured.value.code == "country_scope_invalid"


def test_adapter_payload_enforces_bytes_narrative_and_evidence_bounds() -> None:
    with pytest.raises(AdapterPayloadError, match="payload") as payload_error:
        validate_adapter_payload(AdapterPayload(payload=b"x" * (1024 * 1024 + 1)), request())
    assert payload_error.value.code == "oversize"

    data = json.loads(valid_payload())
    data["narrative"] = "x" * (64 * 1024 + 1)
    with pytest.raises(AdapterPayloadError) as narrative_error:
        validate_adapter_payload(AdapterPayload(payload=json.dumps(data).encode()), request())
    assert narrative_error.value.code == "narrative_oversize"

    data = json.loads(valid_payload())
    data["evidence"] = data["evidence"] * 4
    with pytest.raises(AdapterPayloadError) as evidence_error:
        validate_adapter_payload(AdapterPayload(payload=json.dumps(data).encode()), request())
    assert evidence_error.value.code == "evidence_limit"
