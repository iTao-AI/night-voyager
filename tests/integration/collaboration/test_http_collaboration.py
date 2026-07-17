from __future__ import annotations

import json
import os
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Literal, cast
from uuid import UUID

import pytest
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from starlette.responses import JSONResponse

import night_voyager.interfaces.http.collaboration as collaboration_http
from night_voyager.api import create_app
from night_voyager.collaboration.errors import (
    ActiveTaskBlocksRevisionError,
    CaseRevisionStaleError,
    CollaborationAuthorizationError,
    CollaborationPersistenceError,
    IdempotencyConflictError,
    InvalidCollaborationMessageError,
    MemoryCandidateExpiredError,
    MemoryCandidateStaleError,
    MemoryCandidateTerminalError,
    UnsafeFactValueError,
    UnsupportedFactKeyError,
)
from night_voyager.collaboration.models import (
    AppendMessageCommand,
    CollaborationThreadV1,
    ConfirmedFactAdvisorV1,
    ConfirmedFactParticipantV1,
    FactKey,
    MemoryCandidateAdvisorV1,
    MemoryCandidateParticipantV1,
    MemoryCandidateState,
    MessageEventV1,
    MessagePageV1,
    ProposeMemoryCandidateCommand,
    VerifyMemoryCandidateCommand,
)
from night_voyager.collaboration.ports import MemoryCandidateVerificationV1
from night_voyager.config import Settings
from night_voyager.identity.models import ActorContext, ActorRole, DemoActorChoice
from night_voyager.identity.repository import IdentityRepository
from night_voyager.identity.service import IdentityService, IssuedSession
from night_voyager.interfaces.http.identity import BOOTSTRAP_COOKIE, SESSION_COOKIE
from night_voyager.planning.fixtures import validate_planning_fixture

ORIGIN = "http://127.0.0.1:3000"
ORG_ID = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR_ID = UUID("20000000-0000-0000-0000-000000000001")
STUDENT_ID = UUID("20000000-0000-0000-0000-000000000002")
PARENT_ID = UUID("20000000-0000-0000-0000-000000000003")
SESSION_ID = UUID("30000000-0000-0000-0000-000000000001")
CASE_ID = UUID("40000000-0000-0000-0000-000000000010")
THREAD_ID = UUID("90000000-0000-0000-0000-000000000010")
MESSAGE_ID = UUID("91000000-0000-0000-0000-000000000010")
CANDIDATE_ID = UUID("92000000-0000-0000-0000-000000000010")
VERIFICATION_ID = UUID("93000000-0000-0000-0000-000000000010")
FACT_ID = UUID("94000000-0000-0000-0000-000000000010")
NOW = datetime(2026, 7, 17, tzinfo=UTC)
REAL_CASE_ID = UUID("40000000-0000-0000-0000-000000000380")
REAL_UNASSIGNED_CASE_ID = UUID("40000000-0000-0000-0000-000000000381")
REAL_STALE_CANDIDATE_ID = UUID("45000000-0000-0000-0000-000000000003")

THREAD_PATH = f"/api/v1/cases/{CASE_ID}/collaboration-thread"
MESSAGES_PATH = f"/api/v1/collaboration-threads/{THREAD_ID}/messages"
PROPOSAL_PATH = f"/api/v1/messages/{MESSAGE_ID}/memory-candidates"
CANDIDATES_PATH = f"/api/v1/cases/{CASE_ID}/memory-candidates"
VERIFICATION_PATH = f"/api/v1/memory-candidates/{CANDIDATE_ID}/verification-decisions"
FACTS_PATH = f"/api/v1/cases/{CASE_ID}/confirmed-facts"


def actor_context(role: ActorRole) -> ActorContext:
    actor_id = {
        ActorRole.ADVISOR: ADVISOR_ID,
        ActorRole.STUDENT: STUDENT_ID,
        ActorRole.PARENT: PARENT_ID,
    }[role]
    return ActorContext(ORG_ID, actor_id, role, SESSION_ID)


class FakeIdentityService:
    def __init__(self, _repository: object, _secret_key: str) -> None:
        pass

    async def resolve(self, raw_session: str) -> ActorContext | None:
        return self._context(raw_session)

    async def resolve_with_csrf(self, raw_session: str, raw_csrf: str) -> ActorContext | None:
        context = self._context(raw_session)
        if context is None or raw_csrf != f"csrf-{context.role.value}":
            return None
        return context

    @staticmethod
    def _context(raw_session: str) -> ActorContext | None:
        for role in ActorRole:
            if raw_session == f"opaque-{role.value}":
                return actor_context(role)
        return None


class FakeTransaction:
    def __init__(self, outcomes: list[str]) -> None:
        self._outcomes = outcomes

    async def __aenter__(self) -> FakeTransaction:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> Literal[False]:
        self._outcomes.append("rollback" if exc_type is not None else "commit")
        return False


