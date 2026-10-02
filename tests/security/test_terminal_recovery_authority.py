# ruff: noqa: E501
from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from tests.integration.tasks.test_postgres_tasks import ADVISOR, ORG, context, skill_manifest
from tests.integration.tasks.test_terminal_recovery import digest, failed_source, retry

pytestmark = pytest.mark.database
RETRY_SQL = "SELECT * FROM app.retry_agent_task(:org,:actor,:source,:version,1,:task,CAST(:manifest AS jsonb),:hash,:key)"


@pytest.mark.asyncio
async def test_retry_catalog_has_only_api_execute_and_no_direct_writes():
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as c:
            rows = (
                (
                    await c.execute(
                        text(
                            "SELECT p.proname,p.prosecdef,p.proconfig,has_function_privilege('night_voyager_api',p.oid,'EXECUTE') AS api,has_function_privilege('night_voyager_worker',p.oid,'EXECUTE') AS worker,has_function_privilege('public',p.oid,'EXECUTE') AS public FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='app' AND p.proname IN ('retry_agent_task','project_agent_task_retry_eligible')"
                        )
                    )
                )
                .mappings()
                .all()
            )
            assert len(rows) == 2
            for row in rows:
                assert row["prosecdef"] and row["api"] and not row["worker"] and not row["public"]
                assert row["proconfig"] == ["search_path=pg_catalog, pg_temp"]
            assert (
                await c.scalar(
                    text(
                        "SELECT relforcerowsecurity FROM pg_class WHERE oid='app.agent_tasks'::regclass"
                    )
                )
                is True
            )
            for role in ("night_voyager_api", "night_voyager_worker"):
                for privilege in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                    assert (
                        await c.scalar(
                            text("SELECT has_table_privilege(:role,'app.agent_tasks',:privilege)"),
                            {"role": role, "privilege": privilege},
                        )
                        is False
                    )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("actor_role", ["parent", "student", "unassigned", "foreign"])
async def test_retry_denies_nonassigned_or_foreign_actor(actor_role: str) -> None:
    _, source, version = await failed_source("deadline_exceeded")
    actor = ADVISOR
    role = "advisor"
    org = ORG
    if actor_role in ("parent", "student"):
        from uuid import UUID

        actor = UUID(
            "20000000-0000-0000-0000-00000000000" + ("3" if actor_role == "parent" else "2")
        )
        role = actor_role
    elif actor_role == "unassigned":
        actor = uuid4()
        migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
        try:
            async with migrator.begin() as c:
                await context(c)
                await c.execute(
                    text(
                        "INSERT INTO app.actors(id,organization_id,display_name,is_synthetic) VALUES(:actor,:org,'Unassigned synthetic advisor',true)"
                    ),
                    {"actor": actor, "org": org},
                )
                await c.execute(
                    text(
                        "INSERT INTO app.memberships(id,organization_id,actor_id,role) VALUES(:id,:org,:actor,'advisor')"
                    ),
                    {"id": uuid4(), "actor": actor, "org": org},
                )
        finally:
            await migrator.dispose()
    else:
        org = uuid4()
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with api.begin() as c:
            await context(c, organization_id=org, actor_id=actor, role=role)
            with pytest.raises(DBAPIError) as e:
                await c.execute(
                    text(RETRY_SQL),
                    {
                        "org": org,
                        "actor": actor,
                        "source": source,
                        "version": version,
                        "task": uuid4(),
                        "manifest": skill_manifest(),
                        "hash": digest(str(source)),
                        "key": digest(str(source)),
                    },
                )
            assert getattr(e.value.orig, "sqlstate", None) == "NV007"
    finally:
        await api.dispose()


@pytest.mark.asyncio
async def test_exact_retry_replay_still_requires_current_assignment_and_revision():
    case, source, version = await failed_source("deadline_exceeded")
    await retry(source, version, str(source))
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with migrator.begin() as c:
            await context(c)
            await c.execute(
                text(
                    "DELETE FROM app.student_case_participants WHERE organization_id=:org AND case_id=:case AND actor_id=:actor"
                ),
                {"org": ORG, "case": case, "actor": ADVISOR},
            )
        with pytest.raises(DBAPIError) as e:
            await retry(source, version, str(source))
        assert getattr(e.value.orig, "sqlstate", None) == "NV007"
    finally:
        await migrator.dispose()


@pytest.mark.asyncio
async def test_retry_replay_rechecks_assignment_after_case_lock_wait():
    import asyncio

    case, source, version = await failed_source("deadline_exceeded")
    await retry(source, version, str(source))
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with migrator.connect() as c:
            tx = await c.begin()
            await context(c)
            await c.execute(
                text(
                    "SELECT id FROM app.student_cases WHERE organization_id=:org AND id=:case FOR UPDATE"
                ),
                {"org": ORG, "case": case},
            )
            pending = asyncio.create_task(retry(source, version, str(source)))
            blocked = False
            for _ in range(100):
                blocked = await c.scalar(
                    text(
                        "SELECT EXISTS(SELECT 1 FROM pg_locks WHERE NOT granted AND locktype='transactionid' AND pid<>pg_backend_pid())"
                    )
                )
                if blocked:
                    break
                await asyncio.sleep(0.01)
            assert blocked
            await c.execute(
                text(
                    "DELETE FROM app.student_case_participants WHERE organization_id=:org AND case_id=:case AND actor_id=:actor"
                ),
                {"org": ORG, "case": case, "actor": ADVISOR},
            )
            await tx.commit()
            with pytest.raises(DBAPIError) as denied:
                await asyncio.wait_for(pending, 5)
            assert getattr(denied.value.orig, "sqlstate", None) == "NV007"
    finally:
        await migrator.dispose()
