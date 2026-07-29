from __future__ import annotations

from collections.abc import Awaitable
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Cookie, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, PositiveInt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.responses import JSONResponse

from night_voyager.config import Settings
from night_voyager.identity.auth import require_origin
from night_voyager.identity.models import ActorContext
from night_voyager.identity.repository import IdentityRepository
from night_voyager.identity.service import IdentityService
from night_voyager.interfaces.http.dependencies import (
    resolve_actor_context,
    resolve_mutation_actor_context,
)
from night_voyager.interfaces.http.identity import SESSION_COOKIE
from night_voyager.timeline_execution.application import TimelineExecutionService
from night_voyager.timeline_execution.errors import (
    TimelineExecutionConflictError,
    TimelineExecutionProjectionError,
    TimelineExecutionUnavailableError,
)
from night_voyager.timeline_execution.models import (
    CheckpointAttestationCode,
    CheckpointAttestationKind,
    CheckpointAttestationReasonCode,
    CheckpointStatusCode,
    CheckpointVerificationAction,
    CheckpointVerificationReasonCode,
    ReassessmentTrigger,
    TimelineMutationReceiptV1,
)
from night_voyager.timeline_execution.ports import (
    AttestTimelineCheckpointCommand,
    RequestTimelineReassessmentCommand,
    StartTimelineExecutionCommand,
    VerifyTimelineCheckpointCommand,
)
from night_voyager.timeline_execution.postgres import (
    PostgresTimelineExecutionRepository,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StartTimelineExecutionRequest(StrictModel):
    schema_version: Literal[1]
    case_id: UUID
    expected_case_revision: PositiveInt


class AttestTimelineCheckpointRequest(StrictModel):
    schema_version: Literal[1]
    case_id: UUID
    checkpoint_id: UUID
    expected_execution_version: PositiveInt
    expected_checkpoint_version: PositiveInt
    attestation_kind: CheckpointAttestationKind
    status_code: CheckpointStatusCode
    attestation_code: CheckpointAttestationCode
    reason_code: CheckpointAttestationReasonCode


class VerifyTimelineCheckpointRequest(StrictModel):
    schema_version: Literal[1]
    case_id: UUID
    checkpoint_id: UUID
    attestation_id: UUID
    expected_execution_version: PositiveInt
    expected_checkpoint_version: PositiveInt
    action: CheckpointVerificationAction
    reason_code: CheckpointVerificationReasonCode


class RequestTimelineReassessmentRequest(StrictModel):
    schema_version: Literal[1]
    case_id: UUID
    checkpoint_id: UUID
    expected_execution_version: PositiveInt
    expected_checkpoint_version: PositiveInt
    trigger: ReassessmentTrigger
    trigger_reference_id: UUID | None


def problem(status_code: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        media_type="application/problem+json",
        content={
            "type": f"https://night-voyager.invalid/problems/{code}",
            "title": "Request could not be completed",
            "status": status_code,
            "detail": detail,
            "code": code,
        },
        headers={"Cache-Control": "no-store"},
    )


def is_timeline_execution_http_path(path: str) -> bool:
    return (
        path == "/api/v1/plan-execution-context"
        or "/timeline-execution" in path
        or "/timeline-plans/" in path
    )


def create_timeline_execution_router(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    def enforce_origin(request: Request) -> None:
        try:
            require_origin(request.headers.get("Origin"), settings.allowed_origins)
        except ValueError as error:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "request rejected") from error

    async def read_context(
        session: AsyncSession, raw_session: str | None
    ) -> ActorContext:
        return await resolve_actor_context(
            raw_session,
            IdentityService(IdentityRepository(session), settings.secret_key),
        )

    async def mutation_context(
        session: AsyncSession, raw_session: str | None, csrf: str | None
    ) -> ActorContext:
        return await resolve_mutation_actor_context(
            raw_session,
            csrf,
            IdentityService(IdentityRepository(session), settings.secret_key),
        )

    def require_idempotency(value: str | None) -> str | JSONResponse:
        if value is None or not 1 <= len(value.encode("utf-8")) <= 200:
            return problem(
                400, "invalid_idempotency_key", "Idempotency-Key is required"
            )
        return value

    async def mutation_result(
        operation: str,
        call: Awaitable[TimelineMutationReceiptV1],
    ) -> dict[str, object] | JSONResponse:
        try:
            receipt = await call
        except TimelineExecutionUnavailableError:
            return problem(404, "resource_unavailable", "resource unavailable")
        except TimelineExecutionProjectionError:
            return problem(
                409,
                "execution_projection_unavailable",
                "execution projection unavailable",
            )
        except TimelineExecutionConflictError as error:
            code = (
                "idempotency_conflict"
                if error.code == "NV008"
                else {
                    "start": "checkpoint_not_current",
                    "attest": "checkpoint_attestation_conflict",
                    "verify": "advisor_verification_required",
                    "reassess": "reassessment_required",
                }[operation]
            )
            return problem(409, code, "request conflicts with current state")
        return receipt.model_dump(mode="json")

    @router.get("/plan-execution-context", response_model=None)
    async def get_plan_execution_context(  # pyright: ignore[reportUnusedFunction]
        scenario: Literal["governed-plan-execution-v1"],
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> dict[str, object] | JSONResponse:
        async with session_factory() as session, session.begin():
            actor = await read_context(session, raw_session)
            try:
                result = await TimelineExecutionService(
                    PostgresTimelineExecutionRepository(session)
                ).context(actor, scenario)
            except (TimelineExecutionUnavailableError, TimelineExecutionProjectionError):
                return problem(
                    404,
                    "plan_execution_context_unavailable",
                    "plan execution context unavailable",
                )
        if result is None:
            return problem(
                404,
                "plan_execution_context_unavailable",
                "plan execution context unavailable",
            )
        response.headers["Cache-Control"] = "no-store"
        return result.model_dump(mode="json")

    @router.get("/cases/{case_id}/timeline-execution", response_model=None)
    async def get_timeline_execution(  # pyright: ignore[reportUnusedFunction]
        case_id: UUID,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> dict[str, object] | JSONResponse:
        async with session_factory() as session, session.begin():
            actor = await read_context(session, raw_session)
            try:
                result = await TimelineExecutionService(
                    PostgresTimelineExecutionRepository(session)
                ).read(actor, case_id)
            except TimelineExecutionProjectionError:
                return problem(
                    409,
                    "execution_projection_unavailable",
                    "execution projection unavailable",
                )
        if result is None:
            return problem(404, "resource_unavailable", "resource unavailable")
        response.headers["Cache-Control"] = "no-store"
        return result.model_dump(mode="json")

    @router.post("/timeline-plans/{timeline_plan_id}/executions", response_model=None)
    async def start_timeline_execution(  # pyright: ignore[reportUnusedFunction]
        timeline_plan_id: UUID,
        payload: StartTimelineExecutionRequest,
        request: Request,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, object] | JSONResponse:
        enforce_origin(request)
        key = require_idempotency(idempotency_key)
        if isinstance(key, JSONResponse):
            return key
        async with session_factory() as session, session.begin():
            actor = await mutation_context(session, raw_session, csrf)
            command = StartTimelineExecutionCommand(
                case_id=payload.case_id,
                timeline_plan_id=timeline_plan_id,
                expected_case_revision=payload.expected_case_revision,
                execution_id=uuid4(),
                receipt_id=uuid4(),
            )
            result = await mutation_result(
                "start",
                TimelineExecutionService(
                    PostgresTimelineExecutionRepository(session)
                ).start(actor, command, key),
            )
        response.headers["Cache-Control"] = "no-store"
        return result

    @router.post(
        "/timeline-executions/{execution_id}/checkpoint-attestations",
        response_model=None,
    )
    async def attest_timeline_checkpoint(  # pyright: ignore[reportUnusedFunction]
        execution_id: UUID,
        payload: AttestTimelineCheckpointRequest,
        request: Request,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, object] | JSONResponse:
        enforce_origin(request)
        key = require_idempotency(idempotency_key)
        if isinstance(key, JSONResponse):
            return key
        async with session_factory() as session, session.begin():
            actor = await mutation_context(session, raw_session, csrf)
            result = await mutation_result(
                "attest",
                TimelineExecutionService(
                    PostgresTimelineExecutionRepository(session)
                ).attest(
                    actor,
                    AttestTimelineCheckpointCommand(
                        **payload.model_dump(exclude={"schema_version"}),
                        execution_id=execution_id,
                        attestation_id=uuid4(),
                        receipt_id=uuid4(),
                    ),
                    key,
                ),
            )
        response.headers["Cache-Control"] = "no-store"
        return result

    @router.post(
        "/timeline-executions/{execution_id}/checkpoint-verifications",
        response_model=None,
    )
    async def verify_timeline_checkpoint(  # pyright: ignore[reportUnusedFunction]
        execution_id: UUID,
        payload: VerifyTimelineCheckpointRequest,
        request: Request,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, object] | JSONResponse:
        enforce_origin(request)
        key = require_idempotency(idempotency_key)
        if isinstance(key, JSONResponse):
            return key
        async with session_factory() as session, session.begin():
            actor = await mutation_context(session, raw_session, csrf)
            result = await mutation_result(
                "verify",
                TimelineExecutionService(
                    PostgresTimelineExecutionRepository(session)
                ).verify(
                    actor,
                    VerifyTimelineCheckpointCommand(
                        **payload.model_dump(exclude={"schema_version"}),
                        execution_id=execution_id,
                        verification_id=uuid4(),
                        receipt_id=uuid4(),
                    ),
                    key,
                ),
            )
        response.headers["Cache-Control"] = "no-store"
        return result

    @router.post(
        "/timeline-executions/{execution_id}/reassessments",
        response_model=None,
    )
    async def request_timeline_reassessment(  # pyright: ignore[reportUnusedFunction]
        execution_id: UUID,
        payload: RequestTimelineReassessmentRequest,
        request: Request,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, object] | JSONResponse:
        enforce_origin(request)
        key = require_idempotency(idempotency_key)
        if isinstance(key, JSONResponse):
            return key
        async with session_factory() as session, session.begin():
            actor = await mutation_context(session, raw_session, csrf)
            result = await mutation_result(
                "reassess",
                TimelineExecutionService(
                    PostgresTimelineExecutionRepository(session)
                ).reassess(
                    actor,
                    RequestTimelineReassessmentCommand(
                        **payload.model_dump(exclude={"schema_version"}),
                        execution_id=execution_id,
                        reassessment_id=uuid4(),
                        receipt_id=uuid4(),
                    ),
                    key,
                ),
            )
        response.headers["Cache-Control"] = "no-store"
        return result

    return router
