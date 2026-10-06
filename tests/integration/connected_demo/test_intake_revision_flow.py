from __future__ import annotations

import copy
import json
import os
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from night_voyager.adapters.deterministic_planning import DeterministicPlanningAdapter
from night_voyager.adapters.protocols import (
    AdapterFailure,
    AdapterFailureCode,
    AdapterOutcome,
    AdapterPayload,
    PlanningAdapterRequest,
)
from night_voyager.adapters.router import PlanningAdapterRouter
from night_voyager.collaboration.hashing import canonical_sha256
from night_voyager.connected_demo.application import ConnectedDemoService
from night_voyager.connected_demo.models import AdvisorLedgerV3, CurrentDecisionBriefV2
from night_voyager.connected_demo.postgres import PostgresConnectedDemoRepository
from night_voyager.decision.application import DecisionService
from night_voyager.decision.models import (
    DecisionSource,
    FamilyDecisionCommand,
    ReviewAction,
    ReviewCommand,
)
from night_voyager.decision.postgres import PostgresDecisionRepository
from night_voyager.identity.demo_seed import INTAKE_REVISION_CASE_ID
from night_voyager.identity.models import ActorContext, ActorRole
from night_voyager.planning.intake_fixture import INTAKE_DELAY_SOURCE_PACK_ID
from night_voyager.planning.synthetic_postgres import PersistedSyntheticSnapshotRepository
from night_voyager.skills.registry import SkillRuntimeRegistry
from night_voyager.tasks.application import CreateTaskCommand, RetryTaskCommand, TaskService
from night_voyager.tasks.errors import TaskConflictError
from night_voyager.tasks.postgres import PostgresTaskRepository, postgres_worker_repository_factory
from night_voyager.tasks.worker import TaskWorker
from scripts.verify_controlled_intake_revision import (
    read_persisted_intake_snapshot,
    verify_persisted_intake_revision,
)
from tests.integration.planning.test_revision_authority import (
    ADVISOR,
    ORG,
    PACK,
    PARENT,
    STUDENT,
    digest,
    fixture,
    seed_reviewable_case_from_worker,
    set_context,
)

pytestmark = pytest.mark.database

type Engines = tuple[AsyncEngine, AsyncEngine, AsyncEngine]


@pytest_asyncio.fixture
async def engines() -> AsyncIterator[Engines]:
    values: Engines = (
        create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"]),
        create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"]),
        create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"]),
    )
    try:
        yield values
    finally:
        for engine in values:
            await engine.dispose()


def actor(role: ActorRole = ActorRole.ADVISOR) -> ActorContext:
    identifier = {ActorRole.ADVISOR: ADVISOR, ActorRole.PARENT: PARENT, ActorRole.STUDENT: STUDENT}[
        role
    ]
    return ActorContext(ORG, identifier, role, uuid4())


async def propose(
    c: AsyncConnection,
    case: UUID,
    revision: int,
    value: object,
    *,
    fact_key: str = "student.intake",
) -> UUID:
    thread, message, candidate = uuid4(), uuid4(), uuid4()
    await set_context(c, ADVISOR, "advisor")
    created = await c.execute(
        text(
            "SELECT * FROM app.create_collaboration_thread("
            ":org,:actor,'advisor',:case,:thread,:request,:key)"
        ),
        {
            "org": ORG,
            "actor": ADVISOR,
            "case": case,
            "thread": thread,
            "request": digest(str(thread)),
            "key": digest(str(uuid4())),
        },
    )
    thread = created.mappings().one()["thread_id"]
    await set_context(c, STUDENT, "student")
    body = f"Synthetic student proposal: {fact_key} = {json.dumps(value)}"
    await c.execute(
        text(
            "SELECT * FROM app.append_collaboration_message("
            ":org,:actor,'student',:thread,:message,:body,:content,:request,:key)"
        ),
        {
            "org": ORG,
            "actor": STUDENT,
            "thread": thread,
            "message": message,
            "body": body,
            "content": digest(body),
            "request": digest(str(message)),
            "key": digest(str(uuid4())),
        },
    )
    await c.execute(
        text(
            "SELECT * FROM app.propose_memory_candidate("
            ":org,:actor,'student',:message,:candidate,:revision,:fact,"
            "CAST(:value AS jsonb),:hash,:request,:key)"
        ),
        {
            "org": ORG,
            "actor": STUDENT,
            "message": message,
            "candidate": candidate,
            "revision": revision,
            "fact": fact_key,
            "value": json.dumps(value),
            "hash": canonical_sha256(value),
            "request": digest(str(candidate)),
            "key": digest(str(uuid4())),
        },
    )
    return candidate


