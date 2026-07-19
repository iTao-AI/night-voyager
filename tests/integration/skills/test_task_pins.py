from __future__ import annotations

import json
import os
from dataclasses import dataclass
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from night_voyager.adapters.deterministic_planning import DeterministicPlanningAdapter
from night_voyager.adapters.governed_mixed_planning import GovernedMixedPlanningAdapter
from night_voyager.adapters.protocols import (
    AdapterFailure,
    AdapterFailureCode,
    AdapterOutcome,
    PlanningAdapterRequest,
    PlanningAdapterResolution,
)
from night_voyager.adapters.router import PlanningAdapterRouter
from night_voyager.identity.models import ActorContext, ActorRole
from night_voyager.planning.fixtures import validate_planning_fixture
from night_voyager.planning.hashing import canonical_sha256
from night_voyager.planning.mixed_postgres import PostgresMixedPlanningRepository
from night_voyager.planning.synthetic_postgres import (
    PersistedSyntheticSnapshotRepository,
)
from night_voyager.skills.models import SkillKey, SkillLeafBindingV1, SkillRuntimePin
from night_voyager.skills.registry import SkillRuntimeRegistry
from night_voyager.tasks.application import CreateTaskCommand, TaskService
from night_voyager.tasks.postgres import (
    PostgresTaskRepository,
    postgres_worker_repository_factory,
)
from night_voyager.tasks.worker import TaskWorker

pytestmark = pytest.mark.database

ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
PACK = UUID("50000000-0000-0000-0000-000000000001")
PLANNING_FIXTURE = validate_planning_fixture().planning_input


def registry() -> SkillRuntimeRegistry:
    return SkillRuntimeRegistry.load_packaged()


def runtime_entry(version: str = "1.0.0"):
    return registry().get(SkillKey.STUDY_DESTINATION_COMPARE, version)


def expected_pin() -> SkillRuntimePin:
    return SkillRuntimePin(
        skill_definition_id=UUID("81000000-0000-0000-0000-000000000002"),
        skill_version_id=UUID("82000000-0000-0000-0000-000000000002"),
        skill_activation_event_id=UUID("84000000-0000-0000-0000-000000000001"),
        skill_activation_sequence=1,
        runtime_binding_sha256=runtime_entry().runtime_binding_sha256 or "",
    )


def operation_leaf(index: int) -> SkillLeafBindingV1:
    bindings = runtime_entry().operation_bindings
    assert bindings is not None
    return bindings[index]


def actor() -> ActorContext:
    return ActorContext(ORG, ADVISOR, ActorRole.ADVISOR, UUID(int=1))


async def set_context(session: AsyncSession) -> None:
    for name, value in (
        ("night_voyager.organization_id", str(ORG)),
        ("night_voyager.actor_id", str(ADVISOR)),
        ("night_voyager.role", "advisor"),
    ):
        await session.execute(
            text("SELECT set_config(:name,:value,true)"),
            {"name": name, "value": value},
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
                    "INSERT INTO app.student_case_participants("
                    "organization_id,case_id,actor_id,role) "
                    "VALUES(:org,:case,:actor,'advisor') ON CONFLICT DO NOTHING"
                ),
                {"org": ORG, "case": case_id, "actor": ADVISOR},
            )
    finally:
        await engine.dispose()


async def create_task(case_id: UUID, task_id: UUID, key: str) -> dict[str, object]:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session, session.begin():
            await set_context(session)
            return await TaskService(
                PostgresTaskRepository(session),
                registry=registry(),
                id_factory=lambda: task_id,
            ).create(
                actor(),
                CreateTaskCommand(
                    case_id=case_id,
                    expected_case_revision=1,
                    source_pack_id=PACK,
                    source_pack_version=1,
                ),
                key,
            )
    finally:
        await engine.dispose()


def request(case_id: UUID) -> PlanningAdapterRequest:
    return PlanningAdapterRequest(
        schema_version=1,
        operation="generate_planning_run_v1",
        organization_id=ORG,
        case_id=case_id,
        case_revision=1,
        source_pack_id=PACK,
        source_pack_version=1,
        policy_version="m3a-policy-v1",
    )


def expected_input_sha256(case_id: UUID) -> str:
    return canonical_sha256(
        {
            "request": request(case_id).model_dump(mode="json"),
            "five_field_pin": expected_pin().model_dump(mode="json"),
        }
    )


