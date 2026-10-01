# ruff: noqa: E501
from __future__ import annotations

import asyncio
import hashlib
import os
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from night_voyager.adapters.protocols import AdapterFailure, AdapterFailureCode
from night_voyager.tasks.policy import classify_adapter_outcome
from tests.integration.tasks.test_postgres_tasks import ADVISOR, ORG, PACK, context, skill_manifest
from tests.integration.tasks.test_worker import seed_and_create

pytestmark = pytest.mark.database


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def failed_source(
    code: str = "transport_interrupted", *, existing: tuple[UUID, UUID] | None = None
) -> tuple[UUID, UUID, int]:
    case, task = existing or (uuid4(), uuid4())
    # Existing durable create + terminal classifier/worker mutation authority.
    if existing is None:
        await seed_and_create(case, task, digest(str(task)))
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    worker = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    try:
        async with migrator.begin() as c:
            await context(c)
            await c.execute(
                text(
                    "UPDATE internal.agent_task_dispatch SET available_at=clock_timestamp()+interval '1 day' WHERE task_id<>:task"
                ),
                {"task": task},
            )
        attempts = 1 if code not in ("transport_interrupted", "transient_unavailable") else 3
        for attempt in range(1, attempts + 1):
            async with worker.begin() as c:
                claim = (
                    (await c.execute(text("SELECT * FROM app.claim_agent_task('recovery-test')")))
                    .mappings()
                    .one()
                )
                assert claim["task_id"] == task
                await context(c)
                await c.execute(
                    text(
                        "SELECT app.start_agent_task(:org,:task,'recovery-test',:generation,:hash)"
                    ),
                    {
                        "org": ORG,
                        "task": task,
                        "generation": claim["lease_generation"],
                        "hash": "a" * 64,
                    },
                )
                decision = classify_adapter_outcome(
                    AdapterFailure(code=AdapterFailureCode(code)), attempt_no=attempt
                )
                await c.execute(
                    text(
                        "SELECT app.fail_agent_task(:org,:task,'recovery-test',:generation,:code,:retryable,false)"
                    ),
                    {
                        "org": ORG,
                        "task": task,
                        "generation": claim["lease_generation"],
                        "code": code,
                        "retryable": decision.retryable,
                    },
                )
            if attempt < attempts:
                async with migrator.begin() as c:
                    await c.execute(
                        text(
                            "UPDATE internal.agent_task_dispatch SET available_at=clock_timestamp() WHERE task_id=:task"
                        ),
                        {"task": task},
                    )
        async with api.begin() as c:
            await context(c)
            version = await c.scalar(
                text(
                    "SELECT row_version FROM app.agent_tasks WHERE organization_id=:org AND id=:task"
                ),
                {"org": ORG, "task": task},
            )
        return case, task, int(version)
    finally:
        await api.dispose()
        await migrator.dispose()
        await worker.dispose()


async def retry(
    task: UUID, version: int, key: str, *, revision: int = 1, rollback: bool = False
) -> dict[str, object]:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with engine.connect() as c:
            tx = await c.begin()
            try:
                await context(c)
                row = (
                    (
                        await c.execute(
                            text(
                                "SELECT * FROM app.retry_agent_task(:org,:actor,:source,:version,:revision,:task,CAST(:manifest AS jsonb),:hash,:key)"
                            ),
                            {
                                "org": ORG,
                                "actor": ADVISOR,
                                "source": task,
                                "version": version,
                                "revision": revision,
                                "task": uuid4(),
                                "manifest": skill_manifest(),
                                "hash": digest(f"{task}:{version}:{revision}"),
                                "key": digest(key),
                            },
                        )
                    )
                    .mappings()
                    .one()
                )
                if rollback:
                    await tx.rollback()
                else:
                    await tx.commit()
                return dict(row)
            except BaseException:
                await tx.rollback()
                raise
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_native_retry_same_consent_replays_and_preserves_source():
    _, task, version = await failed_source()
    first, second = await asyncio.gather(
        retry(task, version, str(task)), retry(task, version, str(task))
    )
    assert first["task_id"] == second["task_id"] != task
    assert sorted((bool(first["replayed"]), bool(second["replayed"]))) == [False, True]
    with pytest.raises(DBAPIError):
        await retry(task, version, "distinct-" + str(task))
    assert (await retry(task, version, str(task)))["task_id"] == first["task_id"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code", ["transport_interrupted", "transient_unavailable", "deadline_exceeded"]
)
async def test_native_terminal_producers_accept_fresh_recovery(code: str) -> None:
    case, task, version = await failed_source(code)
    await assert_terminal_ledger_policy(case, eligible=True)
    successor = await retry(task, version, str(task))
    assert successor["state"] == "queued"
    assert successor["attempt_count"] == 0


