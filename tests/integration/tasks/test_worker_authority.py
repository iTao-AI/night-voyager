# ruff: noqa: E501
from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

pytestmark = pytest.mark.database


async def set_worker_context(connection: AsyncConnection) -> None:
    for name, value in (
        ("night_voyager.organization_id", "10000000-0000-0000-0000-000000000001"),
        ("night_voyager.actor_id", "20000000-0000-0000-0000-000000000001"),
        ("night_voyager.role", "advisor"),
    ):
        await connection.execute(
            text("SELECT set_config(:name,:value,true)"), {"name": name, "value": value}
        )


async def assert_worker_denied(connection: AsyncConnection, statement: str) -> None:
    with pytest.raises(DBAPIError) as denied:
        async with connection.begin():
            await set_worker_context(connection)
            await connection.execute(text(statement))
    assert getattr(denied.value.orig, "sqlstate", None) == "42501"


@pytest.mark.asyncio
async def test_worker_cannot_directly_mutate_any_m4a_table() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            for table in ("agent_tasks", "agent_executions", "agent_task_events"):
                await assert_worker_denied(
                    connection,
                    f"INSERT INTO app.{table}(organization_id) "
                    "VALUES('10000000-0000-0000-0000-000000000001')",
                )
                await assert_worker_denied(connection, f"UPDATE app.{table} SET organization_id=organization_id")
                await assert_worker_denied(connection, f"DELETE FROM app.{table}")
                await assert_worker_denied(connection, f"TRUNCATE app.{table}")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_worker_cannot_insert_planning_runs_or_child_results() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            for table in (
                "planning_runs",
                "planning_routes",
                "comparison_dimensions",
                "comparison_dimension_evidence_refs",
                "cost_evidence",
                "ranking_evidence",
            ):
                await assert_worker_denied(
                    connection,
                    f"INSERT INTO app.{table}(organization_id) "
                    "VALUES('10000000-0000-0000-0000-000000000001')",
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_worker_cannot_execute_api_or_human_authority_functions() -> None:
    statements = (
        "SELECT app.create_agent_task(NULL::uuid,NULL::uuid,NULL::uuid,NULL::uuid,'generate_planning_run_v1',1,NULL::uuid,1,'m3a-policy-v1',repeat('a',64),repeat('b',64))",
        "SELECT app.cancel_agent_task(NULL::uuid,NULL::uuid,NULL::uuid,1,repeat('a',64),repeat('b',64))",
        "SELECT app.review_planning_run(NULL::uuid,NULL::uuid,NULL::uuid,NULL::uuid,1,'reject',NULL::uuid,'[]'::jsonb,'[]'::jsonb,NULL,NULL::uuid,'{}'::jsonb,current_date,repeat('a',64),repeat('b',64))",
        "SELECT app.decide_family_brief(NULL::uuid,NULL::uuid,'parent',NULL::uuid,1,NULL::uuid,NULL::uuid,NULL::uuid,0,0,'CNY','[]'::jsonb,NULL::uuid,'direct',NULL::uuid,'[]'::jsonb,repeat('a',64),repeat('b',64))",
    )
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            for statement in statements:
                await assert_worker_denied(connection, statement)
    finally:
        await engine.dispose()
