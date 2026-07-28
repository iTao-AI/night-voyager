from __future__ import annotations

import hashlib
import inspect
import json
import os
from collections.abc import Mapping
from dataclasses import replace
from datetime import date
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from night_voyager.adapters.deterministic_planning import DeterministicPlanningAdapter
from night_voyager.adapters.governed_mixed_planning import GovernedMixedPlanningAdapter
from night_voyager.adapters.router import PlanningAdapterRouter
from night_voyager.connected_demo.errors import DemoContractUnavailableError
from night_voyager.connected_demo.fixtures import (
    CanonicalDemoSourceContract,
    resolve_canonical_demo_source_contract,
)
from night_voyager.connected_demo.models import DemoPhase, DemoPhaseV2
from night_voyager.connected_demo.postgres import PostgresConnectedDemoRepository
from night_voyager.identity.demo_seed import CONNECTED_DEMO_CASE_ID
from night_voyager.identity.models import ActorContext, ActorRole
from night_voyager.planning.fixtures import validate_planning_fixture
from night_voyager.planning.hashing import canonical_sha256
from night_voyager.planning.mixed_postgres import PostgresMixedPlanningRepository
from night_voyager.planning.synthetic_postgres import (
    PersistedSyntheticSnapshotRepository,
)
from night_voyager.skills.registry import SkillRuntimeRegistry
from night_voyager.tasks.application import CreateTaskCommand, TaskService
from night_voyager.tasks.postgres import (
    PostgresTaskRepository,
    postgres_worker_repository_factory,
)
from night_voyager.tasks.worker import TaskWorker

pytestmark = pytest.mark.database
DEMO_ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
PARENT = UUID("20000000-0000-0000-0000-000000000003")
STUDENT = UUID("20000000-0000-0000-0000-000000000002")
PLANNING_FIXTURE = validate_planning_fixture().planning_input


def test_demo_phase_v2_contains_every_revision_journey_projection() -> None:
    assert {
        DemoPhaseV2.REVIEW_REQUIRED,
        DemoPhaseV2.REVISION_REQUESTED,
        DemoPhaseV2.REVISION_FACT_PENDING,
        DemoPhaseV2.REPLAN_REQUIRED,
        DemoPhaseV2.REVISION_TASK_ACTIVE,
        DemoPhaseV2.REVISION_REVIEW_REQUIRED,
        DemoPhaseV2.REVISION_BLOCKED,
        DemoPhaseV2.FAMILY_REVIEW,
        DemoPhaseV2.PLAN_READY,
        DemoPhaseV2.TERMINAL_TASK_FAILURE,
    } <= set(DemoPhaseV2)


def context(role: ActorRole = ActorRole.ADVISOR) -> ActorContext:
    actor = {
        ActorRole.ADVISOR: ADVISOR,
        ActorRole.STUDENT: STUDENT,
        ActorRole.PARENT: PARENT,
    }[role]
    return ActorContext(
        organization_id=DEMO_ORG,
        actor_id=actor,
        role=role,
        session_id=UUID("30000000-0000-0000-0000-000000000001"),
    )


async def set_context(session: AsyncSession) -> None:
    for name, value in (
        ("night_voyager.organization_id", str(DEMO_ORG)),
        ("night_voyager.actor_id", str(ADVISOR)),
        ("night_voyager.role", "advisor"),
    ):
        await session.execute(
            text("SELECT set_config(:name,:value,true)"),
            {"name": name, "value": value},
        )


async def journey_status_for_role(
    connection: AsyncConnection, case_id: UUID, role: ActorRole
):
    actor_context = context(role)
    for name, value in (
        ("night_voyager.organization_id", str(actor_context.organization_id)),
        ("night_voyager.actor_id", str(actor_context.actor_id)),
        ("night_voyager.role", role.value),
    ):
        await connection.execute(
            text("SELECT set_config(:name,:value,true)"),
            {"name": name, "value": value},
        )
    async with AsyncSession(bind=connection) as session:
        return await PostgresConnectedDemoRepository(session).journey_status(
            actor_context, case_id
        )


async def set_connection_role(
    connection: AsyncConnection, role: ActorRole
) -> None:
    actor_context = context(role)
    for name, value in (
        ("night_voyager.actor_id", str(actor_context.actor_id)),
        ("night_voyager.role", role.value),
    ):
        await connection.execute(
            text("SELECT set_config(:name,:value,true)"),
            {"name": name, "value": value},
        )