class FakeSession:
    def __init__(self, outcomes: list[str]) -> None:
        self._outcomes = outcomes

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> Literal[False]:
        return False

    def begin(self) -> FakeTransaction:
        return FakeTransaction(self._outcomes)


class FakeSessionFactory:
    def __init__(self, outcomes: list[str]) -> None:
        self._outcomes = outcomes

    def __call__(self) -> FakeSession:
        return FakeSession(self._outcomes)


class RecordingRepository:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.failure: Exception | None = None

    def _record(self, operation: str) -> None:
        self.calls.append(operation)
        if self.failure is not None:
            raise self.failure

    async def create_thread(
        self,
        context: ActorContext,
        case_id: UUID,
        _thread_id: UUID,
        _request_sha256: str,
        _idempotency_key: str,
    ) -> CollaborationThreadV1:
        self._record("create_thread")
        return CollaborationThreadV1(
            schema_version=1,
            thread_id=THREAD_ID,
            case_id=case_id,
            created_by_actor_id=context.actor_id,
            created_at=NOW,
        )

    async def get_thread(
        self, _context: ActorContext, case_id: UUID
    ) -> CollaborationThreadV1 | None:
        self._record("get_thread")
        return CollaborationThreadV1(
            schema_version=1,
            thread_id=THREAD_ID,
            case_id=case_id,
            created_by_actor_id=ADVISOR_ID,
            created_at=NOW,
        )

    async def list_messages(
        self,
        _context: ActorContext,
        thread_id: UUID,
        after_sequence: int,
        limit: int,
    ) -> MessagePageV1:
        self._record("list_messages")
        available = tuple(
            MessageEventV1(
                schema_version=1,
                message_event_id=UUID(f"91000000-0000-0000-0000-{sequence:012d}"),
                thread_id=thread_id,
                case_id=CASE_ID,
                sequence_no=sequence,
                actor_id=PARENT_ID,
                actor_role=ActorRole.PARENT,
                body=f"Shared bounded message {sequence}",
                content_sha256=f"{sequence:064x}",
                created_at=NOW,
            )
            for sequence in range(1, 5)
            if sequence > after_sequence
        )
        items = available[:limit]
        return MessagePageV1(
            schema_version=1,
            items=items,
            next_after_sequence=(items[-1].sequence_no if len(items) == limit and items else None),
        )

    async def append_message(
        self,
        context: ActorContext,
        command: AppendMessageCommand,
        message_event_id: UUID,
        content_sha256: str,
        _request_sha256: str,
        _idempotency_key: str,
    ) -> MessageEventV1:
        self._record("append_message")
        return MessageEventV1(
            schema_version=1,
            message_event_id=message_event_id,
            thread_id=command.thread_id,
            case_id=CASE_ID,
            sequence_no=5,
            actor_id=context.actor_id,
            actor_role=context.role,
            body=command.body,
            content_sha256=content_sha256,
            created_at=NOW,
        )

    async def propose_candidate(
        self,
        _context: ActorContext,
        command: ProposeMemoryCandidateCommand,
        _candidate_id: UUID,
        _value_sha256: str,
        _request_sha256: str,
        _idempotency_key: str,
    ) -> MemoryCandidateParticipantV1:
        self._record("propose_candidate")
        return MemoryCandidateParticipantV1(
            schema_version=1,
            fact_key=command.proposal.fact_key,
            value=command.proposal.value,
            state=MemoryCandidateState.PENDING,
            created_at=NOW,
            expires_at=NOW + timedelta(days=7),
        )

    async def list_candidates(
        self,
        context: ActorContext,
        _case_id: UUID,
        _limit: int,
    ) -> tuple[MemoryCandidateAdvisorV1 | MemoryCandidateParticipantV1, ...]:
        self._record("list_candidates")
        participant = MemoryCandidateParticipantV1(
            schema_version=1,
            fact_key=FactKey.FAMILY_RISK_TOLERANCE,
            value="high",
            state=MemoryCandidateState.PENDING,
            created_at=NOW,
            expires_at=NOW + timedelta(days=7),
        )
        if context.role is ActorRole.STUDENT:
            return ()
        if context.role is ActorRole.PARENT:
            return (participant,)
        return (
            MemoryCandidateAdvisorV1(
                **participant.model_dump(),
                candidate_id=CANDIDATE_ID,
                message_event_id=MESSAGE_ID,
                source_message_sequence_no=1,
                subject_actor_id=PARENT_ID,
                subject_role=ActorRole.PARENT,
                case_revision=1,
                verification_id=None,
                decision=None,
                reason=None,
                request_sha256="a" * 64,
                value_sha256="b" * 64,
            ),
        )

    async def verify_candidate(
        self,
        _context: ActorContext,
        command: VerifyMemoryCandidateCommand,
        verification_id: UUID,
        confirmed_fact_id: UUID | None,
        _request_sha256: str,
        _idempotency_key: str,
    ) -> MemoryCandidateVerificationV1:
        self._record("verify_candidate")
        return MemoryCandidateVerificationV1(
            schema_version=1,
            verification_id=verification_id,
            candidate_id=command.candidate_id,
            decision=command.decision,
            result_fact_id=confirmed_fact_id,
            result_revision=2 if confirmed_fact_id is not None else None,
            replayed=False,
        )

    async def list_confirmed_facts(
        self,
        context: ActorContext,
        _case_id: UUID,
        _limit: int,
    ) -> tuple[ConfirmedFactAdvisorV1 | ConfirmedFactParticipantV1, ...]:
        self._record("list_confirmed_facts")
        participant = ConfirmedFactParticipantV1(
            schema_version=1,
            fact_key=FactKey.FAMILY_RISK_TOLERANCE,
            value="high",
            fact_version=1,
            confirmed_at=NOW,
            subject_role=ActorRole.PARENT,
            confirming_advisor_role=ActorRole.ADVISOR,
        )
        if context.role is not ActorRole.ADVISOR:
            return (participant,)
        return (
            ConfirmedFactAdvisorV1(
                **participant.model_dump(),
                confirmed_fact_id=FACT_ID,
                candidate_id=CANDIDATE_ID,
                verification_id=VERIFICATION_ID,
                source_message_event_id=MESSAGE_ID,
                source_message_sequence_no=1,
                source_message_sha256_prefix="c" * 12,
                confirming_advisor_actor_id=ADVISOR_ID,
                reason="The participant confirmed this bounded preference.",
                supersedes_fact_id=None,
            ),
        )