@dataclass
class CountingFailureAdapter:
    code: AdapterFailureCode
    calls: int = 0

    async def generate(self, request: PlanningAdapterRequest) -> AdapterOutcome:
        self.calls += 1
        return AdapterFailure(code=self.code)


@dataclass
class DriftRouter:
    adapter: CountingFailureAdapter

    def resolve(self, operation: str) -> PlanningAdapterResolution:
        assert operation == "generate_planning_run_v1"
        return PlanningAdapterResolution(
            leaf_binding=operation_leaf(1),
            adapter=self.adapter,
        )


@pytest.mark.asyncio
async def test_create_replay_claim_and_success_keep_one_exact_five_field_pin() -> None:
    case_id = UUID("40000000-0000-0000-0000-000000001501")
    task_id = UUID("80000000-0000-0000-0000-000000001501")
    await seed_case(case_id)

    created = await create_task(case_id, task_id, "pin-create-1501")
    replayed = await create_task(case_id, UUID(int=15010), "pin-create-1501")
    assert created["task_id"] == replayed["task_id"] == task_id
    assert created["skill_pin"] == replayed["skill_pin"] == expected_pin()
    assert created["leaf_binding"] == replayed["leaf_binding"] == operation_leaf(0)
    assert replayed["replayed"] is True

    worker_engine = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    worker_sessions = async_sessionmaker(worker_engine, expire_on_commit=False)
    worker = TaskWorker(
        postgres_worker_repository_factory(worker_sessions),
        PlanningAdapterRouter(
            synthetic=DeterministicPlanningAdapter(
                PersistedSyntheticSnapshotRepository(worker_sessions)
            ),
            mixed=GovernedMixedPlanningAdapter(PostgresMixedPlanningRepository(worker_sessions)),
        ),
        registry(),
        worker_id="pin-success-1501",
    )
    try:
        assert await worker.run_once() is True
    finally:
        await worker_engine.dispose()

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
                            "SELECT t.state,t.skill_definition_id,t.skill_version_id,"
                            "t.skill_activation_event_id,t.skill_activation_sequence,"
                            "t.runtime_binding_sha256,e.skill_definition_id AS e_definition,"
                            "e.skill_version_id AS e_version,"
                            "e.skill_activation_event_id AS e_activation,"
                            "e.skill_activation_sequence AS e_sequence,"
                            "e.runtime_binding_sha256 AS e_binding,e.input_sha256,e.status "
                            "FROM app.agent_tasks t JOIN app.agent_executions e "
                            "ON e.organization_id=t.organization_id AND e.task_id=t.id "
                            "WHERE t.organization_id=:org AND t.id=:task"
                        ),
                        {"org": ORG, "task": task_id},
                    )
                )
                .mappings()
                .one()
            )
        assert row.state == "waiting_review"
        assert tuple(
            row[name]
            for name in (
                "skill_definition_id",
                "skill_version_id",
                "skill_activation_event_id",
                "skill_activation_sequence",
                "runtime_binding_sha256",
            )
        ) == tuple(expected_pin().model_dump().values())
        assert (
            row.e_definition,
            row.e_version,
            row.e_activation,
            row.e_sequence,
            row.e_binding,
        ) == tuple(expected_pin().model_dump().values())
        assert row.input_sha256 == expected_input_sha256(case_id)
        assert row.status == "succeeded"
    finally:
        await inspector.dispose()


