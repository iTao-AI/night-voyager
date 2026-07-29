from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

import pytest

from night_voyager.identity.models import ActorContext, ActorRole
from night_voyager.timeline_execution.errors import TimelineExecutionProjectionError
from night_voyager.timeline_execution.models import (
    CheckpointAttestationCode,
    CheckpointAttestationKind,
    CheckpointAttestationReasonCode,
    CheckpointStatusCode,
    CheckpointVerificationAction,
    CheckpointVerificationReasonCode,
    ReassessmentTrigger,
    TimelineMutationReceiptV1,
)
from night_voyager.timeline_execution.ports import (
    AttestTimelineCheckpointCommand,
    RequestTimelineReassessmentCommand,
    StartTimelineExecutionCommand,
    VerifyTimelineCheckpointCommand,
)
from night_voyager.timeline_execution.postgres import PostgresTimelineExecutionRepository

ORG = UUID("10000000-0000-0000-0000-000000000001")
ACTOR = UUID("20000000-0000-0000-0000-000000000002")
SESSION = UUID("30000000-0000-0000-0000-000000000002")
CASE = UUID("40000000-0000-0000-0000-000000000001")
DECISION = UUID("50000000-0000-0000-0000-000000000001")
DECISION_RECEIPT = UUID("51000000-0000-0000-0000-000000000001")
TIMELINE = UUID("60000000-0000-0000-0000-000000000001")
EXECUTION = UUID("70000000-0000-0000-0000-000000000001")
RECEIPT = UUID("71000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 7, 29, tzinfo=UTC)


class RecordingSession:
    def __init__(self, values: list[object]) -> None:
        self.values = values
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def scalar(self, statement: object, parameters: dict[str, object]) -> object:
        self.calls.append((str(statement), parameters))
        return self.values.pop(0)


def actor() -> ActorContext:
    return ActorContext(
        organization_id=ORG,
        actor_id=ACTOR,
        role=ActorRole.STUDENT,
        session_id=SESSION,
    )


def context_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "scenario": "governed-plan-execution-v1",
        "case_id": str(CASE),
        "case_revision": 1,
        "decision_id": str(DECISION),
        "decision_receipt_id": str(DECISION_RECEIPT),
        "timeline_plan_id": str(TIMELINE),
        "execution_id": None,
        "active_role": "student",
        "assignment_status": "assigned",
    }


def receipt_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "receipt_id": str(RECEIPT),
        "operation": "start",
        "result_kind": "timeline_execution_started",
        "result_id": str(EXECUTION),
        "execution_id": str(EXECUTION),
        "checkpoint_id": None,
        "before_execution_version": None,
        "after_execution_version": 1,
        "before_checkpoint_version": None,
        "after_checkpoint_version": None,
        "created_at": NOW.isoformat(),
    }


@pytest.mark.asyncio
async def test_context_calls_only_the_frozen_projection_and_decodes_strictly() -> None:
    session = RecordingSession([context_payload()])
    repository = PostgresTimelineExecutionRepository(session)  # type: ignore[arg-type]
    result = await repository.context(actor(), "governed-plan-execution-v1")
    assert result is not None and result.case_id == CASE
    sql, parameters = session.calls[0]
    assert "app.read_plan_execution_context" in sql
    assert parameters == {
        "org": ORG,
        "actor": ACTOR,
        "role": ActorRole.STUDENT,
        "scenario": "governed-plan-execution-v1",
    }


@pytest.mark.asyncio
async def test_start_hash_excludes_generated_ids_and_decodes_exact_receipt() -> None:
    session = RecordingSession([receipt_payload()])
    repository = PostgresTimelineExecutionRepository(session)  # type: ignore[arg-type]
    command = StartTimelineExecutionCommand(
        case_id=CASE,
        timeline_plan_id=TIMELINE,
        expected_case_revision=1,
        execution_id=EXECUTION,
        receipt_id=RECEIPT,
    )
    result = await repository.start(actor(), command, "stable-key")
    assert result == TimelineMutationReceiptV1.model_validate(receipt_payload())
    sql, parameters = session.calls[0]
    assert "app.start_timeline_execution" in sql
    assert parameters["execution"] == EXECUTION
    assert parameters["receipt"] == RECEIPT
    assert parameters["case"] == CASE
    assert parameters["case_revision"] == 1
    assert len(str(parameters["key_hash"])) == 64
    assert len(str(parameters["request_hash"])) == 64


