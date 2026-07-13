# ruff: noqa: E501
from __future__ import annotations

import asyncio
import os
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from night_voyager.adapters.deterministic_planning import DeterministicPlanningAdapter
from night_voyager.adapters.protocols import (
    AdapterFailure,
    AdapterFailureCode,
    AdapterOutcome,
    PlanningAdapterRequest,
)
from night_voyager.tasks.postgres import postgres_worker_repository_factory
from night_voyager.tasks.worker import TaskWorker

pytestmark = pytest.mark.database
ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
PACK = UUID("50000000-0000-0000-0000-000000000001")


class BlockingAdapter:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.inner = DeterministicPlanningAdapter()

    async def generate(self, request: PlanningAdapterRequest) -> AdapterOutcome:
        self.started.set()
        await self.release.wait()
        return await self.inner.generate(request)


async def seed_and_create(case_id: UUID, task_id: UUID, key: str) -> None:
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
                text("SELECT app.transition_case(:org,:case,'intake','planning')"),
                {"org": ORG, "case": case_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.student_case_participants(organization_id,case_id,actor_id,role) "
                    "VALUES(:org,:case,:actor,'advisor') ON CONFLICT DO NOTHING"
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
                    "key_hash": key * 64,
                },
            )
    finally:
        await migrator.dispose()
        await api.dispose()


def task_worker(worker_id: str, adapter: object | None = None) -> tuple[TaskWorker, object]:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    worker = TaskWorker(
        postgres_worker_repository_factory(sessions),
        adapter or DeterministicPlanningAdapter(),  # type: ignore[arg-type]
        worker_id=worker_id,
    )
    return worker, engine


async def task_row(task_id: UUID) -> dict[str, object]:
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with api.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            return dict(
                (
                    await connection.execute(
                        text(
                            "SELECT state,attempt_count,lease_owner,result_planning_run_id,"
                            "(SELECT count(*) FROM app.agent_task_events e WHERE "
                            "e.organization_id=t.organization_id AND e.task_id=t.id "
                            "AND e.event_code='waiting_review') AS waiting_events "
                            "FROM app.agent_tasks t WHERE organization_id=:org AND id=:task"
                        ),
                        {"org": ORG, "task": task_id},
                    )
                ).mappings().one()
            )
    finally:
        await api.dispose()


async def expire_lease(task_id: UUID) -> None:
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with migrator.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            await connection.execute(
                text(
                    "UPDATE app.agent_tasks SET lease_expires_at=clock_timestamp()-interval '1 second' "
                    "WHERE organization_id=:org AND id=:task"
                ),
                {"org": ORG, "task": task_id},
            )
            await connection.execute(
                text(
                    "UPDATE internal.agent_task_dispatch SET available_at=clock_timestamp()-interval '1 second' "
                    "WHERE organization_id=:org AND task_id=:task"
                ),
                {"org": ORG, "task": task_id},
            )
    finally:
        await migrator.dispose()


