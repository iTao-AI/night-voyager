from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from night_voyager.collaboration.application import CollaborationService
from night_voyager.collaboration.errors import (
    CollaborationAuthorizationError,
    MemoryCandidateStaleError,
)
from night_voyager.collaboration.hashing import canonical_sha256
from night_voyager.collaboration.models import (
    AppendMessageCommand,
    CollaborationThreadV1,
    ConfirmedFactAdvisorPageV1,
    ConfirmedFactHistoryCursorV1,
    ConfirmedFactParticipantPageV1,
    FactKey,
    IntendedFieldProposal,
    MemoryCandidateAdvisorV1,
    MemoryCandidateParticipantV1,
    MemoryCandidateState,
    MessageEventV1,
    MessagePageV1,
    ProposeMemoryCandidateCommand,
    RiskToleranceProposal,
    VerificationDecision,
    VerifyMemoryCandidateCommand,
)
from night_voyager.collaboration.ports import MemoryCandidateVerificationV1
from night_voyager.identity.models import ActorContext, ActorRole

ORG = UUID("10000000-0000-0000-0000-000000000001")
CASE = UUID("40000000-0000-0000-0000-000000000001")
THREAD = UUID("90000000-0000-0000-0000-000000000001")
MESSAGE = UUID("90000000-0000-0000-0000-000000000002")
CANDIDATE = UUID("90000000-0000-0000-0000-000000000003")
VERIFICATION = UUID("90000000-0000-0000-0000-000000000004")
FACT = UUID("90000000-0000-0000-0000-000000000005")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
STUDENT = UUID("20000000-0000-0000-0000-000000000002")
PARENT = UUID("20000000-0000-0000-0000-000000000003")
SESSION = UUID(int=100)
NOW = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)


def context(
    role: ActorRole,
    *,
    actor_id: UUID | None = None,
    session_id: UUID = SESSION,
) -> ActorContext:
    default_actor = {
        ActorRole.ADVISOR: ADVISOR,
        ActorRole.STUDENT: STUDENT,
        ActorRole.PARENT: PARENT,
    }[role]
    return ActorContext(ORG, actor_id or default_actor, role, session_id)


def append_command() -> AppendMessageCommand:
    return AppendMessageCommand(thread_id=THREAD, body="Our preferred intake is 2027-04.")


def student_proposal() -> ProposeMemoryCandidateCommand:
    return ProposeMemoryCandidateCommand(
        message_event_id=MESSAGE,
        case_revision=1,
        proposal=IntendedFieldProposal(
            schema_version=1,
            fact_key=FactKey.STUDENT_INTENDED_FIELD,
            value="Computer science",
        ),
    )


def parent_proposal() -> ProposeMemoryCandidateCommand:
    return ProposeMemoryCandidateCommand(
        message_event_id=MESSAGE,
        case_revision=1,
        proposal=RiskToleranceProposal(
            schema_version=1,
            fact_key=FactKey.FAMILY_RISK_TOLERANCE,
            value="medium",
        ),
    )


def verification(
    decision: VerificationDecision = VerificationDecision.CONFIRM,
) -> VerifyMemoryCandidateCommand:
    return VerifyMemoryCandidateCommand(
        candidate_id=CANDIDATE,
        expected_case_revision=1,
        decision=decision,
        reason="The participant-authored message supports this exact fact.",
    )


