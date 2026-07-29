from __future__ import annotations

from typing import Literal
from uuid import UUID

from night_voyager.identity.models import ActorContext, ActorRole
from night_voyager.timeline_execution.errors import TimelineExecutionUnavailableError
from night_voyager.timeline_execution.models import (
    PlanExecutionContextV1,
    TimelineExecutionViewV1,
    TimelineMutationReceiptV1,
)
from night_voyager.timeline_execution.policy import (
    validate_attestation_codes,
    validate_verification_codes,
)
from night_voyager.timeline_execution.ports import (
    AttestTimelineCheckpointCommand,
    RequestTimelineReassessmentCommand,
    StartTimelineExecutionCommand,
    TimelineExecutionRepository,
    VerifyTimelineCheckpointCommand,
)

SCENARIO: Literal["governed-plan-execution-v1"] = "governed-plan-execution-v1"


class TimelineExecutionService:
    def __init__(self, repository: TimelineExecutionRepository) -> None:
        self._repository = repository

    async def context(
        self, actor: ActorContext, scenario: str
    ) -> PlanExecutionContextV1 | None:
        if scenario != SCENARIO:
            raise TimelineExecutionUnavailableError("execution context unavailable")
        return await self._repository.context(actor, SCENARIO)

    async def read(
        self, actor: ActorContext, case_id: UUID
    ) -> TimelineExecutionViewV1 | None:
        return await self._repository.read(actor, case_id)

    async def start(
        self,
        actor: ActorContext,
        command: StartTimelineExecutionCommand,
        idempotency_key: str,
    ) -> TimelineMutationReceiptV1:
        self._require_family(actor)
        return await self._repository.start(actor, command, idempotency_key)

    async def attest(
        self,
        actor: ActorContext,
        command: AttestTimelineCheckpointCommand,
        idempotency_key: str,
    ) -> TimelineMutationReceiptV1:
        self._require_family(actor)
        view = await self._repository.read(actor, command.case_id)
        checkpoint = view.current_checkpoint if view else None
        if (
            checkpoint is None
            or checkpoint.execution_id != command.execution_id
            or checkpoint.checkpoint_id != command.checkpoint_id
            or checkpoint.accountable_role != actor.role.value
        ):
            raise TimelineExecutionUnavailableError("execution authority unavailable")
        validate_attestation_codes(
            milestone_key=checkpoint.milestone_key,
            kind=command.attestation_kind,
            status_code=command.status_code,
            attestation_code=command.attestation_code,
            reason_code=command.reason_code,
        )
        return await self._repository.attest(actor, command, idempotency_key)

    async def verify(
        self,
        actor: ActorContext,
        command: VerifyTimelineCheckpointCommand,
        idempotency_key: str,
    ) -> TimelineMutationReceiptV1:
        self._require_advisor(actor)
        validate_verification_codes(action=command.action, reason_code=command.reason_code)
        return await self._repository.verify(actor, command, idempotency_key)

    async def reassess(
        self,
        actor: ActorContext,
        command: RequestTimelineReassessmentCommand,
        idempotency_key: str,
    ) -> TimelineMutationReceiptV1:
        self._require_advisor(actor)
        return await self._repository.reassess(actor, command, idempotency_key)

    @staticmethod
    def _require_family(actor: ActorContext) -> None:
        if actor.role not in {ActorRole.STUDENT, ActorRole.PARENT}:
            raise TimelineExecutionUnavailableError("execution authority unavailable")

    @staticmethod
    def _require_advisor(actor: ActorContext) -> None:
        if actor.role is not ActorRole.ADVISOR:
            raise TimelineExecutionUnavailableError("execution authority unavailable")