@dataclass
class HttpHarness:
    app: FastAPI
    client: TestClient
    repository: RecordingRepository
    transactions: list[str]


@pytest.fixture
def http_harness(monkeypatch: pytest.MonkeyPatch) -> Iterator[HttpHarness]:
    repository = RecordingRepository()
    transactions: list[str] = []
    monkeypatch.setattr(collaboration_http, "IdentityService", FakeIdentityService)

    def repository_factory(_session: AsyncSession) -> RecordingRepository:
        return repository

    monkeypatch.setattr(
        collaboration_http,
        "PostgresCollaborationRepository",
        repository_factory,
    )
    session_factory = cast(async_sessionmaker[AsyncSession], FakeSessionFactory(transactions))
    settings = Settings.model_validate(
        {
            "environment": "test",
            "demo_mode": True,
            "demo_allow_insecure_cookie": True,
            "allowed_origins": [ORIGIN],
        }
    )
    app = FastAPI()

    @app.exception_handler(RequestValidationError)
    async def validation_problem(  # pyright: ignore[reportUnusedFunction]
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        response = collaboration_http.collaboration_request_validation_problem(request, error)
        assert response is not None
        return response

    app.include_router(collaboration_http.create_collaboration_router(settings, session_factory))
    with TestClient(app) as client:
        yield HttpHarness(app, client, repository, transactions)


def set_session(client: TestClient, role: ActorRole) -> None:
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE, f"opaque-{role.value}")


def mutation_headers(role: ActorRole, key: str = "bounded-key") -> dict[str, str]:
    return {
        "Origin": ORIGIN,
        "X-CSRF-Token": f"csrf-{role.value}",
        "Idempotency-Key": key,
    }


def proposal_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "case_revision": 1,
        "proposal": {
            "schema_version": 1,
            "fact_key": "family.risk_tolerance",
            "value": "high",
        },
    }


def verification_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "expected_case_revision": 1,
        "decision": "confirm",
        "reason": "The participant confirmed this bounded preference.",
    }


async def seed_real_http_cases() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    fixture_case = validate_planning_fixture().planning_input.case
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG_ID)},
            )
            actor_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM app.actors "
                    "WHERE organization_id=:org AND id IN (:advisor,:student,:parent)"
                ),
                {
                    "org": ORG_ID,
                    "advisor": ADVISOR_ID,
                    "student": STUDENT_ID,
                    "parent": PARENT_ID,
                },
            )
            assert actor_count == 3, "the HTTP suite requires the closed demo identity seed"
            existing = await connection.scalar(
                text(
                    "SELECT count(*) FROM app.student_cases "
                    "WHERE organization_id=:org AND id IN (:case,:unassigned)"
                ),
                {
                    "org": ORG_ID,
                    "case": REAL_CASE_ID,
                    "unassigned": REAL_UNASSIGNED_CASE_ID,
                },
            )
            assert existing == 0, "real HTTP fixtures must be isolated"
            for case_id in (REAL_CASE_ID, REAL_UNASSIGNED_CASE_ID):
                await connection.execute(
                    text(
                        "SELECT app.publish_case_revision("
                        ":org,:case,NULL,1,CAST(:student AS jsonb),CAST(:family AS jsonb))"
                    ),
                    {
                        "org": ORG_ID,
                        "case": case_id,
                        "student": json.dumps(fixture_case.student.model_dump(mode="json")),
                        "family": json.dumps(fixture_case.family.model_dump(mode="json")),
                    },
                )
            await connection.execute(
                text("SELECT app.seed_case_participants(:org,:case,:advisor,:student,:parent)"),
                {
                    "org": ORG_ID,
                    "case": REAL_CASE_ID,
                    "advisor": ADVISOR_ID,
                    "student": STUDENT_ID,
                    "parent": PARENT_ID,
                },
            )
    finally:
        await engine.dispose()