@pytest.mark.asyncio
async def test_native_retry_stale_versions_and_rollback():
    _, task, version = await failed_source("deadline_exceeded")
    for row_version, revision in ((version - 1, 1), (version, 2)):
        with pytest.raises(DBAPIError):
            await retry(task, row_version, str(uuid4()), revision=revision)
    rolled_back = await retry(task, version, str(task), rollback=True)
    committed = await retry(task, version, str(task))
    assert committed["task_id"] != rolled_back["task_id"]
    assert committed["replayed"] is False


async def inspect_source(task: UUID) -> dict[str, object]:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as c:
            await context(c)
            row = (
                (
                    await c.execute(
                        text(
                            "SELECT to_jsonb(t) AS task, (SELECT jsonb_agg(to_jsonb(e) ORDER BY e.event_sequence) FROM app.agent_task_events e WHERE e.organization_id=t.organization_id AND e.task_id=t.id) AS events, (SELECT jsonb_agg(to_jsonb(x) ORDER BY x.attempt_no) FROM app.agent_executions x WHERE x.organization_id=t.organization_id AND x.task_id=t.id) AS executions FROM app.agent_tasks t WHERE t.organization_id=:org AND t.id=:task"
                        ),
                        {"org": ORG, "task": task},
                    )
                )
                .mappings()
                .one()
            )
            return dict(row)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_native_old_diagnostics_immutable_successor_worker_requires_fresh_review():
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from night_voyager.connected_demo.fixtures import resolve_canonical_demo_source_contract
    from night_voyager.connected_demo.postgres import PostgresConnectedDemoRepository
    from night_voyager.identity.models import ActorContext, ActorRole
    from tests.integration.tasks.test_worker import task_worker

    case, source, version = await failed_source("deadline_exceeded")
    old = await inspect_source(source)
    fresh = await retry(source, version, str(source))
    assert await inspect_source(source) == old
    worker, engine = task_worker("recovery-success-worker")
    try:
        assert await worker.run_once() is True
    finally:
        await cast(AsyncEngine, engine).dispose()
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    sessions = async_sessionmaker(api)
    try:
        async with sessions() as s, s.begin():
            for setting, value in [
                ("organization_id", ORG),
                ("actor_id", ADVISOR),
                ("role", "advisor"),
            ]:
                await s.execute(
                    text("SELECT set_config(:setting,:value,true)"),
                    {"setting": "night_voyager." + setting, "value": str(value)},
                )
            ledger = await PostgresConnectedDemoRepository(s).advisor_ledger_v2(
                ActorContext(ORG, ADVISOR, ActorRole.ADVISOR, uuid4()),
                case,
                resolve_canonical_demo_source_contract(),
            )
            assert ledger is not None and ledger.task is not None
            assert ledger.phase.value == "review_required"
            assert ledger.task.task_id == fresh["task_id"]
            assert ledger.current_brief_id is None
            assert ledger.review_inputs is not None
            assert (
                await s.scalar(
                    text(
                        "SELECT count(*) FROM app.advisor_reviews WHERE organization_id=:org AND case_id=:case"
                    ),
                    {"org": ORG, "case": case},
                )
                == 0
            )
    finally:
        await api.dispose()
    assert await inspect_source(source) == old


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code",
    ["invalid_schema", "pin_mismatch", "fallback_authority", "policy_rejected", "provider_unknown"],
)
async def test_native_hard_unknown_failure_rejected(code: str) -> None:
    # Unknown is a deliberately controlled negative producer input; real recognized
    # terminal producers remain the success fixtures above.
    case, task, version = await failed_source("deadline_exceeded")
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with migrator.begin() as c:
            await context(c)
            await c.execute(
                text(
                    "UPDATE app.agent_tasks SET state='failed',terminal_code=:code WHERE organization_id=:org AND id=:task"
                ),
                {"org": ORG, "task": task, "code": code},
            )
    finally:
        await migrator.dispose()
    await assert_terminal_ledger_policy(case, eligible=False)
    with pytest.raises(DBAPIError) as e:
        await retry(task, version, str(task))
    assert getattr(e.value.orig, "sqlstate", None) == "NV023"


