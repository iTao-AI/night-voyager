from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Cookie, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, PositiveInt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.responses import JSONResponse, StreamingResponse

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
from night_voyager.interfaces.http.identity import SESSION_COOKIE
from night_voyager.skills.registry import SkillRuntimeRegistry
from night_voyager.tasks.application import (
    CancelTaskCommand,
    CreateTaskCommand,
    TaskService,
)
from night_voyager.tasks.errors import TaskAuthorizationError, TaskConflictError
from night_voyager.tasks.models import PlanningOperation
from night_voyager.tasks.postgres import PostgresTaskRepository
from night_voyager.tasks.streaming import (
    EventCursorAheadError,
    PostgresTaskEventReader,
    parse_last_event_id,
    stream_task_events,
)

EVENTS_PATH = "/tasks/{task_id}/events"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateAgentTaskRequest(StrictModel):
    schema_version: Literal[1]
    operation: PlanningOperation
    expected_case_revision: PositiveInt
    source_pack_id: UUID
    source_pack_version: PositiveInt
    policy_version: Literal["m3a-policy-v1"]


class CancelAgentTaskRequest(StrictModel):
    schema_version: Literal[1]
    expected_row_version: PositiveInt


def create_task_router(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    registry: SkillRuntimeRegistry | None = None

    def task_registry() -> SkillRuntimeRegistry:
        nonlocal registry
        if registry is None:
            registry = SkillRuntimeRegistry.load_packaged()
        return registry

    def enforce_origin(request: Request) -> None:
        try:
            require_origin(request.headers.get("Origin"), settings.allowed_origins)
        except ValueError as error:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "request rejected") from error

    def valid_idempotency_key(value: str | None) -> bool:
        return value is not None and 0 < len(value) <= 200

    async def mutation_context(
        session: AsyncSession, raw_session: str | None, csrf: str | None
    ) -> ActorContext:
        service = IdentityService(IdentityRepository(session), settings.secret_key)
        return await resolve_mutation_actor_context(raw_session, csrf, service)

    async def read_context(session: AsyncSession, raw_session: str | None) -> ActorContext:
        service = IdentityService(IdentityRepository(session), settings.secret_key)
        return await resolve_actor_context(raw_session, service)

    @router.post(
        "/cases/{case_id}/agent-tasks",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=None,
    )
    async def create_agent_task(  # pyright: ignore[reportUnusedFunction]
        case_id: UUID,
        payload: CreateAgentTaskRequest,
        request: Request,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, object] | JSONResponse:
        enforce_origin(request)
        if not valid_idempotency_key(idempotency_key):
            return problem(400, "invalid_idempotency_key", "Idempotency-Key is required")
        assert idempotency_key is not None
        async with session_factory() as session, session.begin():
            context = await mutation_context(session, raw_session, csrf)
            command = CreateTaskCommand(
                case_id=case_id,
                operation=payload.operation,
                expected_case_revision=payload.expected_case_revision,
                source_pack_id=payload.source_pack_id,
                source_pack_version=payload.source_pack_version,
                policy_version=payload.policy_version,
            )
            try:
                result = await TaskService(
                    PostgresTaskRepository(session), registry=task_registry()
                ).create(context, command, idempotency_key)
            except TaskAuthorizationError:
                return problem(404, "resource_unavailable", "resource unavailable")
            except TaskConflictError as error:
                return problem(409, error.code.lower(), "request conflicts with current state")
        response.headers["Cache-Control"] = "no-store"
        return {"schema_version": 1, **result}

    @router.get("/tasks/{task_id}", response_model=None)
    async def get_agent_task(  # pyright: ignore[reportUnusedFunction]
        task_id: UUID,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> dict[str, object] | JSONResponse:
        async with session_factory() as session, session.begin():
            context = await read_context(session, raw_session)
            try:
                result = await TaskService(
                    PostgresTaskRepository(session), registry=task_registry()
                ).get(context, task_id)
            except TaskAuthorizationError:
                result = None
        if result is None:
            return problem(404, "resource_unavailable", "resource unavailable")
        response.headers["Cache-Control"] = "no-store"
        return {"schema_version": 1, **result}

    @router.post("/tasks/{task_id}/cancel", response_model=None)
    async def cancel_agent_task(  # pyright: ignore[reportUnusedFunction]
        task_id: UUID,
        payload: CancelAgentTaskRequest,
        request: Request,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, object] | JSONResponse:
        enforce_origin(request)
        if not valid_idempotency_key(idempotency_key):
            return problem(400, "invalid_idempotency_key", "Idempotency-Key is required")
        assert idempotency_key is not None
        async with session_factory() as session, session.begin():
            context = await mutation_context(session, raw_session, csrf)
            try:
                result = await TaskService(
                    PostgresTaskRepository(session), registry=task_registry()
                ).cancel(
                    context,
                    CancelTaskCommand(
                        task_id=task_id,
                        expected_row_version=payload.expected_row_version,
                    ),
                    idempotency_key,
                )
            except TaskAuthorizationError:
                return problem(404, "resource_unavailable", "resource unavailable")
            except TaskConflictError as error:
                return problem(409, error.code.lower(), "request conflicts with current state")
        response.headers["Cache-Control"] = "no-store"
        return {"schema_version": 1, **result}

    @router.get(EVENTS_PATH, response_model=None)
    async def stream_agent_task_events(  # pyright: ignore[reportUnusedFunction]
        task_id: UUID,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    ) -> StreamingResponse | JSONResponse:
        try:
            cursor = parse_last_event_id(last_event_id)
        except ValueError:
            return problem(400, "invalid_last_event_id", "Last-Event-ID is invalid")
        async with session_factory() as session, session.begin():
            context = await read_context(session, raw_session)
            try:
                initial_page = await PostgresTaskEventReader(session).read_page(
                    context, task_id, cursor
                )
            except TaskAuthorizationError:
                return problem(404, "resource_unavailable", "resource unavailable")
            except EventCursorAheadError:
                return problem(
                    409,
                    "event_cursor_ahead",
                    "Last-Event-ID is ahead of the durable event stream",
                )

        async def load_page(after: int):
            async with session_factory() as session, session.begin():
                await IdentityRepository(session).set_actor_context(context)
                return await PostgresTaskEventReader(session).read_page(context, task_id, after)

        return StreamingResponse(
            stream_task_events(load_page, initial_page, after=cursor),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-store",
                "X-Accel-Buffering": "no",
            },
        )

    return router
