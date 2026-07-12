from __future__ import annotations

import os

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from night_voyager.api import create_app
from night_voyager.config import Settings
from night_voyager.identity.errors import AuthenticationFailedError, StaleSessionError
from night_voyager.identity.models import ActorRole, DemoActorChoice
from night_voyager.identity.repository import IdentityRepository
from night_voyager.identity.service import IdentityService

pytestmark = pytest.mark.database


@pytest.mark.asyncio
async def test_postgres_session_mint_rotate_resolve_revoke_is_opaque() -> None:
    api_engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    migrator_engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    sessions = async_sessionmaker(api_engine, expire_on_commit=False)
    try:
        async with sessions() as session, session.begin():
            service = IdentityService(IdentityRepository(session), "test-session-secret")
            advisor = await service.mint(DemoActorChoice.ADVISOR)
        with pytest.raises(AuthenticationFailedError):
            async with sessions() as session, session.begin():
                await IdentityService(
                    IdentityRepository(session), "test-session-secret"
                ).rotate(advisor.raw_session_token, "wrong-csrf", DemoActorChoice.PARENT)
        async with sessions() as session, session.begin():
            service = IdentityService(IdentityRepository(session), "test-session-secret")
            resolved_advisor = await service.resolve(advisor.raw_session_token)
            assert resolved_advisor is not None
            assert resolved_advisor.role is ActorRole.ADVISOR
            parent = await service.rotate(
                advisor.raw_session_token, advisor.raw_csrf_token, DemoActorChoice.PARENT
            )
        async with sessions() as session, session.begin():
            service = IdentityService(IdentityRepository(session), "test-session-secret")
            assert await service.resolve(advisor.raw_session_token) is None
            resolved_parent = await service.resolve(parent.raw_session_token)
            assert resolved_parent is not None
            assert resolved_parent.role is ActorRole.PARENT
            await service.revoke(parent.raw_session_token, parent.raw_csrf_token)
        async with sessions() as session, session.begin():
            assert await IdentityService(
                IdentityRepository(session), "test-session-secret"
            ).resolve(parent.raw_session_token) is None
        async with sessions() as session, session.begin():
            expiring = await IdentityService(
                IdentityRepository(session), "test-session-secret"
            ).mint(DemoActorChoice.STUDENT)
        async with migrator_engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE auth.demo_sessions "
                    "SET expires_at = clock_timestamp() - interval '1 second' "
                    "WHERE revoked_at IS NULL"
                )
            )
        async with sessions() as session, session.begin():
            assert await IdentityService(
                IdentityRepository(session), "test-session-secret"
            ).resolve(expiring.raw_session_token) is None
        async with migrator_engine.connect() as connection:
            rows = (
                await connection.execute(
                    text("SELECT session_digest, csrf_digest FROM auth.demo_sessions")
                )
            ).all()
            serialized = repr(rows)
            assert advisor.raw_session_token not in serialized
            assert advisor.raw_csrf_token not in serialized
            assert parent.raw_session_token not in serialized
            assert parent.raw_csrf_token not in serialized
    finally:
        await api_engine.dispose()
        await migrator_engine.dispose()


@pytest.mark.asyncio
async def test_postgres_http_rotation_normalizes_auth_errors_and_recovers_stale_cookie() -> None:
    api_url = os.environ["NIGHT_VOYAGER_API_DATABASE_URL"]
    engine = create_async_engine(api_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings.model_validate(
        {
            "environment": "test",
            "database_url": api_url,
            "demo_mode": True,
            "demo_allow_insecure_cookie": True,
            "allowed_origins": ["http://127.0.0.1:3000"],
            "secret_key": "test-session-secret",
        }
    )
    app = create_app(settings=settings, session_factory=sessions)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://127.0.0.1:3000"
        ) as client:
            bootstrap = await client.get(
                "/api/v1/demo/session-bootstrap", headers={"Origin": "http://127.0.0.1:3000"}
            )
            minted = await client.post(
                "/api/v1/demo/sessions",
                headers={
                    "Origin": "http://127.0.0.1:3000",
                    "X-CSRF-Token": bootstrap.json()["csrf_token"],
                },
                json={"demo_actor": "advisor"},
            )
            wrong_csrf = await client.post(
                "/api/v1/demo/sessions",
                headers={"Origin": "http://127.0.0.1:3000", "X-CSRF-Token": "wrong"},
                json={"demo_actor": "parent"},
            )
            rotated = await client.post(
                "/api/v1/demo/sessions",
                headers={
                    "Origin": "http://127.0.0.1:3000",
                    "X-CSRF-Token": minted.json()["csrf_token"],
                },
                json={"demo_actor": "parent"},
            )
            revoked = await client.delete(
                "/api/v1/demo/session",
                headers={
                    "Origin": "http://127.0.0.1:3000",
                    "X-CSRF-Token": rotated.json()["csrf_token"],
                },
            )
            revoked_token = rotated.cookies.get("night_voyager_session")
            assert revoked_token is not None
            stale = await client.post(
                "/api/v1/demo/sessions",
                headers={
                    "Origin": "http://127.0.0.1:3000",
                    "X-CSRF-Token": rotated.json()["csrf_token"],
                    "Cookie": f"night_voyager_session={revoked_token}",
                },
                json={"demo_actor": "advisor"},
            )
            fresh_bootstrap = await client.get(
                "/api/v1/demo/session-bootstrap", headers={"Origin": "http://127.0.0.1:3000"}
            )
            recovered = await client.post(
                "/api/v1/demo/sessions",
                headers={
                    "Origin": "http://127.0.0.1:3000",
                    "X-CSRF-Token": fresh_bootstrap.json()["csrf_token"],
                },
                json={"demo_actor": "student"},
            )

        assert wrong_csrf.status_code == 401
        assert wrong_csrf.json() == {"detail": "authentication failed"}
        assert "night_voyager_session=" not in wrong_csrf.headers.get("set-cookie", "")
        assert rotated.status_code == 201
        assert revoked.status_code == 204
        assert stale.status_code == 401
        assert stale.json() == {"detail": "authentication failed"}
        assert "Max-Age=0" in stale.headers["set-cookie"]
        assert recovered.status_code == 201

        async with sessions() as session, session.begin():
            service = IdentityService(IdentityRepository(session), "test-session-secret")
            with pytest.raises(StaleSessionError):
                await service.rotate("unknown", "unknown", DemoActorChoice.ADVISOR)
    finally:
        await engine.dispose()
