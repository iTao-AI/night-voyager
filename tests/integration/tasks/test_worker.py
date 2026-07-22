# ruff: noqa: E501
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from typing import Never
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from night_voyager.adapters.deterministic_planning import DeterministicPlanningAdapter
from night_voyager.adapters.governed_mixed_planning import GovernedMixedPlanningAdapter
from night_voyager.adapters.protocols import (
    AdapterFailure,
    AdapterFailureCode,
    AdapterOutcome,
    PlanningAdapterRequest,
)
from night_voyager.adapters.router import PlanningAdapterRouter
from night_voyager.planning.fixtures import validate_planning_fixture
from night_voyager.planning.hashing import canonical_sha256
from night_voyager.planning.mixed_postgres import PostgresMixedPlanningRepository
from night_voyager.planning.synthetic_postgres import (
    PersistedSyntheticSnapshotRepository,
)
from night_voyager.skills.models import SkillKey, SkillRuntimePin
from night_voyager.skills.registry import SkillRuntimeRegistry
from night_voyager.tasks.postgres import postgres_worker_repository_factory
from night_voyager.tasks.worker import TaskWorker
from tests.integration.dra.test_postgres_mixed_snapshot import approved_pack

pytestmark = pytest.mark.database
ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
STUDENT = UUID("20000000-0000-0000-0000-000000000002")
PARENT = UUID("20000000-0000-0000-0000-000000000003")
PACK = UUID("50000000-0000-0000-0000-000000000001")
PLANNING_FIXTURE = validate_planning_fixture().planning_input


def registry() -> SkillRuntimeRegistry:
    return SkillRuntimeRegistry.load_packaged()


def skill_manifest() -> str:
    return registry().get(
        SkillKey.STUDY_DESTINATION_COMPARE, "1.0.0"
    ).model_dump_json(exclude_none=True)


def skill_pin() -> SkillRuntimePin:
    runtime_binding_sha256 = registry().get(
        SkillKey.STUDY_DESTINATION_COMPARE, "1.0.0"
    ).runtime_binding_sha256
    return SkillRuntimePin(
        skill_definition_id=UUID("81000000-0000-0000-0000-000000000002"),
        skill_version_id=UUID("82000000-0000-0000-0000-000000000002"),
        skill_activation_event_id=UUID("84000000-0000-0000-0000-000000000001"),
        skill_activation_sequence=1,
        runtime_binding_sha256=runtime_binding_sha256 or "",
    )


def expected_input_sha256(case_id: UUID) -> str:
    return canonical_sha256(
        {
            "request": PlanningAdapterRequest(
                schema_version=1,
                operation="generate_planning_run_v1",
                organization_id=ORG,
                case_id=case_id,
                case_revision=1,
                source_pack_id=PACK,
                source_pack_version=1,
                policy_version="m3a-policy-v1",
            ).model_dump(mode="json"),
            "five_field_pin": skill_pin().model_dump(mode="json"),
        }
    )


class BlockingAdapter:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.inner: DeterministicPlanningAdapter | None = None

    async def generate(self, request: PlanningAdapterRequest) -> AdapterOutcome:
        self.started.set()
        await self.release.wait()
        assert self.inner is not None
        return await self.inner.generate(request)


class NeverSnapshotRepository:
    async def load(self, request: PlanningAdapterRequest) -> Never:
        raise AssertionError(f"unexpected snapshot load for {request.operation}")


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
                text(
                    "SELECT app.publish_case_revision("
                    ":org,:case,NULL,1,CAST(:student AS jsonb),CAST(:family AS jsonb))"
                ),
                {
                    "org": ORG,
                    "case": case_id,
                    "student": json.dumps(PLANNING_FIXTURE.case.student.model_dump(mode="json")),
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
                    "key_hash": key * 64,
                },
            )
    finally:
        await migrator.dispose()
        await api.dispose()