class RecordingRepository:
    def __init__(self, *, source_actor_id: UUID = STUDENT) -> None:
        self.source_actor_id = source_actor_id
        self.calls: list[tuple[object, ...]] = []
        self.failure: Exception | None = None

    def _raise_failure(self) -> None:
        if self.failure is not None:
            raise self.failure

    async def create_thread(
        self,
        context: ActorContext,
        case_id: UUID,
        thread_id: UUID,
        request_sha256: str,
        idempotency_key: str,
    ) -> CollaborationThreadV1:
        self.calls.append(
            (
                "create_thread",
                context,
                case_id,
                thread_id,
                request_sha256,
                idempotency_key,
            )
        )
        self._raise_failure()
        return CollaborationThreadV1(
            schema_version=1,
            thread_id=thread_id,
            case_id=case_id,
            created_by_actor_id=context.actor_id,
            created_at=NOW,
        )

    async def get_thread(
        self, context: ActorContext, case_id: UUID
    ) -> CollaborationThreadV1 | None:
        self.calls.append(("get_thread", context, case_id))
        self._raise_failure()
        return CollaborationThreadV1(
            schema_version=1,
            thread_id=THREAD,
            case_id=case_id,
            created_by_actor_id=ADVISOR,
            created_at=NOW,
        )

    async def list_messages(
        self,
        context: ActorContext,
        thread_id: UUID,
        after_sequence: int,
        limit: int,
    ) -> MessagePageV1:
        self.calls.append(("list_messages", context, thread_id, after_sequence, limit))
        self._raise_failure()
        return MessagePageV1(
            schema_version=1,
            items=(
                MessageEventV1(
                    schema_version=1,
                    message_event_id=MESSAGE,
                    thread_id=thread_id,
                    case_id=CASE,
                    sequence_no=1,
                    actor_id=STUDENT,
                    actor_role=ActorRole.STUDENT,
                    body="Shared message",
                    content_sha256="a" * 64,
                    created_at=NOW,
                ),
            ),
            next_after_sequence=1,
        )

    async def append_message(
        self,
        context: ActorContext,
        command: AppendMessageCommand,
        message_event_id: UUID,
        content_sha256: str,
        request_sha256: str,
        idempotency_key: str,
    ) -> MessageEventV1:
        self.calls.append(
            (
                "append_message",
                context,
                command,
                message_event_id,
                content_sha256,
                request_sha256,
                idempotency_key,
            )
        )
        self._raise_failure()
        return MessageEventV1(
            schema_version=1,
            message_event_id=message_event_id,
            thread_id=command.thread_id,
            case_id=CASE,
            sequence_no=1,
            actor_id=context.actor_id,
            actor_role=context.role,
            body=command.body,
            content_sha256=content_sha256,
            created_at=NOW,
        )

    async def propose_candidate(
        self,
        context: ActorContext,
        command: ProposeMemoryCandidateCommand,
        candidate_id: UUID,
        value_sha256: str,
        request_sha256: str,
        idempotency_key: str,
    ) -> MemoryCandidateParticipantV1:
        self.calls.append(
            (
                "propose_candidate",
                context,
                command,
                candidate_id,
                value_sha256,
                request_sha256,
                idempotency_key,
            )
        )
        self._raise_failure()
        if context.actor_id != self.source_actor_id:
            raise CollaborationAuthorizationError
        return MemoryCandidateParticipantV1(
            schema_version=1,
            fact_key=command.proposal.fact_key,
            value=command.proposal.value,
            state=MemoryCandidateState.PENDING,
            created_at=NOW,
            expires_at=NOW + timedelta(days=7),
        )

    async def list_candidates(
        self, context: ActorContext, case_id: UUID, limit: int
    ) -> tuple[MemoryCandidateAdvisorV1 | MemoryCandidateParticipantV1, ...]:
        self.calls.append(("list_candidates", context, case_id, limit))
        self._raise_failure()
        return ()

    async def verify_candidate(
        self,
        context: ActorContext,
        command: VerifyMemoryCandidateCommand,
        verification_id: UUID,
        confirmed_fact_id: UUID | None,
        request_sha256: str,
        idempotency_key: str,
    ) -> MemoryCandidateVerificationV1:
        self.calls.append(
            (
                "verify_candidate",
                context,
                command,
                verification_id,
                confirmed_fact_id,
                request_sha256,
                idempotency_key,
            )
        )
        self._raise_failure()
        return MemoryCandidateVerificationV1(
            schema_version=1,
            verification_id=verification_id,
            candidate_id=command.candidate_id,
            decision=command.decision,
            result_fact_id=confirmed_fact_id,
            result_revision=(2 if confirmed_fact_id is not None else None),
            replayed=False,
        )

    async def list_confirmed_facts(
        self,
        context: ActorContext,
        case_id: UUID,
        limit: int,
        cursor: ConfirmedFactHistoryCursorV1 | None = None,
    ) -> ConfirmedFactAdvisorPageV1 | ConfirmedFactParticipantPageV1:
        self.calls.append(("list_confirmed_facts", context, case_id, limit, cursor))
        self._raise_failure()
        if context.role is ActorRole.ADVISOR:
            return ConfirmedFactAdvisorPageV1(
                schema_version=1, current=(), history=(), next_cursor=None
            )
        return ConfirmedFactParticipantPageV1(schema_version=1, current=())


