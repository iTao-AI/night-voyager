# ruff: noqa: E501
from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.database
DEMO_ORG = "10000000-0000-0000-0000-000000000001"


@pytest.mark.asyncio
async def test_worker_cannot_write_and_pool_context_does_not_leak() -> None:
    engine = create_async_engine(
        os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"], pool_size=1, max_overflow=0
    )
    try:
        async with engine.begin() as connection:
            assert await connection.scalar(text("SELECT count(*) FROM app.student_cases")) == 0
        async with engine.connect() as connection:
            with pytest.raises(DBAPIError):
                async with connection.begin():
                    await connection.execute(
                        text("SELECT set_config('night_voyager.organization_id', :org, true)"),
                        {"org": DEMO_ORG},
                    )
                    await connection.execute(
                        text("INSERT INTO app.student_cases (organization_id, id) VALUES (:org, gen_random_uuid())"),
                        {"org": DEMO_ORG},
                    )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_api_cannot_delete_or_mutate_immutable_revision() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        for statement in (
            "DELETE FROM app.student_cases",
            "UPDATE app.student_case_revisions SET revision = 2",
        ):
            async with engine.connect() as connection:
                with pytest.raises(DBAPIError):
                    async with connection.begin():
                        await connection.execute(
                            text("SELECT set_config('night_voyager.organization_id', :org, true)"),
                            {"org": DEMO_ORG},
                        )
                        await connection.execute(text(statement))
    finally:
        await engine.dispose()
