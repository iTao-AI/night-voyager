from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from sqlalchemy.exc import DBAPIError, MultipleResultsFound, NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from night_voyager.collaboration.errors import (
    ActiveTaskBlocksRevisionError,
    CaseRevisionStaleError,
    CollaborationAuthorizationError,
    CollaborationPersistenceError,
    CollaborationThreadFullError,
    IdempotencyConflictError,
    InvalidCollaborationMessageError,
    MemoryCandidateExpiredError,
    MemoryCandidateStaleError,
    MemoryCandidateTerminalError,
    UnsafeFactValueError,
)
from night_voyager.collaboration.models import (
    AppendMessageCommand,
    ConfirmedFactAdvisorPageV1,
    ConfirmedFactAdvisorV1,
    ConfirmedFactHistoryCursorV1,
    ConfirmedFactParticipantPageV1,
    ConfirmedFactParticipantV1,
    FactKey,
    MemoryCandidateAdvisorV1,
    MemoryCandidateParticipantV1,
    MemoryCandidateState,
    MessagePageV1,
    ProposeMemoryCandidateCommand,
    RiskToleranceProposal,
    VerificationDecision,
    VerifyMemoryCandidateCommand,
)
from night_voyager.collaboration.ports import MemoryCandidateVerificationV1
from night_voyager.collaboration.postgres import PostgresCollaborationRepository
from night_voyager.identity.models import ActorContext, ActorRole

