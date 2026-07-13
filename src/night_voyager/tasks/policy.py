from __future__ import annotations

import json
from dataclasses import dataclass
from typing import cast

from pydantic import ValidationError

from night_voyager.adapters.protocols import (
    AdapterFailure,
    AdapterFailureCode,
    AdapterPayload,
    PlanningAdapterRequest,
)
from night_voyager.planning.models import EvidenceAuthority, PlanningInput
from night_voyager.tasks.models import AgentTaskState, TaskRuntimePolicy, TaskViewStatus

APPROVED_COUNTRIES = frozenset({"australia", "japan", "malaysia"})
RETRYABLE_FAILURES = frozenset(
    {
        AdapterFailureCode.TRANSIENT_UNAVAILABLE,
        AdapterFailureCode.TRANSPORT_INTERRUPTED,
        AdapterFailureCode.LEASE_EXPIRED,
    }
)


class AdapterPayloadError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"adapter payload rejected: {code}")


@dataclass(frozen=True)
class RetryDecision:
    retryable: bool
    terminal_state: AgentTaskState | None
    public_code: str


def project_task_status(
    state: AgentTaskState, *, result_is_current: bool
) -> TaskViewStatus:
    if not result_is_current and state in {
        AgentTaskState.WAITING_REVIEW,
        AgentTaskState.SUCCEEDED,
    }:
        return TaskViewStatus.OUTDATED
    mapping = {
        AgentTaskState.QUEUED: TaskViewStatus.PREPARING,
        AgentTaskState.LEASED: TaskViewStatus.PREPARING,
        AgentTaskState.RUNNING: TaskViewStatus.PREPARING,
        AgentTaskState.WAITING_REVIEW: TaskViewStatus.NEEDS_ADVISOR_REVIEW,
        AgentTaskState.SUCCEEDED: TaskViewStatus.READY,
        AgentTaskState.BLOCKED: TaskViewStatus.NEEDS_EVIDENCE,
        AgentTaskState.TIMED_OUT: TaskViewStatus.TIMED_OUT,
        AgentTaskState.FAILED: TaskViewStatus.FAILED,
        AgentTaskState.CANCELLED: TaskViewStatus.CANCELLED,
    }
    return mapping[state]


def classify_adapter_outcome(failure: AdapterFailure, *, attempt_no: int) -> RetryDecision:
    policy = TaskRuntimePolicy()
    if failure.code in RETRYABLE_FAILURES and attempt_no < policy.max_attempts:
        return RetryDecision(True, None, failure.code.value)
    terminal = (
        AgentTaskState.TIMED_OUT
        if failure.code is AdapterFailureCode.DEADLINE_EXCEEDED
        else AgentTaskState.BLOCKED
        if failure.code is AdapterFailureCode.REQUIRED_EVIDENCE_GAP
        else AgentTaskState.FAILED
    )
    return RetryDecision(False, terminal, failure.code.value)


def validate_adapter_payload(
    outcome: AdapterPayload, request: PlanningAdapterRequest
) -> PlanningInput:
    policy = TaskRuntimePolicy()
    if len(outcome.payload) > policy.max_payload_bytes:
        raise AdapterPayloadError("oversize")
    try:
        decoded = outcome.payload.decode("utf-8")
        parsed: object = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AdapterPayloadError("invalid_schema") from error
    if not isinstance(parsed, dict):
        raise AdapterPayloadError("invalid_schema")
    raw = cast(dict[str, object], parsed)
    if raw.get("schema_version") != 1:
        raise AdapterPayloadError("invalid_schema")
    evidence_value = raw.get("evidence")
    if not isinstance(evidence_value, list):
        raise AdapterPayloadError("invalid_schema")
    evidence_items: list[dict[str, object]] = []
    for item in cast(list[object], evidence_value):
        if not isinstance(item, dict):
            raise AdapterPayloadError("invalid_schema")
        evidence_items.append(cast(dict[str, object], item))
    if len(evidence_items) > policy.max_evidence_refs:
        raise AdapterPayloadError("evidence_limit")
    narrative = raw.get("narrative")
    if isinstance(narrative, str) and len(narrative.encode("utf-8")) > policy.max_narrative_bytes:
        raise AdapterPayloadError("narrative_oversize")
    if any(item.get("authority") != "accepted_synthetic_demo" for item in evidence_items):
        raise AdapterPayloadError("fallback_authority")
    try:
        planning_input = PlanningInput.model_validate(raw)
    except ValidationError as error:
        raise AdapterPayloadError("invalid_schema") from error
    if (
        planning_input.organization_id != request.organization_id
        or planning_input.case.organization_id != request.organization_id
        or planning_input.case.case_id != request.case_id
        or planning_input.case.revision != request.case_revision
        or planning_input.source_pack.organization_id != request.organization_id
        or planning_input.source_pack.pack_id != request.source_pack_id
        or planning_input.source_pack.version != request.source_pack_version
        or any(item.organization_id != request.organization_id for item in planning_input.evidence)
        or any(item.organization_id != request.organization_id for item in planning_input.costs)
        or any(item.organization_id != request.organization_id for item in planning_input.rankings)
    ):
        raise AdapterPayloadError("pin_mismatch")
    countries = tuple(item.value for item in planning_input.case.student.preferred_countries)
    if len(countries) != 3 or set(countries) != set(APPROVED_COUNTRIES):
        raise AdapterPayloadError("country_scope_invalid")
    if any(
        item.authority is not EvidenceAuthority.ACCEPTED_SYNTHETIC_DEMO
        for item in planning_input.evidence
    ):
        raise AdapterPayloadError("fallback_authority")
    return planning_input