async def verify(
    c: AsyncConnection, candidate: UUID, revision: int, *, decision: str = "confirm"
) -> None:
    await set_context(c, ADVISOR, "advisor")
    await c.execute(
        text(
            "SELECT * FROM app.verify_memory_candidate("
            ":org,:actor,:candidate,:revision,:decision,'synthetic intake review',"
            ":verification,:fact,:request,:key)"
        ),
        {
            "org": ORG,
            "actor": ADVISOR,
            "candidate": candidate,
            "revision": revision,
            "decision": decision,
            "verification": uuid4(),
            "fact": uuid4() if decision == "confirm" else None,
            "request": digest(str(uuid4())),
            "key": digest(str(uuid4())),
        },
    )


async def review(
    c: AsyncConnection, case: UUID, run: UUID, revision: int, *, eligible: tuple[UUID, ...] = ()
) -> UUID:
    await set_context(c, ADVISOR, "advisor")
    identifier = uuid4()
    approving = bool(eligible)
    async with AsyncSession(bind=c) as session:
        await DecisionService(PostgresDecisionRepository(session)).review(
            actor(),
            ReviewCommand(
                schema_version=1,
                case_id=case,
                planning_run_id=run,
                expected_case_revision=revision,
                action=ReviewAction.APPROVE_FOR_CONSULTATION
                if approving
                else ReviewAction.REQUEST_REVISION,
                review_id=identifier,
                eligible_route_ids=eligible,
                risk_acceptances=(),
                reviewer_notes="Synthetic controlled intake",
                brief_id=uuid4() if approving else None,
            ),
            str(uuid4()),
        )
    return identifier


async def ledger(c: AsyncConnection, case: UUID) -> AdvisorLedgerV3:
    await set_context(c, ADVISOR, "advisor")
    async with AsyncSession(bind=c) as session:
        value = await ConnectedDemoService(PostgresConnectedDemoRepository(session)).advisor_ledger(
            actor(), case, contract_version=3
        )
    assert isinstance(value, AdvisorLedgerV3)
    return value


class RecordingAdapter(DeterministicPlanningAdapter):
    def __init__(
        self,
        repository: PersistedSyntheticSnapshotRepository,
        failure: AdapterFailure | None = None,
    ) -> None:
        super().__init__(repository, injected_failure=failure)
        self.requests: list[PlanningAdapterRequest] = []
        self.inputs: list[dict[str, Any]] = []

    async def generate(self, request: PlanningAdapterRequest) -> AdapterOutcome:
        self.requests.append(request)
        outcome = await super().generate(request)
        if isinstance(outcome, AdapterPayload):
            self.inputs.append(json.loads(outcome.payload))
        return outcome


async def create_task(
    c: AsyncConnection, case: UUID, revision: int, *, pack: UUID = INTAKE_DELAY_SOURCE_PACK_ID
) -> UUID:
    await set_context(c, ADVISOR, "advisor")
    task = uuid4()
    async with AsyncSession(bind=c) as session:
        await TaskService(
            PostgresTaskRepository(session),
            registry=SkillRuntimeRegistry.load_packaged(),
            id_factory=lambda: task,
        ).create(
            actor(),
            CreateTaskCommand(
                case_id=case,
                expected_case_revision=revision,
                source_pack_id=pack,
                source_pack_version=1,
                policy_version="m3a-policy-v1",
            ),
            str(uuid4()),
        )
    return task


