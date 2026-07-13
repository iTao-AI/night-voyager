from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Cookie, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, PositiveInt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.responses import JSONResponse

from night_voyager.config import Settings
from night_voyager.decision.application import DecisionService
from night_voyager.decision.errors import DecisionAuthorizationError, DecisionConflictError
from night_voyager.decision.models import (
    DecisionSource,
    EvidenceRiskAcceptance,
    FamilyDecisionCommand,
    ReviewAction,
    ReviewCommand,
)
from night_voyager.decision.postgres import PostgresDecisionRepository
from night_voyager.identity.auth import require_origin
from night_voyager.identity.models import ActorContext, ActorRole
from night_voyager.identity.repository import IdentityRepository
from night_voyager.identity.service import IdentityService
from night_voyager.interfaces.http.dependencies import (
    resolve_actor_context,
    resolve_mutation_actor_context,
)
from night_voyager.interfaces.http.identity import SESSION_COOKIE


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AdvisorReviewRequest(StrictModel):
    schema_version: Literal[1]
    planning_run_id: UUID
    expected_case_revision: PositiveInt
    action: ReviewAction
    eligible_route_ids: tuple[UUID, ...] = ()
    risk_acceptances: tuple[EvidenceRiskAcceptance, ...] = ()
    reviewer_notes: str | None = None


class FamilyDecisionRequest(StrictModel):
    schema_version: Literal[1]
    expected_brief_version: PositiveInt
    selected_route_id: UUID
    accepted_budget_min_minor: PositiveInt
    accepted_budget_max_minor: PositiveInt
    currency: Literal["CNY"]
    accepted_trade_offs: tuple[str, ...]


class AdvisorRecordedDecisionRequest(FamilyDecisionRequest):
    decision_made_by_actor_id: UUID
    source: Literal[DecisionSource.FAMILY_CONSULTATION]


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


