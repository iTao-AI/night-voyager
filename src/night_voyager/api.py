from collections.abc import Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from night_voyager.config import Settings
from night_voyager.database import create_engine, create_session_factory
from night_voyager.interfaces.http.decision import create_decision_router
from night_voyager.interfaces.http.decision import problem as decision_problem
from night_voyager.interfaces.http.identity import (
    IdentityServiceProtocol,
    create_identity_router,
    default_service_factory,
)


def create_app(
    *,
    settings: Settings | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    identity_service_factory: Callable[[AsyncSession | None], IdentityServiceProtocol]
    | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings()
    if session_factory is None and identity_service_factory is None:
        session_factory = create_session_factory(create_engine(resolved_settings.database_url))
    service_factory = identity_service_factory or default_service_factory(resolved_settings)
    app = FastAPI(title="Night Voyager API", version="0.1.0")

    @app.exception_handler(HTTPException)
    async def http_exception_handler(  # pyright: ignore[reportUnusedFunction]
        request: Request, error: HTTPException
    ):
        if request.url.path.startswith("/api/v1/cases/") or request.url.path.startswith(
            "/api/v1/decision-briefs/"
        ):
            code = "authentication_failed" if error.status_code == 401 else "request_rejected"
            return decision_problem(error.status_code, code, str(error.detail))
        from starlette.responses import JSONResponse

        return JSONResponse(status_code=error.status_code, content={"detail": error.detail})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(  # pyright: ignore[reportUnusedFunction]
        request: Request, error: RequestValidationError
    ):
        if request.url.path.startswith("/api/v1/cases/") or request.url.path.startswith(
            "/api/v1/decision-briefs/"
        ):
            return decision_problem(422, "request_validation_failed", "request validation failed")
        from fastapi.exception_handlers import request_validation_exception_handler

        return await request_validation_exception_handler(request, error)

    def health() -> dict[str, str]:
        return {"service": "night-voyager-api", "status": "ok"}

    app.add_api_route("/health", health, methods=["GET"])
    app.include_router(create_identity_router(resolved_settings, session_factory, service_factory))
    if session_factory is not None:
        app.include_router(create_decision_router(resolved_settings, session_factory))
    return app


app = create_app()
