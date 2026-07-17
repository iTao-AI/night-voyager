from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Cookie, Header, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, PositiveInt, ValidationError, field_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.responses import JSONResponse

from night_voyager.collaboration.application import CollaborationService
from night_voyager.collaboration.errors import (
    ActiveTaskBlocksRevisionError,
    CaseRevisionStaleError,
    CollaborationAuthorizationError,
    CollaborationError,
    CollaborationPersistenceError,
    CollaborationThreadFullError,
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
    ConfirmedFactAdvisorPageV1,
    ConfirmedFactHistoryCursorV1,
    ConfirmedFactParticipantPageV1,
    FactProposal,
    MemoryCandidateAdvisorV1,
    MemoryCandidateParticipantV1,
    MessageEventV1,
    MessagePageV1,
    ProposeMemoryCandidateCommand,
    VerificationDecision,
    VerifyMemoryCandidateCommand,
)
from night_voyager.collaboration.ports import MemoryCandidateVerificationV1
from night_voyager.collaboration.postgres import PostgresCollaborationRepository
from night_voyager.config import Settings
from night_voyager.identity.auth import require_origin
from night_voyager.identity.models import ActorContext
from night_voyager.identity.repository import IdentityRepository
from night_voyager.identity.service import IdentityService
from night_voyager.interfaces.http.decision import problem
from night_voyager.interfaces.http.dependencies import (
    resolve_actor_context,
    resolve_mutation_actor_context,
)
from night_voyager.interfaces.http.identity import BOOTSTRAP_COOKIE, SESSION_COOKIE


class StrictModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class CreateCollaborationThreadRequest(StrictModel):
    schema_version: Literal[1]


class AppendMessageRequest(StrictModel):
    schema_version: Literal[1]
    body: str


class ProposeMemoryCandidateRequest(StrictModel):
    schema_version: Literal[1]
    case_revision: PositiveInt
    proposal: FactProposal


class VerifyMemoryCandidateRequest(StrictModel):
    schema_version: Literal[1]
    expected_case_revision: PositiveInt
    decision: VerificationDecision
    reason: str

    @field_validator("decision", mode="before")
    @classmethod
    def parse_json_decision(cls, value: object) -> object:
        if type(value) is str:
            return VerificationDecision(value)
        return value


class _ExpiredSessionError(Exception):
    pass


def is_collaboration_http_path(path: str) -> bool:
    if path.startswith("/api/v1/cases/") and path.endswith(
        ("/collaboration-thread", "/memory-candidates", "/confirmed-facts")
    ):
        return True
    return (
        (path.startswith("/api/v1/collaboration-threads/") and path.endswith("/messages"))
        or (path.startswith("/api/v1/messages/") and path.endswith("/memory-candidates"))
        or (
            path.startswith("/api/v1/memory-candidates/")
            and path.endswith("/verification-decisions")
        )
    )


def collaboration_request_validation_problem(
    request: Request, error: RequestValidationError
) -> JSONResponse | None:
    if not is_collaboration_http_path(request.url.path):
        return None

    code = "request_validation_failed"
    detail = "request validation failed"
    path = request.url.path
    for issue in error.errors():
        location = tuple(issue.get("loc", ()))
        issue_type = issue.get("type")
        if (
            request.method == "POST"
            and path.startswith("/api/v1/collaboration-threads/")
            and path.endswith("/messages")
            and location[:2] == ("body", "body")
        ):
            code = "invalid_collaboration_message"
            detail = "collaboration message is invalid"
            break
        if (
            request.method == "POST"
            and path.startswith("/api/v1/messages/")
            and path.endswith("/memory-candidates")
            and location[:2] == ("body", "proposal")
        ):
            if issue_type in {"union_tag_invalid", "union_tag_not_found"}:
                code = "unsupported_fact_key"
                detail = "fact key is unsupported"
                break
            if "value" in location[2:]:
                code = "unsafe_fact_value"
                detail = "fact value is unsafe"
                break
        if (
            request.method == "POST"
            and path.startswith("/api/v1/memory-candidates/")
            and path.endswith("/verification-decisions")
            and location[:2] == ("body", "reason")
        ):
            code = "unsafe_fact_value"
            detail = "fact value is unsafe"
            break
    return problem(status.HTTP_422_UNPROCESSABLE_CONTENT, code, detail)