def id_factory(*values: UUID) -> Callable[[], UUID]:
    iterator = iter(values)
    return lambda: next(iterator)


@pytest.mark.asyncio
async def test_thread_creation_and_verification_are_advisor_only() -> None:
    repository = RecordingRepository()
    service = CollaborationService(repository)

    for role in (ActorRole.STUDENT, ActorRole.PARENT):
        with pytest.raises(CollaborationAuthorizationError):
            await service.create_thread(context(role), CASE, "create-key")
        with pytest.raises(CollaborationAuthorizationError):
            await service.verify_candidate(context(role), verification(), "verify-key")

    assert repository.calls == []


@pytest.mark.asyncio
async def test_assigned_shared_reads_delegate_every_closed_participant_role() -> None:
    repository = RecordingRepository()
    service = CollaborationService(repository)

    for role in ActorRole:
        actor = context(role)
        assert await service.get_thread(actor, CASE) is not None
        page = await service.list_messages(actor, THREAD)
        assert page.items[0].body == "Shared message"
        assert await service.list_candidates(actor, CASE) == ()
        facts = await service.list_confirmed_facts(actor, CASE)
        assert facts.current == ()
        if role is ActorRole.ADVISOR:
            assert type(facts) is ConfirmedFactAdvisorPageV1
        else:
            assert type(facts) is ConfirmedFactParticipantPageV1

    assert [call[0] for call in repository.calls] == [
        operation
        for _ in ActorRole
        for operation in (
            "get_thread",
            "list_messages",
            "list_candidates",
            "list_confirmed_facts",
        )
    ]
    assert all(call[-2:] == (0, 50) for call in repository.calls if call[0] == "list_messages")


@pytest.mark.asyncio
async def test_source_author_authority_is_delegated_to_repository() -> None:
    repository = RecordingRepository(source_actor_id=STUDENT)
    service = CollaborationService(repository, id_factory=lambda: CANDIDATE)

    with pytest.raises(CollaborationAuthorizationError):
        await service.propose_candidate(
            context(ActorRole.PARENT), parent_proposal(), "proposal-key"
        )

    assert repository.calls[-1][0] == "propose_candidate"


@pytest.mark.asyncio
async def test_proposal_coarse_role_fact_matrix_precedes_repository() -> None:
    repository = RecordingRepository()
    service = CollaborationService(repository)

    with pytest.raises(CollaborationAuthorizationError):
        await service.propose_candidate(
            context(ActorRole.PARENT), student_proposal(), "proposal-key"
        )
    with pytest.raises(CollaborationAuthorizationError):
        await service.propose_candidate(
            context(ActorRole.ADVISOR, actor_id=ADVISOR),
            student_proposal(),
            "proposal-key",
        )

    assert repository.calls == []


@pytest.mark.asyncio
async def test_mutations_generate_ids_and_exact_public_content_hashes() -> None:
    repository = RecordingRepository(source_actor_id=STUDENT)
    service = CollaborationService(
        repository,
        id_factory=id_factory(THREAD, MESSAGE, CANDIDATE, VERIFICATION, FACT),
    )

    await service.create_thread(context(ActorRole.ADVISOR), CASE, "create-key")
    await service.append_message(context(ActorRole.STUDENT), append_command(), "append-key")
    await service.propose_candidate(context(ActorRole.STUDENT), student_proposal(), "proposal-key")
    result = await service.verify_candidate(
        context(ActorRole.ADVISOR), verification(), "verify-key"
    )

    create_call, append_call, proposal_call, verify_call = repository.calls
    assert create_call[3] == THREAD
    assert append_call[3] == MESSAGE
    assert proposal_call[3] == CANDIDATE
    assert verify_call[3:5] == (VERIFICATION, FACT)
    assert append_call[4] == hashlib.sha256(append_command().body.encode("utf-8")).hexdigest()
    proposal_value = student_proposal().proposal.model_dump(mode="json")["value"]
    assert proposal_call[4] == canonical_sha256(proposal_value)
    assert result.result_fact_id == FACT