def create_decision_router(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    def enforce_origin(request: Request) -> None:
        try:
            require_origin(request.headers.get("Origin"), settings.allowed_origins)
        except ValueError as error:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "request rejected") from error

    async def mutation_context(
        session: AsyncSession, raw_session: str | None, csrf: str | None
    ) -> ActorContext:
        service = IdentityService(IdentityRepository(session), settings.secret_key)
        return await resolve_mutation_actor_context(raw_session, csrf, service)

    async def read_context(session: AsyncSession, raw_session: str | None) -> ActorContext:
        service = IdentityService(IdentityRepository(session), settings.secret_key)
        return await resolve_actor_context(raw_session, service)

    @router.post("/cases/{case_id}/advisor-reviews", response_model=None)
    async def review_case(  # pyright: ignore[reportUnusedFunction]
        case_id: UUID,
        payload: AdvisorReviewRequest,
        request: Request,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, object] | JSONResponse:
        enforce_origin(request)
        if not idempotency_key or len(idempotency_key) > 200:
            return problem(400, "invalid_idempotency_key", "Idempotency-Key is required")
        async with session_factory() as session, session.begin():
            context = await mutation_context(session, raw_session, csrf)
            brief_id = uuid4() if payload.action is ReviewAction.APPROVE_FOR_CONSULTATION else None
            command = ReviewCommand(
                schema_version=1,
                case_id=case_id,
                planning_run_id=payload.planning_run_id,
                expected_case_revision=payload.expected_case_revision,
                action=payload.action,
                review_id=uuid4(),
                eligible_route_ids=payload.eligible_route_ids,
                risk_acceptances=payload.risk_acceptances,
                reviewer_notes=payload.reviewer_notes,
                brief_id=brief_id,
            )
            try:
                service = DecisionService(PostgresDecisionRepository(session))
                result = await service.review(context, command, idempotency_key)
            except DecisionAuthorizationError:
                return problem(404, "resource_unavailable", "resource unavailable")
            except DecisionConflictError as error:
                return problem(409, error.code.lower(), "request conflicts with current state")
        response.headers["Cache-Control"] = "no-store"
        return {"schema_version": 1, **result}

    @router.get("/decision-briefs/{brief_id}", response_model=None)
    async def get_brief(  # pyright: ignore[reportUnusedFunction]
        brief_id: UUID,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> dict[str, object] | JSONResponse:
        async with session_factory() as session, session.begin():
            context = await read_context(session, raw_session)
            result = await DecisionService(PostgresDecisionRepository(session)).get_brief(
                context, brief_id
            )
        if result is None:
            return problem(404, "resource_unavailable", "resource unavailable")
        response.headers["Cache-Control"] = "no-store"
        return {"schema_version": 1, **result}

    async def decide(
        brief_id: UUID,
        payload: FamilyDecisionRequest,
        context: ActorContext,
        service: DecisionService,
        idempotency_key: str,
        *,
        made_by: UUID,
        source: DecisionSource,
    ) -> dict[str, object] | JSONResponse:
        command = FamilyDecisionCommand(
            schema_version=1,
            brief_id=brief_id,
            expected_brief_version=payload.expected_brief_version,
            selected_route_id=payload.selected_route_id,
            accepted_budget_min_minor=payload.accepted_budget_min_minor,
            accepted_budget_max_minor=payload.accepted_budget_max_minor,
            currency=payload.currency,
            accepted_trade_offs=payload.accepted_trade_offs,
            decision_made_by_actor_id=made_by,
            source=source,
        )
        try:
            result = await (
                service.decide_direct(context, command, idempotency_key)
                if source is DecisionSource.DIRECT
                else service.decide_as_advisor(context, command, idempotency_key)
            )
        except LookupError:
            return problem(404, "resource_unavailable", "resource unavailable")
        except ValueError:
            return problem(409, "decision_policy_conflict", "request conflicts with current state")
        except DecisionAuthorizationError:
            return problem(404, "resource_unavailable", "resource unavailable")
        except DecisionConflictError as error:
            return problem(409, error.code.lower(), "request conflicts with current state")
        return {"schema_version": 1, **result}

    @router.post("/decision-briefs/{brief_id}/family-decisions", response_model=None)
    async def direct_decision(  # pyright: ignore[reportUnusedFunction]
        brief_id: UUID,
        payload: FamilyDecisionRequest,
        request: Request,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, object] | JSONResponse:
        enforce_origin(request)
        if not idempotency_key:
            return problem(400, "invalid_idempotency_key", "Idempotency-Key is required")
        async with session_factory() as session, session.begin():
            context = await mutation_context(session, raw_session, csrf)
            if context.role not in {ActorRole.STUDENT, ActorRole.PARENT}:
                return problem(404, "resource_unavailable", "resource unavailable")
            service = DecisionService(PostgresDecisionRepository(session))
            result = await decide(
                brief_id,
                payload,
                context,
                service,
                idempotency_key,
                made_by=context.actor_id,
                source=DecisionSource.DIRECT,
            )
        response.headers["Cache-Control"] = "no-store"
        return result

    @router.post("/decision-briefs/{brief_id}/advisor-recorded-decisions", response_model=None)
    async def advisor_decision(  # pyright: ignore[reportUnusedFunction]
        brief_id: UUID,
        payload: AdvisorRecordedDecisionRequest,
        request: Request,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, object] | JSONResponse:
        enforce_origin(request)
        if not idempotency_key:
            return problem(400, "invalid_idempotency_key", "Idempotency-Key is required")
        async with session_factory() as session, session.begin():
            context = await mutation_context(session, raw_session, csrf)
            if context.role is not ActorRole.ADVISOR:
                return problem(404, "resource_unavailable", "resource unavailable")
            service = DecisionService(PostgresDecisionRepository(session))
            result = await decide(
                brief_id,
                payload,
                context,
                service,
                idempotency_key,
                made_by=payload.decision_made_by_actor_id,
                source=DecisionSource.FAMILY_CONSULTATION,
            )
        response.headers["Cache-Control"] = "no-store"
        return result

    return router
