from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal
from uuid import UUID

import pytest
from pydantic import ValidationError

from night_voyager.identity.models import ActorContext, ActorRole
from night_voyager.timeline_execution.application import TimelineExecutionService
from night_voyager.timeline_execution.errors import TimelineExecutionUnavailableError
from night_voyager.timeline_execution.fakes import FakeTimelineExecutionRepository
from night_voyager.timeline_execution.models import (
    CheckpointAttestationCode,
    CheckpointAttestationKind,
    CheckpointAttestationReasonCode,
    CheckpointStatusCode,
    CheckpointVerificationAction,
    CheckpointVerificationReasonCode,
    PlanExecutionContextV1,
    ReassessmentTrigger,
    TimelineCheckpointState,
    TimelineCheckpointV1,
    TimelineCurrentActionCode,
    TimelineCurrentActionV1,
    TimelineExecutionState,
    TimelineExecutionV1,
    TimelineExecutionViewV1,
    TimelineMutationReceiptV1,
    TimelineRiskState,
)
from night_voyager.timeline_execution.ports import (
    AttestTimelineCheckpointCommand,
    RequestTimelineReassessmentCommand,
    StartTimelineExecutionCommand,
    VerifyTimelineCheckpointCommand,
)

U1 = UUID(int=1)
U2 = UUID(int=2)
U3 = UUID(int=3)
NOW = datetime(2026, 7, 29, tzinfo=UTC)


def actor(role: ActorRole) -> ActorContext:
    return ActorContext(organization_id=U1, actor_id=U2, role=role, session_id=U3)


def receipt(operation: str) -> TimelineMutationReceiptV1:
    kinds = {
        "start": "timeline_execution_started",
        "attest": "timeline_checkpoint_attested",
        "verify": "timeline_checkpoint_verified",
        "reassess": "timeline_reassessment_requested",
    }
    return TimelineMutationReceiptV1.model_validate(
        {
            "schema_version": 1,
            "receipt_id": U1,
            "operation": operation,
            "result_kind": kinds[operation],
            "result_id": U2,
            "execution_id": U1,
            "checkpoint_id": U2,
            "before_execution_version": 1,
            "after_execution_version": 2,
            "before_checkpoint_version": 1,
            "after_checkpoint_version": 2,
            "created_at": NOW,
        }
    )


def view(
    accountable_role: Literal["student", "parent"] = "student",
) -> TimelineExecutionViewV1:
    execution = TimelineExecutionV1(
        schema_version=1,
        execution_id=U1,
        case_id=U2,
        case_revision=1,
        decision_id=U1,
        decision_receipt_id=U2,
        timeline_plan_id=U3,
        state=TimelineExecutionState.ACTIVE,
        row_version=1,
        created_at=NOW,
        updated_at=NOW,
    )
    checkpoint = TimelineCheckpointV1.model_validate(
        {
            "schema_version": 1,
            "checkpoint_id": U2,
            "execution_id": U1,
            "ordinal": 1,
            "milestone_key": "documents",
            "due_date": date(2026, 9, 1),
            "accountable_role": accountable_role,
            "state": TimelineCheckpointState.IN_PROGRESS,
            "risk_state": TimelineRiskState.ON_TRACK,
            "row_version": 1,
            "created_at": NOW,
            "updated_at": NOW,
        }
    )
    return TimelineExecutionViewV1(
        schema_version=1,
        execution=execution,
        checkpoints=(checkpoint,),
        current_checkpoint=checkpoint,
        latest_attestation=None,
        latest_verification=None,
        reassessment=None,
        current_action=TimelineCurrentActionV1(
            schema_version=1,
            code=TimelineCurrentActionCode.CHECKPOINT_ATTESTATION_REQUIRED,
            owner_role=accountable_role,
            checkpoint_id=checkpoint.checkpoint_id,
            execution_version=1,
            checkpoint_version=1,
        ),
        observed_date=date(2026, 7, 29),
        activity=(),
        activity_total=0,
        activity_truncated=False,
    )


def repository() -> FakeTimelineExecutionRepository:
    context = PlanExecutionContextV1(
        schema_version=1,
        scenario="governed-plan-execution-v1",
        case_id=U2,
        case_revision=1,
        decision_id=U1,
        decision_receipt_id=U2,
        timeline_plan_id=U3,
        execution_id=U1,
        active_role="student",
        assignment_status="assigned",
    )
    return FakeTimelineExecutionRepository(
        context_result=context,
        view_result=view(),
        receipts={name: receipt(name) for name in ("start", "attest", "verify", "reassess")},
    )


@pytest.mark.asyncio
async def test_context_closes_scenario_before_repository_call() -> None:
    repo = repository()
    service = TimelineExecutionService(repo)
    with pytest.raises(TimelineExecutionUnavailableError):
        await service.context(actor(ActorRole.STUDENT), "other")
    assert repo.calls == []


