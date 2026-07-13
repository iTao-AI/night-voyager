# ruff: noqa: E501
from __future__ import annotations

import os
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

pytestmark = pytest.mark.database
ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
PACK = UUID("50000000-0000-0000-0000-000000000001")
OTHER_ORG = UUID("10000000-0000-0000-0000-000000000002")
OTHER_ADVISOR = UUID("20000000-0000-0000-0000-000000000099")
OTHER_PACK = UUID("50000000-0000-0000-0000-000000000002")


async def context(
    connection: AsyncConnection,
    *,
    organization_id: UUID = ORG,
    actor_id: UUID = ADVISOR,
    role: str = "advisor",
) -> None:
    for name, value in (
        ("night_voyager.organization_id", str(organization_id)),
        ("night_voyager.actor_id", str(actor_id)),
        ("night_voyager.role", role),
    ):
        await connection.execute(
            text("SELECT set_config(:name,:value,true)"), {"name": name, "value": value}
        )


async def seed_case(case_id: UUID) -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
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
    finally:
        await engine.dispose()


async def seed_other_tenant_case(case_id: UUID) -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(OTHER_ORG)},
            )
            for statement in (
                "INSERT INTO app.organizations(id,name,is_synthetic) VALUES(:org,'M4A other synthetic tenant',true) ON CONFLICT DO NOTHING",
                "INSERT INTO app.actors(id,organization_id,display_name,is_synthetic) VALUES(:actor,:org,'M4A other advisor',true) ON CONFLICT DO NOTHING",
                "INSERT INTO app.memberships(id,organization_id,actor_id,role) VALUES('30000000-0000-0000-0000-000000000098',:org,:actor,'advisor') ON CONFLICT DO NOTHING",
                "INSERT INTO app.source_packs(organization_id,id,version,schema_version,manifest_sha256) VALUES(:org,:pack,1,1,repeat('a',64)) ON CONFLICT DO NOTHING",
            ):
                await connection.execute(
                    text(statement),
                    {"org": OTHER_ORG, "actor": OTHER_ADVISOR, "pack": OTHER_PACK},
                )
            await connection.execute(
                text("SELECT app.publish_case_revision(:org,:case,NULL,1,'{}'::jsonb,'{}'::jsonb)"),
                {"org": OTHER_ORG, "case": case_id},
            )
            await connection.execute(
                text("SELECT app.transition_case(:org,:case,'intake','planning')"),
                {"org": OTHER_ORG, "case": case_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.student_case_participants(organization_id,case_id,actor_id,role) "
                    "VALUES(:org,:case,:actor,'advisor') ON CONFLICT DO NOTHING"
                ),
                {"org": OTHER_ORG, "case": case_id, "actor": OTHER_ADVISOR},
            )
    finally:
        await engine.dispose()


async def create_task(connection: AsyncConnection, case_id: UUID, task_id: UUID, key: str) -> dict[str, object]:
    await context(connection)
    result = await connection.execute(
        text(
            "SELECT * FROM app.create_agent_task(:org,:actor,:case,:task,1,:pack,1,"
            "'m3a-policy-v1',:request_hash,:key_hash)"
        ),
        {
            "org": ORG,
            "actor": ADVISOR,
            "case": case_id,
            "task": task_id,
            "pack": PACK,
            "request_hash": "a" * 64,
            "key_hash": key * 64,
        },
    )
    return dict(result.mappings().one())