def _expired_session_problem() -> JSONResponse:
    response = problem(
        status.HTTP_401_UNAUTHORIZED,
        "authentication_failed",
        "authentication failed",
    )
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(BOOTSTRAP_COOKIE, path="/")
    return response


def _runtime_problem(
    error: HTTPException | _ExpiredSessionError | CollaborationError | SQLAlchemyError,
) -> JSONResponse:
    if isinstance(error, _ExpiredSessionError):
        return _expired_session_problem()
    if isinstance(error, HTTPException):
        code = (
            "authentication_failed"
            if error.status_code == status.HTTP_401_UNAUTHORIZED
            else "request_rejected"
        )
        detail = "authentication failed" if error.status_code == 401 else "request rejected"
        return problem(error.status_code, code, detail)

    mappings: tuple[tuple[type[CollaborationError], int, str, str], ...] = (
        (
            CollaborationAuthorizationError,
            status.HTTP_404_NOT_FOUND,
            "resource_unavailable",
            "resource unavailable",
        ),
        (
            CaseRevisionStaleError,
            status.HTTP_409_CONFLICT,
            "case_revision_stale",
            "request conflicts with current state",
        ),
        (
            MemoryCandidateStaleError,
            status.HTTP_409_CONFLICT,
            "memory_candidate_stale",
            "request conflicts with current state",
        ),
        (
            MemoryCandidateExpiredError,
            status.HTTP_409_CONFLICT,
            "memory_candidate_expired",
            "request conflicts with current state",
        ),
        (
            MemoryCandidateTerminalError,
            status.HTTP_409_CONFLICT,
            "memory_candidate_terminal",
            "request conflicts with current state",
        ),
        (
            CollaborationThreadFullError,
            status.HTTP_409_CONFLICT,
            "collaboration_thread_full",
            "collaboration thread is full",
        ),
        (
            ActiveTaskBlocksRevisionError,
            status.HTTP_409_CONFLICT,
            "active_task_blocks_revision",
            "request conflicts with current state",
        ),
        (
            InvalidCollaborationMessageError,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_collaboration_message",
            "collaboration message is invalid",
        ),
        (
            UnsupportedFactKeyError,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "unsupported_fact_key",
            "fact key is unsupported",
        ),
        (
            UnsafeFactValueError,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "unsafe_fact_value",
            "fact value is unsafe",
        ),
        (
            IdempotencyConflictError,
            status.HTTP_409_CONFLICT,
            "idempotency_conflict",
            "request conflicts with current state",
        ),
        (
            CollaborationPersistenceError,
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "persistence_unavailable",
            "persistence unavailable",
        ),
    )
    if isinstance(error, CollaborationError):
        for error_type, status_code, code, detail in mappings:
            if isinstance(error, error_type):
                return problem(status_code, code, detail)
    return problem(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "persistence_unavailable",
        "persistence unavailable",
    )


def _mutation_guard(
    request: Request,
    idempotency_key: str | None,
    allowed_origins: tuple[str, ...],
) -> JSONResponse | None:
    try:
        require_origin(request.headers.get("Origin"), allowed_origins)
    except ValueError:
        return problem(status.HTTP_403_FORBIDDEN, "request_rejected", "request rejected")
    if idempotency_key is None or not 1 <= len(idempotency_key) <= 200:
        return problem(
            status.HTTP_400_BAD_REQUEST,
            "invalid_idempotency_key",
            "Idempotency-Key is required",
        )
    return None


