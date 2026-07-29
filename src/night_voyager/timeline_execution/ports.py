from __future__ import annotations

from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, PositiveInt

from night_voyager.identity.models import ActorContext
from night_voyager.timeline_execution.models import (
    CheckpointAttestationCode,
    CheckpointAttestationKind,
    CheckpointAttestationReasonCode,
    CheckpointStatusCode,
    CheckpointVerificationAction,
    CheckpointVerificationReasonCode,
    PlanExecutionContextV1,
    ReassessmentTrigger,
    TimelineExecutionViewV1,
    TimelineMutationReceiptV1,
)


class CommandModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StartTimelineExecutionCommand(CommandModel):
    case_id: UUID
    timeline_plan_id: UUID
    expected_case_revision: PositiveInt
    execution_id: UUID
    receipt_id: UUID


class AttestTimelineCheckpointCommand(CommandModel):
    case_id: UUID
    execution_id: UUID
    checkpoint_id: UUID
    expected_execution_version: PositiveInt
    expected_checkpoint_version: PositiveInt
    attestation_kind: CheckpointAttestationKind
    status_code: CheckpointStatusCode
    attestation_code: CheckpointAttestationCode
    reason_code: CheckpointAttestationReasonCode
    attestation_id: UUID
    receipt_id: UUID


class VerifyTimelineCheckpointCommand(CommandModel):
    case_id: UUID
    execution_id: UUID
    checkpoint_id: UUID
    attestation_id: UUID
    expected_execution_version: PositiveInt
    expected_checkpoint_version: PositiveInt
    action: CheckpointVerificationAction
    reason_code: CheckpointVerificationReasonCode
    verification_id: UUID
    receipt_id: UUID


class RequestTimelineReassessmentCommand(CommandModel):
    case_id: UUID
    execution_id: UUID
    checkpoint_id: UUID
    expected_execution_version: PositiveInt
    expected_checkpoint_version: PositiveInt
    trigger: ReassessmentTrigger
    trigger_reference_id: UUID | None
    reassessment_id: UUID
    receipt_id: UUID


class TimelineExecutionRepository(Protocol):
    async def context(
        self,
        actor: ActorContext,
        scenario: Literal["governed-plan-execution-v1"],
    ) -> PlanExecutionContextV1 | None: ...

    async def read(
        self, actor: ActorContext, case_id: UUID
    ) -> TimelineExecutionViewV1 | None: ...

    async def start(
        self,
        actor: ActorContext,
        command: StartTimelineExecutionCommand,
        idempotency_key: str,
    ) -> TimelineMutationReceiptV1: ...

    async def attest(
        self,
        actor: ActorContext,
        command: AttestTimelineCheckpointCommand,
        idempotency_key: str,
    ) -> TimelineMutationReceiptV1: ...

    async def verify(
        self,
        actor: ActorContext,
        command: VerifyTimelineCheckpointCommand,
        idempotency_key: str,
    ) -> TimelineMutationReceiptV1: ...

    async def reassess(
        self,
        actor: ActorContext,
        command: RequestTimelineReassessmentCommand,
        idempotency_key: str,
    ) -> TimelineMutationReceiptV1: ...