def task_worker(worker_id: str, adapter: object | None = None) -> tuple[TaskWorker, object]:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    repository = PersistedSyntheticSnapshotRepository(sessions)
    synthetic = adapter or DeterministicPlanningAdapter(repository)
    if isinstance(synthetic, BlockingAdapter):
        synthetic.inner = DeterministicPlanningAdapter(repository)
    worker = TaskWorker(
        postgres_worker_repository_factory(sessions),
        PlanningAdapterRouter(
            synthetic=synthetic,  # type: ignore[arg-type]
            mixed=GovernedMixedPlanningAdapter(PostgresMixedPlanningRepository(sessions)),
        ),
        registry(),
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
                )
                .mappings()
                .one()
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
async def test_worker_claim_loads_confirmed_revision_two_budget_and_exact_task_pin() -> None:
    case_id = UUID("a4000000-0000-0000-0000-000000000407")
    thread_id = UUID("a9000000-0000-0000-0000-000000000407")
    message_id = UUID("a9100000-0000-0000-0000-000000000407")
    candidate_id = UUID("a9200000-0000-0000-0000-000000000407")
    verification_id = UUID("a9300000-0000-0000-0000-000000000407")
    fact_id = UUID("a9400000-0000-0000-0000-000000000407")
    task_id = UUID("a8000000-0000-0000-0000-000000000407")
    budget = {
        "schema_version": 1,
        "currency": "CNY",
        "period": "program_total",
        "preferred_minor": 31_000_000,
        "hard_ceiling_minor": 37_000_000,
        "elasticity_bps": 750,
        "refused": False,
    }
    body = "Synthetic family budget confirmation for the local pilot."
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    worker_engine = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    worker_sessions = async_sessionmaker(worker_engine, expire_on_commit=False)
    factory = postgres_worker_repository_factory(worker_sessions)
    try:
        async with migrator.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
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
                    "family": json.dumps(
                        PLANNING_FIXTURE.case.family.model_dump(mode="json")
                    ),
                },
            )
            await connection.execute(
                text(
                    "SELECT app.seed_case_participants("
                    ":org,:case,:advisor,:student,:parent)"
                ),
                {
                    "org": ORG,
                    "case": case_id,
                    "advisor": ADVISOR,
                    "student": STUDENT,
                    "parent": PARENT,
                },
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
                    "SELECT * FROM app.create_collaboration_thread("
                    ":org,:actor,'advisor',:case,:thread,:request_hash,:key_hash)"
                ),
                {
                    "org": ORG,
                    "actor": ADVISOR,
                    "case": case_id,
                    "thread": thread_id,
                    "request_hash": hashlib.sha256(b"revision-two-thread").hexdigest(),
                    "key_hash": hashlib.sha256(b"revision-two-thread-key").hexdigest(),
                },
            )
            for name, value in (
                ("night_voyager.actor_id", str(PARENT)),
                ("night_voyager.role", "parent"),
            ):
                await connection.execute(
                    text("SELECT set_config(:name,:value,true)"),
                    {"name": name, "value": value},
                )
            await connection.execute(
                text(
                    "SELECT * FROM app.append_collaboration_message("
                    ":org,:actor,'parent',:thread,:message,:body,:content_hash,"
                    ":request_hash,:key_hash)"
                ),
                {
                    "org": ORG,
                    "actor": PARENT,
                    "thread": thread_id,
                    "message": message_id,
                    "body": body,
                    "content_hash": hashlib.sha256(body.encode()).hexdigest(),
                    "request_hash": hashlib.sha256(b"revision-two-message").hexdigest(),
                    "key_hash": hashlib.sha256(b"revision-two-message-key").hexdigest(),
                },
            )
            await connection.execute(
                text(
                    "SELECT * FROM app.propose_memory_candidate("
                    ":org,:actor,'parent',:message,:candidate,1,'family.budget',"
                    "CAST(:value AS jsonb),:value_hash,:request_hash,:key_hash)"
                ),
                {
                    "org": ORG,
                    "actor": PARENT,
                    "message": message_id,
                    "candidate": candidate_id,
                    "value": json.dumps(budget),
                    "value_hash": canonical_sha256(budget),
                    "request_hash": hashlib.sha256(b"revision-two-candidate").hexdigest(),
                    "key_hash": hashlib.sha256(b"revision-two-candidate-key").hexdigest(),
                },
            )
            for name, value in (
                ("night_voyager.actor_id", str(ADVISOR)),
                ("night_voyager.role", "advisor"),
            ):
                await connection.execute(
                    text("SELECT set_config(:name,:value,true)"),
                    {"name": name, "value": value},
                )
            confirmed = (
                await connection.execute(
                    text(
                        "SELECT * FROM app.verify_memory_candidate("
                        ":org,:actor,:candidate,1,'confirm',:reason,:verification,"
                        ":fact,:request_hash,:key_hash)"
                    ),
                    {
                        "org": ORG,
                        "actor": ADVISOR,
                        "candidate": candidate_id,
                        "reason": "Confirmed synthetic family budget for planning.",
                        "verification": verification_id,
                        "fact": fact_id,
                        "request_hash": hashlib.sha256(b"revision-two-verify").hexdigest(),
                        "key_hash": hashlib.sha256(b"revision-two-verify-key").hexdigest(),
                    },
                )
            ).mappings().one()
            assert confirmed.result_revision == 2
            created = (
                await connection.execute(
                    text(
                        "SELECT * FROM app.create_agent_task("
                        ":org,:actor,:case,:task,'generate_planning_run_v1',2,"
                        ":pack,1,'m3a-policy-v1',CAST(:manifest AS jsonb),"
                        ":request_hash,:key_hash)"
                    ),
                    {
                        "org": ORG,
                        "actor": ADVISOR,
                        "case": case_id,
                        "task": task_id,
                        "pack": PACK,
                        "manifest": skill_manifest(),
                        "request_hash": hashlib.sha256(b"revision-two-task").hexdigest(),
                        "key_hash": hashlib.sha256(b"revision-two-task-key").hexdigest(),
                    },
                )
            ).mappings().one()
            assert created.task_id == task_id
            assert created.state == "queued"

        worker_id = "worker-revision-two"
        async with factory() as repository:
            claim = await repository.claim(worker_id)
            assert claim is not None
            assert claim.task_id == task_id
            task_input = await repository.load(claim)
        assert task_input.request.case_id == case_id
        assert task_input.request.case_revision == 2
        assert task_input.skill_pin == skill_pin()
        snapshot = await PersistedSyntheticSnapshotRepository(worker_sessions).load(
            task_input.request
        )
        assert snapshot.case.case_id == case_id
        assert snapshot.case.revision == 2
        assert snapshot.case.family.budget.model_dump(mode="json") == budget
        async with factory() as repository:
            assert (
                await repository.fail(
                    claim,
                    worker_id,
                    "test_complete",
                    retryable=False,
                    fallback_used=False,
                )
                == "failed"
            )

        async with migrator.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            row = (
                await connection.execute(
                    text(
                        "SELECT c.state AS case_state,c.current_revision,t.state AS task_state,"
                        "t.case_revision,t.skill_definition_id,t.skill_version_id,"
                        "t.skill_activation_event_id,t.skill_activation_sequence,"
                        "t.runtime_binding_sha256,e.skill_definition_id AS e_definition,"
                        "e.skill_version_id AS e_version,"
                        "e.skill_activation_event_id AS e_activation,"
                        "e.skill_activation_sequence AS e_sequence,"
                        "e.runtime_binding_sha256 AS e_binding,e.status AS execution_status "
                        "FROM app.student_cases c JOIN app.agent_tasks t "
                        "ON t.organization_id=c.organization_id AND t.case_id=c.id "
                        "JOIN app.agent_executions e ON e.organization_id=t.organization_id "
                        "AND e.task_id=t.id WHERE c.organization_id=:org AND c.id=:case "
                        "AND t.id=:task"
                    ),
                    {"org": ORG, "case": case_id, "task": task_id},
                )
            ).mappings().one()
        expected_pin = tuple(skill_pin().model_dump().values())
        assert row.case_state == "planning"
        assert row.current_revision == row.case_revision == 2
        assert row.task_state == row.execution_status == "failed"
        assert tuple(
            row[name]
            for name in (
                "skill_definition_id",
                "skill_version_id",
                "skill_activation_event_id",
                "skill_activation_sequence",
                "runtime_binding_sha256",
            )
        ) == expected_pin
        assert (
            row.e_definition,
            row.e_version,
            row.e_activation,
            row.e_sequence,
            row.e_binding,
        ) == expected_pin
    finally:
        await migrator.dispose()
        await api.dispose()
        await worker_engine.dispose()