@pytest.mark.asyncio
async def test_assigned_advisor_create_replay_conflict_and_direct_dml_denial() -> None:
    case_id = UUID("40000000-0000-0000-0000-000000000201")
    task_id = UUID("80000000-0000-0000-0000-000000000201")
    await seed_case(case_id)
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            created = await create_task(connection, case_id, task_id, "1")
            assert created == {
                "task_id": task_id,
                "row_version": 1,
                "state": "queued",
                "attempt_count": 0,
                "replayed": False,
            }
        async with engine.begin() as connection:
            replayed = await create_task(connection, case_id, UUID(int=999), "1")
            assert replayed["task_id"] == task_id
            assert replayed["replayed"] is True
        async with engine.connect() as connection:
            with pytest.raises(DBAPIError) as mismatch:
                async with connection.begin():
                    await context(connection)
                    await connection.execute(
                        text(
                            "SELECT * FROM app.create_agent_task(:org,:actor,:case,:task,1,:pack,1,"
                            "'m3a-policy-v1',:request_hash,:key_hash)"
                        ),
                        {
                            "org": ORG,
                            "actor": ADVISOR,
                            "case": case_id,
                            "task": UUID(int=998),
                            "pack": PACK,
                            "request_hash": "b" * 64,
                            "key_hash": "1" * 64,
                        },
                    )
            assert getattr(mismatch.value.orig, "sqlstate", None) == "NV008"
        async with engine.connect() as connection:
            for statement in (
                "UPDATE app.agent_tasks SET state='failed'",
                "INSERT INTO app.agent_task_events(organization_id,task_id,event_sequence,event_code,public_status,attempt_no) VALUES('10000000-0000-0000-0000-000000000001','80000000-0000-0000-0000-000000000201',99,'failed','failed',0)",
                "SELECT * FROM internal.agent_task_dispatch",
            ):
                with pytest.raises(DBAPIError) as denied:
                    async with connection.begin():
                        await context(connection)
                        await connection.execute(text(statement))
                assert getattr(denied.value.orig, "sqlstate", None) == "42501"
        async with engine.begin() as connection:
            await context(connection)
            cancelled = (
                await connection.execute(
                    text(
                        "SELECT * FROM app.cancel_agent_task(:org,:actor,:task,1,"
                        ":request_hash,:key_hash)"
                    ),
                    {
                        "org": ORG,
                        "actor": ADVISOR,
                        "task": task_id,
                        "request_hash": "d" * 64,
                        "key_hash": "5" * 64,
                    },
                )
            ).mappings().one()
            assert cancelled.state == "cancelled"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_claim_heartbeat_generation_fence_cancel_and_contiguous_events() -> None:
    case_id = UUID("40000000-0000-0000-0000-000000000202")
    task_id = UUID("80000000-0000-0000-0000-000000000202")
    await seed_case(case_id)
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    worker = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    try:
        async with api.begin() as connection:
            await create_task(connection, case_id, task_id, "2")
        async with worker.begin() as connection:
            claim = dict(
                (
                    await connection.execute(
                        text("SELECT * FROM app.claim_agent_task('worker-a')")
                    )
                ).mappings().one()
            )
            assert set(claim) == {"task_id", "organization_id", "lease_generation"}
            assert claim["task_id"] == task_id
            assert claim["organization_id"] == ORG
            assert claim["lease_generation"] == 1
        async with worker.begin() as connection:
            assert (
                await connection.execute(text("SELECT * FROM app.claim_agent_task('worker-b')"))
            ).mappings().all() == []
        async with worker.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            await connection.execute(
                text("SELECT app.start_agent_task(:org,:task,'worker-a',1,repeat('a',64))"),
                {"org": ORG, "task": task_id},
            )
            await connection.execute(
                text("SELECT app.heartbeat_agent_task(:org,:task,'worker-a',1)"),
                {"org": ORG, "task": task_id},
            )
        async with worker.connect() as connection:
            with pytest.raises(DBAPIError) as stale:
                async with connection.begin():
                    await connection.execute(
                        text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                        {"org": str(ORG)},
                    )
                    await connection.execute(
                        text("SELECT app.heartbeat_agent_task(:org,:task,'worker-a',0)"),
                        {"org": ORG, "task": task_id},
                    )
            assert getattr(stale.value.orig, "sqlstate", None) == "NV010"
        async with api.begin() as connection:
            await context(connection)
            cancelled = dict(
                (
                    await connection.execute(
                        text(
                            "SELECT * FROM app.cancel_agent_task(:org,:actor,:task,3,"
                            ":request_hash,:key_hash)"
                        ),
                        {
                            "org": ORG,
                            "actor": ADVISOR,
                            "task": task_id,
                            "request_hash": "c" * 64,
                            "key_hash": "3" * 64,
                        },
                    )
                ).mappings().one()
            )
            assert cancelled["state"] == "cancelled"
        async with worker.connect() as connection:
            with pytest.raises(DBAPIError) as lost:
                async with connection.begin():
                    await connection.execute(
                        text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                        {"org": str(ORG)},
                    )
                    await connection.execute(
                        text(
                            "SELECT app.fail_agent_task(:org,:task,'worker-a',1,'unknown',false,false)"
                        ),
                        {"org": ORG, "task": task_id},
                    )
            assert getattr(lost.value.orig, "sqlstate", None) == "NV010"
        async with api.begin() as connection:
            await context(connection)
            sequences = (
                await connection.execute(
                    text(
                        "SELECT event_sequence FROM app.agent_task_events "
                        "WHERE organization_id=:org AND task_id=:task ORDER BY event_sequence"
                    ),
                    {"org": ORG, "task": task_id},
                )
            ).scalars().all()
            assert sequences == list(range(1, len(sequences) + 1))
    finally:
        await api.dispose()
        await worker.dispose()


