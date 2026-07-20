from collections.abc import Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from night_voyager.config import Settings
from night_voyager.database import create_engine, create_session_factory
from night_voyager.interfaces.http.collaboration import (
    collaboration_request_validation_problem,
    create_collaboration_router,
    is_collaboration_http_path,
)
from night_voyager.interfaces.http.connected_demo import create_connected_demo_router
from night_voyager.interfaces.http.decision import create_decision_router
from night_voyager.interfaces.http.decision import problem as decision_problem
from night_voyager.interfaces.http.dra import create_dra_router
from night_voyager.interfaces.http.identity import (
    IdentityServiceProtocol,
    create_identity_router,
    default_service_factory,
)
from night_voyager.interfaces.http.skills import (
    create_skills_router,
    is_skills_http_path,
    skills_request_validation_problem,
)
from night_voyager.interfaces.http.tasks import create_task_router


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
    app = FastAPI(title="Night Voyager API", version="0.1.2")

    def uses_problem_json(path: str) -> bool:
        return (
            path.startswith("/api/v1/cases/")
            or path.startswith("/api/v1/decision-briefs/")
            or path.startswith("/api/v1/tasks/")
            or is_collaboration_http_path(path)
            or is_skills_http_path(path)
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(  # pyright: ignore[reportUnusedFunction]
        request: Request, error: HTTPException
    ):
        if uses_problem_json(request.url.path):
            code = "authentication_failed" if error.status_code == 401 else "request_rejected"
            return decision_problem(error.status_code, code, str(error.detail))
        from starlette.responses import JSONResponse

        return JSONResponse(status_code=error.status_code, content={"detail": error.detail})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(  # pyright: ignore[reportUnusedFunction]
        request: Request, error: RequestValidationError
    ):
        collaboration_response = collaboration_request_validation_problem(request, error)
        if collaboration_response is not None:
            return collaboration_response
        skills_response = skills_request_validation_problem(request, error)
        if skills_response is not None:
            return skills_response
        if uses_problem_json(request.url.path):
            return decision_problem(422, "request_validation_failed", "request validation failed")
        from fastapi.exception_handlers import request_validation_exception_handler

        return await request_validation_exception_handler(request, error)

    def health() -> dict[str, str]:
        return {"service": "night-voyager-api", "status": "ok"}

    app.add_api_route("/health", health, methods=["GET"])
    app.include_router(create_identity_router(resolved_settings, session_factory, service_factory))
    if session_factory is not None:
        app.include_router(create_connected_demo_router(resolved_settings, session_factory))
        app.include_router(create_collaboration_router(resolved_settings, session_factory))
        app.include_router(create_decision_router(resolved_settings, session_factory))
        app.include_router(create_dra_router(resolved_settings, session_factory))
        app.include_router(create_skills_router(resolved_settings, session_factory))
        app.include_router(create_task_router(resolved_settings, session_factory))
    return app


app = create_app()
