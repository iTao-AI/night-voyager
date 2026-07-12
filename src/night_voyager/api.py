from collections.abc import Callable

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from night_voyager.config import Settings
from night_voyager.database import create_engine, create_session_factory
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

    def health() -> dict[str, str]:
        return {"service": "night-voyager-api", "status": "ok"}

    app.add_api_route("/health", health, methods=["GET"])
    app.include_router(create_identity_router(resolved_settings, session_factory, service_factory))
    return app


app = create_app()