@pytest.mark.asyncio
async def test_task_ready_projection_uses_canonical_server_inputs_under_api_role() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with AsyncSession(engine) as session, session.begin():
            await set_context(session)
            projection = await PostgresConnectedDemoRepository(session).advisor_ledger(
                context(), CONNECTED_DEMO_CASE_ID, resolve_canonical_demo_source_contract()
            )

        assert projection is not None
        assert projection.phase is DemoPhase.TASK_READY
        assert projection.canonical_task_inputs is not None
        assert projection.canonical_task_inputs.case_id == CONNECTED_DEMO_CASE_ID
        assert projection.model_dump().keys() == {
            "schema_version",
            "proof_mode",
            "phase",
            "case_id",
            "case_revision",
            "case_state",
            "canonical_task_inputs",
            "task",
            "planning_run",
            "routes",
            "evidence",
            "review_inputs",
            "current_brief_id",
            "recovery",
        }
    finally:
        await engine.dispose()


@pytest.mark.parametrize(
    ("task_state", "revision"),
    (("failed", 1), ("timed_out", 1), ("cancelled", 2)),
)
def test_journey_phase_projects_terminal_tasks_as_failure(
    task_state: str, revision: int
) -> None:
    class JourneyPhaseProbe(PostgresConnectedDemoRepository):
        @classmethod
        def project(cls, row: Mapping[str, Any]) -> DemoPhaseV2:
            return cls._journey_phase(row)

    row = {
        "state": "planning",
        "current_revision": revision,
        "brief_id": None,
        "decision_id": None,
        "revision_requested": False,
        "revision_fact_pending": False,
        "run_state": None,
        "supersedes_run_id": None,
        "task_state": task_state,
    }
    assert (
        JourneyPhaseProbe.project(row)
        is DemoPhaseV2.TERMINAL_TASK_FAILURE
    )


def test_journey_brief_authority_is_state_aware_and_cardinality_closed() -> None:
    source = inspect.getsource(PostgresConnectedDemoRepository.journey_status)
    authority = source.split(
        "LEFT JOIN LATERAL (SELECT brief_row.id", 1
    )[1].split("brief ON true", 1)[0]

    assert "c.state='family_review'" in authority
    assert "brief_row.is_current" in authority
    assert "decision_row.id IS NULL" in authority
    assert "c.state='plan_ready'" in authority
    assert "NOT brief_row.is_current" in authority
    assert "decision_row.id IS NOT NULL" in authority
    assert "LIMIT" not in authority
    assert "ORDER BY" not in authority


def test_journey_phase_rejects_brief_without_matching_decision() -> None:
    class JourneyPhaseProbe(PostgresConnectedDemoRepository):
        @classmethod
        def project(cls, row: Mapping[str, Any]) -> DemoPhaseV2:
            return cls._journey_phase(row)

    row = {
        "state": "plan_ready",
        "current_revision": 1,
        "brief_id": UUID("81000000-0000-0000-0000-000000000399"),
        "decision_id": None,
        "revision_requested": False,
        "revision_fact_pending": False,
        "run_state": None,
        "supersedes_run_id": None,
        "task_state": None,
    }

    assert JourneyPhaseProbe.project(row) is not DemoPhaseV2.PLAN_READY