@pytest.mark.asyncio
async def test_native_distinct_clicks_and_ordinary_create_share_case_serialization():
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from night_voyager.identity.models import ActorContext, ActorRole
    from night_voyager.skills.registry import SkillRuntimeRegistry
    from night_voyager.tasks.application import TaskService
    from night_voyager.tasks.errors import TaskConflictError
    from night_voyager.tasks.models import CreateTaskCommand
    from night_voyager.tasks.postgres import PostgresTaskRepository

    case, task, version = await failed_source("deadline_exceeded")
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    sessions = async_sessionmaker(api)

    async def ordinary():
        async with sessions() as s, s.begin():
            for setting, value in [
                ("organization_id", ORG),
                ("actor_id", ADVISOR),
                ("role", "advisor"),
            ]:
                await s.execute(
                    text("SELECT set_config(:setting,:value,true)"),
                    {"setting": "night_voyager." + setting, "value": str(value)},
                )
            return await TaskService(
                PostgresTaskRepository(s), registry=SkillRuntimeRegistry.load_packaged()
            ).create(
                ActorContext(ORG, ADVISOR, ActorRole.ADVISOR, uuid4()),
                CreateTaskCommand(
                    case_id=case,
                    expected_case_revision=1,
                    source_pack_id=PACK,
                    source_pack_version=1,
                ),
                str(uuid4()),
            )

    try:
        outcomes = await asyncio.wait_for(
            asyncio.gather(
                retry(task, version, "first-" + str(task)),
                retry(task, version, "second-" + str(task)),
                ordinary(),
                return_exceptions=True,
            ),
            10,
        )
        assert sum(isinstance(x, dict) for x in outcomes) == 1
        assert all(isinstance(x, (dict, DBAPIError, TaskConflictError)) for x in outcomes)
    finally:
        await api.dispose()


@pytest.mark.asyncio
async def test_native_ordinary_key_cannot_replay_as_retry():
    from tests.integration.tasks.test_postgres_tasks import seed_case

    _, source, version = await failed_source("deadline_exceeded")
    unrelated_case, unrelated_task = uuid4(), uuid4()
    await seed_case(unrelated_case)
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    key = digest(str(unrelated_task))
    try:
        async with api.begin() as c:
            await context(c)
            await c.execute(
                text(
                    "SELECT * FROM app.create_agent_task(:org,:actor,:case,:task,'generate_planning_run_v1',1,:pack,1,'m3a-policy-v1',CAST(:manifest AS jsonb),:hash,:key)"
                ),
                {
                    "org": ORG,
                    "actor": ADVISOR,
                    "case": unrelated_case,
                    "task": unrelated_task,
                    "pack": PACK,
                    "manifest": skill_manifest(),
                    "hash": digest(str(unrelated_case)),
                    "key": key,
                },
            )
        # SQL helpers take hashes; supply the exact existing ordinary key hash.
        async with api.begin() as c:
            await context(c)
            new = (
                (
                    await c.execute(
                        text(
                            "SELECT * FROM app.retry_agent_task(:org,:actor,:source,:version,1,:task,CAST(:manifest AS jsonb),:hash,:key)"
                        ),
                        {
                            "org": ORG,
                            "actor": ADVISOR,
                            "source": source,
                            "version": version,
                            "task": uuid4(),
                            "manifest": skill_manifest(),
                            "hash": digest(str(source)),
                            "key": key,
                        },
                    )
                )
                .mappings()
                .one()
            )
            assert new["task_id"] not in (source, unrelated_task)
            assert new["replayed"] is False
    finally:
        await api.dispose()


