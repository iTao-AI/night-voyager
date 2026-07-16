from __future__ import annotations

from typing import Literal, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, PositiveInt, model_validator

from night_voyager.collaboration.models import (
    AppendMessageCommand,
    CollaborationThreadV1,
    ConfirmedFactAdvisorV1,
    ConfirmedFactParticipantV1,
    MemoryCandidateAdvisorV1,
    MemoryCandidateParticipantV1,
    MessageEventV1,
    MessagePageV1,
    ProposeMemoryCandidateCommand,
    VerificationDecision,
    VerifyMemoryCandidateCommand,
)
from night_voyager.identity.models import ActorContext


class _StrictPortModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class MemoryCandidateVerificationV1(_StrictPortModel):
    schema_version: Literal[1]
    verification_id: UUID
    candidate_id: UUID
    decision: VerificationDecision
    result_fact_id: UUID | None
    result_revision: PositiveInt | None
    replayed: bool

    @model_validator(mode="after")
    def exact_decision_shape(self) -> Self:
        has_result_fact = self.result_fact_id is not None
        has_result_revision = self.result_revision is not None
        if has_result_fact != has_result_revision:
            raise ValueError("verification result identities must be paired")
        if (self.decision is VerificationDecision.CONFIRM) != has_result_fact:
            raise ValueError("verification result does not match decision")
        return self


type MemoryCandidateProjection = MemoryCandidateAdvisorV1 | MemoryCandidateParticipantV1
type ConfirmedFactProjection = ConfirmedFactAdvisorV1 | ConfirmedFactParticipantV1


class CollaborationRepository(Protocol):
    async def create_thread(
        self,
        context: ActorContext,
        case_id: UUID,
        thread_id: UUID,
        request_sha256: str,
        idempotency_key: str,
    ) -> CollaborationThreadV1: ...

    async def get_thread(
        self, context: ActorContext, case_id: UUID
    ) -> CollaborationThreadV1 | None: ...

    async def list_messages(
        self,
        context: ActorContext,
        thread_id: UUID,
        after_sequence: int,
        limit: int,
    ) -> MessagePageV1: ...

    async def append_message(
        self,
        context: ActorContext,
        command: AppendMessageCommand,
        message_event_id: UUID,
        content_sha256: str,
        request_sha256: str,
        idempotency_key: str,
    ) -> MessageEventV1: ...

    async def propose_candidate(
        self,
        context: ActorContext,
        command: ProposeMemoryCandidateCommand,
        candidate_id: UUID,
        value_sha256: str,
        request_sha256: str,
        idempotency_key: str,
    ) -> MemoryCandidateParticipantV1: ...

    async def list_candidates(
        self,
        context: ActorContext,
        case_id: UUID,
        limit: int,
    ) -> tuple[MemoryCandidateProjection, ...]: ...

    async def verify_candidate(
        self,
        context: ActorContext,
        command: VerifyMemoryCandidateCommand,
        verification_id: UUID,
        confirmed_fact_id: UUID | None,
        request_sha256: str,
        idempotency_key: str,
    ) -> MemoryCandidateVerificationV1: ...

    async def list_confirmed_facts(
        self,
        context: ActorContext,
        case_id: UUID,
        limit: int,
    ) -> tuple[ConfirmedFactProjection, ...]: ...
