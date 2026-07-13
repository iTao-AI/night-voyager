# ruff: noqa: E501
from __future__ import annotations

import asyncio
import os
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from night_voyager.adapters.deterministic_planning import DeterministicPlanningAdapter
from night_voyager.tasks.postgres import postgres_worker_repository_factory
from night_voyager.tasks.worker import TaskWorker

pytestmark = pytest.mark.database
ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
PACK = UUID("50000000-0000-0000-0000-000000000001")
COUNT = 100


@pytest.mark.asyncio
async def test_two_workers_process_100_tasks_without_duplicate_accepted_results() -> None:
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    worker_engine = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    sessions = async_sessionmaker(worker_engine, expire_on_commit=False)
    factory = postgres_worker_repository_factory(sessions)
    task_ids: list[UUID] = []
    try:
        async with migrator.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            for offset in range(COUNT):
                case_id = UUID(int=0x44000000000000000000000000000500 + offset)
                task_id = UUID(int=0x88000000000000000000000000000500 + offset)
                task_ids.append(task_id)
                await connection.execute(
                    text("SELECT app.publish_case_revision(:org,:case,NULL,1,'{}'::jsonb,'{}'::jsonb)"),
                    {"org": ORG, "case": case_id},
                )
                await connection.execute(
                    text("SELECT app.transition_case(:org,:case,'intake','planning')"),
                    {"org": ORG, "case": case_id},
                )
                await connection.execute(
                    text(
                        "INSERT INTO app.student_case_participants(organization_id,case_id,actor_id,role) "
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
            for offset, task_id in enumerate(task_ids):
                case_id = UUID(int=0x44000000000000000000000000000500 + offset)
                await connection.execute(
                    text(
                        "SELECT * FROM app.create_agent_task(:org,:actor,:case,:task,1,:pack,1,"
                        "'m3a-policy-v1',repeat('a',64),:key_hash)"
                    ),
                    {
                        "org": ORG,
                        "actor": ADVISOR,
                        "case": case_id,
                        "task": task_id,
                        "pack": PACK,
                        "key_hash": f"{offset:064x}",
                    },
                )

        workers = (
            TaskWorker(factory, DeterministicPlanningAdapter(), worker_id="capacity-a"),
            TaskWorker(factory, DeterministicPlanningAdapter(), worker_id="capacity-b"),
        )

        async def drain(worker: TaskWorker) -> int:
            processed = 0
            while await worker.run_once():
                processed += 1
            return processed

        processed = await asyncio.gather(*(drain(worker) for worker in workers))
        assert sum(processed) == COUNT
        async with api.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            summary = (
                await connection.execute(
                    text(
                        "SELECT count(*) FILTER (WHERE state='waiting_review') AS waiting,"
                        "count(DISTINCT result_planning_run_id) AS results,"
                        "(SELECT count(*) FROM app.agent_task_events e WHERE "
                        "e.organization_id=:org AND e.task_id=ANY(:tasks) "
                        "AND e.event_code='waiting_review') AS waiting_events "
                        "FROM app.agent_tasks WHERE organization_id=:org AND id=ANY(:tasks)"
                    ),
                    {"org": ORG, "tasks": task_ids},
                )
            ).mappings().one()
            assert dict(summary) == {
                "waiting": COUNT,
                "results": COUNT,
                "waiting_events": COUNT,
            }
    finally:
        await migrator.dispose()
        await api.dispose()
        await worker_engine.dispose()
