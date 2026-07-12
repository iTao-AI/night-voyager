from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

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
        with pytest.raises(DBAPIError):
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