@pytest.mark.asyncio
async def test_native_lease_exhaustion_producer_allows_fresh_task():
    from tests.integration.tasks.test_worker import expire_lease

    case, task = uuid4(), uuid4()
    await seed_and_create(case, task, digest(str(task)))
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    worker = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    try:
        async with migrator.begin() as c:
            await c.execute(
                text(
                    "UPDATE internal.agent_task_dispatch SET available_at=clock_timestamp()+interval '1 day' WHERE task_id<>:task"
                ),
                {"task": task},
            )
        for attempt in range(1, 4):
            async with worker.begin() as c:
                claim = (
                    (
                        await c.execute(
                            text("SELECT * FROM app.claim_agent_task('recovery-lease-producer')")
                        )
                    )
                    .mappings()
                    .one()
                )
                assert claim["task_id"] == task and claim["lease_generation"] == attempt
            await expire_lease(task)
        async with worker.begin() as c:
            assert (
                await c.execute(
                    text("SELECT * FROM app.claim_agent_task('recovery-lease-producer')")
                )
            ).mappings().one_or_none() is None
        source = await inspect_source(task)
        raw = source["task"]
        assert isinstance(raw, dict) and raw["terminal_code"] == "lease_expired"
        version = int(cast(int, raw["row_version"]))
        fresh = await retry(task, version, str(task))
        assert fresh["task_id"] != task and fresh["state"] == "queued"
    finally:
        await worker.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_native_cancelled_and_accepted_worker_result_have_no_retry():
    from tests.integration.tasks.test_worker import task_worker

    case, task = uuid4(), uuid4()
    await seed_and_create(case, task, digest(str(task)))
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with api.begin() as c:
            await context(c)
            await c.execute(
                text("SELECT * FROM app.cancel_agent_task(:org,:actor,:task,1,:hash,:key)"),
                {
                    "org": ORG,
                    "actor": ADVISOR,
                    "task": task,
                    "hash": digest(str(task)),
                    "key": digest(str(task)),
                },
            )
        with pytest.raises(DBAPIError):
            await retry(task, 2, str(task))
        next_case, next_task = uuid4(), uuid4()
        await seed_and_create(next_case, next_task, digest(str(next_task)))
        async with migrator.begin() as c:
            await c.execute(
                text(
                    "UPDATE internal.agent_task_dispatch SET available_at=clock_timestamp()+interval '1 day' WHERE task_id<>:task"
                ),
                {"task": next_task},
            )
        worker, worker_engine = task_worker("recovery-accepted-control")
        try:
            assert await worker.run_once()
        finally:
            await cast(AsyncEngine, worker_engine).dispose()
        snapshot = await inspect_source(next_task)
        row = snapshot["task"]
        assert isinstance(row, dict) and row["result_planning_run_id"] is not None
        with pytest.raises(DBAPIError):
            await retry(next_task, int(cast(int, row["row_version"])), str(next_task))
        # Controlled currentness negative retains the real worker-produced result.
        async with migrator.begin() as c:
            await context(c)
            await c.execute(
                text(
                    "UPDATE app.planning_runs SET is_current=false WHERE organization_id=:org AND id=:run"
                ),
                {"org": ORG, "run": UUID(cast(str, row["result_planning_run_id"]))},
            )
        await assert_terminal_ledger_policy(next_case, eligible=False, expected_status="outdated")
        with pytest.raises(DBAPIError):
            await retry(next_task, int(cast(int, row["row_version"])), str(uuid4()))
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_native_revision_publication_revalidates_blocked_retry_after_case_lock():
    case, task, version = await failed_source("deadline_exceeded")
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
            pending = asyncio.create_task(retry(task, version, str(task)))
            # Database-observed wait ensures revision wins the same Case boundary.
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
            assert blocked is True
            await c.execute(
                text("SELECT app.publish_case_revision(:org,:case,1,2,'{}'::jsonb,'{}'::jsonb)"),
                {"org": ORG, "case": case},
            )
            await tx.commit()
            with pytest.raises(DBAPIError) as stale:
                await asyncio.wait_for(pending, 5)
            assert getattr(stale.value.orig, "sqlstate", None) == "NV003"
        with pytest.raises(DBAPIError):
            await retry(task, version, str(task))
    finally:
        await migrator.dispose()


