from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from fastapi import APIRouter, Cookie, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.responses import JSONResponse

from night_voyager.config import Settings
from night_voyager.identity.auth import generate_token, require_csrf, require_origin
from night_voyager.identity.errors import AuthenticationFailedError, StaleSessionError
from night_voyager.identity.models import DemoActorChoice
from night_voyager.identity.service import IdentityService, IssuedSession

SESSION_COOKIE = "night_voyager_session"
BOOTSTRAP_COOKIE = "night_voyager_csrf_bootstrap"


class IdentityServiceProtocol(Protocol):
    async def mint(self, choice: DemoActorChoice) -> IssuedSession: ...
    async def rotate(
        self, old_token: str, csrf_token: str, choice: DemoActorChoice
    ) -> IssuedSession: ...
    async def revoke(self, session_token: str, csrf_token: str) -> None: ...


ServiceFactory = Callable[[AsyncSession | None], IdentityServiceProtocol]


class DemoSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    demo_actor: DemoActorChoice


def create_identity_router(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession] | None,
    service_factory: ServiceFactory,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/demo")

    def enforce_demo(request: Request) -> None:
        if not settings.demo_mode:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "resource unavailable")
        try:
            require_origin(request.headers.get("Origin"), settings.allowed_origins)
        except ValueError as error:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "request rejected") from error

    @router.get("/session-bootstrap")
    async def bootstrap(  # pyright: ignore[reportUnusedFunction]
        request: Request, response: Response
    ) -> dict[str, str]:
        enforce_demo(request)
        token = generate_token()
        response.set_cookie(
            BOOTSTRAP_COOKIE,
            token,
            max_age=300,
            secure=settings.session_cookie_secure,
            httponly=True,
            samesite="lax",
            path="/",
        )
        return {"csrf_token": token}

    @router.post("/sessions", status_code=status.HTTP_201_CREATED, response_model=None)
    async def create_session(  # pyright: ignore[reportUnusedFunction]
        payload: DemoSessionRequest,
        request: Request,
        response: Response,
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        bootstrap_token: str | None = Cookie(default=None, alias=BOOTSTRAP_COOKIE),
        csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    ) -> dict[str, str] | JSONResponse:
        enforce_demo(request)
        if session_token is None:
            try:
                require_csrf(csrf_token, bootstrap_token)
            except ValueError as error:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "request rejected") from error
        try:
            issued = await _with_service(
                session_factory,
                service_factory,
                lambda service: (
                    service.mint(payload.demo_actor)
                    if session_token is None
                    else service.rotate(session_token, csrf_token or "", payload.demo_actor)
                ),
            )
        except StaleSessionError:
            return _stale_session_response()
        except AuthenticationFailedError as error:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication failed") from error
        response.set_cookie(
            SESSION_COOKIE,
            issued.raw_session_token,
            max_age=1800,
            secure=settings.session_cookie_secure,
            httponly=True,
            samesite="lax",
            path="/",
        )
        response.delete_cookie(BOOTSTRAP_COOKIE, path="/")
        return {
            "role": issued.context.role.value,
            "proof_mode": "synthetic-demo",
            "csrf_token": issued.raw_csrf_token,
        }

    @router.delete("/session", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
    async def delete_session(  # pyright: ignore[reportUnusedFunction]
        request: Request,
        response: Response,
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
        csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    ) -> None | JSONResponse:
        enforce_demo(request)
        if session_token is None or csrf_token is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication failed")
        try:
            await _with_service(
                session_factory,
                service_factory,
                lambda service: service.revoke(session_token, csrf_token),
            )
        except StaleSessionError:
            return _stale_session_response()
        except AuthenticationFailedError as error:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication failed") from error
        response.delete_cookie(SESSION_COOKIE, path="/")
        response.delete_cookie(BOOTSTRAP_COOKIE, path="/")

    return router


def _stale_session_response() -> JSONResponse:
    response = JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "authentication failed"},
    )
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(BOOTSTRAP_COOKIE, path="/")
    return response


async def _with_service[T](
    session_factory: async_sessionmaker[AsyncSession] | None,
    service_factory: ServiceFactory,
    operation: Callable[[IdentityServiceProtocol], Awaitable[T]],
) -> T:
    if session_factory is None:
        return await operation(service_factory(None))
    async with session_factory() as session, session.begin():
        return await operation(service_factory(session))


def default_service_factory(settings: Settings) -> ServiceFactory:
    from night_voyager.identity.repository import IdentityRepository

    def factory(session: AsyncSession | None) -> IdentityService:
        if session is None:
            raise RuntimeError("database session required")
        return IdentityService(IdentityRepository(session), settings.secret_key)

    return factory