@pytest.mark.asyncio
async def test_mixed_operation_reuses_the_existing_queue_and_worker_authority() -> None:
    case_id, version = await approved_pack(902)
    task_id = UUID("80000000-0000-0000-0000-000000000902")
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    worker_engine = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    sessions = async_sessionmaker(worker_engine, expire_on_commit=False)
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
                    "SELECT * FROM app.create_agent_task(:org,:actor,:case,:task,"
                    "'generate_governed_mixed_planning_run_v1',1,:pack,:version,"
                    "'m3a-policy-v1',CAST(:skill_manifest AS jsonb),"
                    ":request_hash,:key_hash)"
                ),
                {
                    "org": ORG,
                    "actor": ADVISOR,
                    "case": case_id,
                    "task": task_id,
                    "pack": PACK,
                    "version": version,
                    "skill_manifest": skill_manifest(),
                    "request_hash": hashlib.sha256(str(task_id).encode()).hexdigest(),
                    "key_hash": hashlib.sha256(f"key:{task_id}".encode()).hexdigest(),
                },
            )
        worker = TaskWorker(
            postgres_worker_repository_factory(sessions),
            PlanningAdapterRouter(
                synthetic=DeterministicPlanningAdapter(
                    PersistedSyntheticSnapshotRepository(sessions)
                ),
                mixed=GovernedMixedPlanningAdapter(PostgresMixedPlanningRepository(sessions)),
            ),
            registry(),
            worker_id="worker-mixed-real",
        )
        assert await worker.run_once() is True
        inspector = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
        async with inspector.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            row = (
                (
                    await connection.execute(
                        text(
                            "SELECT t.state,r.state AS run_state,r.source_pack_version,"
                            "e.adapter_id,e.adapter_version "
                            "FROM app.agent_tasks t JOIN app.agent_executions e "
                            "ON e.organization_id=t.organization_id AND e.task_id=t.id "
                            "JOIN app.planning_runs r ON r.organization_id=t.organization_id "
                            "AND r.id=t.result_planning_run_id "
                            "WHERE t.organization_id=:org AND t.id=:task"
                        ),
                        {"org": ORG, "task": task_id},
                    )
                )
                .mappings()
                .one()
            )
            assert dict(row) == {
                "state": "waiting_review",
                "run_state": "review_required",
                "source_pack_version": version,
                "adapter_id": "governed_mixed_planning",
                "adapter_version": "dra-mixed-v1",
            }
        await inspector.dispose()
    finally:
        await api.dispose()
        await worker_engine.dispose()


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
        inspector = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
        try:
            async with inspector.begin() as connection:
                await connection.execute(
                    text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                    {"org": str(ORG)},
                )
                execution = (
                    (
                        await connection.execute(
                            text(
                                "SELECT status,retryable,fallback_used,input_sha256,output_sha256,"
                                "duration_ms,cost_status FROM app.agent_executions "
                                "WHERE organization_id=:org AND task_id=:task"
                            ),
                            {"org": ORG, "task": task_id},
                        )
                    )
                    .mappings()
                    .one()
                )
        finally:
            await inspector.dispose()
        assert execution.status == "succeeded"
        assert execution.retryable is False
        assert execution.fallback_used is False
        assert execution.input_sha256 == expected_input_sha256(case_id)
        assert execution.output_sha256 is not None
        assert execution.duration_ms is not None and execution.duration_ms >= 0
        assert execution.cost_status == "not_applicable"
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
            await repository.start(claim, "worker-before-restart", expected_input_sha256(case_id))
        await expire_lease(task_id)
        restarted = TaskWorker(
            factory,
            PlanningAdapterRouter(
                synthetic=DeterministicPlanningAdapter(
                    PersistedSyntheticSnapshotRepository(sessions)
                ),
                mixed=GovernedMixedPlanningAdapter(PostgresMixedPlanningRepository(sessions)),
            ),
            registry(),
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
        NeverSnapshotRepository(),
        injected_failure=AdapterFailure(code=AdapterFailureCode.TRANSIENT_UNAVAILABLE),
    )
    worker, engine = task_worker("worker-retry", adapter)
    try:
        assert await worker.run_once() is True
        assert await worker.run_once() is True
        assert await worker.run_once() is True
        assert await worker.run_once() is False
        inspector = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
        try:
            async with inspector.begin() as connection:
                await connection.execute(
                    text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                    {"org": str(ORG)},
                )
                row = (
                    (
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
                    )
                    .mappings()
                    .one()
                )
                executions = (
                    (
                        await connection.execute(
                            text(
                                "SELECT attempt_no,status,retryable,fallback_used,input_sha256,"
                                "output_sha256,duration_ms,cost_status "
                                "FROM app.agent_executions WHERE organization_id=:org "
                                "AND task_id=:task ORDER BY attempt_no"
                            ),
                            {"org": ORG, "task": task_id},
                        )
                    )
                    .mappings()
                    .all()
                )
        finally:
            await inspector.dispose()
        assert dict(row) == {
            "state": "failed",
            "attempt_count": 3,
            "terminal_code": "transient_unavailable",
            "executions": 3,
            "retries": 2,
        }
        assert [execution.status for execution in executions] == [
            "retry_scheduled",
            "retry_scheduled",
            "failed",
        ]
        assert [execution.retryable for execution in executions] == [True, True, False]
        assert all(execution.fallback_used is False for execution in executions)
        assert all(
            execution.input_sha256 == expected_input_sha256(case_id) for execution in executions
        )
        assert all(execution.output_sha256 is None for execution in executions)
        assert all(
            execution.duration_ms is not None and execution.duration_ms >= 0
            for execution in executions
        )
        assert all(execution.cost_status == "not_applicable" for execution in executions)
    finally:
        await engine.dispose()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_fallback_authority_failure_is_audited_without_raw_payload() -> None:
    case_id = UUID("40000000-0000-0000-0000-000000000406")
    task_id = UUID("80000000-0000-0000-0000-000000000406")
    await seed_and_create(case_id, task_id, "8")
    adapter = DeterministicPlanningAdapter(
        NeverSnapshotRepository(),
        injected_failure=AdapterFailure(code=AdapterFailureCode.FALLBACK_AUTHORITY),
    )
    worker, engine = task_worker("worker-fallback", adapter)
    try:
        assert await worker.run_once() is True
        inspector = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
        try:
            async with inspector.begin() as connection:
                await connection.execute(
                    text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                    {"org": str(ORG)},
                )
                execution = (
                    (
                        await connection.execute(
                            text(
                                "SELECT status,retryable,fallback_used,input_sha256,output_sha256,"
                                "public_code,duration_ms,cost_status "
                                "FROM app.agent_executions WHERE organization_id=:org "
                                "AND task_id=:task"
                            ),
                            {"org": ORG, "task": task_id},
                        )
                    )
                    .mappings()
                    .one()
                )
        finally:
            await inspector.dispose()
        assert execution.status == "failed"
        assert execution.retryable is False
        assert execution.fallback_used is True
        assert execution.input_sha256 == expected_input_sha256(case_id)
        assert execution.output_sha256 is None
        assert execution.public_code == "fallback_authority"
        assert execution.duration_ms is not None and execution.duration_ms >= 0
        assert execution.cost_status == "not_applicable"
    finally:
        await engine.dispose()  # type: ignore[attr-defined]
