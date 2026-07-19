# ruff: noqa: E501
from __future__ import annotations

import asyncio
import json
import os
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from night_voyager.adapters.deterministic_planning import DeterministicPlanningAdapter
from night_voyager.adapters.governed_mixed_planning import GovernedMixedPlanningAdapter
from night_voyager.adapters.router import PlanningAdapterRouter
from night_voyager.planning.fixtures import validate_planning_fixture
from night_voyager.planning.mixed_postgres import PostgresMixedPlanningRepository
from night_voyager.planning.synthetic_postgres import (
    PersistedSyntheticSnapshotRepository,
)
from night_voyager.skills.models import SkillKey
from night_voyager.skills.registry import SkillRuntimeRegistry
from night_voyager.tasks.postgres import postgres_worker_repository_factory
from night_voyager.tasks.worker import TaskWorker

pytestmark = pytest.mark.database
ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
PACK = UUID("50000000-0000-0000-0000-000000000001")
COUNT = 100


def registry() -> SkillRuntimeRegistry:
    return SkillRuntimeRegistry.load_packaged()


def skill_manifest() -> str:
    return registry().get(
        SkillKey.STUDY_DESTINATION_COMPARE, "1.0.0"
    ).model_dump_json(exclude_none=True)
PLANNING_FIXTURE = validate_planning_fixture().planning_input


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
                    text(
                        "SELECT app.publish_case_revision("
                        ":org,:case,NULL,1,CAST(:student AS jsonb),CAST(:family AS jsonb))"
                    ),
                    {
                        "org": ORG,
                        "case": case_id,
                        "student": json.dumps(
                            PLANNING_FIXTURE.case.student.model_dump(mode="json")
                        ),
                        "family": json.dumps(PLANNING_FIXTURE.case.family.model_dump(mode="json")),
                    },
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
                        "SELECT * FROM app.create_agent_task(:org,:actor,:case,:task,"
                        "'generate_planning_run_v1',1,:pack,1,"
                        "'m3a-policy-v1',CAST(:skill_manifest AS jsonb),"
                        "repeat('a',64),:key_hash)"
                    ),
                    {
                        "org": ORG,
                        "actor": ADVISOR,
                        "case": case_id,
                        "task": task_id,
                        "pack": PACK,
                        "skill_manifest": skill_manifest(),
                        "key_hash": f"{offset:064x}",
                    },
                )

        router = PlanningAdapterRouter(
            synthetic=DeterministicPlanningAdapter(PersistedSyntheticSnapshotRepository(sessions)),
            mixed=GovernedMixedPlanningAdapter(PostgresMixedPlanningRepository(sessions)),
        )
        workers = (
            TaskWorker(factory, router, registry(), worker_id="capacity-a"),
            TaskWorker(factory, router, registry(), worker_id="capacity-b"),
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
                (
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
                )
                .mappings()
                .one()
            )
            assert dict(summary) == {
                "waiting": COUNT,
                "results": COUNT,
                "waiting_events": COUNT,
            }
    finally:
        await migrator.dispose()
        await api.dispose()
        await worker_engine.dispose()