@pytest.mark.asyncio
async def test_rejection_generates_no_confirmed_fact_identity() -> None:
    repository = RecordingRepository()
    service = CollaborationService(
        repository,
        id_factory=id_factory(VERIFICATION),
    )

    result = await service.verify_candidate(
        context(ActorRole.ADVISOR),
        verification(VerificationDecision.REJECT),
        "verify-key",
    )

    assert repository.calls[-1][3:5] == (VERIFICATION, None)
    assert result.result_fact_id is None
    assert result.result_revision is None


@pytest.mark.asyncio
async def test_canonical_request_hash_excludes_session_and_idempotency_plaintext() -> None:
    repository = RecordingRepository()
    service = CollaborationService(repository, id_factory=id_factory(THREAD, THREAD))
    first_context = context(ActorRole.ADVISOR, session_id=UUID(int=101))
    second_context = context(ActorRole.ADVISOR, session_id=UUID(int=202))

    await service.create_thread(first_context, CASE, "first-secret-idempotency")
    await service.create_thread(second_context, CASE, "second-secret-idempotency")

    first_call, second_call = repository.calls
    expected = canonical_sha256({"schema_version": 1, "case_id": str(CASE)})
    assert first_call[4] == second_call[4] == expected
    assert first_call[5] != second_call[5]
    assert first_context.session_id.hex not in expected
    assert "first-secret-idempotency" not in expected


@pytest.mark.asyncio
async def test_each_command_request_hash_is_the_exact_command_projection() -> None:
    repository = RecordingRepository(source_actor_id=STUDENT)
    service = CollaborationService(
        repository,
        id_factory=id_factory(MESSAGE, CANDIDATE, VERIFICATION, FACT),
    )

    await service.append_message(context(ActorRole.STUDENT), append_command(), "key-a")
    await service.propose_candidate(context(ActorRole.STUDENT), student_proposal(), "key-b")
    await service.verify_candidate(context(ActorRole.ADVISOR), verification(), "key-c")

    assert repository.calls[0][5] == canonical_sha256(append_command().model_dump(mode="json"))
    assert repository.calls[1][5] == canonical_sha256(student_proposal().model_dump(mode="json"))
    assert repository.calls[2][5] == canonical_sha256(verification().model_dump(mode="json"))


@pytest.mark.asyncio
async def test_repository_typed_errors_pass_through_unchanged() -> None:
    repository = RecordingRepository(source_actor_id=STUDENT)
    failure = MemoryCandidateStaleError("candidate is stale")
    repository.failure = failure
    service = CollaborationService(repository, id_factory=lambda: CANDIDATE)

    with pytest.raises(MemoryCandidateStaleError) as captured:
        await service.propose_candidate(
            context(ActorRole.STUDENT), student_proposal(), "proposal-key"
        )

    assert captured.value is failure


def test_verification_result_enforces_exact_decision_shape() -> None:
    confirmed = MemoryCandidateVerificationV1(
        schema_version=1,
        verification_id=VERIFICATION,
        candidate_id=CANDIDATE,
        decision=VerificationDecision.CONFIRM,
        result_fact_id=FACT,
        result_revision=2,
        replayed=True,
    )
    assert confirmed.replayed is True

    with pytest.raises(ValidationError):
        MemoryCandidateVerificationV1(
            schema_version=1,
            verification_id=VERIFICATION,
            candidate_id=CANDIDATE,
            decision=VerificationDecision.CONFIRM,
            result_fact_id=None,
            result_revision=None,
            replayed=False,
        )
    with pytest.raises(ValidationError):
        MemoryCandidateVerificationV1(
            schema_version=1,
            verification_id=VERIFICATION,
            candidate_id=CANDIDATE,
            decision=VerificationDecision.REJECT,
            result_fact_id=FACT,
            result_revision=2,
            replayed=False,
        )
