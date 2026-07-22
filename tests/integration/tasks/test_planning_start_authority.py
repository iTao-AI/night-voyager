# ruff: noqa: E501
from __future__ import annotations

import os
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from night_voyager.skills.models import SkillKey
from night_voyager.skills.registry import SkillRuntimeRegistry

pytestmark = pytest.mark.database

ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
PACK = UUID("50000000-0000-0000-0000-000000000001")
UNSTARTED_CASE = UUID("42000000-0000-0000-0000-000000000901")
START_CASE = UUID("42000000-0000-0000-0000-000000000902")
TASK = UUID("85000000-0000-0000-0000-000000000902")


def skill_manifest() -> str:
    return (
        SkillRuntimeRegistry.load_packaged()
        .get(SkillKey.STUDY_DESTINATION_COMPARE, "1.0.0")
        .model_dump_json(exclude_none=True)
    )


async def set_api_context(connection: AsyncConnection) -> None:
    for name, value in (
        ("night_voyager.organization_id", str(ORG)),
        ("night_voyager.actor_id", str(ADVISOR)),
        ("night_voyager.role", "advisor"),
    ):
        await connection.execute(
            text("SELECT set_config(:name,:value,true)"),
            {"name": name, "value": value},
        )


async def seed_intake_case(case_id: UUID) -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            await connection.execute(
                text(
                    "SELECT app.publish_case_revision("
                    ":org,:case,NULL,1,'{}'::jsonb,'{}'::jsonb)"
                ),
                {"org": ORG, "case": case_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.student_case_participants("
                    "organization_id,case_id,actor_id,role) "
                    "VALUES(:org,:case,:actor,'advisor')"
                ),
                {"org": ORG, "case": case_id, "actor": ADVISOR},
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_intake_case_has_no_task_before_explicit_planning_start() -> None:
    await seed_intake_case(UNSTARTED_CASE)
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await set_api_context(connection)
            assert await connection.scalar(
                text(
                    "SELECT state FROM app.student_cases "
                    "WHERE organization_id=:org AND id=:case"
                ),
                {"org": ORG, "case": UNSTARTED_CASE},
            ) == "intake"
            assert await connection.scalar(
                text(
                    "SELECT count(*) FROM app.agent_tasks "
                    "WHERE organization_id=:org AND case_id=:case"
                ),
                {"org": ORG, "case": UNSTARTED_CASE},
            ) == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_first_deterministic_task_atomically_starts_planning() -> None:
    await seed_intake_case(START_CASE)
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with api.begin() as connection:
            await set_api_context(connection)
            created = (
                await connection.execute(
                    text(
                        "SELECT * FROM app.create_agent_task("
                        ":org,:actor,:case,:task,'generate_planning_run_v1',1,"
                        ":pack,1,'m3a-policy-v1',CAST(:manifest AS jsonb),"
                        ":request_hash,:key_hash)"
                    ),
                    {
                        "org": ORG,
                        "actor": ADVISOR,
                        "case": START_CASE,
                        "task": TASK,
                        "pack": PACK,
                        "manifest": skill_manifest(),
                        "request_hash": "a" * 64,
                        "key_hash": "b" * 64,
                    },
                )
            ).mappings().one()
            assert dict(created) == {
                "task_id": TASK,
                "row_version": 1,
                "state": "queued",
                "attempt_count": 0,
                "replayed": False,
            }

        async with migrator.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            assert await connection.scalar(
                text(
                    "SELECT state FROM app.student_cases "
                    "WHERE organization_id=:org AND id=:case"
                ),
                {"org": ORG, "case": START_CASE},
            ) == "planning"
            counts = (
                await connection.execute(
                    text(
                        "SELECT "
                        "(SELECT count(*) FROM app.agent_tasks "
                        " WHERE organization_id=:org AND id=:task) AS tasks,"
                        "(SELECT count(*) FROM internal.agent_task_dispatch "
                        " WHERE organization_id=:org AND task_id=:task) AS dispatches,"
                        "(SELECT count(*) FROM app.agent_task_events "
                        " WHERE organization_id=:org AND task_id=:task "
                        "   AND event_sequence=1 AND event_code='queued') AS events,"
                        "(SELECT count(*) FROM app.idempotency_records "
                        " WHERE organization_id=:org AND operation='agent_task_create' "
                        "   AND response_id=:task) AS idempotency"
                    ),
                    {"org": ORG, "task": TASK},
                )
            ).mappings().one()
            assert tuple(counts) == (1, 1, 1, 1)
    finally:
        await api.dispose()
        await migrator.dispose()
