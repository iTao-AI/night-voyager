from __future__ import annotations

import hashlib
from collections.abc import Callable
from uuid import UUID, uuid4

from night_voyager.collaboration.errors import CollaborationAuthorizationError
from night_voyager.collaboration.hashing import canonical_sha256
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
from night_voyager.collaboration.policy import role_allows_fact
from night_voyager.collaboration.ports import (
    CollaborationRepository,
    MemoryCandidateVerificationV1,
)
from night_voyager.identity.models import ActorContext, ActorRole

__all__ = ["CollaborationService"]


class CollaborationService:
    def __init__(
        self,
        repository: CollaborationRepository,
        *,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._id_factory = id_factory

    async def create_thread(
        self,
        context: ActorContext,
        case_id: UUID,
        idempotency_key: str,
    ) -> CollaborationThreadV1:
        self._require_advisor(context)
        request_sha256 = canonical_sha256({"schema_version": 1, "case_id": str(case_id)})
        return await self._repository.create_thread(
            context,
            case_id,
            self._id_factory(),
            request_sha256,
            idempotency_key,
        )

    async def get_thread(
        self, context: ActorContext, case_id: UUID
    ) -> CollaborationThreadV1 | None:
        return await self._repository.get_thread(context, case_id)

    async def list_messages(
        self,
        context: ActorContext,
        thread_id: UUID,
        *,
        after_sequence: int = 0,
        limit: int = 50,
    ) -> MessagePageV1:
        return await self._repository.list_messages(context, thread_id, after_sequence, limit)

    async def append_message(
        self,
        context: ActorContext,
        command: AppendMessageCommand,
        idempotency_key: str,
    ) -> MessageEventV1:
        content_sha256 = hashlib.sha256(command.body.encode("utf-8")).hexdigest()
        request_sha256 = canonical_sha256(command.model_dump(mode="json"))
        return await self._repository.append_message(
            context,
            command,
            self._id_factory(),
            content_sha256,
            request_sha256,
            idempotency_key,
        )

    async def propose_candidate(
        self,
        context: ActorContext,
        command: ProposeMemoryCandidateCommand,
        idempotency_key: str,
    ) -> MemoryCandidateParticipantV1:
        if context.role not in (ActorRole.STUDENT, ActorRole.PARENT) or not role_allows_fact(
            context.role, command.proposal.fact_key
        ):
            raise CollaborationAuthorizationError
        proposal_projection = command.proposal.model_dump(mode="json")
        value_sha256 = canonical_sha256(proposal_projection["value"])
        request_sha256 = canonical_sha256(command.model_dump(mode="json"))
        return await self._repository.propose_candidate(
            context,
            command,
            self._id_factory(),
            value_sha256,
            request_sha256,
            idempotency_key,
        )

    async def list_candidates(
        self,
        context: ActorContext,
        case_id: UUID,
        *,
        limit: int = 50,
    ) -> tuple[MemoryCandidateAdvisorV1 | MemoryCandidateParticipantV1, ...]:
        return await self._repository.list_candidates(context, case_id, limit)

    async def verify_candidate(
        self,
        context: ActorContext,
        command: VerifyMemoryCandidateCommand,
        idempotency_key: str,
    ) -> MemoryCandidateVerificationV1:
        self._require_advisor(context)
        verification_id = self._id_factory()
        confirmed_fact_id = (
            self._id_factory() if command.decision is VerificationDecision.CONFIRM else None
        )
        request_sha256 = canonical_sha256(command.model_dump(mode="json"))
        return await self._repository.verify_candidate(
            context,
            command,
            verification_id,
            confirmed_fact_id,
            request_sha256,
            idempotency_key,
        )

    async def list_confirmed_facts(
        self,
        context: ActorContext,
        case_id: UUID,
        *,
        limit: int = 50,
    ) -> tuple[ConfirmedFactAdvisorV1 | ConfirmedFactParticipantV1, ...]:
        return await self._repository.list_confirmed_facts(context, case_id, limit)

    @staticmethod
    def _require_advisor(context: ActorContext) -> None:
        if context.role is not ActorRole.ADVISOR:
            raise CollaborationAuthorizationError