ORG_ID = UUID("10000000-0000-0000-0000-000000000001")
CASE_ID = UUID("40000000-0000-0000-0000-000000000010")
THREAD_ID = UUID("90000000-0000-0000-0000-000000000010")
MESSAGE_ID = UUID("91000000-0000-0000-0000-000000000010")
CANDIDATE_ID = UUID("92000000-0000-0000-0000-000000000010")
VERIFICATION_ID = UUID("93000000-0000-0000-0000-000000000010")
FACT_ID = UUID("94000000-0000-0000-0000-000000000010")
ADVISOR_ID = UUID("20000000-0000-0000-0000-000000000001")
STUDENT_ID = UUID("20000000-0000-0000-0000-000000000002")
PARENT_ID = UUID("20000000-0000-0000-0000-000000000003")
SESSION_ID = UUID("30000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 7, 17, tzinfo=UTC)
CONTENT_HASH = "a" * 64
REQUEST_HASH = "b" * 64
VALUE_HASH = "c" * 64
IDEMPOTENCY_KEY = "bounded-idempotency-key"


class SqlStateOrigin(Exception):
    def __init__(self, sqlstate: str | None) -> None:
        super().__init__("database detail must not escape")
        self.sqlstate = sqlstate


def db_error(sqlstate: str | None) -> DBAPIError:
    return DBAPIError(
        "SELECT bounded_function()",
        {},
        SqlStateOrigin(sqlstate),
        connection_invalidated=sqlstate is None,
    )


def context(role: ActorRole = ActorRole.ADVISOR) -> ActorContext:
    actor_id = {
        ActorRole.ADVISOR: ADVISOR_ID,
        ActorRole.STUDENT: STUDENT_ID,
        ActorRole.PARENT: PARENT_ID,
    }[role]
    return ActorContext(
        organization_id=ORG_ID,
        actor_id=actor_id,
        role=role,
        session_id=SESSION_ID,
    )


def session_returning(*rows: Mapping[str, object]) -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    mappings = result.mappings.return_value
    if rows:
        mappings.one.return_value = rows[0]
    mappings.one_or_none.return_value = rows[0] if rows else None
    mappings.all.return_value = list(rows)
    session.execute.return_value = result
    return session


def repository(session: AsyncMock) -> PostgresCollaborationRepository:
    return PostgresCollaborationRepository(cast(AsyncSession, session))


def append_command() -> AppendMessageCommand:
    return AppendMessageCommand(thread_id=THREAD_ID, body="We prefer a bounded option.")


def propose_command() -> ProposeMemoryCandidateCommand:
    return ProposeMemoryCandidateCommand(
        message_event_id=MESSAGE_ID,
        case_revision=1,
        proposal=RiskToleranceProposal(
            schema_version=1,
            fact_key=FactKey.FAMILY_RISK_TOLERANCE,
            value="high",
        ),
    )


def verify_command(
    decision: VerificationDecision = VerificationDecision.CONFIRM,
) -> VerifyMemoryCandidateCommand:
    return VerifyMemoryCandidateCommand(
        candidate_id=CANDIDATE_ID,
        expected_case_revision=1,
        decision=decision,
        reason="The participant confirmed this bounded preference.",
    )


@pytest.mark.asyncio
async def test_get_thread_returns_typed_row_or_none() -> None:
    row = {
        "schema_version": 1,
        "thread_id": THREAD_ID,
        "case_id": CASE_ID,
        "created_by_actor_id": ADVISOR_ID,
        "created_at": NOW,
    }
    session = session_returning(row)
    thread = await repository(session).get_thread(context(), CASE_ID)
    assert thread is not None
    assert thread.thread_id == THREAD_ID
    statement, params = session.execute.await_args.args
    assert "app.read_collaboration_thread" in str(statement)
    assert params == {
        "org": ORG_ID,
        "actor": ADVISOR_ID,
        "role": "advisor",
        "case": CASE_ID,
    }

    empty_session = session_returning()
    assert await repository(empty_session).get_thread(context(), CASE_ID) is None


@pytest.mark.asyncio
async def test_mutations_call_only_closed_functions_with_server_authority_parameters() -> None:
    thread_row = {
        "schema_version": 1,
        "thread_id": THREAD_ID,
        "case_id": CASE_ID,
        "created_by_actor_id": ADVISOR_ID,
        "created_at": NOW,
        "replayed": False,
    }
    message_row = {
        "schema_version": 1,
        "message_event_id": MESSAGE_ID,
        "thread_id": THREAD_ID,
        "case_id": CASE_ID,
        "sequence_no": 1,
        "actor_id": PARENT_ID,
        "actor_role": "parent",
        "body": append_command().body,
        "content_sha256": CONTENT_HASH,
        "created_at": NOW,
        "replayed": False,
    }
    candidate_row = {
        "schema_version": 1,
        "fact_key": "family.risk_tolerance",
        "value": "high",
        "state": "pending",
        "created_at": NOW,
        "expires_at": NOW + timedelta(days=7),
        "replayed": False,
    }
    verification_row = {
        "verification_id": VERIFICATION_ID,
        "candidate_id": CANDIDATE_ID,
        "decision": "confirm",
        "result_fact_id": FACT_ID,
        "result_revision": 2,
        "replayed": False,
    }
    session = session_returning(thread_row)
    adapter = repository(session)

    await adapter.create_thread(
        context(), CASE_ID, THREAD_ID, REQUEST_HASH, IDEMPOTENCY_KEY
    )
    statement, params = session.execute.await_args.args
    assert "app.create_collaboration_thread" in str(statement)
    assert set(params) == {
        "org",
        "actor",
        "role",
        "case",
        "thread",
        "request_sha256",
        "key_sha256",
    }
    assert params["role"] == "advisor"
    assert params["key_sha256"] == hashlib.sha256(IDEMPOTENCY_KEY.encode()).hexdigest()

    session = session_returning(message_row)
    adapter = repository(session)
    await adapter.append_message(
        context(ActorRole.PARENT),
        append_command(),
        MESSAGE_ID,
        CONTENT_HASH,
        REQUEST_HASH,
        IDEMPOTENCY_KEY,
    )
    statement, params = session.execute.await_args.args
    assert "app.append_collaboration_message" in str(statement)
    assert set(params) == {
        "org",
        "actor",
        "role",
        "thread",
        "message",
        "body",
        "content_sha256",
        "request_sha256",
        "key_sha256",
    }
    assert "case" not in params and "subject" not in params

    session = session_returning(candidate_row)
    adapter = repository(session)
    await adapter.propose_candidate(
        context(ActorRole.PARENT),
        propose_command(),
        CANDIDATE_ID,
        VALUE_HASH,
        REQUEST_HASH,
        IDEMPOTENCY_KEY,
    )
    statement, params = session.execute.await_args.args
    assert "app.propose_memory_candidate" in str(statement)
    assert set(params) == {
        "org",
        "actor",
        "role",
        "message",
        "candidate",
        "case_revision",
        "fact_key",
        "value",
        "value_sha256",
        "request_sha256",
        "key_sha256",
    }
    assert "case" not in params and "subject_actor" not in params
    assert json.loads(cast(str, params["value"])) == "high"

    session = session_returning(verification_row)
    adapter = repository(session)
    await adapter.verify_candidate(
        context(),
        verify_command(),
        VERIFICATION_ID,
        FACT_ID,
        REQUEST_HASH,
        IDEMPOTENCY_KEY,
    )
    statement, params = session.execute.await_args.args
    assert "app.verify_memory_candidate" in str(statement)
    assert set(params) == {
        "org",
        "actor",
        "candidate",
        "expected_revision",
        "decision",
        "reason",
        "verification",
        "fact",
        "request_sha256",
        "key_sha256",
    }
    assert "role" not in params and "case" not in params and "subject" not in params


@pytest.mark.asyncio
async def test_thread_message_and_verification_rows_are_strict_typed_models() -> None:
    session = session_returning(
        {
            "schema_version": 1,
            "thread_id": THREAD_ID,
            "case_id": CASE_ID,
            "created_by_actor_id": ADVISOR_ID,
            "created_at": NOW,
            "replayed": True,
        }
    )
    thread = await repository(session).create_thread(
        context(), CASE_ID, THREAD_ID, REQUEST_HASH, IDEMPOTENCY_KEY
    )
    assert thread.thread_id == THREAD_ID
    assert thread.model_dump().keys() == {
        "schema_version",
        "thread_id",
        "case_id",
        "created_by_actor_id",
        "created_at",
    }

    session = session_returning(
        {
            "schema_version": 1,
            "message_event_id": MESSAGE_ID,
            "thread_id": THREAD_ID,
            "case_id": CASE_ID,
            "sequence_no": 1,
            "actor_id": PARENT_ID,
            "actor_role": "parent",
            "body": append_command().body,
            "content_sha256": CONTENT_HASH,
            "created_at": NOW,
            "replayed": False,
        }
    )
    message = await repository(session).append_message(
        context(ActorRole.PARENT),
        append_command(),
        MESSAGE_ID,
        CONTENT_HASH,
        REQUEST_HASH,
        IDEMPOTENCY_KEY,
    )
    assert message.actor_role is ActorRole.PARENT

    session = session_returning(
        {
            "verification_id": VERIFICATION_ID,
            "candidate_id": CANDIDATE_ID,
            "decision": "confirm",
            "result_fact_id": FACT_ID,
            "result_revision": 2,
            "replayed": True,
        }
    )
    verified = await repository(session).verify_candidate(
        context(),
        verify_command(),
        VERIFICATION_ID,
        FACT_ID,
        REQUEST_HASH,
        IDEMPOTENCY_KEY,
    )
    assert isinstance(verified, MemoryCandidateVerificationV1)
    assert verified.replayed is True
    assert verified.result_fact_id == FACT_ID


@pytest.mark.asyncio
async def test_message_page_uses_stable_after_sequence_cursor() -> None:
    rows = tuple(
        {
            "schema_version": 1,
            "message_event_id": UUID(f"91000000-0000-0000-0000-{index:012d}"),
            "thread_id": THREAD_ID,
            "case_id": CASE_ID,
            "sequence_no": index,
            "actor_id": PARENT_ID,
            "actor_role": "parent",
            "body": f"Bounded message {index}",
            "content_sha256": f"{index:064x}",
            "created_at": NOW,
        }
        for index in (3, 4)
    )
    session = session_returning(*rows)
    page = await repository(session).list_messages(
        context(ActorRole.PARENT), THREAD_ID, after_sequence=2, limit=2
    )
    assert isinstance(page, MessagePageV1)
    assert tuple(item.sequence_no for item in page.items) == (3, 4)
    assert page.next_after_sequence == 4
    _, params = session.execute.await_args.args
    assert params == {
        "org": ORG_ID,
        "actor": PARENT_ID,
        "role": "parent",
        "thread": THREAD_ID,
        "after_sequence": 2,
        "limit": 2,
    }


@pytest.mark.asyncio
async def test_candidate_projections_are_selected_by_trusted_context_role() -> None:
    participant_projection = {
        "schema_version": 1,
        "fact_key": "family.risk_tolerance",
        "value": "high",
        "state": "pending",
        "created_at": NOW.isoformat(),
        "expires_at": (NOW + timedelta(days=7)).isoformat(),
    }
    session = session_returning({"projection": participant_projection})
    participant = (
        await repository(session).list_candidates(
            context(ActorRole.PARENT), CASE_ID, limit=50
        )
    )[0]
    assert type(participant) is MemoryCandidateParticipantV1
    assert set(participant.model_dump()) == {
        "schema_version",
        "fact_key",
        "value",
        "state",
        "created_at",
        "expires_at",
    }

    advisor_projection = {
        **participant_projection,
        "candidate_id": str(CANDIDATE_ID),
        "message_event_id": str(MESSAGE_ID),
        "source_message_sequence_no": 1,
        "subject_actor_id": str(PARENT_ID),
        "subject_role": "parent",
        "case_revision": 1,
        "verification_id": None,
        "decision": None,
        "reason": None,
        "request_sha256": REQUEST_HASH,
        "value_sha256": VALUE_HASH,
    }
    session = session_returning({"projection": advisor_projection})
    advisor = (
        await repository(session).list_candidates(context(), CASE_ID, limit=50)
    )[0]
    assert type(advisor) is MemoryCandidateAdvisorV1
    assert advisor.candidate_id == CANDIDATE_ID
    assert advisor.state is MemoryCandidateState.PENDING


@pytest.mark.asyncio
async def test_confirmed_fact_projections_are_selected_by_trusted_context_role() -> None:
    participant_projection = {
        "schema_version": 1,
        "fact_key": "family.risk_tolerance",
        "value": "high",
        "fact_version": 1,
        "confirmed_at": NOW.isoformat(),
        "subject_role": "parent",
        "confirming_advisor_role": "advisor",
    }
    session = session_returning(
        {
            "section": "current",
            "projection": participant_projection,
            "page_snapshot_revision": 2,
        }
    )
    participant_page = await repository(session).list_confirmed_facts(
        context(ActorRole.PARENT), CASE_ID, limit=50
    )
    assert type(participant_page) is ConfirmedFactParticipantPageV1
    participant = participant_page.current[0]
    assert type(participant) is ConfirmedFactParticipantV1
    assert set(participant.model_dump()) == {
        "schema_version",
        "fact_key",
        "value",
        "fact_version",
        "confirmed_at",
        "subject_role",
        "confirming_advisor_role",
    }

    advisor_projection = {
        **participant_projection,
        "confirmed_fact_id": str(FACT_ID),
        "candidate_id": str(CANDIDATE_ID),
        "verification_id": str(VERIFICATION_ID),
        "source_message_event_id": str(MESSAGE_ID),
        "source_message_sequence_no": 1,
        "source_message_sha256_prefix": CONTENT_HASH[:12],
        "confirming_advisor_actor_id": str(ADVISOR_ID),
        "reason": "The participant confirmed this bounded preference.",
        "supersedes_fact_id": None,
    }
    older_projection = {
        **advisor_projection,
        "confirmed_fact_id": str(UUID("94000000-0000-0000-0000-000000000011")),
        "fact_version": 2,
        "supersedes_fact_id": str(FACT_ID),
    }
    session = session_returning(
        {
            "section": "current",
            "projection": advisor_projection,
            "page_snapshot_revision": 3,
        },
        {
            "section": "history",
            "projection": advisor_projection,
            "page_snapshot_revision": 3,
        },
        {
            "section": "history",
            "projection": older_projection,
            "page_snapshot_revision": 3,
        },
    )
    advisor_page = await repository(session).list_confirmed_facts(
        context(), CASE_ID, limit=1
    )
    assert type(advisor_page) is ConfirmedFactAdvisorPageV1
    advisor = advisor_page.current[0]
    assert type(advisor) is ConfirmedFactAdvisorV1
    assert advisor.confirmed_fact_id == FACT_ID
    assert len(advisor_page.history) == 1
    assert advisor_page.next_cursor is not None
    cursor = ConfirmedFactHistoryCursorV1.decode(advisor_page.next_cursor)
    assert cursor.snapshot_revision == 3
    assert cursor.fact_key is FactKey.FAMILY_RISK_TOLERANCE
    assert cursor.fact_version == 1


@pytest.mark.parametrize(
    ("sqlstate", "expected"),
    [
        ("NV006", UnsafeFactValueError),
        ("NV007", CollaborationAuthorizationError),
        ("NV008", IdempotencyConflictError),
        ("NV012", MemoryCandidateTerminalError),
        ("NV013", MemoryCandidateExpiredError),
        ("NV014", ActiveTaskBlocksRevisionError),
    ],
)
@pytest.mark.asyncio
async def test_frozen_sqlstates_map_to_separate_typed_errors(
    sqlstate: str, expected: type[Exception]
) -> None:
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = db_error(sqlstate)
    with pytest.raises(expected) as raised:
        await repository(session).verify_candidate(
            context(),
            verify_command(),
            VERIFICATION_ID,
            FACT_ID,
            REQUEST_HASH,
            IDEMPOTENCY_KEY,
        )
    assert "database detail" not in str(raised.value)


@pytest.mark.asyncio
async def test_append_nv006_fallback_maps_to_closed_message_error() -> None:
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = db_error("NV006")
    command = AppendMessageCommand.model_construct(
        thread_id=THREAD_ID,
        body="file://local/private.txt",
    )

    with pytest.raises(InvalidCollaborationMessageError) as raised:
        await repository(session).append_message(
            context(ActorRole.PARENT),
            command,
            MESSAGE_ID,
            CONTENT_HASH,
            REQUEST_HASH,
            IDEMPOTENCY_KEY,
        )
    assert str(raised.value) == "invalid_collaboration_message"
    assert "database detail" not in str(raised.value)


@pytest.mark.asyncio
async def test_append_nv012_maps_to_thread_full_without_widening_other_operations() -> None:
    append_session = AsyncMock(spec=AsyncSession)
    append_session.execute.side_effect = db_error("NV012")
    with pytest.raises(CollaborationThreadFullError) as raised:
        await repository(append_session).append_message(
            context(ActorRole.PARENT),
            append_command(),
            MESSAGE_ID,
            CONTENT_HASH,
            REQUEST_HASH,
            IDEMPOTENCY_KEY,
        )
    assert str(raised.value) == "collaboration_thread_full"

    read_session = AsyncMock(spec=AsyncSession)
    read_session.execute.side_effect = db_error("NV012")
    with pytest.raises(CollaborationPersistenceError, match="persistence_unavailable"):
        await repository(read_session).get_thread(context(), CASE_ID)


@pytest.mark.asyncio
async def test_nv003_mapping_is_operation_sensitive_without_sql_text_parsing() -> None:
    proposal_session = AsyncMock(spec=AsyncSession)
    proposal_session.execute.side_effect = db_error("NV003")
    with pytest.raises(CaseRevisionStaleError):
        await repository(proposal_session).propose_candidate(
            context(ActorRole.PARENT),
            propose_command(),
            CANDIDATE_ID,
            VALUE_HASH,
            REQUEST_HASH,
            IDEMPOTENCY_KEY,
        )

    verification_session = AsyncMock(spec=AsyncSession)
    verification_session.execute.side_effect = db_error("NV003")
    with pytest.raises(MemoryCandidateStaleError):
        await repository(verification_session).verify_candidate(
            context(),
            verify_command(),
            VERIFICATION_ID,
            FACT_ID,
            REQUEST_HASH,
            IDEMPOTENCY_KEY,
        )


@pytest.mark.parametrize("sqlstate", (None, "40001", "42501", "XX999"))
@pytest.mark.asyncio
async def test_connection_serialization_permission_and_unknown_database_errors_fail_closed(
    sqlstate: str | None,
) -> None:
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = db_error(sqlstate)
    with pytest.raises(CollaborationPersistenceError) as raised:
        await repository(session).create_thread(
            context(), CASE_ID, THREAD_ID, REQUEST_HASH, IDEMPOTENCY_KEY
        )
    assert str(raised.value) == "persistence_unavailable"


@pytest.mark.asyncio
async def test_malformed_database_projection_fails_as_persistence_not_authorization() -> None:
    session = session_returning(
        {
            "schema_version": 1,
            "thread_id": THREAD_ID,
            "case_id": CASE_ID,
            "created_by_actor_id": ADVISOR_ID,
            # Missing created_at proves the result boundary is strict.
            "replayed": False,
        }
    )
    with pytest.raises(CollaborationPersistenceError, match="persistence_unavailable"):
        await repository(session).create_thread(
            context(), CASE_ID, THREAD_ID, REQUEST_HASH, IDEMPOTENCY_KEY
        )


@pytest.mark.parametrize("shape_error", (NoResultFound(), MultipleResultsFound()))
@pytest.mark.asyncio
async def test_mutation_missing_or_multiple_rows_fails_as_persistence(
    shape_error: Exception,
) -> None:
    session = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.mappings.return_value.one.side_effect = shape_error
    session.execute.return_value = result
    with pytest.raises(CollaborationPersistenceError, match="persistence_unavailable"):
        await repository(session).create_thread(
            context(), CASE_ID, THREAD_ID, REQUEST_HASH, IDEMPOTENCY_KEY
        )


@pytest.mark.asyncio
async def test_projection_fetch_failure_fails_as_persistence() -> None:
    session = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.mappings.return_value.all.side_effect = MultipleResultsFound()
    session.execute.return_value = result
    with pytest.raises(CollaborationPersistenceError, match="persistence_unavailable"):
        await repository(session).list_candidates(context(), CASE_ID, 50)


@pytest.mark.asyncio
async def test_nv012_outside_verification_is_not_misclassified_as_terminal() -> None:
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = db_error("NV012")
    with pytest.raises(CollaborationPersistenceError, match="persistence_unavailable"):
        await repository(session).create_thread(
            context(), CASE_ID, THREAD_ID, REQUEST_HASH, IDEMPOTENCY_KEY
        )