async def process(
    worker: AsyncEngine, task: UUID, *, failure: AdapterFailure | None = None
) -> RecordingAdapter:
    sessions = async_sessionmaker(worker, expire_on_commit=False)
    adapter = RecordingAdapter(PersistedSyntheticSnapshotRepository(sessions), failure)
    runner = TaskWorker(
        postgres_worker_repository_factory(sessions),
        PlanningAdapterRouter(synthetic=adapter, mixed=adapter),
        SkillRuntimeRegistry.load_packaged(),
        worker_id=f"intake-{task}",
    )
    assert await runner.run_once() is True
    assert len(adapter.requests) == 1
    async with worker.begin() as c:
        await c.execute(
            text("SELECT set_config('night_voyager.organization_id',:org,true)"), {"org": str(ORG)}
        )
        stored = (
            (
                await c.execute(
                    text(
                        "SELECT case_id,case_revision,state FROM app.agent_tasks "
                        "WHERE organization_id=:org AND id=:task"
                    ),
                    {"org": ORG, "task": task},
                )
            )
            .mappings()
            .one()
        )
        assert adapter.requests[0].case_id == stored["case_id"]
        assert adapter.requests[0].case_revision == stored["case_revision"]
        assert stored["state"] == ("waiting_review" if failure is None else "timed_out")
    return adapter


def predecessor(snapshot: dict[str, Any], run: str) -> dict[str, Any]:
    row = next(copy.deepcopy(item) for item in snapshot["runs"] if item["id"] == run)
    row.pop("is_current")
    return {
        "run": row,
        **{
            key: [item for item in snapshot[key] if item["planning_run_id"] == run]
            for key in ("routes", "costs", "dimensions", "dimension_evidence", "rankings")
        },
        "evidence": [item for item in snapshot["evidence"] if item["source_pack_id"] == str(PACK)],
    }