async def mint_real_session(
    sessions: async_sessionmaker[AsyncSession], choice: DemoActorChoice
) -> IssuedSession:
    async with sessions() as session, session.begin():
        return await IdentityService(IdentityRepository(session), "test-session-secret").mint(
            choice
        )


def set_real_session(client: AsyncClient, issued: IssuedSession) -> None:
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE, issued.raw_session_token)


def real_mutation_headers(issued: IssuedSession, key: str) -> dict[str, str]:
    return {
        "Origin": ORIGIN,
        "X-CSRF-Token": issued.raw_csrf_token,
        "Idempotency-Key": key,
    }


async def runtime_connection_snapshot(
    sessions: async_sessionmaker[AsyncSession],
) -> tuple[int, str | None, str | None, str | None]:
    async with sessions() as session:
        row = (
            await session.execute(
                text(
                    "SELECT pg_backend_pid(),"
                    "current_setting('night_voyager.organization_id',true),"
                    "current_setting('night_voyager.actor_id',true),"
                    "current_setting('night_voyager.role',true)"
                )
            )
        ).one()
    return cast(tuple[int, str | None, str | None, str | None], tuple(row))


def test_router_registers_exact_closed_http_surface(http_harness: HttpHarness) -> None:
    paths = cast(dict[str, dict[str, object]], http_harness.app.openapi()["paths"])
    actual = {
        (path, method)
        for path, operations in paths.items()
        for method in operations
        if method in {"get", "post"}
    }
    assert actual == {
        ("/api/v1/cases/{case_id}/collaboration-thread", "post"),
        ("/api/v1/cases/{case_id}/collaboration-thread", "get"),
        ("/api/v1/collaboration-threads/{thread_id}/messages", "get"),
        ("/api/v1/collaboration-threads/{thread_id}/messages", "post"),
        ("/api/v1/messages/{message_id}/memory-candidates", "post"),
        ("/api/v1/cases/{case_id}/memory-candidates", "get"),
        ("/api/v1/memory-candidates/{candidate_id}/verification-decisions", "post"),
        ("/api/v1/cases/{case_id}/confirmed-facts", "get"),
    }


@pytest.mark.parametrize(
    ("path", "role", "payload"),
    [
        (THREAD_PATH, ActorRole.ADVISOR, {"schema_version": 1}),
        (
            MESSAGES_PATH,
            ActorRole.PARENT,
            {"schema_version": 1, "body": "A bounded shared message."},
        ),
        (PROPOSAL_PATH, ActorRole.PARENT, proposal_payload()),
        (VERIFICATION_PATH, ActorRole.ADVISOR, verification_payload()),
    ],
)
def test_every_mutation_requires_origin_csrf_and_bounded_idempotency_key(
    http_harness: HttpHarness,
    path: str,
    role: ActorRole,
    payload: Mapping[str, object],
) -> None:
    set_session(http_harness.client, role)
    missing_origin = http_harness.client.post(
        path,
        headers={
            "X-CSRF-Token": f"csrf-{role.value}",
            "Idempotency-Key": "missing-origin",
        },
        json=dict(payload),
    )
    wrong_origin = http_harness.client.post(
        path,
        headers={**mutation_headers(role), "Origin": "https://example.invalid"},
        json=dict(payload),
    )
    missing_csrf = http_harness.client.post(
        path,
        headers={"Origin": ORIGIN, "Idempotency-Key": "missing-csrf"},
        json=dict(payload),
    )
    wrong_csrf = http_harness.client.post(
        path,
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": "wrong",
            "Idempotency-Key": "wrong-csrf",
        },
        json=dict(payload),
    )
    missing_key = http_harness.client.post(
        path,
        headers={"Origin": ORIGIN, "X-CSRF-Token": f"csrf-{role.value}"},
        json=dict(payload),
    )
    oversized_key = http_harness.client.post(
        path,
        headers=mutation_headers(role, "x" * 201),
        json=dict(payload),
    )

    assert [missing_origin.status_code, wrong_origin.status_code] == [403, 403]
    assert [missing_csrf.status_code, wrong_csrf.status_code] == [401, 401]
    assert [missing_key.status_code, oversized_key.status_code] == [400, 400]
    assert wrong_csrf.headers.get_list("set-cookie") == []
    for response in (
        missing_origin,
        wrong_origin,
        missing_csrf,
        wrong_csrf,
        missing_key,
        oversized_key,
    ):
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["content-type"].startswith("application/problem+json")
    assert http_harness.repository.calls == []


