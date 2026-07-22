# ruff: noqa: E501
from __future__ import annotations

import os
import subprocess
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from night_voyager.skills.models import SkillKey
from night_voyager.skills.registry import SkillRuntimeRegistry

pytestmark = pytest.mark.database

ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
PACK = UUID("50000000-0000-0000-0000-000000000001")
SIGNATURE = (
    "uuid, uuid, uuid, uuid, text, integer, uuid, integer, text, jsonb, text, text"
)
TRANSITION_SIGNATURE = "uuid, uuid, text, text"


def run_alembic(*arguments: str) -> None:
    subprocess.run(
        ("uv", "run", "alembic", *arguments),
        check=True,
        env=os.environ.copy(),
        text=True,
    )


def skill_manifest() -> str:
    return SkillRuntimeRegistry.load_packaged().get(
        SkillKey.STUDY_DESTINATION_COMPARE, "1.0.0"
    ).model_dump_json(exclude_none=True)


async def capture_function_contract() -> dict[str, object]:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT pg_get_functiondef(p.oid) AS definition,"
                        "owner.rolname AS owner,oidvectortypes(p.proargtypes) AS signature,"
                        "p.proacl::text AS acl,"
                        "has_function_privilege('public',p.oid,'EXECUTE') AS public_execute,"
                        "has_function_privilege('night_voyager_api',p.oid,'EXECUTE') AS api_execute,"
                        "has_function_privilege('night_voyager_worker',p.oid,'EXECUTE') AS worker_execute "
                        "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                        "JOIN pg_roles owner ON owner.oid=p.proowner "
                        "WHERE n.nspname='app' AND p.proname='create_agent_task' "
                        "AND oidvectortypes(p.proargtypes)=:signature"
                    ),
                    {"signature": SIGNATURE},
                )
            ).mappings().one()
        contract = dict(row)
        assert contract["owner"] == "night_voyager_migrator"
        assert contract["signature"] == SIGNATURE
        assert contract["public_execute"] is False
        assert contract["api_execute"] is True
        assert contract["worker_execute"] is False
        return contract
    finally:
        await engine.dispose()


async def capture_transition_grants() -> dict[str, object]:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT owner.rolname AS owner,"
                        "has_function_privilege('public',p.oid,'EXECUTE') AS public_execute,"
                        "has_function_privilege('night_voyager_api',p.oid,'EXECUTE') AS api_execute,"
                        "has_function_privilege('night_voyager_worker',p.oid,'EXECUTE') AS worker_execute "
                        "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                        "JOIN pg_roles owner ON owner.oid=p.proowner "
                        "WHERE n.nspname='app' AND p.proname='transition_case' "
                        "AND oidvectortypes(p.proargtypes)=:signature"
                    ),
                    {"signature": TRANSITION_SIGNATURE},
                )
            ).mappings().one()
        return dict(row)
    finally:
        await engine.dispose()


async def prove_first_task(case_id: UUID, task_id: UUID, key_hash: str) -> dict[str, object]:
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with migrator.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            await connection.execute(
                text("SELECT app.publish_case_revision(:org,:case,NULL,1,'{}'::jsonb,'{}'::jsonb)"),
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

        async with api.begin() as connection:
            for name, value in (
                ("night_voyager.organization_id", str(ORG)),
                ("night_voyager.actor_id", str(ADVISOR)),
                ("night_voyager.role", "advisor"),
            ):
                await connection.execute(
                    text("SELECT set_config(:name,:value,true)"),
                    {"name": name, "value": value},
                )
            created = (
                await connection.execute(
                    text(
                        "SELECT * FROM app.create_agent_task("
                        ":org,:actor,:case,:task,'generate_planning_run_v1',1,"
                        ":pack,1,'m3a-policy-v1',CAST(:manifest AS jsonb),"
                        "repeat('a',64),:key_hash)"
                    ),
                    {
                        "org": ORG,
                        "actor": ADVISOR,
                        "case": case_id,
                        "task": task_id,
                        "pack": PACK,
                        "manifest": skill_manifest(),
                        "key_hash": key_hash,
                    },
                )
            ).mappings().one()
            assert created.task_id == task_id
            assert created.state == "queued"
            assert created.replayed is False
        return await authority_projection(case_id, task_id)
    finally:
        await migrator.dispose()
        await api.dispose()


async def authority_projection(case_id: UUID, task_id: UUID) -> dict[str, object]:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            row = (
                await connection.execute(
                    text(
                        "SELECT c.state,"
                        "(SELECT count(*) FROM app.agent_tasks t WHERE t.organization_id=:org AND t.id=:task) AS tasks,"
                        "(SELECT count(*) FROM internal.agent_task_dispatch d WHERE d.organization_id=:org AND d.task_id=:task) AS dispatches,"
                        "(SELECT count(*) FROM app.agent_task_events e WHERE e.organization_id=:org AND e.task_id=:task) AS events,"
                        "(SELECT count(*) FROM app.idempotency_records i WHERE i.organization_id=:org "
                        "AND i.operation='agent_task_create' AND i.response_id=:task) AS idempotency,"
                        "(SELECT count(*) FROM app.agent_executions e WHERE e.organization_id=:org AND e.task_id=:task) AS executions "
                        "FROM app.student_cases c WHERE c.organization_id=:org AND c.id=:case"
                    ),
                    {"org": ORG, "case": case_id, "task": task_id},
                )
            ).mappings().one()
        return dict(row)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_0009_upgrade_downgrade_upgrade_restores_exact_0008_authority() -> None:
    first_case = UUID("42000000-0000-0000-0000-000000000971")
    first_task = UUID("85000000-0000-0000-0000-000000000971")
    second_case = UUID("42000000-0000-0000-0000-000000000972")
    second_task = UUID("85000000-0000-0000-0000-000000000972")
    baseline_0008 = await capture_function_contract()
    baseline_transition_grants = await capture_transition_grants()
    assert baseline_transition_grants == {
        "owner": "night_voyager_migrator",
        "public_execute": False,
        "api_execute": True,
        "worker_execute": False,
    }
    try:
        run_alembic("upgrade", "0009")
        contract_0009 = await capture_function_contract()
        assert contract_0009["definition"] != baseline_0008["definition"]
        assert contract_0009["owner"] == baseline_0008["owner"]
        assert contract_0009["acl"] == baseline_0008["acl"]
        assert await capture_transition_grants() == {
            "owner": "night_voyager_migrator",
            "public_execute": False,
            "api_execute": False,
            "worker_execute": False,
        }
        first_projection = await prove_first_task(first_case, first_task, "7" * 64)
        assert first_projection == {
            "state": "planning",
            "tasks": 1,
            "dispatches": 1,
            "events": 1,
            "idempotency": 1,
            "executions": 0,
        }

        run_alembic("downgrade", "0008")
        assert await capture_function_contract() == baseline_0008
        assert await capture_transition_grants() == baseline_transition_grants
        assert await authority_projection(first_case, first_task) == first_projection

        run_alembic("upgrade", "0009")
        assert await capture_transition_grants() == {
            "owner": "night_voyager_migrator",
            "public_execute": False,
            "api_execute": False,
            "worker_execute": False,
        }
        assert await authority_projection(first_case, first_task) == first_projection
        assert await prove_first_task(second_case, second_task, "8" * 64) == {
            "state": "planning",
            "tasks": 1,
            "dispatches": 1,
            "events": 1,
            "idempotency": 1,
            "executions": 0,
        }
    finally:
        run_alembic("upgrade", "0009")