@pytest.mark.asyncio
async def test_fixed_case_real_intake_receipt_timeline_and_finalized_refusal(
    engines: Engines,
) -> None:
    _, api, worker = engines
    case = INTAKE_REVISION_CASE_ID
    async with api.begin() as c:
        assert await c.scalar(text("SELECT current_user")) == "night_voyager_api"
        await set_context(c, ADVISOR, "advisor")
        before = await read_persisted_intake_snapshot(c)
        assert before["case"]["current_revision"] == 1
        assert not before["decisions"] and not before["timelines"]
        initial = await ledger(c, case)
        assert initial.planning_run is not None
        old_run = initial.planning_run.planning_run_id
        old_bytes = predecessor(before, str(old_run))
        old_review = await review(c, case, old_run, 1)
        requested = await read_persisted_intake_snapshot(c)
        frozen_review = copy.deepcopy(requested["reviews"])
        candidate = await propose(c, case, 1, "2028-02")
        await verify(c, candidate, 1)
        ready = await ledger(c, case)
        assert ready.case_revision == 2 and ready.case_intake == "2028-02"
        assert ready.task is None and ready.canonical_task_inputs is not None
        assert ready.canonical_task_inputs.source_pack_id == INTAKE_DELAY_SOURCE_PACK_ID
        task = await create_task(c, case, 2)
    adapter = await process(worker, task)
    assert adapter.inputs[0]["case"]["student"]["intake"] == "2028-02"
    assert adapter.inputs[0]["source_pack"]["pack_id"] == str(INTAKE_DELAY_SOURCE_PACK_ID)
    assert adapter.inputs[0]["costs"][0]["intake"] == "2028-02"
    async with api.begin() as c:
        current = await ledger(c, case)
        assert current.comparison is not None and current.planning_run is not None
        assert current.comparison.previous_request_review.review_id == old_review
        assert all(country.delta == "unchanged" for country in current.comparison.countries)
        assert current.review_inputs is not None
        await review(
            c,
            case,
            current.planning_run.planning_run_id,
            2,
            eligible=current.review_inputs.eligible_route_ids,
        )
        # A pending real student candidate proves that finalization, rather than
        # absence of a candidate, prevents another intake revision.
        pending = await propose(c, case, 2, "2028-09")
        await set_context(c, PARENT, "parent")
        async with AsyncSession(bind=c) as session:
            brief = await ConnectedDemoService(
                PostgresConnectedDemoRepository(session)
            ).current_decision_brief(actor(ActorRole.PARENT), case, contract_version=2)
            assert isinstance(brief, CurrentDecisionBriefV2)
            assert brief.family_safe_projection.intake == "2028-02"
            assert brief.decision_requirements is not None
            assert brief.decision_requirements.pinned_cost_minor == 32640000
            command = FamilyDecisionCommand(
                schema_version=1,
                brief_id=brief.brief_id,
                expected_brief_version=brief.brief_version,
                selected_route_id=brief.decision_requirements.eligible_route_id,
                accepted_budget_min_minor=32000000,
                accepted_budget_max_minor=36000000,
                currency="CNY",
                accepted_trade_offs=("budget_elasticity",),
                decision_made_by_actor_id=PARENT,
                source=DecisionSource.DIRECT,
            )
            result = await DecisionService(PostgresDecisionRepository(session)).decide_direct(
                actor(ActorRole.PARENT), command, str(uuid4())
            )
            assert result["decision_id"] is not None
    async with api.begin() as c:
        await set_context(c, ADVISOR, "advisor")
        final = await read_persisted_intake_snapshot(c)
        summary = verify_persisted_intake_revision(final)
        assert summary["new_cost_minor"] == 32640000
        assert summary["timeline_dates"] == ["2027-09-01", "2027-10-15", "2027-12-15", "2028-01-20"]
        assert predecessor(final, str(old_run)) == old_bytes
        assert [row for row in final["reviews"] if row["id"] == str(old_review)] == frozen_review
        with pytest.raises(DBAPIError) as denied:
            async with c.begin_nested():
                await verify(c, pending, 2)
        assert getattr(denied.value.orig, "sqlstate", None) == "NV003"
        assert await read_persisted_intake_snapshot(c) == final
        # Corrupt persisted joins or values must never become acceptance proof.
        for table, field, wrong in (
            ("decisions", "recorded_by_actor_id", str(ADVISOR)),
            ("briefs", "source_pack_id", str(PACK)),
            ("costs", "intake", "2027-02"),
            ("timelines", "intake", "2027-02"),
        ):
            broken = copy.deepcopy(final)
            target = (
                broken[table][-1]
                if table != "costs"
                else next(row for row in broken[table] if row["planning_run_id"] != str(old_run))
            )
            target[field] = wrong
            with pytest.raises(ValueError):
                verify_persisted_intake_revision(broken)
        broken = copy.deepcopy(final)
        broken["decisions"].append(copy.deepcopy(broken["decisions"][0]))
        with pytest.raises(ValueError):
            verify_persisted_intake_revision(broken)


@pytest.mark.asyncio
async def test_unavailable_month_preserves_then_allows_explicit_replacement(
    engines: Engines,
) -> None:
    migrator, api, worker = engines
    target, _ = await seed_reviewable_case_from_worker(
        migrator, api, worker, fixture(uuid4().int % 10**12)
    )
    async with api.begin() as c:
        await review(c, target.case_id, target.run_id, 1)
        candidate = await propose(c, target.case_id, 1, "2028-09")
        await set_context(c, ADVISOR, "advisor")
        before = await read_persisted_intake_snapshot(c, case_id=target.case_id)
        with pytest.raises(DBAPIError) as denied:
            async with c.begin_nested():
                await verify(c, candidate, 1)
        assert getattr(denied.value.orig, "sqlstate", None) == "NV027"
        assert await read_persisted_intake_snapshot(c, case_id=target.case_id) == before
        retained = await ledger(c, target.case_id)
        assert retained.case_revision == 1 and retained.case_intake == "2027-02"
        await verify(c, candidate, 1, decision="reject")
        replacement = await propose(c, target.case_id, 1, "2028-02")
        await verify(c, replacement, 1)
        assert (await ledger(c, target.case_id)).case_intake == "2028-02"