@pytest.mark.asyncio
async def test_native_retry_preserves_promoted_mixed_operation_and_pack() -> None:
    from httpx2 import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from night_voyager.api import create_app
    from night_voyager.config import Settings
    from night_voyager.identity.models import DemoActorChoice
    from tests.integration.dra.test_postgres_mixed_snapshot import approved_pack
    from tests.integration.tasks.test_http_tasks import ORIGIN, mint, mutation_headers

    case, promoted_version = await approved_pack(uuid4().int % 1_000_000_000_000)
    source = uuid4()
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with api.begin() as c:
            await context(c)
            await c.execute(
                text(
                    "SELECT * FROM app.create_agent_task(:org,:actor,:case,:task,"
                    "'generate_governed_mixed_planning_run_v1',1,:pack,:version,"
                    "'m3a-policy-v1',CAST(:manifest AS jsonb),:hash,:key)"
                ),
                {
                    "org": ORG,
                    "actor": ADVISOR,
                    "case": case,
                    "task": source,
                    "pack": PACK,
                    "version": promoted_version,
                    "manifest": skill_manifest(),
                    "hash": digest(str(source)),
                    "key": digest(str(case)),
                },
            )
        _, _, row_version = await failed_source(existing=(case, source))
        before = await inspect_source(source)
        sessions = async_sessionmaker(api, expire_on_commit=False)
        issued = await mint(sessions, DemoActorChoice.ADVISOR)
        settings = Settings.model_validate(
            {
                "environment": "test",
                "database_url": os.environ["NIGHT_VOYAGER_API_DATABASE_URL"],
                "demo_mode": True,
                "demo_allow_insecure_cookie": True,
                "allowed_origins": [ORIGIN],
                "secret_key": "test-session-secret",
            }
        )
        app = create_app(settings=settings, session_factory=sessions)
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            client.cookies.set("night_voyager_session", issued.raw_session_token)
            response = await client.post(
                f"/api/v1/tasks/{source}/retry",
                headers=mutation_headers(issued, str(uuid4())),
                json={
                    "schema_version": 1,
                    "expected_row_version": row_version,
                    "expected_case_revision": 1,
                },
            )
            assert response.status_code == 202, response.text
            fresh = response.json()
            assert fresh["skill_pin"]["skill_activation_sequence"] > 0
        async with api.begin() as c:
            await context(c)
            row = (
                (
                    await c.execute(
                        text(
                            "SELECT operation,source_pack_id,source_pack_version,policy_version,"
                            "retried_from_task_id,skill_version_id FROM app.agent_tasks WHERE id=:task"
                        ),
                        {"task": UUID(fresh["task_id"])},
                    )
                )
                .mappings()
                .one()
            )
            assert row["operation"] == "generate_governed_mixed_planning_run_v1"
            assert row["source_pack_id"] == PACK
            assert row["source_pack_version"] == promoted_version
            assert row["policy_version"] == "m3a-policy-v1"
            assert row["retried_from_task_id"] == source
            source_row = before["task"]
            assert isinstance(source_row, dict)
            assert str(row["skill_version_id"]) == source_row["skill_version_id"]
        assert await inspect_source(source) == before
    finally:
        await api.dispose()


async def assert_terminal_ledger_policy(
    case: UUID, *, eligible: bool, expected_status: str | None = None
) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from night_voyager.connected_demo.fixtures import resolve_canonical_demo_source_contract
    from night_voyager.connected_demo.postgres import PostgresConnectedDemoRepository
    from night_voyager.identity.models import ActorContext, ActorRole

    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    sessions = async_sessionmaker(api)
    try:
        async with sessions() as session, session.begin():
            for setting, value in [
                ("organization_id", ORG),
                ("actor_id", ADVISOR),
                ("role", "advisor"),
            ]:
                await session.execute(
                    text("SELECT set_config(:setting,:value,true)"),
                    {"setting": "night_voyager." + setting, "value": str(value)},
                )
            repo = PostgresConnectedDemoRepository(session)
            actor = ActorContext(ORG, ADVISOR, ActorRole.ADVISOR, uuid4())
            legacy = await repo.advisor_ledger(
                actor, case, resolve_canonical_demo_source_contract()
            )
            current = await repo.advisor_ledger_v2(
                actor, case, resolve_canonical_demo_source_contract()
            )
            assert legacy is not None and legacy.recovery is not None
            assert current is not None and current.recovery is not None
            assert legacy.canonical_task_inputs is None
            if expected_status is not None:
                assert legacy.task is not None and legacy.task.status.value == expected_status
            assert legacy.recovery.retry_allowed is eligible
            assert current.recovery.retry_allowed is eligible
            assert (current.canonical_task_inputs is not None) is eligible
    finally:
        await api.dispose()


@pytest.mark.asyncio
async def test_exact_retry_replay_rejects_new_current_revision() -> None:
    case, source, version = await failed_source("deadline_exceeded")
    key = str(uuid4())
    first = await retry(source, version, key)
    await failed_source("deadline_exceeded", existing=(case, cast(UUID, first["task_id"])))
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with migrator.begin() as c:
            await context(c)
            await c.execute(
                text("SELECT app.publish_case_revision(:org,:case,1,2,'{}'::jsonb,'{}'::jsonb)"),
                {"org": ORG, "case": case},
            )
        with pytest.raises(DBAPIError) as stale:
            await retry(source, version, key)
        assert getattr(stale.value.orig, "sqlstate", None) == "NV003"
    finally:
        await migrator.dispose()