@pytest.mark.asyncio
async def test_terminal_task_phase_and_role_are_durable_across_repository_reload() -> None:
    case_id = uuid4()
    task_id = uuid4()
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with migrator.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(DEMO_ORG)},
            )
            await connection.execute(
                text(
                    "SELECT app.publish_case_revision("
                    ":org,:case,NULL,1,CAST(:student AS jsonb),CAST(:family AS jsonb))"
                ),
                {
                    "org": DEMO_ORG,
                    "case": case_id,
                    "student": PLANNING_FIXTURE.case.student.model_dump_json(),
                    "family": PLANNING_FIXTURE.case.family.model_dump_json(),
                },
            )
            await connection.execute(
                text(
                    "SELECT app.seed_case_participants("
                    ":org,:case,:advisor,:student,:parent)"
                ),
                {
                    "org": DEMO_ORG,
                    "case": case_id,
                    "advisor": ADVISOR,
                    "student": STUDENT,
                    "parent": PARENT,
                },
            )
            await connection.execute(
                text("SELECT app.transition_case(:org,:case,'intake','planning')"),
                {"org": DEMO_ORG, "case": case_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.agent_tasks("
                    "organization_id,id,case_id,operation,case_revision,"
                    "source_pack_id,source_pack_version,policy_version,"
                    "request_sha256,created_by_actor_id,state,terminal_code) VALUES("
                    ":org,:task,:case,'generate_planning_run_v1',1,"
                    "'50000000-0000-0000-0000-000000000001',1,'m3a-policy-v1',"
                    "repeat('a',64),:advisor,'failed','synthetic_failure')"
                ),
                {
                    "org": DEMO_ORG,
                    "task": task_id,
                    "case": case_id,
                    "advisor": ADVISOR,
                },
            )
        phases: list[tuple[DemoPhaseV2, str]] = []
        for role in (ActorRole.ADVISOR, ActorRole.STUDENT, ActorRole.PARENT):
            async with api.begin() as connection:
                status = await journey_status_for_role(connection, case_id, role)
                assert status is not None
                phases.append((status.phase, status.active_role))
        assert phases == [
            (DemoPhaseV2.TERMINAL_TASK_FAILURE, "advisor"),
            (DemoPhaseV2.TERMINAL_TASK_FAILURE, "advisor"),
            (DemoPhaseV2.TERMINAL_TASK_FAILURE, "advisor"),
        ]
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_wrong_role_is_hidden_and_source_mismatch_fails_closed() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    source = resolve_canonical_demo_source_contract()
    bad_source = CanonicalDemoSourceContract(
        source_pack_id=source.source_pack_id,
        source_pack_version=source.source_pack_version,
        manifest_sha256="0" * 64,
        policy_version=source.policy_version,
    )
    try:
        async with AsyncSession(engine) as session, session.begin():
            await set_context(session)
            repository = PostgresConnectedDemoRepository(session)
            assert (
                await repository.advisor_ledger(
                    context(ActorRole.PARENT), CONNECTED_DEMO_CASE_ID, source
                )
                is None
            )
            assert (
                await repository.journey_status(
                    replace(context(), actor_id=uuid4()),
                    CONNECTED_DEMO_CASE_ID,
                )
                is None
            )
            assert (
                await repository.journey_status(
                    replace(context(), organization_id=uuid4()),
                    CONNECTED_DEMO_CASE_ID,
                )
                is None
            )
            with pytest.raises(DemoContractUnavailableError):
                await repository.advisor_ledger(context(), CONNECTED_DEMO_CASE_ID, bad_source)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_review_required_projection_reads_real_worker_result() -> None:
    case_id = uuid4()
    task_id = uuid4()
    source = resolve_canonical_demo_source_contract()
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    worker_engine = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    try:
        async with migrator.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(DEMO_ORG)},
            )
            await connection.execute(
                text(
                    "SELECT app.publish_case_revision(:org,:case,NULL,1,"
                    "CAST(:student AS jsonb),CAST(:family AS jsonb))"
                ),
                {
                    "org": DEMO_ORG,
                    "case": case_id,
                    "student": json.dumps(PLANNING_FIXTURE.case.student.model_dump(mode="json")),
                    "family": json.dumps(PLANNING_FIXTURE.case.family.model_dump(mode="json")),
                },
            )
            await connection.execute(
                text("SELECT app.transition_case(:org,:case,'intake','planning')"),
                {"org": DEMO_ORG, "case": case_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.student_case_participants"
                    "(organization_id,case_id,actor_id,role) "
                    "VALUES(:org,:case,:actor,'advisor')"
                ),
                {"org": DEMO_ORG, "case": case_id, "actor": ADVISOR},
            )
        sessions = async_sessionmaker(api, expire_on_commit=False)
        async with sessions() as session, session.begin():
            for name, value in (
                ("night_voyager.organization_id", str(DEMO_ORG)),
                ("night_voyager.actor_id", str(ADVISOR)),
                ("night_voyager.role", "advisor"),
            ):
                await session.execute(
                    text("SELECT set_config(:name,:value,true)"),
                    {"name": name, "value": value},
                )
            await TaskService(
                PostgresTaskRepository(session),
                registry=SkillRuntimeRegistry.load_packaged(),
                id_factory=lambda: task_id,
            ).create(
                context(),
                CreateTaskCommand(
                    case_id=case_id,
                    expected_case_revision=1,
                    source_pack_id=source.source_pack_id,
                    source_pack_version=source.source_pack_version,
                    policy_version=source.policy_version,
                ),
                f"connected-demo-{task_id}",
            )
        worker_sessions = async_sessionmaker(worker_engine, expire_on_commit=False)
        worker = TaskWorker(
            postgres_worker_repository_factory(worker_sessions),
            PlanningAdapterRouter(
                synthetic=DeterministicPlanningAdapter(
                    PersistedSyntheticSnapshotRepository(worker_sessions)
                ),
                mixed=GovernedMixedPlanningAdapter(
                    PostgresMixedPlanningRepository(worker_sessions)
                ),
            ),
            SkillRuntimeRegistry.load_packaged(),
            worker_id="connected-demo-review-projection",
        )
        assert await worker.run_once() is True
        async with AsyncSession(api) as session, session.begin():
            await set_context(session)
            projection = await PostgresConnectedDemoRepository(session).advisor_ledger(
                context(), case_id, source
            )
        assert projection is not None
        assert projection.phase is DemoPhase.REVIEW_REQUIRED
        assert projection.planning_run is not None
        assert projection.review_inputs is not None
        assert projection.routes
        assert projection.evidence
        australia = next(route for route in projection.routes if route.country.value == "australia")
        japan = next(route for route in projection.routes if route.country.value == "japan")
        malaysia = next(route for route in projection.routes if route.country.value == "malaysia")
        assert projection.review_inputs.eligible_route_ids == (australia.route_id,)
        assert australia.eligible is True
        assert japan.eligible is False
        assert malaysia.eligible is False
        assert australia.required_claims
        assert japan.required_claims
        assert malaysia.required_claims
        assert malaysia.known_gaps
    finally:
        await migrator.dispose()
        await api.dispose()
        await worker_engine.dispose()


