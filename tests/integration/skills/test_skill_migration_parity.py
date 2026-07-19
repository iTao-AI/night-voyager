from __future__ import annotations

import os
import subprocess

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from night_voyager.identity.demo_seed import (
    COLLABORATION_ACTIVE_CASE_ID,
    COLLABORATION_ACTIVE_TASK_ID,
    COLLABORATION_THREAD_IDS,
)

ORG = "10000000-0000-0000-0000-000000000001"
ADVISOR = "20000000-0000-0000-0000-000000000001"
SIGNATURE = (
    "app.seed_demo_collaboration(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text)"
)
ORIGINAL_SIGNATURE = (
    "app.seed_demo_collaboration_0007(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text)"
)


def _alembic(*arguments: str) -> None:
    subprocess.run(
        ["uv", "run", "alembic", *arguments],
        check=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )


def _seed_0007_demo() -> None:
    subprocess.run(
        [
            "uv",
            "run",
            "--no-editable",
            "python",
            "scripts/seed_demo.py",
            "--without-skills",
        ],
        check=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )


async def _function_definition(connection: AsyncConnection, signature: str) -> str | None:
    return await connection.scalar(
        text(
            "SELECT CASE WHEN to_regprocedure(:signature) IS NULL THEN NULL "
            "ELSE pg_get_functiondef(to_regprocedure(:signature)) END"
        ),
        {"signature": signature},
    )


async def _history_counts(connection: AsyncConnection) -> tuple[int, int, int, int]:
    parameters = {"org": ORG, "task": COLLABORATION_ACTIVE_TASK_ID}
    counts: list[int] = []
    for table, task_column in (
        ("app.agent_tasks", "id"),
        ("app.agent_task_events", "task_id"),
        ("app.agent_executions", "task_id"),
        ("internal.agent_task_dispatch", "task_id"),
    ):
        counts.append(
            int(
                await connection.scalar(
                    text(
                        f"SELECT count(*) FROM {table} "
                        "WHERE organization_id=:org AND "
                    f"{task_column}=:task"
                ),
                    parameters,
                )
                or 0
            )
        )
    return counts[0], counts[1], counts[2], counts[3]


async def _assert_missing_event_rejected(connection: AsyncConnection) -> None:
    await connection.execute(
        text("SELECT set_config('night_voyager.organization_id',:org,true)"),
        {"org": ORG},
    )
    await connection.execute(
        text("ALTER TABLE app.agent_task_events DISABLE TRIGGER agent_task_events_immutable")
    )
    await connection.execute(
        text(
            "DELETE FROM app.agent_task_events "
            "WHERE organization_id=:org AND task_id=:task"
        ),
        {"org": ORG, "task": COLLABORATION_ACTIVE_TASK_ID},
    )
    before = await _history_counts(connection)
    assert before == (1, 0, 0, 0)
    savepoint = await connection.begin_nested()
    with pytest.raises(DBAPIError):
        await connection.execute(
            text(
                "SELECT app.seed_demo_collaboration("
                ":org,:case,:thread,:advisor,NULL,NULL,NULL,:task,'active_task')"
            ),
            {
                "org": ORG,
                "case": COLLABORATION_ACTIVE_CASE_ID,
                "thread": COLLABORATION_THREAD_IDS["active_task"],
                "advisor": ADVISOR,
                "task": COLLABORATION_ACTIVE_TASK_ID,
            },
        )
    await savepoint.rollback()
    assert await _history_counts(connection) == before == (1, 0, 0, 0)


@pytest.mark.database
@pytest.mark.asyncio
async def test_0008_legacy_seed_helper_has_fresh_upgrade_and_downgrade_parity() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            fresh_0008 = await _function_definition(connection, SIGNATURE)
            fresh_preserved_0007 = await _function_definition(connection, ORIGINAL_SIGNATURE)
            assert fresh_0008 is not None
            assert fresh_preserved_0007 is not None

        _alembic("downgrade", "0001")
        _alembic("upgrade", "0007")
        _seed_0007_demo()

        async with engine.connect() as connection:
            original_0007 = await _function_definition(connection, SIGNATURE)
            assert original_0007 is not None
            assert "ON CONFLICT DO NOTHING" in original_0007
            assert "GET DIAGNOSTICS" not in original_0007

        _alembic("upgrade", "head")
        async with engine.connect() as connection:
            upgraded_0008 = await _function_definition(connection, SIGNATURE)
            preserved_0007 = await _function_definition(connection, ORIGINAL_SIGNATURE)
            assert upgraded_0008 == fresh_0008
            assert preserved_0007 == fresh_preserved_0007
            assert isinstance(upgraded_0008, str)
            assert isinstance(preserved_0007, str)
            assert "demo collaboration legacy task event mismatch" in upgraded_0008
            assert "GET DIAGNOSTICS" not in preserved_0007
            privilege_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM pg_roles role "
                    "WHERE role.rolname=ANY(:roles) AND ("
                    "has_function_privilege(role.rolname,:wrapper,'EXECUTE') OR "
                    "has_function_privilege(role.rolname,:original,'EXECUTE'))"
                ),
                {
                    "roles": ["night_voyager_api", "night_voyager_worker"],
                    "wrapper": SIGNATURE,
                    "original": ORIGINAL_SIGNATURE,
                },
            )
            assert privilege_count == 0
            await connection.rollback()
            transaction = await connection.begin()
            await _assert_missing_event_rejected(connection)
            await transaction.rollback()

        _alembic("downgrade", "0007")
        async with engine.connect() as connection:
            assert await _function_definition(connection, SIGNATURE) == original_0007
            assert await _function_definition(connection, ORIGINAL_SIGNATURE) is None
    finally:
        await engine.dispose()