@pytest.mark.asyncio
async def test_all_three_retry_executions_copy_the_pin_and_exact_input_hash() -> None:
    case_id = UUID("40000000-0000-0000-0000-000000001502")
    task_id = UUID("80000000-0000-0000-0000-000000001502")
    await seed_case(case_id)
    await create_task(case_id, task_id, "pin-retry-1502")

    adapter = CountingFailureAdapter(AdapterFailureCode.TRANSIENT_UNAVAILABLE)
    worker_engine = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    worker_sessions = async_sessionmaker(worker_engine, expire_on_commit=False)
    worker = TaskWorker(
        postgres_worker_repository_factory(worker_sessions),
        PlanningAdapterRouter(synthetic=adapter, mixed=adapter),
        registry(),
        worker_id="pin-retry-1502",
    )
    try:
        assert [await worker.run_once() for _ in range(4)] == [True, True, True, False]
    finally:
        await worker_engine.dispose()
    assert adapter.calls == 3

    inspector = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with inspector.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            executions = (
                (
                    await connection.execute(
                        text(
                            "SELECT attempt_no,skill_definition_id,skill_version_id,"
                            "skill_activation_event_id,skill_activation_sequence,"
                            "runtime_binding_sha256,input_sha256,status,retryable "
                            "FROM app.agent_executions WHERE organization_id=:org "
                            "AND task_id=:task ORDER BY attempt_no"
                        ),
                        {"org": ORG, "task": task_id},
                    )
                )
                .mappings()
                .all()
            )
            task = (
                (
                    await connection.execute(
                        text(
                            "SELECT state,terminal_code FROM app.agent_tasks "
                            "WHERE organization_id=:org AND id=:task"
                        ),
                        {"org": ORG, "task": task_id},
                    )
                )
                .mappings()
                .one()
            )
        assert [row.attempt_no for row in executions] == [1, 2, 3]
        assert all(
            tuple(
                row[name]
                for name in (
                    "skill_definition_id",
                    "skill_version_id",
                    "skill_activation_event_id",
                    "skill_activation_sequence",
                    "runtime_binding_sha256",
                )
            )
            == tuple(expected_pin().model_dump().values())
            for row in executions
        )
        assert all(row.input_sha256 == expected_input_sha256(case_id) for row in executions)
        assert [row.status for row in executions] == [
            "retry_scheduled",
            "retry_scheduled",
            "failed",
        ]
        assert [row.retryable for row in executions] == [True, True, False]
        assert dict(task) == {
            "state": "failed",
            "terminal_code": "transient_unavailable",
        }
    finally:
        await inspector.dispose()


@pytest.mark.asyncio
async def test_router_leaf_drift_fails_before_start_adapter_or_retry_loop() -> None:
    case_id = UUID("40000000-0000-0000-0000-000000001503")
    task_id = UUID("80000000-0000-0000-0000-000000001503")
    await seed_case(case_id)
    await create_task(case_id, task_id, "pin-drift-1503")

    adapter = CountingFailureAdapter(AdapterFailureCode.UNKNOWN)
    worker_engine = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    worker_sessions = async_sessionmaker(worker_engine, expire_on_commit=False)
    worker = TaskWorker(
        postgres_worker_repository_factory(worker_sessions),
        DriftRouter(adapter),
        registry(),
        worker_id="pin-drift-1503",
    )
    try:
        assert await worker.run_once() is True
        assert await worker.run_once() is False
    finally:
        await worker_engine.dispose()
    assert adapter.calls == 0

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
                            "SELECT t.state,t.terminal_code,t.attempt_count,"
                            "e.status,e.retryable,e.public_code,e.input_sha256,"
                            "(SELECT count(*) FROM internal.agent_task_dispatch d "
                            "WHERE d.organization_id=t.organization_id "
                            "AND d.task_id=t.id) AS dispatches,"
                            "(SELECT count(*) FROM app.agent_task_events event "
                            "WHERE event.organization_id=t.organization_id "
                            "AND event.task_id=t.id "
                            "AND event.event_code='execution_started') AS starts "
                            "FROM app.agent_tasks t JOIN app.agent_executions e "
                            "ON e.organization_id=t.organization_id AND e.task_id=t.id "
                            "WHERE t.organization_id=:org AND t.id=:task"
                        ),
                        {"org": ORG, "task": task_id},
                    )
                )
                .mappings()
                .one()
            )
        assert dict(row) == {
            "state": "failed",
            "terminal_code": "skill_pin_invalid",
            "attempt_count": 1,
            "status": "failed",
            "retryable": False,
            "public_code": "skill_pin_invalid",
            "input_sha256": None,
            "dispatches": 0,
            "starts": 0,
        }
    finally:
        await inspector.dispose()


def test_packaged_registry_keeps_same_binding_digest_but_distinct_versions() -> None:
    entry = runtime_entry()
    next_entry = runtime_entry("1.0.1")
    assert entry.runtime_binding_sha256 == next_entry.runtime_binding_sha256
    assert (entry.skill_key, entry.version) != (
        next_entry.skill_key,
        next_entry.version,
    )
    with pytest.raises(ValueError, match="unsupported Skill key/version"):
        registry().validate_pin(
            expected_pin(),
            SkillKey.STUDY_DESTINATION_COMPARE,
            "9.9.9",
            "generate_planning_run_v1",
            SkillLeafBindingV1(
                operation="generate_planning_run_v1",
                adapter_id="deterministic_planning",
                adapter_version="m4a-v1",
            ),
        )