def create_collaboration_router(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    async def read_context(session: AsyncSession, raw_session: str | None) -> ActorContext:
        identity = IdentityService(IdentityRepository(session), settings.secret_key)
        try:
            return await resolve_actor_context(raw_session, identity)
        except HTTPException as error:
            if error.status_code == status.HTTP_401_UNAUTHORIZED and raw_session is not None:
                raise _ExpiredSessionError from error
            raise

    async def mutation_context(
        session: AsyncSession,
        raw_session: str | None,
        csrf: str | None,
    ) -> ActorContext:
        identity = IdentityService(IdentityRepository(session), settings.secret_key)
        try:
            return await resolve_mutation_actor_context(raw_session, csrf, identity)
        except HTTPException as error:
            if (
                error.status_code == status.HTTP_401_UNAUTHORIZED
                and raw_session is not None
                and await identity.resolve(raw_session) is None
            ):
                raise _ExpiredSessionError from error
            raise

    async def run_read[T](
        raw_session: str | None,
        operation: Callable[[ActorContext, CollaborationService], Awaitable[T]],
    ) -> T | JSONResponse:
        try:
            async with session_factory() as session, session.begin():
                context = await read_context(session, raw_session)
                service = CollaborationService(PostgresCollaborationRepository(session))
                return await operation(context, service)
        except (HTTPException, _ExpiredSessionError, CollaborationError, SQLAlchemyError) as error:
            return _runtime_problem(error)

    async def run_mutation[T](
        raw_session: str | None,
        csrf: str | None,
        operation: Callable[[ActorContext, CollaborationService], Awaitable[T]],
    ) -> T | JSONResponse:
        try:
            async with session_factory() as session, session.begin():
                context = await mutation_context(session, raw_session, csrf)
                service = CollaborationService(PostgresCollaborationRepository(session))
                return await operation(context, service)
        except (HTTPException, _ExpiredSessionError, CollaborationError, SQLAlchemyError) as error:
            return _runtime_problem(error)

    def guard_mutation(request: Request, idempotency_key: str | None) -> JSONResponse | None:
        return _mutation_guard(request, idempotency_key, settings.allowed_origins)

    @router.post(
        "/cases/{case_id}/collaboration-thread",
        status_code=status.HTTP_201_CREATED,
        response_model=CollaborationThreadV1,
    )
    async def create_thread(  # pyright: ignore[reportUnusedFunction]
        case_id: UUID,
        payload: CreateCollaborationThreadRequest,
        request: Request,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> CollaborationThreadV1 | JSONResponse:
        guarded = guard_mutation(request, idempotency_key)
        if guarded is not None:
            return guarded
        assert idempotency_key is not None
        result = await run_mutation(
            raw_session,
            csrf,
            lambda context, service: service.create_thread(context, case_id, idempotency_key),
        )
        if isinstance(result, JSONResponse):
            return result
        response.headers["Cache-Control"] = "no-store"
        return result

    @router.get(
        "/cases/{case_id}/collaboration-thread",
        response_model=CollaborationThreadV1,
    )
    async def get_thread(  # pyright: ignore[reportUnusedFunction]
        case_id: UUID,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> CollaborationThreadV1 | JSONResponse:
        result = await run_read(
            raw_session,
            lambda context, service: service.get_thread(context, case_id),
        )
        if isinstance(result, JSONResponse):
            return result
        if result is None:
            return problem(404, "resource_unavailable", "resource unavailable")
        response.headers["Cache-Control"] = "no-store"
        return result

    @router.get(
        "/collaboration-threads/{thread_id}/messages",
        response_model=MessagePageV1,
    )
    async def list_messages(  # pyright: ignore[reportUnusedFunction]
        thread_id: UUID,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        after_sequence: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> MessagePageV1 | JSONResponse:
        result = await run_read(
            raw_session,
            lambda context, service: service.list_messages(
                context,
                thread_id,
                after_sequence=after_sequence,
                limit=limit,
            ),
        )
        if isinstance(result, JSONResponse):
            return result
        response.headers["Cache-Control"] = "no-store"
        return result

    @router.post(
        "/collaboration-threads/{thread_id}/messages",
        status_code=status.HTTP_201_CREATED,
        response_model=MessageEventV1,
        responses={
            status.HTTP_409_CONFLICT: {
                "description": "Collaboration thread capacity conflict",
                "content": {
                    "application/problem+json": {
                        "example": {
                            "type": "https://night-voyager.invalid/problems/collaboration_thread_full",
                            "title": "Request could not be completed",
                            "status": 409,
                            "detail": "collaboration thread is full",
                            "code": "collaboration_thread_full",
                        }
                    }
                },
            }
        },
    )
    async def append_message(  # pyright: ignore[reportUnusedFunction]
        thread_id: UUID,
        payload: AppendMessageRequest,
        request: Request,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> MessageEventV1 | JSONResponse:
        guarded = guard_mutation(request, idempotency_key)
        if guarded is not None:
            return guarded
        try:
            command = AppendMessageCommand(thread_id=thread_id, body=payload.body)
        except ValidationError:
            return problem(
                422,
                "invalid_collaboration_message",
                "collaboration message is invalid",
            )
        assert idempotency_key is not None
        result = await run_mutation(
            raw_session,
            csrf,
            lambda context, service: service.append_message(context, command, idempotency_key),
        )
        if isinstance(result, JSONResponse):
            return result
        response.headers["Cache-Control"] = "no-store"
        return result

    @router.post(
        "/messages/{message_id}/memory-candidates",
        status_code=status.HTTP_201_CREATED,
        response_model=MemoryCandidateParticipantV1,
    )
    async def propose_candidate(  # pyright: ignore[reportUnusedFunction]
        message_id: UUID,
        payload: ProposeMemoryCandidateRequest,
        request: Request,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> MemoryCandidateParticipantV1 | JSONResponse:
        guarded = guard_mutation(request, idempotency_key)
        if guarded is not None:
            return guarded
        try:
            command = ProposeMemoryCandidateCommand(
                message_event_id=message_id,
                case_revision=payload.case_revision,
                proposal=payload.proposal,
            )
        except ValidationError:
            return problem(422, "unsafe_fact_value", "fact value is unsafe")
        assert idempotency_key is not None
        result = await run_mutation(
            raw_session,
            csrf,
            lambda context, service: service.propose_candidate(context, command, idempotency_key),
        )
        if isinstance(result, JSONResponse):
            return result
        response.headers["Cache-Control"] = "no-store"
        return result

    @router.get(
        "/cases/{case_id}/memory-candidates",
        response_model=list[MemoryCandidateAdvisorV1 | MemoryCandidateParticipantV1],
    )
    async def list_candidates(  # pyright: ignore[reportUnusedFunction]
        case_id: UUID,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> tuple[MemoryCandidateAdvisorV1 | MemoryCandidateParticipantV1, ...] | JSONResponse:
        result = await run_read(
            raw_session,
            lambda context, service: service.list_candidates(context, case_id, limit=limit),
        )
        if isinstance(result, JSONResponse):
            return result
        response.headers["Cache-Control"] = "no-store"
        return result

    @router.post(
        "/memory-candidates/{candidate_id}/verification-decisions",
        status_code=status.HTTP_201_CREATED,
        response_model=MemoryCandidateVerificationV1,
    )
    async def verify_candidate(  # pyright: ignore[reportUnusedFunction]
        candidate_id: UUID,
        payload: VerifyMemoryCandidateRequest,
        request: Request,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> MemoryCandidateVerificationV1 | JSONResponse:
        guarded = guard_mutation(request, idempotency_key)
        if guarded is not None:
            return guarded
        try:
            command = VerifyMemoryCandidateCommand(
                candidate_id=candidate_id,
                expected_case_revision=payload.expected_case_revision,
                decision=payload.decision,
                reason=payload.reason,
            )
        except ValidationError:
            return problem(422, "unsafe_fact_value", "fact value is unsafe")
        assert idempotency_key is not None
        result = await run_mutation(
            raw_session,
            csrf,
            lambda context, service: service.verify_candidate(context, command, idempotency_key),
        )
        if isinstance(result, JSONResponse):
            return result
        response.headers["Cache-Control"] = "no-store"
        return result

    @router.get(
        "/cases/{case_id}/confirmed-facts",
        response_model=ConfirmedFactAdvisorPageV1 | ConfirmedFactParticipantPageV1,
    )
    async def list_confirmed_facts(  # pyright: ignore[reportUnusedFunction]
        case_id: UUID,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        cursor: Annotated[
            str | None,
            Query(min_length=1, max_length=512, pattern=r"^[A-Za-z0-9_-]+$"),
        ] = None,
    ) -> ConfirmedFactAdvisorPageV1 | ConfirmedFactParticipantPageV1 | JSONResponse:
        try:
            decoded_cursor = (
                ConfirmedFactHistoryCursorV1.decode(cursor) if cursor is not None else None
            )
        except ValueError:
            return problem(422, "request_validation_failed", "request validation failed")
        result = await run_read(
            raw_session,
            lambda context, service: service.list_confirmed_facts(
                context,
                case_id,
                limit=limit,
                cursor=decoded_cursor,
            ),
        )
        if isinstance(result, JSONResponse):
            return result
        response.headers["Cache-Control"] = "no-store"
        return result

    return router


__all__ = [
    "AppendMessageRequest",
    "CreateCollaborationThreadRequest",
    "ProposeMemoryCandidateRequest",
    "VerifyMemoryCandidateRequest",
    "collaboration_request_validation_problem",
    "create_collaboration_router",
    "is_collaboration_http_path",
]