@pytest.mark.parametrize("blocked", (False, True))
@pytest.mark.asyncio
async def test_revision_two_ledger_projects_exact_predecessor_comparison(
    blocked: bool,
) -> None:
    case_id = uuid4()
    first_task_id = uuid4()
    second_task_id = uuid4()
    review_id = uuid4()
    thread_id = uuid4()
    message_id = uuid4()
    candidate_id = uuid4()
    verification_id = uuid4()
    fact_id = uuid4()
    source = resolve_canonical_demo_source_contract()
    revised_budget = {
        **PLANNING_FIXTURE.case.family.budget.model_dump(mode="json"),
        "preferred_minor": 10_000_000 if blocked else 31_000_000,
        "hard_ceiling_minor": 12_000_000 if blocked else 37_000_000,
        "elasticity_bps": 500 if blocked else 750,
    }

    def case_hash(label: str) -> str:
        return hashlib.sha256(f"{label}:{case_id}".encode()).hexdigest()

    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    worker_engine = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    api_sessions = async_sessionmaker(api, expire_on_commit=False)
    worker_sessions = async_sessionmaker(worker_engine, expire_on_commit=False)
    try:
        async with migrator.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(DEMO_ORG)},
            )
            await connection.execute(
                text(
                    "SELECT app.publish_case_revision(:org,:case,NULL,1,"
                    "CAST(:student AS jsonb),CAST(:family AS jsonb))"
                ),
                {
                    "org": DEMO_ORG,
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
                    "org": DEMO_ORG,
                    "case": case_id,
                    "advisor": ADVISOR,
                    "student": STUDENT,
                    "parent": PARENT,
                },
            )
            await connection.execute(
                text("SELECT app.transition_case(:org,:case,'intake','planning')"),
                {"org": DEMO_ORG, "case": case_id},
            )

        async with api_sessions() as session, session.begin():
            for name, value in (
                ("night_voyager.organization_id", str(DEMO_ORG)),
                ("night_voyager.actor_id", str(ADVISOR)),
                ("night_voyager.role", "advisor"),
            ):
                await session.execute(
                    text("SELECT set_config(:name,:value,true)"),
                    {"name": name, "value": value},
                )
            await TaskService(
                PostgresTaskRepository(session),
                registry=SkillRuntimeRegistry.load_packaged(),
                id_factory=lambda: first_task_id,
            ).create(
                context(),
                CreateTaskCommand(
                    case_id=case_id,
                    expected_case_revision=1,
                    source_pack_id=source.source_pack_id,
                    source_pack_version=source.source_pack_version,
                    policy_version=source.policy_version,
                ),
                f"comparison-first-{first_task_id}",
            )
        factory = postgres_worker_repository_factory(worker_sessions)
        first_worker = TaskWorker(
            factory,
            PlanningAdapterRouter(
                synthetic=DeterministicPlanningAdapter(
                    PersistedSyntheticSnapshotRepository(worker_sessions)
                ),
                mixed=GovernedMixedPlanningAdapter(
                    PostgresMixedPlanningRepository(worker_sessions)
                ),
            ),
            SkillRuntimeRegistry.load_packaged(),
            worker_id=f"comparison-first-{case_id}",
        )
        assert await first_worker.run_once() is True
        async with api.begin() as connection:
            for name, value in (
                ("night_voyager.organization_id", str(DEMO_ORG)),
                ("night_voyager.actor_id", str(ADVISOR)),
                ("night_voyager.role", "advisor"),
            ):
                await connection.execute(
                    text("SELECT set_config(:name,:value,true)"),
                    {"name": name, "value": value},
                )
            predecessor = await connection.scalar(
                text(
                    "SELECT id FROM app.planning_runs WHERE organization_id=:org "
                    "AND case_id=:case AND is_current"
                ),
                {"org": DEMO_ORG, "case": case_id},
            )
            assert predecessor is not None
            await connection.execute(
                text(
                    "SELECT * FROM app.review_planning_run("
                    ":org,:actor,:case,:run,1,'request_revision',:review,"
                    "'[]'::jsonb,'[]'::jsonb,'bounded revision request',"
                    "NULL,'{}'::jsonb,current_date,:key_hash,:request_hash)"
                ),
                {
                    "org": DEMO_ORG,
                    "actor": ADVISOR,
                    "case": case_id,
                    "run": predecessor,
                    "review": review_id,
                    "key_hash": case_hash("comparison-review-key"),
                    "request_hash": case_hash("comparison-review-request"),
                },
            )
            async with AsyncSession(bind=connection) as session:
                requested_ledger = (
                    await PostgresConnectedDemoRepository(session).advisor_ledger_v2(
                        context(), case_id, source
                    )
                )
            requested_status = await journey_status_for_role(
                connection, case_id, ActorRole.STUDENT
            )
            assert requested_ledger is not None
            assert requested_ledger.phase is DemoPhaseV2.REVISION_REQUESTED
            assert requested_status is not None
            assert requested_status.phase is DemoPhaseV2.REVISION_REQUESTED
            await set_connection_role(connection, ActorRole.ADVISOR)
            await connection.execute(
                text(
                    "SELECT * FROM app.create_collaboration_thread("
                    ":org,:actor,'advisor',:case,:thread,:request_hash,:key_hash)"
                ),
                {
                    "org": DEMO_ORG,
                    "actor": ADVISOR,
                    "case": case_id,
                    "thread": thread_id,
                    "request_hash": case_hash("comparison-thread"),
                    "key_hash": case_hash("comparison-thread-key"),
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
            body = "Synthetic revised family budget for comparison."
            await connection.execute(
                text(
                    "SELECT * FROM app.append_collaboration_message("
                    ":org,:actor,'parent',:thread,:message,:body,:content_hash,"
                    ":request_hash,:key_hash)"
                ),
                {
                    "org": DEMO_ORG,
                    "actor": PARENT,
                    "thread": thread_id,
                    "message": message_id,
                    "body": body,
                    "content_hash": hashlib.sha256(body.encode()).hexdigest(),
                    "request_hash": case_hash("comparison-message"),
                    "key_hash": case_hash("comparison-message-key"),
                },
            )
            await connection.execute(
                text(
                    "SELECT * FROM app.propose_memory_candidate("
                    ":org,:actor,'parent',:message,:candidate,1,'family.budget',"
                    "CAST(:value AS jsonb),:value_hash,:request_hash,:key_hash)"
                ),
                {
                    "org": DEMO_ORG,
                    "actor": PARENT,
                    "message": message_id,
                    "candidate": candidate_id,
                    "value": json.dumps(revised_budget),
                    "value_hash": canonical_sha256(revised_budget),
                    "request_hash": case_hash("comparison-candidate"),
                    "key_hash": case_hash("comparison-candidate-key"),
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
            async with AsyncSession(bind=connection) as session:
                pending_ledger = (
                    await PostgresConnectedDemoRepository(session).advisor_ledger_v2(
                        context(), case_id, source
                    )
                )
            pending_statuses = tuple(
                [
                    await journey_status_for_role(connection, case_id, role)
                    for role in (
                        ActorRole.ADVISOR,
                        ActorRole.STUDENT,
                        ActorRole.PARENT,
                    )
                ]
            )
            assert pending_ledger is not None
            assert pending_ledger.phase is DemoPhaseV2.REVISION_FACT_PENDING
            assert all(status is not None for status in pending_statuses)
            assert {
                status.phase for status in pending_statuses if status is not None
            } == {DemoPhaseV2.REVISION_FACT_PENDING}
            assert {
                status.active_role
                for status in pending_statuses
                if status is not None
            } == {"advisor"}
            assert all(
                status.model_dump(by_alias=True).keys()
                == {
                    "schema",
                    "case_id",
                    "current_revision",
                    "phase",
                    "active_role",
                }
                for status in pending_statuses
                if status is not None
            )
            for name, value in (
                ("night_voyager.actor_id", str(ADVISOR)),
                ("night_voyager.role", "advisor"),
            ):
                await connection.execute(
                    text("SELECT set_config(:name,:value,true)"),
                    {"name": name, "value": value},
                )
            await connection.execute(
                text(
                    "SELECT * FROM app.verify_memory_candidate("
                    ":org,:actor,:candidate,1,'confirm',:reason,:verification,"
                    ":fact,:request_hash,:key_hash)"
                ),
                {
                    "org": DEMO_ORG,
                    "actor": ADVISOR,
                    "candidate": candidate_id,
                    "reason": "Confirmed synthetic budget revision.",
                    "verification": verification_id,
                    "fact": fact_id,
                    "request_hash": case_hash("comparison-verify"),
                    "key_hash": case_hash("comparison-verify-key"),
                },
            )
            async with AsyncSession(bind=connection) as session:
                replan_ledger = (
                    await PostgresConnectedDemoRepository(session).advisor_ledger_v2(
                        context(), case_id, source
                    )
                )
            statuses = tuple(
                [
                    await journey_status_for_role(connection, case_id, role)
                    for role in (
                        ActorRole.ADVISOR,
                        ActorRole.STUDENT,
                        ActorRole.PARENT,
                    )
                ]
            )
            assert replan_ledger is not None
            assert replan_ledger.phase is DemoPhaseV2.REPLAN_REQUIRED
            assert all(status is not None for status in statuses)
            assert {status.phase for status in statuses if status is not None} == {
                DemoPhaseV2.REPLAN_REQUIRED
            }
            assert {
                status.active_role for status in statuses if status is not None
            } == {"advisor"}
        async with api_sessions() as session, session.begin():
            for name, value in (
                ("night_voyager.organization_id", str(DEMO_ORG)),
                ("night_voyager.actor_id", str(ADVISOR)),
                ("night_voyager.role", "advisor"),
            ):
                await session.execute(
                    text("SELECT set_config(:name,:value,true)"),
                    {"name": name, "value": value},
                )
            await TaskService(
                PostgresTaskRepository(session),
                registry=SkillRuntimeRegistry.load_packaged(),
                id_factory=lambda: second_task_id,
            ).create(
                context(),
                CreateTaskCommand(
                    case_id=case_id,
                    expected_case_revision=2,
                    source_pack_id=source.source_pack_id,
                    source_pack_version=source.source_pack_version,
                    policy_version=source.policy_version,
                ),
                f"comparison-second-{second_task_id}",
            )
            repository = PostgresConnectedDemoRepository(session)
            active_ledger = await repository.advisor_ledger_v2(
                context(), case_id, source
            )
            active_status = await repository.journey_status(context(), case_id)
            assert active_ledger is not None
            assert active_ledger.phase is DemoPhaseV2.REVISION_TASK_ACTIVE
            assert active_status is not None
            assert active_status.phase is DemoPhaseV2.REVISION_TASK_ACTIVE
        second_worker = TaskWorker(
            factory,
            PlanningAdapterRouter(
                synthetic=DeterministicPlanningAdapter(
                    PersistedSyntheticSnapshotRepository(worker_sessions)
                ),
                mixed=GovernedMixedPlanningAdapter(
                    PostgresMixedPlanningRepository(worker_sessions)
                ),
            ),
            SkillRuntimeRegistry.load_packaged(),
            worker_id=f"comparison-second-{case_id}",
        )
        assert await second_worker.run_once() is True
        async with AsyncSession(api) as session, session.begin():
            await set_context(session)
            repository = PostgresConnectedDemoRepository(session)
            legacy = await repository.advisor_ledger(context(), case_id, source)
            projection = await repository.advisor_ledger_v2(
                context(), case_id, source
            )
            journey = await repository.journey_status(context(), case_id)
        assert legacy is not None
        if blocked:
            assert legacy.phase is DemoPhase.TERMINAL_TASK_FAILURE
            assert legacy.recovery is not None
        assert projection is not None
        assert projection.phase is (
            DemoPhaseV2.REVISION_BLOCKED
            if blocked
            else DemoPhaseV2.REVISION_REVIEW_REQUIRED
        )
        assert projection.case_revision == 2
        assert projection.task is not None
        assert projection.task.task_id == second_task_id
        assert projection.comparison is not None
        assert projection.comparison.previous_planning_run_id == predecessor
        assert projection.planning_run is not None
        assert projection.planning_run.state == (
            "blocked" if blocked else "review_required"
        )
        assert (projection.review_inputs is None) is blocked
        assert projection.recovery is None
        assert (
            projection.comparison.current_planning_run_id
            == projection.planning_run.planning_run_id
        )
        assert journey is not None
        assert journey.phase is projection.phase
        assert journey.model_dump(by_alias=True).keys() == {
            "schema",
            "case_id",
            "current_revision",
            "phase",
            "active_role",
        }
    finally:
        await migrator.dispose()
        await api.dispose()
        await worker_engine.dispose()


@pytest.mark.asyncio
async def test_plan_ready_projection_reads_decision_linked_completed_brief() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    case_id = UUID("40000000-0000-0000-0000-000000000001")
    brief_id = UUID("81000000-0000-0000-0000-000000000301")
    review_id = UUID("80000000-0000-0000-0000-000000000301")
    decision_id = UUID("82000000-0000-0000-0000-000000000301")
    receipt_id = UUID("83000000-0000-0000-0000-000000000301")
    timeline_id = UUID("84000000-0000-0000-0000-000000000301")
    australia_route_id = UUID("71000000-0000-0000-0000-000000000001")
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                for name, value in (
                    ("night_voyager.organization_id", str(DEMO_ORG)),
                    ("night_voyager.actor_id", str(ADVISOR)),
                    ("night_voyager.role", "advisor"),
                ):
                    await connection.execute(
                        text("SELECT set_config(:name,:value,true)"),
                        {"name": name, "value": value},
                    )
                family_projection = {
                    "schema_version": 1,
                    "eligible_route_ids": [str(australia_route_id)],
                    "routes": [
                        {
                            "route_id": str(australia_route_id),
                            "country": "australia",
                            "outcome": "recommended_with_condition",
                            "reason_code": "complete_cost_and_fx_within_boundary",
                        },
                        {
                            "route_id": "71000000-0000-0000-0000-000000000002",
                            "country": "japan",
                            "outcome": "conditional",
                            "reason_code": "synthetic_high_risk_alternative",
                        },
                        {
                            "route_id": "71000000-0000-0000-0000-000000000003",
                            "country": "malaysia",
                            "outcome": "blocked",
                            "reason_code": "direct_program_fit_evidence_absent",
                        },
                    ],
                    "intake": "2027-02",
                    "accepted_evidence_risks": [],
                    "synthetic_proof": True,
                }
                await connection.execute(
                    text(
                        "SELECT * FROM app.review_planning_run("
                        ":org,:actor,:case,:run,1,'approve_for_consultation',:review,"
                        "CAST(:eligible AS jsonb),'[]'::jsonb,NULL,:brief,"
                        "CAST(:projection AS jsonb),:source_date,:key_hash,:request_hash)"
                    ),
                    {
                        "org": DEMO_ORG,
                        "actor": ADVISOR,
                        "case": case_id,
                        "run": UUID("70000000-0000-0000-0000-000000000001"),
                        "review": review_id,
                        "brief": brief_id,
                        "eligible": json.dumps([str(australia_route_id)]),
                        "projection": json.dumps(family_projection),
                        "source_date": date(2026, 7, 1),
                        "key_hash": "31" * 32,
                        "request_hash": "32" * 32,
                    },
                )
                family_review_statuses = tuple(
                    [
                        await journey_status_for_role(connection, case_id, role)
                        for role in (
                            ActorRole.ADVISOR,
                            ActorRole.STUDENT,
                            ActorRole.PARENT,
                        )
                    ]
                )
                assert all(status is not None for status in family_review_statuses)
                assert {
                    status.phase
                    for status in family_review_statuses
                    if status is not None
                } == {DemoPhaseV2.FAMILY_REVIEW}
                assert {
                    status.active_role
                    for status in family_review_statuses
                    if status is not None
                } == {"parent"}
                await set_connection_role(connection, ActorRole.ADVISOR)
                await connection.execute(
                    text(
                        "SELECT * FROM app.decide_family_brief("
                        ":org,:actor,'advisor',:brief,1,:decision,:receipt,:route,"
                        "30000000,40000000,'CNY','[\"budget_elasticity\"]'::jsonb,"
                        ":made_by,'family_consultation',:timeline,"
                        "CAST(:milestones AS jsonb),:key_hash,:request_hash)"
                    ),
                    {
                        "org": DEMO_ORG,
                        "actor": ADVISOR,
                        "brief": brief_id,
                        "decision": decision_id,
                        "receipt": receipt_id,
                        "route": australia_route_id,
                        "made_by": PARENT,
                        "timeline": timeline_id,
                        "milestones": json.dumps(
                            [
                                {"key": "documents", "due_date": "2026-09-01"},
                                {"key": "application", "due_date": "2026-10-15"},
                                {"key": "visa", "due_date": "2026-12-15"},
                                {"key": "arrival", "due_date": "2027-01-20"},
                            ]
                        ),
                        "key_hash": "33" * 32,
                        "request_hash": "34" * 32,
                    },
                )
                durable = (
                    await connection.execute(
                        text(
                            "SELECT c.state,b.is_current,d.id AS decision_id,"
                            "d.receipt_id,t.id AS timeline_id "
                            "FROM app.student_cases c JOIN app.decision_briefs b "
                            "ON b.organization_id=c.organization_id "
                            "AND b.case_id=c.id "
                            "JOIN app.family_decisions d "
                            "ON d.organization_id=b.organization_id "
                            "AND d.decision_brief_id=b.id "
                            "JOIN app.timeline_plans t "
                            "ON t.organization_id=d.organization_id "
                            "AND t.family_decision_id=d.id "
                            "WHERE c.organization_id=:org AND c.id=:case "
                            "AND b.id=:brief"
                        ),
                        {"org": DEMO_ORG, "case": case_id, "brief": brief_id},
                    )
                ).mappings().one()
                assert dict(durable) == {
                    "state": "plan_ready",
                    "is_current": False,
                    "decision_id": decision_id,
                    "receipt_id": receipt_id,
                    "timeline_id": timeline_id,
                }
                plan_ready_statuses = tuple(
                    [
                        await journey_status_for_role(connection, case_id, role)
                        for role in (
                            ActorRole.ADVISOR,
                            ActorRole.STUDENT,
                            ActorRole.PARENT,
                        )
                    ]
                )
                assert all(status is not None for status in plan_ready_statuses)
                assert {
                    status.phase
                    for status in plan_ready_statuses
                    if status is not None
                } == {DemoPhaseV2.PLAN_READY}
                assert {
                    status.active_role
                    for status in plan_ready_statuses
                    if status is not None
                } == {"parent"}
                await set_connection_role(connection, ActorRole.ADVISOR)
                async with AsyncSession(bind=connection) as session:
                    advisor_ledger = await PostgresConnectedDemoRepository(session).advisor_ledger(
                        context(), case_id, resolve_canonical_demo_source_contract()
                    )

                assert advisor_ledger is not None
                assert advisor_ledger.phase is DemoPhase.PLAN_READY
                assert advisor_ledger.current_brief_id == brief_id
                assert advisor_ledger.review_inputs is None
                for name, value in (
                    ("night_voyager.actor_id", str(PARENT)),
                    ("night_voyager.role", "parent"),
                ):
                    await connection.execute(
                        text("SELECT set_config(:name,:value,true)"),
                        {"name": name, "value": value},
                    )
                async with AsyncSession(bind=connection) as session:
                    repository = PostgresConnectedDemoRepository(session)
                    projection = await repository.current_decision_brief(
                        context(ActorRole.PARENT), case_id
                    )
                    projection_v2 = await repository.current_decision_brief_v2(
                        context(ActorRole.PARENT), case_id
                    )

                assert projection is not None
                assert projection.phase is DemoPhase.PLAN_READY
                assert projection.brief_id == brief_id
                assert projection.receipt is not None
                assert projection.receipt.receipt_id == receipt_id
                assert projection.timeline is not None
                assert projection_v2 is not None
                assert (
                    projection_v2.revision_context.current_case_revision == 1
                )
                assert projection_v2.revision_context.planning_version == "initial"
                assert (
                    projection_v2.revision_context.advisor_authorization
                    == "authorized_for_initial_revision"
                )
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