@pytest.mark.asyncio
async def test_expired_lease_reclaim_and_three_total_attempts() -> None:
    case_id = UUID("40000000-0000-0000-0000-000000000203")
    task_id = UUID("80000000-0000-0000-0000-000000000203")
    await seed_case(case_id)
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    worker = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with api.begin() as connection:
            await create_task(connection, case_id, task_id, "4")
        async with worker.begin() as connection:
            first = (
                await connection.execute(text("SELECT * FROM app.claim_agent_task('worker-a')"))
            ).mappings().one()
            assert first.lease_generation == 1
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
        async with worker.begin() as connection:
            second = (
                await connection.execute(text("SELECT * FROM app.claim_agent_task('worker-b')"))
            ).mappings().one()
            assert second.lease_generation == 2
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            state = await connection.scalar(
                text(
                    "SELECT app.fail_agent_task(:org,:task,'worker-b',2,"
                    "'transient_unavailable',true,false)"
                ),
                {"org": ORG, "task": task_id},
            )
            assert state == "queued"
        async with worker.begin() as connection:
            third = (
                await connection.execute(text("SELECT * FROM app.claim_agent_task('worker-c')"))
            ).mappings().one()
            assert third.lease_generation == 3
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            state = await connection.scalar(
                text(
                    "SELECT app.fail_agent_task(:org,:task,'worker-c',3,"
                    "'transient_unavailable',true,false)"
                ),
                {"org": ORG, "task": task_id},
            )
            assert state == "failed"
        async with api.begin() as connection:
            await context(connection)
            row = (
                await connection.execute(
                    text(
                        "SELECT state,attempt_count,lease_owner,lease_expires_at "
                        "FROM app.agent_tasks WHERE organization_id=:org AND id=:task"
                    ),
                    {"org": ORG, "task": task_id},
                )
            ).mappings().one()
            assert row.state == "failed"
            assert row.attempt_count == 3
            assert row.lease_owner is None
            assert row.lease_expires_at is None
    finally:
        await api.dispose()
        await worker.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_third_expired_lease_fails_last_execution_without_scheduling_retry() -> None:
    case_id = UUID("40000000-0000-0000-0000-000000000207")
    task_id = UUID("80000000-0000-0000-0000-000000000207")
    await seed_case(case_id)
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    worker = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with api.begin() as connection:
            await create_task(connection, case_id, task_id, "7")

        for attempt, worker_id in enumerate(("lease-a", "lease-b", "lease-c"), start=1):
            async with worker.begin() as connection:
                claim = (
                    await connection.execute(
                        text("SELECT * FROM app.claim_agent_task(:worker)"),
                        {"worker": worker_id},
                    )
                ).mappings().one()
                assert claim.task_id == task_id
                assert claim.lease_generation == attempt
            async with migrator.begin() as connection:
                await connection.execute(
                    text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                    {"org": str(ORG)},
                )
                await connection.execute(
                    text(
                        "UPDATE app.agent_tasks SET "
                        "lease_expires_at=clock_timestamp()-interval '1 second' "
                        "WHERE organization_id=:org AND id=:task"
                    ),
                    {"org": ORG, "task": task_id},
                )
                await connection.execute(
                    text(
                        "UPDATE internal.agent_task_dispatch SET "
                        "available_at=clock_timestamp()-interval '1 second' "
                        "WHERE organization_id=:org AND task_id=:task"
                    ),
                    {"org": ORG, "task": task_id},
                )

        async with worker.begin() as connection:
            assert (
                await connection.execute(
                    text("SELECT * FROM app.claim_agent_task('lease-exhausted')")
                )
            ).mappings().all() == []

        async with migrator.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            task = (
                await connection.execute(
                    text(
                        "SELECT state,attempt_count,terminal_code,lease_owner,lease_expires_at,"
                        "(SELECT count(*) FROM internal.agent_task_dispatch d "
                        "WHERE d.organization_id=t.organization_id AND d.task_id=t.id) dispatches "
                        "FROM app.agent_tasks t WHERE organization_id=:org AND id=:task"
                    ),
                    {"org": ORG, "task": task_id},
                )
            ).mappings().one()
            assert dict(task) == {
                "state": "failed",
                "attempt_count": 3,
                "terminal_code": "lease_expired",
                "lease_owner": None,
                "lease_expires_at": None,
                "dispatches": 0,
            }
            executions = (
                await connection.execute(
                    text(
                        "SELECT attempt_no,status,retryable,public_code,finished_at "
                        "FROM app.agent_executions WHERE organization_id=:org AND task_id=:task "
                        "ORDER BY attempt_no"
                    ),
                    {"org": ORG, "task": task_id},
                )
            ).mappings().all()
            assert len(executions) == 3
            assert executions[-1].attempt_no == 3
            assert executions[-1].status == "failed"
            assert executions[-1].retryable is False
            assert executions[-1].public_code == "lease_expired"
            assert executions[-1].finished_at is not None
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.agent_task_events "
                        "WHERE organization_id=:org AND task_id=:task "
                        "AND event_code='retry_scheduled'"
                    ),
                    {"org": ORG, "task": task_id},
                )
                == 0
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.agent_task_events "
                        "WHERE organization_id=:org AND task_id=:task "
                        "AND event_code='failed' AND public_code='lease_expired'"
                    ),
                    {"org": ORG, "task": task_id},
                )
                == 1
            )
    finally:
        await api.dispose()
        await worker.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_two_tenant_claim_isolation_and_pool_context_cleanup() -> None:
    demo_case = UUID("40000000-0000-0000-0000-000000000204")
    other_case = UUID("40000000-0000-0000-0000-000000000205")
    demo_task = UUID("80000000-0000-0000-0000-000000000204")
    other_task = UUID("80000000-0000-0000-0000-000000000205")
    await seed_case(demo_case)
    await seed_other_tenant_case(other_case)
    api = create_async_engine(
        os.environ["NIGHT_VOYAGER_API_DATABASE_URL"], pool_size=1, max_overflow=0
    )
    worker = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    try:
        async with api.begin() as connection:
            await create_task(connection, demo_case, demo_task, "6")
        async with api.begin() as connection:
            await context(
                connection,
                organization_id=OTHER_ORG,
                actor_id=OTHER_ADVISOR,
            )
            created = (
                await connection.execute(
                    text(
                        "SELECT * FROM app.create_agent_task(:org,:actor,:case,:task,1,:pack,1,"
                        "'m3a-policy-v1',repeat('a',64),repeat('7',64))"
                    ),
                    {
                        "org": OTHER_ORG,
                        "actor": OTHER_ADVISOR,
                        "case": other_case,
                        "task": other_task,
                        "pack": OTHER_PACK,
                    },
                )
            ).mappings().one()
            assert created.task_id == other_task
            assert await connection.scalar(
                text("SELECT count(*) FROM app.agent_tasks WHERE id=:task"),
                {"task": other_task},
            ) == 1
            assert await connection.scalar(
                text("SELECT count(*) FROM app.agent_tasks WHERE id=:task"),
                {"task": demo_task},
            ) == 0
        async with api.begin() as connection:
            assert await connection.scalar(text("SELECT count(*) FROM app.agent_tasks")) == 0
            await context(connection)
            assert await connection.scalar(
                text("SELECT count(*) FROM app.agent_tasks WHERE id=:task"),
                {"task": demo_task},
            ) == 1
            assert await connection.scalar(
                text("SELECT count(*) FROM app.agent_tasks WHERE id=:task"),
                {"task": other_task},
            ) == 0

        claimed: dict[UUID, tuple[UUID, int]] = {}
        for worker_name in ("worker-tenant-a", "worker-tenant-b"):
            async with worker.begin() as connection:
                row = (
                    await connection.execute(
                        text("SELECT * FROM app.claim_agent_task(:worker)"),
                        {"worker": worker_name},
                    )
                ).mappings().one()
                claimed[row.organization_id] = (row.task_id, row.lease_generation)
        assert claimed == {ORG: (demo_task, 1), OTHER_ORG: (other_task, 1)}

        for organization_id, actor_id, task_id, key in (
            (ORG, ADVISOR, demo_task, "8"),
            (OTHER_ORG, OTHER_ADVISOR, other_task, "9"),
        ):
            async with api.begin() as connection:
                await context(
                    connection,
                    organization_id=organization_id,
                    actor_id=actor_id,
                )
                row = (
                    await connection.execute(
                        text(
                            "SELECT * FROM app.cancel_agent_task(:org,:actor,:task,2,"
                            "repeat('c',64),:key_hash)"
                        ),
                        {
                            "org": organization_id,
                            "actor": actor_id,
                            "task": task_id,
                            "key_hash": key * 64,
                        },
                    )
                ).mappings().one()
                assert row.state == "cancelled"
    finally:
        await api.dispose()
        await worker.dispose()


