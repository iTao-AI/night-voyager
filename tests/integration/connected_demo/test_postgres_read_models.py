from __future__ import annotations

import json
import os
from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from night_voyager.adapters.deterministic_planning import DeterministicPlanningAdapter
from night_voyager.adapters.governed_mixed_planning import GovernedMixedPlanningAdapter
from night_voyager.adapters.router import PlanningAdapterRouter
from night_voyager.connected_demo.errors import DemoContractUnavailableError
from night_voyager.connected_demo.fixtures import (
    CanonicalDemoSourceContract,
    resolve_canonical_demo_source_contract,
)
from night_voyager.connected_demo.models import DemoPhase
from night_voyager.connected_demo.postgres import PostgresConnectedDemoRepository
from night_voyager.identity.demo_seed import CONNECTED_DEMO_CASE_ID
from night_voyager.identity.models import ActorContext, ActorRole
from night_voyager.planning.fixtures import validate_planning_fixture
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
PLANNING_FIXTURE = validate_planning_fixture().planning_input


def context(role: ActorRole = ActorRole.ADVISOR) -> ActorContext:
    return ActorContext(
        organization_id=DEMO_ORG,
        actor_id=ADVISOR if role is ActorRole.ADVISOR else PARENT,
        role=role,
        session_id=UUID("30000000-0000-0000-0000-000000000001"),
    )


async def set_context(session: AsyncSession) -> None:
    await session.execute(
        text("SELECT set_config('night_voyager.organization_id',:org,true)"),
        {"org": str(DEMO_ORG)},
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
                    projection = await PostgresConnectedDemoRepository(
                        session
                    ).current_decision_brief(context(ActorRole.PARENT), case_id)

                assert projection is not None
                assert projection.phase is DemoPhase.PLAN_READY
                assert projection.brief_id == brief_id
                assert projection.receipt is not None
                assert projection.receipt.receipt_id == receipt_id
                assert projection.timeline is not None
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