@pytest.mark.asyncio
async def test_start_requires_assigned_family_role_and_passes_receipt_through() -> None:
    command = StartTimelineExecutionCommand(
        case_id=U2,
        timeline_plan_id=U3,
        expected_case_revision=1,
        execution_id=U1,
        receipt_id=U2,
    )
    repo = repository()
    service = TimelineExecutionService(repo)
    with pytest.raises(TimelineExecutionUnavailableError):
        await service.start(actor(ActorRole.ADVISOR), command, "key")
    accepted = await service.start(actor(ActorRole.STUDENT), command, "key")
    assert accepted is repo.receipts["start"]
    assert repo.calls[-1][0] == "start"


@pytest.mark.asyncio
async def test_attestation_defers_locked_operation_conflicts_to_repository() -> None:
    command = AttestTimelineCheckpointCommand(
        case_id=U2,
        execution_id=U1,
        checkpoint_id=U2,
        expected_execution_version=1,
        expected_checkpoint_version=1,
        attestation_kind=CheckpointAttestationKind.PROGRESS,
        status_code=CheckpointStatusCode.WORK_IN_PROGRESS,
        attestation_code=CheckpointAttestationCode.DOCUMENTS_STATUS_CONFIRMED,
        reason_code=CheckpointAttestationReasonCode.NOT_APPLICABLE,
        attestation_id=U3,
        receipt_id=U1,
    )
    repo = repository()
    service = TimelineExecutionService(repo)
    delegated = await service.attest(actor(ActorRole.PARENT), command, "key")
    assert delegated is repo.receipts["attest"]
    assert repo.calls[-1][0] == "attest"
    accepted = await service.attest(actor(ActorRole.STUDENT), command, "key")
    assert accepted is repo.receipts["attest"]


@pytest.mark.asyncio
async def test_attestation_does_not_classify_non_current_checkpoint_codes() -> None:
    future_checkpoint_id = UUID(int=4)
    repo = repository()
    current_view = repo.view_result
    assert current_view is not None
    future_checkpoint = TimelineCheckpointV1.model_validate(
        {
            "schema_version": 1,
            "checkpoint_id": future_checkpoint_id,
            "execution_id": U1,
            "ordinal": 2,
            "milestone_key": "application",
            "due_date": date(2026, 10, 1),
            "accountable_role": "parent",
            "state": TimelineCheckpointState.PENDING,
            "risk_state": TimelineRiskState.ON_TRACK,
            "row_version": 1,
            "created_at": NOW,
            "updated_at": NOW,
        }
    )
    repo.view_result = current_view.model_copy(
        update={"checkpoints": (*current_view.checkpoints, future_checkpoint)}
    )
    command = AttestTimelineCheckpointCommand(
        case_id=U2,
        execution_id=U1,
        checkpoint_id=future_checkpoint_id,
        expected_execution_version=1,
        expected_checkpoint_version=1,
        attestation_kind=CheckpointAttestationKind.COMPLETION,
        status_code=CheckpointStatusCode.READY_FOR_ADVISOR,
        attestation_code=CheckpointAttestationCode.DOCUMENTS_STATUS_CONFIRMED,
        reason_code=CheckpointAttestationReasonCode.NOT_APPLICABLE,
        attestation_id=U3,
        receipt_id=U1,
    )

    accepted = await TimelineExecutionService(repo).attest(
        actor(ActorRole.STUDENT), command, "key"
    )

    assert accepted is repo.receipts["attest"]
    assert repo.calls[-1][0] == "attest"


@pytest.mark.asyncio
async def test_verification_and_reassessment_are_advisor_only() -> None:
    verify = VerifyTimelineCheckpointCommand(
        case_id=U2,
        execution_id=U1,
        checkpoint_id=U2,
        attestation_id=U3,
        expected_execution_version=1,
        expected_checkpoint_version=1,
        action=CheckpointVerificationAction.VERIFY,
        reason_code=CheckpointVerificationReasonCode.ATTESTATION_VERIFIED,
        verification_id=U1,
        receipt_id=U2,
    )
    reassess = RequestTimelineReassessmentCommand(
        case_id=U2,
        execution_id=U1,
        checkpoint_id=U2,
        expected_execution_version=1,
        expected_checkpoint_version=1,
        trigger=ReassessmentTrigger.BLOCKED_ATTESTATION,
        trigger_reference_id=U3,
        reassessment_id=U1,
        receipt_id=U2,
    )
    repo = repository()
    service = TimelineExecutionService(repo)
    with pytest.raises(TimelineExecutionUnavailableError):
        await service.verify(actor(ActorRole.STUDENT), verify, "key")
    with pytest.raises(TimelineExecutionUnavailableError):
        await service.reassess(actor(ActorRole.PARENT), reassess, "key")
    assert await service.verify(actor(ActorRole.ADVISOR), verify, "key") is repo.receipts[
        "verify"
    ]
    assert await service.reassess(
        actor(ActorRole.ADVISOR), reassess, "key"
    ) is repo.receipts["reassess"]


def test_commands_forbid_client_authority_fields() -> None:
    base = {
        "case_id": U2,
        "timeline_plan_id": U3,
        "expected_case_revision": 1,
        "execution_id": U1,
        "receipt_id": U2,
    }
    for forbidden in ("organization_id", "actor_id", "as_of", "milestones", "accountable_role"):
        with pytest.raises(ValidationError):
            StartTimelineExecutionCommand.model_validate({**base, forbidden: "forbidden"})