@pytest.mark.asyncio
async def test_two_workers_accept_one_result_and_clear_lease() -> None:
    case_id = UUID("40000000-0000-0000-0000-000000000401")
    task_id = UUID("80000000-0000-0000-0000-000000000401")
    await seed_and_create(case_id, task_id, "b")
    worker_a, engine_a = task_worker("worker-real-a")
    worker_b, engine_b = task_worker("worker-real-b")
    try:
        assert sorted(await asyncio.gather(worker_a.run_once(), worker_b.run_once())) == [
            False,
            True,
        ]
        row = await task_row(task_id)
        assert row["state"] == "waiting_review"
        assert row["attempt_count"] == 1
        assert row["lease_owner"] is None
        assert row["result_planning_run_id"] is not None
        assert row["waiting_events"] == 1
    finally:
        await engine_a.dispose()  # type: ignore[attr-defined]
        await engine_b.dispose()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_cancel_wins_against_inflight_adapter_and_discards_output() -> None:
    case_id = UUID("40000000-0000-0000-0000-000000000402")
    task_id = UUID("80000000-0000-0000-0000-000000000402")
    await seed_and_create(case_id, task_id, "c")
    adapter = BlockingAdapter()
    worker, engine = task_worker("worker-cancel", adapter)
    run = asyncio.create_task(worker.run_once())
    try:
        await asyncio.wait_for(adapter.started.wait(), timeout=2)
        api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
        try:
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
                await connection.execute(
                    text(
                        "SELECT * FROM app.cancel_agent_task(:org,:actor,:task,3,"
                        "repeat('c',64),repeat('d',64))"
                    ),
                    {"org": ORG, "actor": ADVISOR, "task": task_id},
                )
        finally:
            await api.dispose()
        adapter.release.set()
        assert await asyncio.wait_for(run, timeout=2) is True
        row = await task_row(task_id)
        assert row["state"] == "cancelled"
        assert row["result_planning_run_id"] is None
        assert row["waiting_events"] == 0
    finally:
        adapter.release.set()
        await engine.dispose()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_reclaim_wins_and_stale_worker_cannot_finalize() -> None:
    case_id = UUID("40000000-0000-0000-0000-000000000403")
    task_id = UUID("80000000-0000-0000-0000-000000000403")
    await seed_and_create(case_id, task_id, "e")
    stale_adapter = BlockingAdapter()
    stale_worker, stale_engine = task_worker("worker-stale", stale_adapter)
    fresh_worker, fresh_engine = task_worker("worker-reclaim")
    stale_run = asyncio.create_task(stale_worker.run_once())
    try:
        await asyncio.wait_for(stale_adapter.started.wait(), timeout=2)
        await expire_lease(task_id)
        assert await fresh_worker.run_once() is True
        stale_adapter.release.set()
        assert await asyncio.wait_for(stale_run, timeout=2) is True
        row = await task_row(task_id)
        assert row["state"] == "waiting_review"
        assert row["attempt_count"] == 2
        assert row["waiting_events"] == 1
    finally:
        stale_adapter.release.set()
        await stale_engine.dispose()  # type: ignore[attr-defined]
        await fresh_engine.dispose()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_restart_reclaims_expired_started_execution() -> None:
    case_id = UUID("40000000-0000-0000-0000-000000000404")
    task_id = UUID("80000000-0000-0000-0000-000000000404")
    await seed_and_create(case_id, task_id, "f")
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    factory = postgres_worker_repository_factory(sessions)
    try:
        async with factory() as repository:
            claim = await repository.claim("worker-before-restart")
        assert claim is not None
        async with factory() as repository:
            await repository.start(claim, "worker-before-restart")
        await expire_lease(task_id)
        restarted = TaskWorker(
            factory,
            DeterministicPlanningAdapter(),
            worker_id="worker-after-restart",
        )
        assert await restarted.run_once() is True
        row = await task_row(task_id)
        assert row["state"] == "waiting_review"
        assert row["attempt_count"] == 2
        assert row["waiting_events"] == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_transient_adapter_failure_stops_after_three_attempts() -> None:
    case_id = UUID("40000000-0000-0000-0000-000000000405")
    task_id = UUID("80000000-0000-0000-0000-000000000405")
    await seed_and_create(case_id, task_id, "9")
    adapter = DeterministicPlanningAdapter(
        injected_failure=AdapterFailure(
            code=AdapterFailureCode.TRANSIENT_UNAVAILABLE
        )
    )
    worker, engine = task_worker("worker-retry", adapter)
    try:
        assert await worker.run_once() is True
        assert await worker.run_once() is True
        assert await worker.run_once() is True
        assert await worker.run_once() is False
        inspector = create_async_engine(
            os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"]
        )
        try:
            async with inspector.begin() as connection:
                await connection.execute(
                    text(
                        "SELECT set_config('night_voyager.organization_id',:org,true)"
                    ),
                    {"org": str(ORG)},
                )
                row = (
                    await connection.execute(
                        text(
                            "SELECT state,attempt_count,terminal_code,"
                            "(SELECT count(*) FROM app.agent_executions e WHERE "
                            "e.organization_id=t.organization_id AND e.task_id=t.id) "
                            "AS executions,"
                            "(SELECT count(*) FROM app.agent_task_events e WHERE "
                            "e.organization_id=t.organization_id AND e.task_id=t.id "
                            "AND e.event_code='retry_scheduled') AS retries "
                            "FROM app.agent_tasks t WHERE organization_id=:org AND id=:task"
                        ),
                        {"org": ORG, "task": task_id},
                    )
                ).mappings().one()
        finally:
            await inspector.dispose()
        assert dict(row) == {
            "state": "failed",
            "attempt_count": 3,
            "terminal_code": "transient_unavailable",
            "executions": 3,
            "retries": 2,
        }
    finally:
        await engine.dispose()  # type: ignore[attr-defined]
