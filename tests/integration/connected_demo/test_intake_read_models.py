from __future__ import annotations

import os
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from night_voyager.adapters.deterministic_planning import DeterministicPlanningAdapter
from night_voyager.adapters.governed_mixed_planning import GovernedMixedPlanningAdapter
from night_voyager.adapters.router import PlanningAdapterRouter
from night_voyager.connected_demo.application import ConnectedDemoService
from night_voyager.connected_demo.errors import DemoContractUnavailableError
from night_voyager.connected_demo.models import AdvisorLedgerV3, DemoPhaseV2
from night_voyager.connected_demo.postgres import PostgresConnectedDemoRepository
from night_voyager.identity.models import ActorRole
from night_voyager.planning.mixed_postgres import PostgresMixedPlanningRepository
from night_voyager.planning.synthetic_postgres import PersistedSyntheticSnapshotRepository
from night_voyager.skills.registry import SkillRuntimeRegistry
from night_voyager.tasks.application import CreateTaskCommand, TaskService
from night_voyager.tasks.postgres import PostgresTaskRepository, postgres_worker_repository_factory
from night_voyager.tasks.worker import TaskWorker
from tests.integration.connected_demo.test_postgres_read_models import context
from tests.integration.planning.test_revision_authority import (
    ADVISOR,
    PARENT,
    confirm_candidate,
    digest,
    fixture,
    prepare_preferred_countries_candidate,
    request_revision,
    seed_reviewable_case_from_worker,
    set_context,
)

pytestmark = pytest.mark.database


@pytest.mark.asyncio
async def test_v3_reads_real_intake_source_pins_and_frozen_request_review() -> None:
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    worker = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    registry = SkillRuntimeRegistry.load_packaged()
    try:
        target, _ = await seed_reviewable_case_from_worker(
            migrator, api, worker, fixture(uuid4().int % 1000000000000)
        )
        async with api.begin() as c:
            await set_context(c, ADVISOR, "advisor")
            async with AsyncSession(bind=c) as session:
                initial = await ConnectedDemoService(
                    PostgresConnectedDemoRepository(session)
                ).advisor_ledger(context(), target.case_id, contract_version=3)
            assert isinstance(initial, AdvisorLedgerV3)
            assert initial.case_intake == "2027-02"
            assert initial.phase is DemoPhaseV2.REVIEW_REQUIRED
            assert initial.routes[0].cost is not None
            assert initial.routes[0].cost.intake == "2027-02"
            review_id = target.identifier("8a000000")
            await request_revision(
                c,
                target,
                review_id=review_id,
                key_hash=digest(str(uuid4())),
                request_hash=digest(str(uuid4())),
            )
            candidate = await prepare_preferred_countries_candidate(
                c, target, fact_key="student.intake", value="2028-02"
            )
            await confirm_candidate(c, target, candidate)
        async with api.begin() as c:
            await set_context(c, ADVISOR, "advisor")
            async with AsyncSession(bind=c) as session:
                service = ConnectedDemoService(PostgresConnectedDemoRepository(session))
                ready = await service.advisor_ledger(context(), target.case_id, contract_version=3)
                assert isinstance(ready, AdvisorLedgerV3)
                assert ready.phase is DemoPhaseV2.REPLAN_REQUIRED
                assert ready.case_intake == "2028-02"
                assert ready.canonical_task_inputs is not None
                assert ready.canonical_task_inputs.source_pack_id == UUID(
                    "50000000-0000-0000-0000-000000000017"
                )
                for version in (1, 2):
                    with pytest.raises(DemoContractUnavailableError):
                        await service.advisor_ledger(
                            context(), target.case_id, contract_version=version
                        )
                task_id = uuid4()
                await TaskService(
                    PostgresTaskRepository(session), registry=registry, id_factory=lambda: task_id
                ).create(
                    context(),
                    CreateTaskCommand(
                        case_id=target.case_id,
                        expected_case_revision=2,
                        source_pack_id=ready.canonical_task_inputs.source_pack_id,
                        source_pack_version=1,
                        policy_version="m3a-policy-v1",
                    ),
                    f"intake-read-{task_id}",
                )
                active = await service.advisor_ledger(context(), target.case_id, contract_version=3)
                assert isinstance(active, AdvisorLedgerV3)
                assert active.phase is DemoPhaseV2.REVISION_TASK_ACTIVE
        worker_sessions = async_sessionmaker(worker, expire_on_commit=False)
        runner = TaskWorker(
            postgres_worker_repository_factory(worker_sessions),
            PlanningAdapterRouter(
                synthetic=DeterministicPlanningAdapter(
                    PersistedSyntheticSnapshotRepository(worker_sessions)
                ),
                mixed=GovernedMixedPlanningAdapter(
                    PostgresMixedPlanningRepository(worker_sessions)
                ),
            ),
            registry,
            worker_id="intake-read-models",
        )
        assert await runner.run_once() is True
        async with api.begin() as c:
            await set_context(c, ADVISOR, "advisor")
            async with AsyncSession(bind=c) as session:
                service = ConnectedDemoService(PostgresConnectedDemoRepository(session))
                ledger = await service.advisor_ledger(context(), target.case_id, contract_version=3)
                assert isinstance(ledger, AdvisorLedgerV3)
                assert ledger.phase is DemoPhaseV2.REVISION_REVIEW_REQUIRED
                assert ledger.comparison is not None
                assert ledger.comparison.changed_fact.fact_key == "student.intake"
                assert ledger.comparison.previous_request_review.review_id == review_id
                assert ledger.comparison.previous_request_review.planning_run_id == target.run_id
                assert ledger.comparison.previous_request_review.case_revision == 1
                assert ledger.task is not None
                assert ledger.comparison.current_planning_run_id == ledger.task.planning_run_id
                cost = next(
                    route.cost for route in ledger.routes if route.country.value == "australia"
                )
                assert cost is not None
                assert (cost.intake, cost.cny_total_minor) == ("2028-02", 32640000)
                assert ledger.planning_run is not None
                assert ledger.planning_run.source_pack_id == UUID(
                    "50000000-0000-0000-0000-000000000017"
                )
            await set_context(c, PARENT, "parent")
            async with AsyncSession(bind=c) as session:
                assert (
                    await ConnectedDemoService(
                        PostgresConnectedDemoRepository(session)
                    ).advisor_ledger(context(ActorRole.PARENT), target.case_id, contract_version=3)
                    is None
                )
            await set_context(c, ADVISOR, "advisor")
            async with AsyncSession(bind=c) as session:
                assert (
                    await ConnectedDemoService(
                        PostgresConnectedDemoRepository(session)
                    ).advisor_ledger(
                        replace(context(), organization_id=UUID(int=999)),
                        target.case_id,
                        contract_version=3,
                    )
                    is None
                )
    finally:
        await migrator.dispose()
        await api.dispose()
        await worker.dispose()
