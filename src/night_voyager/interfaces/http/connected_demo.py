from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Cookie, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.responses import JSONResponse

from night_voyager.config import Settings
from night_voyager.connected_demo.application import ConnectedDemoService
from night_voyager.connected_demo.errors import DemoContractUnavailableError
from night_voyager.connected_demo.models import AdvisorLedgerV1, CurrentDecisionBriefV1
from night_voyager.connected_demo.postgres import PostgresConnectedDemoRepository
from night_voyager.identity.models import ActorContext
from night_voyager.identity.repository import IdentityRepository
from night_voyager.identity.service import IdentityService
from night_voyager.interfaces.http.decision import problem
from night_voyager.interfaces.http.dependencies import resolve_actor_context
from night_voyager.interfaces.http.identity import BOOTSTRAP_COOKIE, SESSION_COOKIE


def create_connected_demo_router(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    async def read_context(
        session: AsyncSession, raw_session: str | None
    ) -> ActorContext:
        service = IdentityService(IdentityRepository(session), settings.secret_key)
        return await resolve_actor_context(raw_session, service)

    def expired_session_response() -> JSONResponse:
        expired = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "authentication failed"},
        )
        expired.delete_cookie(SESSION_COOKIE, path="/")
        expired.delete_cookie(BOOTSTRAP_COOKIE, path="/")
        return expired

    @router.get("/cases/{case_id}/advisor-ledger", response_model=AdvisorLedgerV1)
    async def advisor_ledger(  # pyright: ignore[reportUnusedFunction]
        case_id: UUID,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> AdvisorLedgerV1 | JSONResponse:
        try:
            async with session_factory() as session, session.begin():
                context = await read_context(session, raw_session)
                projection = await ConnectedDemoService(
                    PostgresConnectedDemoRepository(session)
                ).advisor_ledger(context, case_id)
        except HTTPException as error:
            if error.status_code == status.HTTP_401_UNAUTHORIZED:
                return expired_session_response()
            raise
        except DemoContractUnavailableError:
            return problem(
                503, "demo_contract_unavailable", "connected demo contract unavailable"
            )
        if projection is None:
            return problem(404, "resource_unavailable", "resource unavailable")
        response.headers["Cache-Control"] = "no-store"
        return projection

    @router.get(
        "/cases/{case_id}/current-decision-brief",
        response_model=CurrentDecisionBriefV1,
    )
    async def current_decision_brief(  # pyright: ignore[reportUnusedFunction]
        case_id: UUID,
        response: Response,
        raw_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> CurrentDecisionBriefV1 | JSONResponse:
        try:
            async with session_factory() as session, session.begin():
                context = await read_context(session, raw_session)
                projection = await ConnectedDemoService(
                    PostgresConnectedDemoRepository(session)
                ).current_decision_brief(context, case_id)
        except HTTPException as error:
            if error.status_code == status.HTTP_401_UNAUTHORIZED:
                return expired_session_response()
            raise
        except DemoContractUnavailableError:
            return problem(
                503, "demo_contract_unavailable", "connected demo contract unavailable"
            )
        if projection is None:
            return problem(404, "resource_unavailable", "resource unavailable")
        response.headers["Cache-Control"] = "no-store"
        return projection

    return router