@pytest.mark.asyncio
async def test_mutations_bind_case_inside_postgresql_call() -> None:
    attestation_payload = {
        **receipt_payload(),
        "operation": "attest",
        "result_kind": "timeline_checkpoint_attested",
    }
    verification_payload = {
        **receipt_payload(),
        "operation": "verify",
        "result_kind": "timeline_checkpoint_verified",
    }
    reassessment_payload = {
        **receipt_payload(),
        "operation": "reassess",
        "result_kind": "timeline_reassessment_requested",
    }
    session = RecordingSession(
        [attestation_payload, verification_payload, reassessment_payload]
    )
    repository = PostgresTimelineExecutionRepository(session)  # type: ignore[arg-type]
    await repository.attest(
        actor(),
        AttestTimelineCheckpointCommand(
            case_id=CASE,
            execution_id=EXECUTION,
            checkpoint_id=RECEIPT,
            expected_execution_version=1,
            expected_checkpoint_version=1,
            attestation_kind=CheckpointAttestationKind.COMPLETION,
            status_code=CheckpointStatusCode.READY_FOR_ADVISOR,
            attestation_code=CheckpointAttestationCode.DOCUMENTS_STATUS_CONFIRMED,
            reason_code=CheckpointAttestationReasonCode.NOT_APPLICABLE,
            attestation_id=UUID(int=18),
            receipt_id=UUID(int=19),
        ),
        "attest-key",
    )
    advisor = ActorContext(
        organization_id=ORG,
        actor_id=ACTOR,
        role=ActorRole.ADVISOR,
        session_id=SESSION,
    )
    await repository.verify(
        advisor,
        VerifyTimelineCheckpointCommand(
            case_id=CASE,
            execution_id=EXECUTION,
            checkpoint_id=RECEIPT,
            attestation_id=TIMELINE,
            expected_execution_version=1,
            expected_checkpoint_version=1,
            action=CheckpointVerificationAction.VERIFY,
            reason_code=CheckpointVerificationReasonCode.ATTESTATION_VERIFIED,
            verification_id=UUID(int=20),
            receipt_id=UUID(int=21),
        ),
        "verify-key",
    )
    await repository.reassess(
        advisor,
        RequestTimelineReassessmentCommand(
            case_id=CASE,
            execution_id=EXECUTION,
            checkpoint_id=RECEIPT,
            expected_execution_version=1,
            expected_checkpoint_version=1,
            trigger=ReassessmentTrigger.DEADLINE_ELAPSED,
            trigger_reference_id=None,
            reassessment_id=UUID(int=22),
            receipt_id=UUID(int=23),
        ),
        "reassess-key",
    )
    assert session.calls[0][1]["case"] == CASE
    assert session.calls[1][1]["case"] == CASE
    assert session.calls[2][1]["case"] == CASE


@pytest.mark.asyncio
async def test_malformed_projection_fails_closed() -> None:
    payload: dict[str, Any] = context_payload()
    payload["hidden_tenant"] = str(ORG)
    repository = PostgresTimelineExecutionRepository(
        RecordingSession([payload])  # type: ignore[arg-type]
    )
    with pytest.raises(TimelineExecutionProjectionError):
        await repository.context(actor(), "governed-plan-execution-v1")


@pytest.mark.asyncio
async def test_read_rejects_contradictory_activity_total() -> None:
    view: dict[str, object] = {
        "schema_version": 1,
        "execution": {
            "schema_version": 1,
            "execution_id": str(EXECUTION),
            "case_id": str(CASE),
            "case_revision": 1,
            "decision_id": str(DECISION),
            "decision_receipt_id": str(DECISION_RECEIPT),
            "timeline_plan_id": str(TIMELINE),
            "state": "active",
            "row_version": 1,
            "created_at": NOW.isoformat(),
            "updated_at": NOW.isoformat(),
        },
        "checkpoints": [],
        "current_checkpoint": None,
        "latest_attestation": None,
        "latest_verification": None,
        "reassessment": None,
        "current_action": {
            "schema_version": 1,
            "code": "checkpoint_attestation_required",
            "owner_role": "student",
            "checkpoint_id": None,
            "execution_version": 1,
            "checkpoint_version": None,
        },
        "observed_date": date(2026, 7, 29).isoformat(),
        "activity": [],
        "activity_total": -1,
        "activity_truncated": False,
    }
    repository = PostgresTimelineExecutionRepository(
        RecordingSession([view])  # type: ignore[arg-type]
    )
    with pytest.raises(TimelineExecutionProjectionError):
        await repository.read(actor(), CASE)
