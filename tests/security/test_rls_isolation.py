from __future__ import annotations

import os
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.database
DEMO_ORG = UUID("10000000-0000-0000-0000-000000000001")
OTHER_ORG = UUID("10000000-0000-0000-0000-000000000002")


def _url(name: str) -> str:
    return os.environ[name]


@pytest.mark.asyncio
async def test_api_and_worker_see_only_transaction_tenant_and_pool_does_not_leak() -> None:
    migrator = create_async_engine(_url("NIGHT_VOYAGER_MIGRATION_DATABASE_URL"))
    try:
        async with migrator.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id', :value, true)"),
                {"value": str(OTHER_ORG)},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.organizations (id, name) VALUES (:id, 'other') "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {"id": OTHER_ORG},
            )
    finally:
        await migrator.dispose()

    for variable in ("NIGHT_VOYAGER_API_DATABASE_URL", "NIGHT_VOYAGER_WORKER_DATABASE_URL"):
        engine = create_async_engine(_url(variable), pool_size=1, max_overflow=0)
        try:
            async with engine.begin() as connection:
                missing = await connection.scalar(text("SELECT count(*) FROM app.organizations"))
                assert missing == 0
                await connection.execute(
                    text("SELECT set_config('night_voyager.organization_id', :value, true)"),
                    {"value": str(DEMO_ORG)},
                )
                own = await connection.scalar(text("SELECT count(*) FROM app.organizations"))
                joined = await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.actors a JOIN app.memberships m "
                        "ON (m.organization_id, m.actor_id) = (a.organization_id, a.id)"
                    )
                )
                assert own == 1
                assert joined == 3
                cross_tenant = await connection.scalar(
                    text("SELECT count(*) FROM app.organizations WHERE id = :id"),
                    {"id": OTHER_ORG},
                )
                assert cross_tenant == 0
            async with engine.begin() as connection:
                leaked = await connection.scalar(text("SELECT count(*) FROM app.organizations"))
                assert leaked == 0
            async with engine.connect() as connection:
                with pytest.raises(DBAPIError):
                    async with connection.begin():
                        await connection.execute(
                            text(
                                "SELECT set_config("
                                "'night_voyager.organization_id', 'not-a-uuid', true)"
                            )
                        )
                        await connection.execute(text("SELECT * FROM app.organizations"))
        finally:
            await engine.dispose()


@pytest.mark.asyncio
async def test_runtime_roles_cannot_write_auth_or_escalate() -> None:
    for variable in ("NIGHT_VOYAGER_API_DATABASE_URL", "NIGHT_VOYAGER_WORKER_DATABASE_URL"):
        engine = create_async_engine(_url(variable))
        try:
            async with engine.connect() as connection:
                for statement in (
                    "SELECT count(*) FROM auth.demo_sessions",
                    "INSERT INTO app.organizations (id, name) VALUES "
                    "('10000000-0000-0000-0000-000000000099', 'forbidden')",
                    "SET ROLE night_voyager_migrator",
                ):
                    with pytest.raises(DBAPIError):
                        async with connection.begin():
                            await connection.execute(text(statement))
                if variable == "NIGHT_VOYAGER_WORKER_DATABASE_URL":
                    with pytest.raises(DBAPIError):
                        async with connection.begin():
                            await connection.execute(
                                text("SELECT * FROM auth.resolve_demo_session('\\x00'::bytea)")
                            )
        finally:
            await engine.dispose()


@pytest.mark.asyncio
async def test_forced_owner_with_check_rejects_wrong_tenant_and_accepts_correct_tenant() -> None:
    engine = create_async_engine(_url("NIGHT_VOYAGER_MIGRATION_DATABASE_URL"))
    try:
        async with engine.connect() as connection:
            with pytest.raises(DBAPIError):
                async with connection.begin():
                    await connection.execute(
                        text("SELECT set_config('night_voyager.organization_id', :value, true)"),
                        {"value": str(DEMO_ORG)},
                    )
                    await connection.execute(
                        text("INSERT INTO app.organizations (id, name) VALUES (:id, 'other')"),
                        {"id": OTHER_ORG},
                    )
            async with connection.begin():
                await connection.execute(
                    text("SELECT set_config('night_voyager.organization_id', :value, true)"),
                    {"value": str(OTHER_ORG)},
                )
                await connection.execute(
                    text(
                        "INSERT INTO app.organizations (id, name) VALUES (:id, 'other') "
                        "ON CONFLICT (id) DO NOTHING"
                    ),
                    {"id": OTHER_ORG},
                )
    finally:
        await engine.dispose()