@pytest.mark.asyncio
async def test_later_country_revision_inherits_intake_pack_but_terminal_retry_stays_closed(
    engines: Engines,
) -> None:
    migrator, api, worker = engines
    target, _ = await seed_reviewable_case_from_worker(
        migrator, api, worker, fixture(uuid4().int % 10**12)
    )
    async with api.begin() as c:
        await review(c, target.case_id, target.run_id, 1)
        candidate = await propose(c, target.case_id, 1, "2028-02")
        await verify(c, candidate, 1)
        first = await create_task(c, target.case_id, 2)
    await process(worker, first)
    async with api.begin() as c:
        current = await ledger(c, target.case_id)
        assert current.planning_run is not None
        await review(c, target.case_id, current.planning_run.planning_run_id, 2)
        candidate = await propose(
            c, target.case_id, 2, ["australia", "japan"], fact_key="student.preferred_countries"
        )
        await verify(c, candidate, 2)
        before = await read_persisted_intake_snapshot(c, case_id=target.case_id)
        with pytest.raises(TaskConflictError):
            async with c.begin_nested():
                await create_task(c, target.case_id, 3, pack=PACK)
        assert await read_persisted_intake_snapshot(c, case_id=target.case_id) == before
        second = await create_task(c, target.case_id, 3)
    adapter = await process(
        worker, second, failure=AdapterFailure(code=AdapterFailureCode.DEADLINE_EXCEEDED)
    )
    request = adapter.requests[0]
    assert request.case_revision == 3 and request.source_pack_id == INTAKE_DELAY_SOURCE_PACK_ID
    loaded = await PersistedSyntheticSnapshotRepository(async_sessionmaker(worker)).load(request)
    assert loaded.case.student.intake == "2028-02"
    async with api.begin() as c:
        current = await ledger(c, target.case_id)
        assert current.recovery is not None and current.task is not None
        assert current.recovery.retry_allowed is False
        assert current.task.public_code == "deadline_exceeded"
        before = await read_persisted_intake_snapshot(c, case_id=target.case_id)
        with pytest.raises(TaskConflictError) as denied:
            async with c.begin_nested():
                async with AsyncSession(bind=c) as session:
                    service = TaskService(
                        PostgresTaskRepository(session),
                        registry=SkillRuntimeRegistry.load_packaged(),
                    )
                    await service.retry(
                        actor(),
                        RetryTaskCommand(
                            task_id=second,
                            expected_row_version=current.task.row_version,
                            expected_case_revision=3,
                        ),
                        str(uuid4()),
                    )
        assert denied.value.code == "task_retry_ineligible"
        assert await read_persisted_intake_snapshot(c, case_id=target.case_id) == before


@pytest.mark.asyncio
async def test_intake_readback_rejects_changed_source_metadata(engines: Engines) -> None:
    _, api, _ = engines
    async with api.begin() as c:
        await set_context(c, ADVISOR, "advisor")
        snapshot = await read_persisted_intake_snapshot(c)
        verify_persisted_intake_revision(snapshot)
        changed = next(
            row
            for row in snapshot["entries"]
            if row["source_pack_id"] == str(INTAKE_DELAY_SOURCE_PACK_ID)
        )
        changed["institution"] = "undeclared institution"
        with pytest.raises(ValueError):
            verify_persisted_intake_revision(snapshot)
