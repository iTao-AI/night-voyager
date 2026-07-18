from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Literal, Protocol
from uuid import UUID

from fastapi import APIRouter, Cookie, Header, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, PositiveInt, field_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.responses import JSONResponse

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
from night_voyager.skills.application import SkillService
from night_voyager.skills.errors import (
    SkillActivationStaleError,
    SkillAuthorizationError,
    SkillCandidateStaleError,
    SkillCandidateTerminalError,
    SkillError,
    SkillEvaluationFailedError,
    SkillIdempotencyConflictError,
    SkillPersistenceError,
    SkillPinInvalidError,
    SkillRollbackUnsupportedError,
    SkillScopeExpansionError,
    SkillVersionUnavailableError,
)
from night_voyager.skills.evaluation import SkillEvaluator
from night_voyager.skills.models import (
    SemanticVersion,
    SkillChangeProvenance,
    SkillKey,
)
from night_voyager.skills.ports import (
    ActivateSkillCandidateCommand,
    CreateSkillCandidateCommand,
    EvaluateSkillCandidateCommand,
    PlanningSkillInspectorV1,
    RollbackSkillCommand,
    SkillActivationRecordedV1,
    SkillCandidateCreatedV1,
    SkillCatalogDetailV1,
    SkillCatalogV1,
    SkillEvaluationRecordedV1,
)
from night_voyager.skills.postgres import PostgresSkillRepository
from night_voyager.skills.registry import SkillRuntimeRegistry


class StrictRequestModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


def _bounded_text(value: str, *, field: str) -> str:
    if not 1 <= len(value.encode("utf-8")) <= 512:
        raise ValueError(f"{field} must contain 1..512 UTF-8 bytes")
    return value


class CreateSkillCandidateRequest(StrictRequestModel):
    schema_version: Literal[1]
    proposed_version: SemanticVersion
    provenance: SkillChangeProvenance
    reason: str
    reference: str | None = None

    @field_validator("provenance", mode="before")
    @classmethod
    def parse_json_provenance(cls, value: object) -> object:
        if type(value) is str:
            return SkillChangeProvenance(value)
        return value

    @field_validator("reason")
    @classmethod
    def bounded_reason(cls, value: str) -> str:
        return _bounded_text(value, field="reason")

    @field_validator("reference")
    @classmethod
    def bounded_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _bounded_text(value, field="reference")


class EvaluateSkillCandidateRequest(StrictRequestModel):
    schema_version: Literal[1]


class ActivateSkillCandidateRequest(StrictRequestModel):
    schema_version: Literal[1]
    expected_active_version: SemanticVersion
    expected_activation_sequence: PositiveInt
    reason: str

    @field_validator("reason")
    @classmethod
    def bounded_reason(cls, value: str) -> str:
        return _bounded_text(value, field="reason")


class RollbackSkillRequest(StrictRequestModel):
    schema_version: Literal[1]
    target_version: SemanticVersion
    expected_active_version: SemanticVersion
    expected_activation_sequence: PositiveInt
    reason: str

    @field_validator("reason")
    @classmethod
    def bounded_reason(cls, value: str) -> str:
        return _bounded_text(value, field="reason")


class _ExpiredSessionError(Exception):
    pass


def is_skills_http_path(path: str) -> bool:
    if path == "/api/v1/skills":
        return True
    if path.startswith("/api/v1/skills/"):
        return True
    if path.startswith("/api/v1/skill-change-candidates/") and path.endswith(
        ("/evaluations", "/activations")
    ):
        return True
    return path.startswith("/api/v1/cases/") and path.endswith(
        "/planning-skill-inspector"
    )


def skills_request_validation_problem(
    request: Request,
    _error: RequestValidationError,
) -> JSONResponse | None:
    if not is_skills_http_path(request.url.path):
        return None
    return problem(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "request_validation_failed",
        "request validation failed",
    )


def _expired_session_problem() -> JSONResponse:
    response = problem(
        status.HTTP_401_UNAUTHORIZED,
        "authentication_failed",
        "authentication failed",
    )
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(BOOTSTRAP_COOKIE, path="/")
    return response


def _runtime_problem(error: BaseException) -> JSONResponse:
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

    mappings: tuple[tuple[type[SkillError], int, str], ...] = (
        (SkillAuthorizationError, status.HTTP_404_NOT_FOUND, "resource_unavailable"),
        (
            SkillVersionUnavailableError,
            status.HTTP_409_CONFLICT,
            "skill_version_unavailable",
        ),
        (SkillCandidateStaleError, status.HTTP_409_CONFLICT, "skill_candidate_stale"),
        (
            SkillCandidateTerminalError,
            status.HTTP_409_CONFLICT,
            "skill_candidate_terminal",
        ),
        (
            SkillEvaluationFailedError,
            status.HTTP_409_CONFLICT,
            "skill_evaluation_failed",
        ),
        (
            SkillActivationStaleError,
            status.HTTP_409_CONFLICT,
            "skill_activation_stale",
        ),
        (SkillScopeExpansionError, status.HTTP_409_CONFLICT, "skill_scope_expansion"),
        (
            SkillRollbackUnsupportedError,
            status.HTTP_409_CONFLICT,
            "skill_rollback_unsupported",
        ),
        (SkillPinInvalidError, status.HTTP_409_CONFLICT, "skill_pin_invalid"),
        (
            SkillIdempotencyConflictError,
            status.HTTP_409_CONFLICT,
            "idempotency_conflict",
        ),
        (
            SkillPersistenceError,
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "persistence_unavailable",
        ),
    )
    if isinstance(error, SkillError):
        for error_type, status_code, code in mappings:
            if isinstance(error, error_type):
                detail = (
                    "resource unavailable"
                    if code == "resource_unavailable"
                    else "persistence unavailable"
                    if code == "persistence_unavailable"
                    else "request conflicts with current state"
                )
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