@pytest.mark.asyncio
async def test_generation_fenced_finalize_is_atomic() -> None:
    case_id = UUID("40000000-0000-0000-0000-000000000206")
    task_id = UUID("80000000-0000-0000-0000-000000000206")
    run_id = UUID("70000000-0000-0000-0000-000000000206")
    await seed_case(case_id)
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    worker = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    try:
        async with api.begin() as connection:
            await create_task(connection, case_id, task_id, "a")
        async with worker.begin() as connection:
            claim = (
                await connection.execute(text("SELECT * FROM app.claim_agent_task('worker-final')"))
            ).mappings().one()
            assert claim.task_id == task_id
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            await connection.execute(
                text("SELECT app.start_agent_task(:org,:task,'worker-final',1,repeat('a',64))"),
                {"org": ORG, "task": task_id},
            )
            state = await connection.scalar(
                text(
                    "SELECT app.finalize_agent_task_result(:org,:task,'worker-final',1,:run,"
                    "repeat('e',64),'blocked','missing_evidence',repeat('f',64),"
                    "'{\"routes\":[],\"costs\":[],\"rankings\":[]}'::jsonb,NULL)"
                ),
                {"org": ORG, "task": task_id, "run": run_id},
            )
            assert state == "blocked"
        async with api.begin() as connection:
            await context(connection)
            task = (
                await connection.execute(
                    text(
                        "SELECT state,result_planning_run_id,lease_owner FROM app.agent_tasks "
                        "WHERE organization_id=:org AND id=:task"
                    ),
                    {"org": ORG, "task": task_id},
                )
            ).mappings().one()
            assert dict(task) == {
                "state": "blocked",
                "result_planning_run_id": run_id,
                "lease_owner": None,
            }
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.planning_runs WHERE organization_id=:org "
                        "AND id=:run AND state='blocked' AND is_current"
                    ),
                    {"org": ORG, "run": run_id},
                )
                == 1
            )
            event = (
                await connection.execute(
                    text(
                        "SELECT event_code,public_status,result_planning_run_id "
                        "FROM app.agent_task_events WHERE organization_id=:org AND task_id=:task "
                        "ORDER BY event_sequence DESC LIMIT 1"
                    ),
                    {"org": ORG, "task": task_id},
                )
            ).mappings().one()
            assert dict(event) == {
                "event_code": "blocked",
                "public_status": "needs_evidence",
                "result_planning_run_id": run_id,
            }
    finally:
        await api.dispose()
        await worker.dispose()