def test_strict_body_validation_uses_closed_problem_codes(
    http_harness: HttpHarness,
) -> None:
    set_session(http_harness.client, ActorRole.PARENT)
    extra = http_harness.client.post(
        MESSAGES_PATH,
        headers=mutation_headers(ActorRole.PARENT, "extra"),
        json={
            "schema_version": 1,
            "body": "A bounded shared message.",
            "actor_id": str(PARENT_ID),
        },
    )
    unsafe_message = http_harness.client.post(
        MESSAGES_PATH,
        headers=mutation_headers(ActorRole.PARENT, "unsafe-message"),
        json={"schema_version": 1, "body": "https://user:pass@example.invalid"},
    )
    oversized_message = http_harness.client.post(
        MESSAGES_PATH,
        headers=mutation_headers(ActorRole.PARENT, "oversized-message"),
        json={"schema_version": 1, "body": "x" * 4097},
    )
    unsupported_fact = http_harness.client.post(
        PROPOSAL_PATH,
        headers=mutation_headers(ActorRole.PARENT, "unsupported-fact"),
        json={
            **proposal_payload(),
            "proposal": {
                "schema_version": 1,
                "fact_key": "family.unbounded",
                "value": "high",
            },
        },
    )
    unsafe_fact = http_harness.client.post(
        PROPOSAL_PATH,
        headers=mutation_headers(ActorRole.PARENT, "unsafe-fact"),
        json={
            **proposal_payload(),
            "proposal": {
                "schema_version": 1,
                "fact_key": "student.intended_field",
                "value": "https://example.invalid/profile",
            },
        },
    )
    set_session(http_harness.client, ActorRole.ADVISOR)
    unsafe_reason = http_harness.client.post(
        VERIFICATION_PATH,
        headers=mutation_headers(ActorRole.ADVISOR, "unsafe-reason"),
        json={
            **verification_payload(),
            "reason": "https://example.invalid/reason",
        },
    )

    assert extra.json()["code"] == "request_validation_failed"
    assert unsafe_message.json()["code"] == "invalid_collaboration_message"
    assert oversized_message.json()["code"] == "invalid_collaboration_message"
    assert unsupported_fact.json()["code"] == "unsupported_fact_key"
    assert unsafe_fact.json()["code"] == "unsafe_fact_value"
    assert unsafe_reason.json()["code"] == "unsafe_fact_value"
    for response in (
        extra,
        unsafe_message,
        oversized_message,
        unsupported_fact,
        unsafe_fact,
        unsafe_reason,
    ):
        assert response.status_code == 422
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["content-type"].startswith("application/problem+json")
    assert http_harness.repository.calls == []
    assert http_harness.transactions == []


def test_happy_path_exposes_shared_messages_and_role_safe_projections(
    http_harness: HttpHarness,
) -> None:
    set_session(http_harness.client, ActorRole.ADVISOR)
    created = http_harness.client.post(
        THREAD_PATH,
        headers=mutation_headers(ActorRole.ADVISOR, "create-thread"),
        json={"schema_version": 1},
    )
    assert created.status_code == 201

    set_session(http_harness.client, ActorRole.PARENT)
    thread = http_harness.client.get(THREAD_PATH)
    appended = http_harness.client.post(
        MESSAGES_PATH,
        headers=mutation_headers(ActorRole.PARENT, "append-message"),
        json={"schema_version": 1, "body": "A bounded shared message."},
    )
    page = http_harness.client.get(f"{MESSAGES_PATH}?after_sequence=1&limit=2")
    proposed = http_harness.client.post(
        PROPOSAL_PATH,
        headers=mutation_headers(ActorRole.PARENT, "propose-candidate"),
        json=proposal_payload(),
    )
    parent_candidates = http_harness.client.get(CANDIDATES_PATH)
    assert thread.status_code == 200
    assert appended.status_code == 201
    assert [item["sequence_no"] for item in page.json()["items"]] == [2, 3]
    assert page.json()["next_after_sequence"] == 3
    assert set(proposed.json()) == {
        "schema_version",
        "fact_key",
        "value",
        "state",
        "created_at",
        "expires_at",
    }
    assert set(parent_candidates.json()[0]) == set(proposed.json())

    set_session(http_harness.client, ActorRole.STUDENT)
    student_messages = http_harness.client.get(MESSAGES_PATH)
    student_candidates = http_harness.client.get(CANDIDATES_PATH)
    assert student_messages.json()["items"][0]["body"] == "Shared bounded message 1"
    assert student_candidates.json() == []

    set_session(http_harness.client, ActorRole.ADVISOR)
    advisor_candidates = http_harness.client.get(CANDIDATES_PATH)
    verified = http_harness.client.post(
        VERIFICATION_PATH,
        headers=mutation_headers(ActorRole.ADVISOR, "verify-candidate"),
        json=verification_payload(),
    )
    advisor_facts = http_harness.client.get(FACTS_PATH)
    assert set(advisor_candidates.json()[0]) > set(parent_candidates.json()[0])
    assert verified.status_code == 201
    assert verified.json()["result_fact_id"] is not None
    assert verified.json()["result_revision"] == 2
    assert {
        "candidate_id",
        "verification_id",
        "source_message_event_id",
        "source_message_sequence_no",
        "source_message_sha256_prefix",
        "confirming_advisor_actor_id",
        "reason",
        "supersedes_fact_id",
    } <= set(advisor_facts.json()[0])

    set_session(http_harness.client, ActorRole.PARENT)
    parent_facts = http_harness.client.get(FACTS_PATH)
    assert set(parent_facts.json()[0]) == {
        "schema_version",
        "fact_key",
        "value",
        "fact_version",
        "confirmed_at",
        "subject_role",
        "confirming_advisor_role",
    }
    assert all(
        response.headers["cache-control"] == "no-store"
        for response in (
            created,
            thread,
            appended,
            page,
            proposed,
            parent_candidates,
            student_messages,
            student_candidates,
            advisor_candidates,
            verified,
            advisor_facts,
            parent_facts,
        )
    )
    assert set(http_harness.transactions) == {"commit"}