class SkillApplication(Protocol):
    async def list_catalog(self, context: ActorContext) -> SkillCatalogV1: ...

    async def get_catalog_item(
        self, context: ActorContext, skill_key: SkillKey
    ) -> SkillCatalogDetailV1: ...

    async def create_candidate(
        self,
        context: ActorContext,
        command: CreateSkillCandidateCommand,
        idempotency_key: str,
    ) -> SkillCandidateCreatedV1: ...

    async def evaluate_candidate(
        self,
        context: ActorContext,
        command: EvaluateSkillCandidateCommand,
        idempotency_key: str,
    ) -> SkillEvaluationRecordedV1: ...

    async def activate_candidate(
        self,
        context: ActorContext,
        command: ActivateSkillCandidateCommand,
        idempotency_key: str,
    ) -> SkillActivationRecordedV1: ...

    async def rollback_skill(
        self,
        context: ActorContext,
        command: RollbackSkillCommand,
        idempotency_key: str,
    ) -> SkillActivationRecordedV1: ...

    async def inspect_planning_skill(
        self, context: ActorContext, case_id: UUID
    ) -> PlanningSkillInspectorV1: ...


SkillServiceFactory = Callable[[AsyncSession], SkillApplication]


def create_skills_router(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    service_factory: SkillServiceFactory | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    if service_factory is None:
        registry = SkillRuntimeRegistry.load_packaged()
        evaluator = SkillEvaluator.load_packaged(registry)

        def default_service_factory(session: AsyncSession) -> SkillApplication:
            return SkillService(
                PostgresSkillRepository(session),
                registry=registry,
                evaluator=evaluator,
            )

        resolved_service_factory: SkillServiceFactory = default_service_factory
    else:
        resolved_service_factory = service_factory

    async def read_context(
        session: AsyncSession,
        raw_session: str | None,
    ) -> ActorContext:
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
                and csrf is not None
                and await identity.resolve(raw_session) is None
            ):
                raise _ExpiredSessionError from error
            raise

    async def run_read[T](
        raw_session: str | None,
        operation: Callable[[ActorContext, SkillApplication], Awaitable[T]],
    ) -> T | JSONResponse:
        try:
            async with session_factory() as session, session.begin():
                context = await read_context(session, raw_session)
                return await operation(context, resolved_service_factory(session))
        except (
            HTTPException,
            _ExpiredSessionError,
            SkillError,
            SQLAlchemyError,
            Exception,
        ) as error:
            return _runtime_problem(error)

    async def run_mutation[T](
        raw_session: str | None,
        csrf: str | None,
        operation: Callable[[ActorContext, SkillApplication], Awaitable[T]],
    ) -> T | JSONResponse:
        try:
            async with session_factory() as session, session.begin():
                context = await mutation_context(session, raw_session, csrf)
                return await operation(context, resolved_service_factory(session))
        except (
            HTTPException,
            _ExpiredSessionError,
            SkillError,
            SQLAlchemyError,
            Exception,
        ) as error:
            return _runtime_problem(error)

    def guard_mutation(
        request: Request,
        idempotency_key: str | None,
    ) -> JSONResponse | None:
        return _mutation_guard(request, idempotency_key, settings.allowed_origins)

    def require_skill_key(raw: str) -> SkillKey:
        try:
            return SkillKey(raw)
        except ValueError as error:
            raise SkillAuthorizationError("resource_unavailable") from error

    @router.get("/skills", response_model=SkillCatalogV1)
    async def list_catalog(  # pyright: ignore[reportUnusedFunction]
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> SkillCatalogV1 | JSONResponse:
        result = await run_read(
            raw_session,
            lambda context, service: service.list_catalog(context),
        )
        if isinstance(result, JSONResponse):
            return result
        response.headers["Cache-Control"] = "no-store"
        return result

    @router.get("/skills/{skill_key}", response_model=SkillCatalogDetailV1)
    async def get_catalog_item(  # pyright: ignore[reportUnusedFunction]
        skill_key: str,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> SkillCatalogDetailV1 | JSONResponse:
        result = await run_read(
            raw_session,
            lambda context, service: service.get_catalog_item(
                context, require_skill_key(skill_key)
            ),
        )
        if isinstance(result, JSONResponse):
            return result
        response.headers["Cache-Control"] = "no-store"
        return result

    @router.post(
        "/skills/{skill_key}/change-candidates",
        status_code=status.HTTP_201_CREATED,
        response_model=SkillCandidateCreatedV1,
    )
    async def create_candidate(  # pyright: ignore[reportUnusedFunction]
        skill_key: str,
        payload: CreateSkillCandidateRequest,
        request: Request,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> SkillCandidateCreatedV1 | JSONResponse:
        guarded = guard_mutation(request, idempotency_key)
        if guarded is not None:
            return guarded
        assert idempotency_key is not None
        result = await run_mutation(
            raw_session,
            csrf,
            lambda context, service: service.create_candidate(
                context,
                CreateSkillCandidateCommand(
                    skill_key=require_skill_key(skill_key),
                    proposed_version=payload.proposed_version,
                    provenance=payload.provenance,
                    reason=payload.reason,
                    reference=payload.reference,
                ),
                idempotency_key,
            ),
        )
        if isinstance(result, JSONResponse):
            return result
        response.headers["Cache-Control"] = "no-store"
        return result

    @router.post(
        "/skill-change-candidates/{candidate_id}/evaluations",
        status_code=status.HTTP_201_CREATED,
        response_model=SkillEvaluationRecordedV1,
    )
    async def evaluate_candidate(  # pyright: ignore[reportUnusedFunction]
        candidate_id: UUID,
        _payload: EvaluateSkillCandidateRequest,
        request: Request,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> SkillEvaluationRecordedV1 | JSONResponse:
        guarded = guard_mutation(request, idempotency_key)
        if guarded is not None:
            return guarded
        assert idempotency_key is not None
        result = await run_mutation(
            raw_session,
            csrf,
            lambda context, service: service.evaluate_candidate(
                context,
                EvaluateSkillCandidateCommand(candidate_id=candidate_id),
                idempotency_key,
            ),
        )
        if isinstance(result, JSONResponse):
            return result
        response.headers["Cache-Control"] = "no-store"
        return result

    @router.post(
        "/skill-change-candidates/{candidate_id}/activations",
        status_code=status.HTTP_201_CREATED,
        response_model=SkillActivationRecordedV1,
    )
    async def activate_candidate(  # pyright: ignore[reportUnusedFunction]
        candidate_id: UUID,
        payload: ActivateSkillCandidateRequest,
        request: Request,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> SkillActivationRecordedV1 | JSONResponse:
        guarded = guard_mutation(request, idempotency_key)
        if guarded is not None:
            return guarded
        assert idempotency_key is not None
        command = ActivateSkillCandidateCommand(
            candidate_id=candidate_id,
            expected_active_version=payload.expected_active_version,
            expected_activation_sequence=payload.expected_activation_sequence,
            reason=payload.reason,
        )
        result = await run_mutation(
            raw_session,
            csrf,
            lambda context, service: service.activate_candidate(
                context, command, idempotency_key
            ),
        )
        if isinstance(result, JSONResponse):
            return result
        response.headers["Cache-Control"] = "no-store"
        return result

    @router.post(
        "/skills/{skill_key}/rollbacks",
        status_code=status.HTTP_201_CREATED,
        response_model=SkillActivationRecordedV1,
    )
    async def rollback_skill(  # pyright: ignore[reportUnusedFunction]
        skill_key: str,
        payload: RollbackSkillRequest,
        request: Request,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> SkillActivationRecordedV1 | JSONResponse:
        guarded = guard_mutation(request, idempotency_key)
        if guarded is not None:
            return guarded
        assert idempotency_key is not None
        result = await run_mutation(
            raw_session,
            csrf,
            lambda context, service: service.rollback_skill(
                context,
                RollbackSkillCommand(
                    skill_key=require_skill_key(skill_key),
                    target_version=payload.target_version,
                    expected_active_version=payload.expected_active_version,
                    expected_activation_sequence=payload.expected_activation_sequence,
                    reason=payload.reason,
                ),
                idempotency_key,
            ),
        )
        if isinstance(result, JSONResponse):
            return result
        response.headers["Cache-Control"] = "no-store"
        return result

    @router.get(
        "/cases/{case_id}/planning-skill-inspector",
        response_model=PlanningSkillInspectorV1,
    )
    async def inspect_planning_skill(  # pyright: ignore[reportUnusedFunction]
        case_id: UUID,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> PlanningSkillInspectorV1 | JSONResponse:
        result = await run_read(
            raw_session,
            lambda context, service: service.inspect_planning_skill(context, case_id),
        )
        if isinstance(result, JSONResponse):
            return result
        response.headers["Cache-Control"] = "no-store"
        return result

    return router


__all__ = [
    "ActivateSkillCandidateRequest",
    "CreateSkillCandidateRequest",
    "EvaluateSkillCandidateRequest",
    "RollbackSkillRequest",
    "create_skills_router",
    "is_skills_http_path",
    "skills_request_validation_problem",
]