@pytest.mark.database
@pytest.mark.asyncio
async def test_real_http_surface_uses_identity_postgres_rls_and_closed_sqlstates() -> None:
    """The public surface must cross the runtime role, not a fake repository seam."""
    assert os.environ.get("NIGHT_VOYAGER_DEMO_SEED_READY") == "1"
    await seed_real_http_cases()
    url = os.environ["NIGHT_VOYAGER_API_DATABASE_URL"]
    engine = create_async_engine(url, pool_size=1, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings.model_validate(
        {
            "environment": "test",
            "database_url": url,
            "demo_mode": True,
            "demo_allow_insecure_cookie": True,
            "allowed_origins": [ORIGIN],
            "secret_key": "test-session-secret",
        }
    )
    participant_candidate_fields = {
        "schema_version",
        "fact_key",
        "value",
        "state",
        "created_at",
        "expires_at",
    }
    participant_fact_fields = {
        "schema_version",
        "fact_key",
        "value",
        "fact_version",
        "confirmed_at",
        "subject_role",
        "confirming_advisor_role",
    }
    try:
        advisor = await mint_real_session(sessions, DemoActorChoice.ADVISOR)
        student = await mint_real_session(sessions, DemoActorChoice.STUDENT)
        parent = await mint_real_session(sessions, DemoActorChoice.PARENT)
        revoked = await mint_real_session(sessions, DemoActorChoice.PARENT)
        initial_snapshot = await runtime_connection_snapshot(sessions)
        app = create_app(settings=settings, session_factory=sessions)
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            thread_path = f"/api/v1/cases/{REAL_CASE_ID}/collaboration-thread"

            set_real_session(client, parent)
            wrong_role = await client.post(
                thread_path,
                headers=real_mutation_headers(parent, "real-parent-cannot-create"),
                json={"schema_version": 1},
            )
            assert (wrong_role.status_code, wrong_role.json()["code"]) == (
                404,
                "resource_unavailable",
            )

            set_real_session(client, advisor)
            unassigned = await client.get(
                f"/api/v1/cases/{REAL_UNASSIGNED_CASE_ID}/collaboration-thread"
            )
            assert (unassigned.status_code, unassigned.json()["code"]) == (
                404,
                "resource_unavailable",
            )
            rollback_snapshot = await runtime_connection_snapshot(sessions)
            create_headers = real_mutation_headers(advisor, "real-create-thread")
            created = await client.post(
                thread_path,
                headers=create_headers,
                json={"schema_version": 1},
            )
            create_replay = await client.post(
                thread_path,
                headers=create_headers,
                json={"schema_version": 1},
            )
            assert created.status_code == create_replay.status_code == 201
            assert create_replay.json() == created.json()
            successful_snapshot = await runtime_connection_snapshot(sessions)
            assert (
                initial_snapshot[0]
                == rollback_snapshot[0]
                == successful_snapshot[0]
            )
            for snapshot in (rollback_snapshot, successful_snapshot):
                assert all(value in (None, "") for value in snapshot[1:])
            thread_id = UUID(created.json()["thread_id"])

            set_real_session(client, student)
            thread = await client.get(thread_path)
            assert thread.status_code == 200
            assert UUID(thread.json()["thread_id"]) == thread_id

            set_real_session(client, parent)
            messages_path = f"/api/v1/collaboration-threads/{thread_id}/messages"
            append_headers = real_mutation_headers(parent, "real-append-message")
            append_payload = {
                "schema_version": 1,
                "body": "Our family can accept a bounded high-risk option.",
            }
            appended = await client.post(
                messages_path,
                headers=append_headers,
                json=append_payload,
            )
            append_replay = await client.post(
                messages_path,
                headers=append_headers,
                json=append_payload,
            )
            assert appended.status_code == append_replay.status_code == 201
            assert append_replay.json() == appended.json()
            message_id = UUID(appended.json()["message_event_id"])

            set_real_session(client, student)
            first_page = await client.get(f"{messages_path}?after_sequence=0&limit=1")
            final_page = await client.get(f"{messages_path}?after_sequence=1&limit=1")
            assert [item["sequence_no"] for item in first_page.json()["items"]] == [1]
            assert first_page.json()["next_after_sequence"] == 1
            assert final_page.json() == {
                "schema_version": 1,
                "items": [],
                "next_after_sequence": None,
            }

            set_real_session(client, parent)
            proposal_path = f"/api/v1/messages/{message_id}/memory-candidates"
            proposal_headers = real_mutation_headers(parent, "real-propose-candidate")
            real_proposal = proposal_payload()
            proposed = await client.post(
                proposal_path,
                headers=proposal_headers,
                json=real_proposal,
            )
            proposal_replay = await client.post(
                proposal_path,
                headers=proposal_headers,
                json=real_proposal,
            )
            assert proposed.status_code == proposal_replay.status_code == 201
            assert proposal_replay.json() == proposed.json()
            assert set(proposed.json()) == participant_candidate_fields

            candidates_path = f"/api/v1/cases/{REAL_CASE_ID}/memory-candidates"
            parent_candidates = await client.get(candidates_path)
            assert len(parent_candidates.json()) == 1
            assert set(parent_candidates.json()[0]) == participant_candidate_fields

            set_real_session(client, student)
            student_candidates = await client.get(candidates_path)
            assert student_candidates.json() == []

            set_real_session(client, advisor)
            advisor_candidates = await client.get(candidates_path)
            assert len(advisor_candidates.json()) == 1
            assert set(advisor_candidates.json()[0]) > participant_candidate_fields
            candidate_id = UUID(advisor_candidates.json()[0]["candidate_id"])
            verification_path = f"/api/v1/memory-candidates/{candidate_id}/verification-decisions"
            verification_headers = real_mutation_headers(advisor, "real-confirm-candidate")
            real_verification = verification_payload()
            verified = await client.post(
                verification_path,
                headers=verification_headers,
                json=real_verification,
            )
            verification_replay = await client.post(
                verification_path,
                headers=verification_headers,
                json=real_verification,
            )
            assert verified.status_code == verification_replay.status_code == 201
            assert verified.json()["replayed"] is False
            assert verification_replay.json()["replayed"] is True
            assert (
                verification_replay.json()["verification_id"] == verified.json()["verification_id"]
            )
            assert verification_replay.json()["result_fact_id"] == verified.json()["result_fact_id"]
            assert verified.json()["result_revision"] == 2

            facts_path = f"/api/v1/cases/{REAL_CASE_ID}/confirmed-facts"
            advisor_facts = await client.get(facts_path)
            assert len(advisor_facts.json()) == 1
            assert set(advisor_facts.json()[0]) > participant_fact_fields

            set_real_session(client, parent)
            parent_facts = await client.get(facts_path)
            assert len(parent_facts.json()) == 1
            assert set(parent_facts.json()[0]) == participant_fact_fields

            set_real_session(client, advisor)
            stale = await client.post(
                f"/api/v1/memory-candidates/{REAL_STALE_CANDIDATE_ID}"
                "/verification-decisions",
                headers=real_mutation_headers(advisor, "real-stale-candidate"),
                json=verification_payload(),
            )
            assert (stale.status_code, stale.json()["code"]) == (
                409,
                "memory_candidate_stale",
            )

            async with sessions() as session, session.begin():
                await IdentityService(IdentityRepository(session), "test-session-secret").revoke(
                    revoked.raw_session_token, revoked.raw_csrf_token
                )
            set_real_session(client, revoked)
            revoked_read = await client.get(thread_path)
            assert revoked_read.status_code == 401
            assert revoked_read.json()["code"] == "authentication_failed"
            assert len(revoked_read.headers.get_list("set-cookie")) == 2

            for response in (
                wrong_role,
                unassigned,
                created,
                create_replay,
                thread,
                appended,
                append_replay,
                first_page,
                final_page,
                proposed,
                proposal_replay,
                parent_candidates,
                student_candidates,
                advisor_candidates,
                verified,
                verification_replay,
                advisor_facts,
                parent_facts,
                stale,
                revoked_read,
            ):
                assert response.headers["cache-control"] == "no-store"

        async with engine.connect() as connection:
            assert await connection.scalar(text("SELECT current_user")) == "night_voyager_api"
            with pytest.raises(DBAPIError) as denied:
                await connection.execute(text("SELECT * FROM app.collaboration_threads"))
            assert getattr(denied.value.orig, "sqlstate", None) == "42501"
    finally:
        await engine.dispose()


def test_wrong_role_is_non_enumerating_and_rolls_back(
    http_harness: HttpHarness,
) -> None:
    set_session(http_harness.client, ActorRole.PARENT)
    create = http_harness.client.post(
        THREAD_PATH,
        headers=mutation_headers(ActorRole.PARENT, "parent-create"),
        json={"schema_version": 1},
    )
    verify = http_harness.client.post(
        VERIFICATION_PATH,
        headers=mutation_headers(ActorRole.PARENT, "parent-verify"),
        json=verification_payload(),
    )
    set_session(http_harness.client, ActorRole.ADVISOR)
    propose = http_harness.client.post(
        PROPOSAL_PATH,
        headers=mutation_headers(ActorRole.ADVISOR, "advisor-propose"),
        json=proposal_payload(),
    )

    for response in (create, verify, propose):
        assert response.status_code == 404
        assert response.json()["code"] == "resource_unavailable"
        assert response.headers["cache-control"] == "no-store"
    assert http_harness.repository.calls == []
    assert http_harness.transactions == ["rollback", "rollback", "rollback"]


@pytest.mark.parametrize(
    ("failure", "status_code", "code"),
    [
        (CollaborationAuthorizationError("sensitive detail"), 404, "resource_unavailable"),
        (CaseRevisionStaleError("sensitive detail"), 409, "case_revision_stale"),
        (MemoryCandidateStaleError("sensitive detail"), 409, "memory_candidate_stale"),
        (MemoryCandidateExpiredError("sensitive detail"), 409, "memory_candidate_expired"),
        (MemoryCandidateTerminalError("sensitive detail"), 409, "memory_candidate_terminal"),
        (ActiveTaskBlocksRevisionError("sensitive detail"), 409, "active_task_blocks_revision"),
        (
            InvalidCollaborationMessageError("sensitive detail"),
            422,
            "invalid_collaboration_message",
        ),
        (UnsupportedFactKeyError("sensitive detail"), 422, "unsupported_fact_key"),
        (UnsafeFactValueError("sensitive detail"), 422, "unsafe_fact_value"),
        (IdempotencyConflictError("sensitive detail"), 409, "idempotency_conflict"),
        (CollaborationPersistenceError("sensitive detail"), 503, "persistence_unavailable"),
        (SQLAlchemyError("database detail"), 503, "persistence_unavailable"),
    ],
)
def test_error_mapping_is_closed_redacted_and_rolls_back(
    http_harness: HttpHarness,
    failure: Exception,
    status_code: int,
    code: str,
) -> None:
    http_harness.repository.failure = failure
    set_session(http_harness.client, ActorRole.ADVISOR)
    response = http_harness.client.get(THREAD_PATH)

    assert response.status_code == status_code
    assert response.json()["code"] == code
    assert response.headers["cache-control"] == "no-store"
    assert "sensitive detail" not in response.text
    assert "database detail" not in response.text
    assert http_harness.transactions == ["rollback"]


def test_expired_session_clears_both_cookies_but_wrong_csrf_does_not(
    http_harness: HttpHarness,
) -> None:
    http_harness.client.cookies.set(SESSION_COOKIE, "expired-session")
    http_harness.client.cookies.set(BOOTSTRAP_COOKIE, "stale-bootstrap")
    expired_read = http_harness.client.get(THREAD_PATH)
    expired_cookies = expired_read.headers.get_list("set-cookie")

    assert expired_read.status_code == 401
    assert expired_read.json()["code"] == "authentication_failed"
    assert len(expired_cookies) == 2
    assert any(f"{SESSION_COOKIE}=" in value and "Max-Age=0" in value for value in expired_cookies)
    assert any(
        f"{BOOTSTRAP_COOKIE}=" in value and "Max-Age=0" in value for value in expired_cookies
    )

    http_harness.client.cookies.set(SESSION_COOKIE, "expired-session")
    http_harness.client.cookies.set(BOOTSTRAP_COOKIE, "stale-bootstrap")
    expired_mutation = http_harness.client.post(
        THREAD_PATH,
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": "expired-csrf",
            "Idempotency-Key": "expired-mutation",
        },
        json={"schema_version": 1},
    )
    assert expired_mutation.status_code == 401
    assert len(expired_mutation.headers.get_list("set-cookie")) == 2

    set_session(http_harness.client, ActorRole.ADVISOR)
    wrong_csrf = http_harness.client.post(
        THREAD_PATH,
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": "wrong",
            "Idempotency-Key": "wrong-csrf",
        },
        json={"schema_version": 1},
    )
    assert wrong_csrf.status_code == 401
    assert wrong_csrf.headers.get_list("set-cookie") == []
    assert http_harness.transactions == ["rollback", "rollback", "rollback"]


@pytest.mark.parametrize(
    "query",
    (
        "after_sequence=-1",
        "after_sequence=not-an-integer",
        "limit=0",
        "limit=101",
        "limit=not-an-integer",
    ),
)
def test_message_pagination_rejects_unstable_or_unbounded_queries(
    http_harness: HttpHarness, query: str
) -> None:
    response = http_harness.client.get(f"{MESSAGES_PATH}?{query}")

    assert response.status_code == 422
    assert response.json()["code"] == "request_validation_failed"
    assert response.headers["cache-control"] == "no-store"
    assert http_harness.repository.calls == []
    assert http_harness.transactions == []
