# ruff: noqa: E501
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import dataclass
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from night_voyager.adapters.deterministic_planning import DeterministicPlanningAdapter
from night_voyager.adapters.governed_mixed_planning import GovernedMixedPlanningAdapter
from night_voyager.adapters.router import PlanningAdapterRouter
from night_voyager.collaboration.hashing import canonical_sha256
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
STUDENT = UUID("20000000-0000-0000-0000-000000000002")
PARENT = UUID("20000000-0000-0000-0000-000000000003")
PACK = UUID("50000000-0000-0000-0000-000000000001")


@dataclass(frozen=True)
class RevisionFixture:
    suffix: int
    case_id: UUID
    run_id: UUID

    def identifier(self, prefix: str, offset: int = 0) -> UUID:
        return UUID(f"{prefix}-0000-0000-0000-{self.suffix + offset:012d}")


def fixture(suffix: int) -> RevisionFixture:
    return RevisionFixture(
        suffix=suffix,
        case_id=UUID(f"4a000000-0000-0000-0000-{suffix:012d}"),
        run_id=UUID(f"7a000000-0000-0000-0000-{suffix:012d}"),
    )


def digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


async def set_context(
    connection: AsyncConnection,
    actor: UUID,
    role: str,
) -> None:
    for key, value in (
        ("organization_id", ORG),
        ("actor_id", actor),
        ("role", role),
    ):
        await connection.execute(
            text("SELECT set_config(:key,:value,true)"),
            {"key": f"night_voyager.{key}", "value": str(value)},
        )


async def seed_reviewable_case(
    migrator: AsyncEngine,
    revision_fixture: RevisionFixture,
) -> None:
    planning_input = validate_planning_fixture().planning_input
    async with migrator.begin() as connection:
        await set_context(connection, ADVISOR, "advisor")
        await connection.execute(
            text(
                "SELECT app.publish_case_revision("
                ":org,:case,NULL,1,CAST(:student AS jsonb),CAST(:family AS jsonb))"
            ),
            {
                "org": ORG,
                "case": revision_fixture.case_id,
                "student": json.dumps(planning_input.case.student.model_dump(mode="json")),
                "family": json.dumps(planning_input.case.family.model_dump(mode="json")),
            },
        )
        await connection.execute(
            text("SELECT app.seed_case_participants(:org,:case,:advisor,:student,:parent)"),
            {
                "org": ORG,
                "case": revision_fixture.case_id,
                "advisor": ADVISOR,
                "student": STUDENT,
                "parent": PARENT,
            },
        )
        await connection.execute(
            text("SELECT app.transition_case(:org,:case,'intake','planning')"),
            {"org": ORG, "case": revision_fixture.case_id},
        )
        await connection.execute(
            text(
                "INSERT INTO app.planning_runs("
                "organization_id,id,case_id,case_revision,source_pack_id,"
                "source_pack_version,policy_version,evidence_projection_sha256,"
                "state,is_current) VALUES("
                ":org,:run,:case,1,:pack,1,'revision-authority-v1',repeat('a',64),"
                "'synthesizing',true)"
            ),
            {
                "org": ORG,
                "run": revision_fixture.run_id,
                "case": revision_fixture.case_id,
                "pack": PACK,
            },
        )
        await connection.execute(
            text(
                "UPDATE app.planning_runs SET state='review_required',"
                "reason_code='revision_requested',output_sha256=repeat('b',64) "
                "WHERE organization_id=:org AND id=:run"
            ),
            {"org": ORG, "run": revision_fixture.run_id},
        )


async def seed_reviewable_case_from_worker(
    migrator: AsyncEngine,
    api: AsyncEngine,
    worker: AsyncEngine,
    revision_fixture: RevisionFixture,
) -> tuple[RevisionFixture, UUID]:
    planning_input = validate_planning_fixture().planning_input
    task_id = revision_fixture.identifier("8f000000")
    registry = SkillRuntimeRegistry.load_packaged()
    skill_manifest = registry.get(
        SkillKey.STUDY_DESTINATION_COMPARE, "1.0.0"
    ).model_dump_json(exclude_none=True)
    async with migrator.begin() as connection:
        await set_context(connection, ADVISOR, "advisor")
        await connection.execute(
            text(
                "SELECT app.publish_case_revision("
                ":org,:case,NULL,1,CAST(:student AS jsonb),CAST(:family AS jsonb))"
            ),
            {
                "org": ORG,
                "case": revision_fixture.case_id,
                "student": json.dumps(
                    planning_input.case.student.model_dump(mode="json")
                ),
                "family": json.dumps(
                    planning_input.case.family.model_dump(mode="json")
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
                "case": revision_fixture.case_id,
                "advisor": ADVISOR,
                "student": STUDENT,
                "parent": PARENT,
            },
        )
        await connection.execute(
            text("SELECT app.transition_case(:org,:case,'intake','planning')"),
            {"org": ORG, "case": revision_fixture.case_id},
        )
    async with api.begin() as connection:
        await set_context(connection, ADVISOR, "advisor")
        await connection.execute(
            text(
                "SELECT * FROM app.create_agent_task("
                ":org,:actor,:case,:task,'generate_planning_run_v1',1,"
                ":pack,1,'m3a-policy-v1',CAST(:manifest AS jsonb),"
                ":request_hash,:key_hash)"
            ),
            {
                "org": ORG,
                "actor": ADVISOR,
                "case": revision_fixture.case_id,
                "task": task_id,
                "pack": PACK,
                "manifest": skill_manifest,
                "request_hash": digest(
                    f"worker-seed-request-{revision_fixture.suffix}"
                ),
                "key_hash": digest(f"worker-seed-key-{revision_fixture.suffix}"),
            },
        )
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
        worker_id=f"revision-authority-{revision_fixture.suffix}",
    )
    assert await runner.run_once() is True
    async with migrator.begin() as connection:
        await set_context(connection, ADVISOR, "advisor")
        row = (
            await connection.execute(
                text(
                    "SELECT t.state,t.result_planning_run_id,r.state AS run_state,"
                    "r.is_current FROM app.agent_tasks t JOIN app.planning_runs r "
                    "ON r.organization_id=t.organization_id "
                    "AND r.id=t.result_planning_run_id "
                    "WHERE t.organization_id=:org AND t.id=:task"
                ),
                {"org": ORG, "task": task_id},
            )
        ).mappings().one()
    assert dict(row) == {
        "state": "waiting_review",
        "result_planning_run_id": row["result_planning_run_id"],
        "run_state": "review_required",
        "is_current": True,
    }
    return (
        RevisionFixture(
            suffix=revision_fixture.suffix,
            case_id=revision_fixture.case_id,
            run_id=row["result_planning_run_id"],
        ),
        task_id,
    )


async def request_revision(
    connection: AsyncConnection,
    revision_fixture: RevisionFixture,
    *,
    review_id: UUID,
    key_hash: str,
    request_hash: str,
    run_id: UUID | None = None,
    action: str = "request_revision",
) -> dict[str, object]:
    await set_context(connection, ADVISOR, "advisor")
    result = await connection.execute(
        text(
            "SELECT * FROM app.review_planning_run("
            ":org,:actor,:case,:run,1,:action,:review,'[]'::jsonb,'[]'::jsonb,"
            "'bounded revision request',NULL,'{}'::jsonb,current_date,:key,:request)"
        ),
        {
            "org": ORG,
            "actor": ADVISOR,
            "case": revision_fixture.case_id,
            "run": run_id or revision_fixture.run_id,
            "action": action,
            "review": review_id,
            "key": key_hash,
            "request": request_hash,
        },
    )
    return dict(result.mappings().one())


async def prepare_preferred_countries_candidate(
    connection: AsyncConnection,
    revision_fixture: RevisionFixture,
    *,
    fact_key: str = "student.preferred_countries",
    value: object | None = None,
) -> UUID:
    thread_id = revision_fixture.identifier("9a000000")
    message_id = revision_fixture.identifier("9b000000")
    candidate_id = revision_fixture.identifier("9c000000")
    await set_context(connection, ADVISOR, "advisor")
    await connection.execute(
        text(
            "SELECT * FROM app.create_collaboration_thread("
            ":org,:actor,'advisor',:case,:thread,:request,:key)"
        ),
        {
            "org": ORG,
            "actor": ADVISOR,
            "case": revision_fixture.case_id,
            "thread": thread_id,
            "request": digest(f"thread-request-{revision_fixture.suffix}"),
            "key": digest(f"thread-key-{revision_fixture.suffix}"),
        },
    )
    body = "I prefer Australia and Japan for this bounded revision."
    await set_context(connection, STUDENT, "student")
    await connection.execute(
        text(
            "SELECT * FROM app.append_collaboration_message("
            ":org,:actor,'student',:thread,:message,:body,:content,:request,:key)"
        ),
        {
            "org": ORG,
            "actor": STUDENT,
            "thread": thread_id,
            "message": message_id,
            "body": body,
            "content": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "request": digest(f"message-request-{revision_fixture.suffix}"),
            "key": digest(f"message-key-{revision_fixture.suffix}"),
        },
    )
    value = ["australia", "japan"] if value is None else value
    await connection.execute(
        text(
            "SELECT * FROM app.propose_memory_candidate("
            ":org,:actor,'student',:message,:candidate,1,"
            ":fact_key,CAST(:value AS jsonb),"
            ":value_hash,:request,:key)"
        ),
        {
            "org": ORG,
            "actor": STUDENT,
            "message": message_id,
            "candidate": candidate_id,
            "fact_key": fact_key,
            "value": json.dumps(value),
            "value_hash": canonical_sha256(value),
            "request": digest(f"candidate-request-{revision_fixture.suffix}"),
            "key": digest(f"candidate-key-{revision_fixture.suffix}"),
        },
    )
    return candidate_id


@pytest.mark.asyncio
async def test_unsupported_fact_cannot_publish_revision_or_leave_partial_writes() -> None:
    target = fixture(1220)
    review_id = target.identifier("8a000000")
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        await seed_reviewable_case(migrator, target)
        async with api.begin() as connection:
            await request_revision(
                connection,
                target,
                review_id=review_id,
                key_hash=digest("unsupported-review-key"),
                request_hash=digest("unsupported-review-request"),
            )
            candidate_id = await prepare_preferred_countries_candidate(
                connection,
                target,
                fact_key="student.intended_field",
                value="computer_science",
            )
        async with api.begin() as connection:
            with pytest.raises(
                DBAPIError, match="unsupported planning revision fact"
            ):
                await confirm_candidate(
                    connection, target, candidate_id, key_label="unsupported"
                )
        async with migrator.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            snapshot = (
                await connection.execute(
                    text(
                        "SELECT c.current_revision,r.is_current,"
                        "(SELECT count(*) FROM app.memory_candidate_verifications v "
                        " WHERE v.organization_id=:org AND v.candidate_id=:candidate) "
                        "AS verifications,"
                        "(SELECT count(*) FROM app.confirmed_facts f "
                        " WHERE f.organization_id=:org AND f.case_id=:case "
                        " AND f.fact_key='student.intended_field') AS facts,"
                        "(SELECT count(*) FROM app.student_case_revisions cr "
                        " WHERE cr.organization_id=:org AND cr.case_id=:case "
                        " AND cr.revision=2) AS revisions "
                        "FROM app.student_cases c JOIN app.planning_runs r "
                        "ON r.organization_id=c.organization_id AND r.id=:run "
                        "WHERE c.organization_id=:org AND c.id=:case"
                    ),
                    {
                        "org": ORG,
                        "case": target.case_id,
                        "run": target.run_id,
                        "candidate": candidate_id,
                    },
                )
            ).mappings().one()
        assert dict(snapshot) == {
            "current_revision": 1,
            "is_current": True,
            "verifications": 0,
            "facts": 0,
            "revisions": 0,
        }
    finally:
        await api.dispose()
        await migrator.dispose()


async def confirm_candidate(
    connection: AsyncConnection,
    revision_fixture: RevisionFixture,
    candidate_id: UUID,
    *,
    verification_offset: int = 0,
    key_label: str = "confirm",
) -> dict[str, object]:
    await set_context(connection, ADVISOR, "advisor")
    result = await connection.execute(
        text(
            "SELECT * FROM app.verify_memory_candidate("
            ":org,:actor,:candidate,1,'confirm',:reason,:verification,:fact,"
            ":request,:key)"
        ),
        {
            "org": ORG,
            "actor": ADVISOR,
            "candidate": candidate_id,
            "reason": "The student confirmed the bounded country set.",
            "verification": revision_fixture.identifier(
                "9d000000", verification_offset
            ),
            "fact": revision_fixture.identifier("9e000000", verification_offset),
            "request": digest(
                f"{key_label}-request-{revision_fixture.suffix}-{verification_offset}"
            ),
            "key": digest(
                f"{key_label}-key-{revision_fixture.suffix}-{verification_offset}"
            ),
        },
    )
    return dict(result.mappings().one())


async def insert_blocking_task(
    connection: AsyncConnection,
    revision_fixture: RevisionFixture,
    *,
    state: str,
    result_run_id: UUID | None = None,
) -> UUID:
    task_id = revision_fixture.identifier("8f000000")
    leased = state in {"leased", "running"}
    await set_context(connection, ADVISOR, "advisor")
    await connection.execute(
        text(
            "INSERT INTO app.agent_tasks("
            "organization_id,id,case_id,operation,case_revision,source_pack_id,"
            "source_pack_version,policy_version,request_sha256,created_by_actor_id,"
            "state,attempt_count,lease_owner,lease_generation,lease_expires_at,"
            "result_planning_run_id) VALUES("
            ":org,:task,:case,'generate_planning_run_v1',1,:pack,1,"
            "'m3a-policy-v1',:request,:actor,:state,:attempt,:owner,:generation,"
            "CASE WHEN :leased THEN clock_timestamp()+interval '5 minutes' END,:run)"
        ),
        {
            "org": ORG,
            "task": task_id,
            "case": revision_fixture.case_id,
            "pack": PACK,
            "request": digest(f"blocking-task-{revision_fixture.suffix}-{state}"),
            "actor": ADVISOR,
            "state": state,
            "attempt": 1 if leased or state == "waiting_review" else 0,
            "owner": "blocking-worker" if leased else None,
            "generation": 1 if leased else 0,
            "leased": leased,
            "run": result_run_id,
        },
    )
    return task_id


@pytest.mark.asyncio
async def test_request_revision_then_confirmation_creates_exact_atomic_lineage() -> None:
    target = fixture(1201)
    review_id = target.identifier("8a000000")
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        await seed_reviewable_case(migrator, target)
        async with api.begin() as connection:
            review = await request_revision(
                connection,
                target,
                review_id=review_id,
                key_hash=digest("revision-success-key"),
                request_hash=digest("revision-success-request"),
            )
        assert review == {
            "review_id": review_id,
            "brief_id": None,
            "case_state": "planning",
            "replayed": False,
        }
        async with migrator.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            before = (
                await connection.execute(
                    text(
                        "SELECT current_revision,state,"
                        "(SELECT is_current FROM app.planning_runs "
                        " WHERE organization_id=:org AND id=:run) AS predecessor_current,"
                        "(SELECT count(*) FROM app.agent_tasks "
                        " WHERE organization_id=:org AND case_id=:case) AS task_count "
                        "FROM app.student_cases WHERE organization_id=:org AND id=:case"
                    ),
                    {"org": ORG, "case": target.case_id, "run": target.run_id},
                )
            ).mappings().one()
        assert dict(before) == {
            "current_revision": 1,
            "state": "planning",
            "predecessor_current": True,
            "task_count": 0,
        }
        async with api.begin() as connection:
            candidate_id = await prepare_preferred_countries_candidate(connection, target)
            confirmation = await confirm_candidate(connection, target, candidate_id)
        assert confirmation["result_revision"] == 2
        async with migrator.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            lineage = (
                await connection.execute(
                    text(
                        "SELECT revision_requested_by_review_id,"
                        "superseded_planning_run_id "
                        "FROM app.student_case_revisions "
                        "WHERE organization_id=:org AND case_id=:case AND revision=2"
                    ),
                    {"org": ORG, "case": target.case_id},
                )
            ).mappings().one()
            current = await connection.scalar(
                text(
                    "SELECT is_current FROM app.planning_runs "
                    "WHERE organization_id=:org AND id=:run"
                ),
                {"org": ORG, "run": target.run_id},
            )
            refs = await connection.scalar(
                text(
                    "SELECT count(*) FROM app.case_revision_confirmed_fact_refs "
                    "WHERE organization_id=:org AND case_id=:case AND case_revision=2"
                ),
                {"org": ORG, "case": target.case_id},
            )
        assert dict(lineage) == {
            "revision_requested_by_review_id": review_id,
            "superseded_planning_run_id": target.run_id,
        }
        assert current is False
        assert refs == 1
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_reviewed_waiting_task_allows_exact_revision_lineage_without_task_mutation() -> None:
    target = fixture(1210)
    review_id = target.identifier("8a000000")
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    worker = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    try:
        target, task_id = await seed_reviewable_case_from_worker(
            migrator, api, worker, target
        )
        async with api.begin() as connection:
            await request_revision(
                connection,
                target,
                review_id=review_id,
                key_hash=digest("reviewed-waiting-review-key"),
                request_hash=digest("reviewed-waiting-review-request"),
            )
            candidate_id = await prepare_preferred_countries_candidate(
                connection, target
            )
            confirmation = await confirm_candidate(
                connection,
                target,
                candidate_id,
                key_label="reviewed-waiting",
            )
        assert confirmation["result_revision"] == 2
        async with migrator.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            row = (
                await connection.execute(
                    text(
                        "SELECT t.state,t.result_planning_run_id,r.is_current,"
                        "revision_row.revision_requested_by_review_id,"
                        "revision_row.superseded_planning_run_id "
                        "FROM app.agent_tasks t JOIN app.planning_runs r "
                        "ON r.organization_id=t.organization_id "
                        "AND r.id=t.result_planning_run_id "
                        "JOIN app.student_case_revisions revision_row "
                        "ON revision_row.organization_id=t.organization_id "
                        "AND revision_row.case_id=t.case_id "
                        "AND revision_row.revision=2 "
                        "WHERE t.organization_id=:org AND t.id=:task"
                    ),
                    {"org": ORG, "task": task_id},
                )
            ).mappings().one()
        assert dict(row) == {
            "state": "waiting_review",
            "result_planning_run_id": target.run_id,
            "is_current": False,
            "revision_requested_by_review_id": review_id,
            "superseded_planning_run_id": target.run_id,
        }
    finally:
        await worker.dispose()
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_terminal_finalize_replay_requires_exact_durable_result() -> None:
    target = fixture(1221)
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    worker = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    try:
        target, task_id = await seed_reviewable_case_from_worker(
            migrator, api, worker, target
        )
        async with migrator.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            durable = (
                await connection.execute(
                    text(
                        "SELECT t.lease_generation,r.state,r.reason_code,"
                        "r.evidence_projection_sha256,r.output_sha256,"
                        "r.supersedes_run_id "
                        "FROM app.agent_tasks t JOIN app.planning_runs r "
                        "ON r.organization_id=t.organization_id "
                        "AND r.id=t.result_planning_run_id "
                        "WHERE t.organization_id=:org AND t.id=:task"
                    ),
                    {"org": ORG, "task": task_id},
                )
            ).mappings().one()
            before_counts = (
                await connection.execute(
                    text(
                        "SELECT "
                        "(SELECT count(*) FROM app.planning_runs "
                        " WHERE organization_id=:org AND case_id=:case) AS runs,"
                        "(SELECT count(*) FROM app.agent_executions "
                        " WHERE organization_id=:org AND task_id=:task) AS executions,"
                        "(SELECT count(*) FROM app.agent_task_events "
                        " WHERE organization_id=:org AND task_id=:task) AS events"
                    ),
                    {"org": ORG, "case": target.case_id, "task": task_id},
                )
            ).mappings().one()

        async def replay(**changes: object) -> str:
            values = {
                "generation": durable["lease_generation"],
                "state": durable["state"],
                "reason": durable["reason_code"],
                "evidence": durable["evidence_projection_sha256"],
                "output_hash": durable["output_sha256"],
                "supersedes": durable["supersedes_run_id"],
                **changes,
            }
            async with worker.begin() as connection:
                await set_context(connection, ADVISOR, "advisor")
                return str(
                    await connection.scalar(
                        text(
                            "SELECT app.finalize_agent_task_result("
                            ":org,:task,'replay-worker',:generation,:run,"
                            ":evidence,:state,:reason,:output_hash,"
                            "'{\"routes\":[],\"costs\":[],\"rankings\":[]}'::jsonb,"
                            ":supersedes)"
                        ),
                        {
                            "org": ORG,
                            "task": task_id,
                            "run": target.run_id,
                            **values,
                        },
                    )
                )

        assert await replay() == "waiting_review"
        for changes, error in (
            ({"generation": durable["lease_generation"] + 1}, "lease generation lost"),
            ({"state": "blocked"}, "task result replay mismatch"),
            ({"reason": "altered"}, "task result replay mismatch"),
            ({"evidence": digest("altered-evidence")}, "task result replay mismatch"),
            ({"output_hash": digest("altered-output")}, "task result replay mismatch"),
            ({"supersedes": target.identifier("7f000000")}, "task result replay mismatch"),
        ):
            with pytest.raises(DBAPIError, match=error):
                await replay(**changes)
        async with migrator.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            counts = (
                await connection.execute(
                    text(
                        "SELECT "
                        "(SELECT count(*) FROM app.planning_runs "
                        " WHERE organization_id=:org AND case_id=:case) AS runs,"
                        "(SELECT count(*) FROM app.agent_executions "
                        " WHERE organization_id=:org AND task_id=:task) AS executions,"
                        "(SELECT count(*) FROM app.agent_task_events "
                        " WHERE organization_id=:org AND task_id=:task) AS events"
                    ),
                    {"org": ORG, "case": target.case_id, "task": task_id},
                )
            ).mappings().one()
        assert dict(counts) == dict(before_counts)
    finally:
        await worker.dispose()
        await api.dispose()
        await migrator.dispose()


@pytest.mark.parametrize("state", ("queued", "leased", "running"))
@pytest.mark.asyncio
async def test_incomplete_task_states_still_block_reviewed_revision_publication(
    state: str,
) -> None:
    target = fixture({"queued": 1211, "leased": 1212, "running": 1213}[state])
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        await seed_reviewable_case(migrator, target)
        async with api.begin() as connection:
            await request_revision(
                connection,
                target,
                review_id=target.identifier("8a000000"),
                key_hash=digest(f"{state}-review-key"),
                request_hash=digest(f"{state}-review-request"),
            )
        async with migrator.begin() as connection:
            await insert_blocking_task(connection, target, state=state)
        async with api.begin() as connection:
            candidate_id = await prepare_preferred_countries_candidate(
                connection, target
            )
            with pytest.raises(
                DBAPIError, match="active task blocks revision publication"
            ):
                await confirm_candidate(
                    connection, target, candidate_id, key_label=f"{state}-blocked"
                )
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_waiting_review_without_exact_request_authority_still_blocks() -> None:
    target = fixture(1214)
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        await seed_reviewable_case(migrator, target)
        async with api.begin() as connection:
            await request_revision(
                connection,
                target,
                review_id=target.identifier("8a000000"),
                key_hash=digest("waiting-no-review-reject-key"),
                request_hash=digest("waiting-no-review-reject-request"),
                action="reject",
            )
        async with migrator.begin() as connection:
            await insert_blocking_task(
                connection,
                target,
                state="waiting_review",
                result_run_id=target.run_id,
            )
        async with api.begin() as connection:
            candidate_id = await prepare_preferred_countries_candidate(
                connection, target
            )
            with pytest.raises(
                DBAPIError, match="active task blocks revision publication"
            ):
                await confirm_candidate(
                    connection, target, candidate_id, key_label="waiting-no-review"
                )
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_waiting_review_for_another_run_still_blocks_exact_review() -> None:
    target = fixture(1215)
    other_run = target.identifier("7b000000")
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        await seed_reviewable_case(migrator, target)
        async with api.begin() as connection:
            await request_revision(
                connection,
                target,
                review_id=target.identifier("8a000000"),
                key_hash=digest("other-run-review-key"),
                request_hash=digest("other-run-review-request"),
            )
        async with migrator.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            await connection.execute(
                text(
                    "INSERT INTO app.planning_runs("
                    "organization_id,id,case_id,case_revision,source_pack_id,"
                    "source_pack_version,policy_version,evidence_projection_sha256,"
                    "state,reason_code,output_sha256,is_current) VALUES("
                    ":org,:run,:case,1,:pack,1,'m3a-policy-v1',repeat('c',64),"
                    "'review_required','historical_run',repeat('d',64),false)"
                ),
                {
                    "org": ORG,
                    "run": other_run,
                    "case": target.case_id,
                    "pack": PACK,
                },
            )
            await insert_blocking_task(
                connection,
                target,
                state="waiting_review",
                result_run_id=other_run,
            )
        async with api.begin() as connection:
            candidate_id = await prepare_preferred_countries_candidate(
                connection, target
            )
            with pytest.raises(
                DBAPIError, match="active task blocks revision publication"
            ):
                await confirm_candidate(
                    connection, target, candidate_id, key_label="waiting-other-run"
                )
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_confirmation_without_request_revision_is_rejected_without_writes() -> None:
    target = fixture(1202)
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        await seed_reviewable_case(migrator, target)
        async with api.begin() as connection:
            await request_revision(
                connection,
                target,
                review_id=target.identifier("8a000000"),
                key_hash=digest("reject-review-key"),
                request_hash=digest("reject-review-request"),
                action="reject",
            )
            candidate_id = await prepare_preferred_countries_candidate(connection, target)
            with pytest.raises(DBAPIError) as rejected:
                await confirm_candidate(connection, target, candidate_id)
            assert getattr(rejected.value.orig, "sqlstate", None) == "NV003"
        async with migrator.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            revision_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM app.student_case_revisions "
                    "WHERE organization_id=:org AND case_id=:case"
                ),
                {"org": ORG, "case": target.case_id},
            )
            assert revision_count == 1
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_request_revision_rejects_noncurrent_old_run() -> None:
    target = fixture(1203)
    new_run = target.identifier("7b000000")
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        await seed_reviewable_case(migrator, target)
        async with migrator.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            await connection.execute(
                text(
                    "UPDATE app.planning_runs SET is_current=false "
                    "WHERE organization_id=:org AND id=:run"
                ),
                {"org": ORG, "run": target.run_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.planning_runs("
                    "organization_id,id,case_id,case_revision,source_pack_id,"
                    "source_pack_version,policy_version,evidence_projection_sha256,"
                    "state,reason_code,output_sha256,is_current) VALUES("
                    ":org,:run,:case,1,:pack,1,'revision-authority-v1',repeat('c',64),"
                    "'review_required','replacement',repeat('d',64),true)"
                ),
                {
                    "org": ORG,
                    "run": new_run,
                    "case": target.case_id,
                    "pack": PACK,
                },
            )
        async with api.begin() as connection:
            with pytest.raises(DBAPIError) as rejected:
                await request_revision(
                    connection,
                    target,
                    review_id=target.identifier("8a000000"),
                    key_hash=digest("old-run-key"),
                    request_hash=digest("old-run-request"),
                )
            assert getattr(rejected.value.orig, "sqlstate", None) == "NV003"
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_composite_lineage_constraints_reject_cross_case_predecessor() -> None:
    first = fixture(1204)
    second = fixture(1205)
    review_id = first.identifier("8a000000")
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        await seed_reviewable_case(migrator, first)
        await seed_reviewable_case(migrator, second)
        async with api.begin() as connection:
            await request_revision(
                connection,
                first,
                review_id=review_id,
                key_hash=digest("cross-case-key"),
                request_hash=digest("cross-case-request"),
            )
        planning_input = validate_planning_fixture().planning_input
        async with migrator.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            with pytest.raises(DBAPIError) as rejected:
                await connection.execute(
                    text(
                        "INSERT INTO app.student_case_revisions("
                        "organization_id,case_id,revision,schema_version,"
                        "student_preferences,family_preferences,"
                        "revision_requested_by_review_id,superseded_planning_run_id) "
                        "VALUES(:org,:case,2,1,CAST(:student AS jsonb),"
                        "CAST(:family AS jsonb),:review,:run)"
                    ),
                    {
                        "org": ORG,
                        "case": second.case_id,
                        "student": json.dumps(
                            planning_input.case.student.model_dump(mode="json")
                        ),
                        "family": json.dumps(
                            planning_input.case.family.model_dump(mode="json")
                        ),
                        "review": review_id,
                        "run": first.run_id,
                    },
                )
            assert getattr(rejected.value.orig, "sqlstate", None) == "23503"
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_revision_request_replay_conflict_and_different_key_race_are_closed() -> None:
    target = fixture(1206)
    review_id = target.identifier("8a000000")
    key_hash = digest("replay-key")
    request_hash = digest("replay-request")
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        await seed_reviewable_case(migrator, target)
        async with api.begin() as connection:
            first = await request_revision(
                connection,
                target,
                review_id=review_id,
                key_hash=key_hash,
                request_hash=request_hash,
            )
        async with api.begin() as connection:
            replay = await request_revision(
                connection,
                target,
                review_id=target.identifier("8a000000", 1),
                key_hash=key_hash,
                request_hash=request_hash,
            )
        assert first["replayed"] is False
        assert replay["replayed"] is True
        assert replay["review_id"] == review_id
        async with api.begin() as connection:
            with pytest.raises(DBAPIError) as conflict:
                await request_revision(
                    connection,
                    target,
                    review_id=target.identifier("8a000000", 2),
                    key_hash=key_hash,
                    request_hash=digest("different-payload"),
                )
            assert getattr(conflict.value.orig, "sqlstate", None) == "NV008"

        raced = fixture(1207)
        await seed_reviewable_case(migrator, raced)
        async with api.connect() as first_connection, api.connect() as second_connection:
            first_transaction = await first_connection.begin()
            second_transaction = await second_connection.begin()
            first_result = await request_revision(
                first_connection,
                raced,
                review_id=raced.identifier("8a000000"),
                key_hash=digest("race-key-a"),
                request_hash=digest("race-request"),
            )
            pending = asyncio.create_task(
                request_revision(
                    second_connection,
                    raced,
                    review_id=raced.identifier("8a000000", 1),
                    key_hash=digest("race-key-b"),
                    request_hash=digest("race-request"),
                )
            )
            await first_transaction.commit()
            with pytest.raises(DBAPIError) as loser:
                await asyncio.wait_for(pending, timeout=10)
            assert getattr(loser.value.orig, "sqlstate", None) == "NV008"
            await second_transaction.rollback()
        assert first_result["replayed"] is False
        async with migrator.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            counts = (
                await connection.execute(
                    text(
                        "SELECT "
                        "(SELECT count(*) FROM app.advisor_reviews "
                        " WHERE organization_id=:org AND planning_run_id=:run "
                        " AND action='request_revision') AS reviews,"
                        "(SELECT count(*) FROM app.audit_events "
                        " WHERE organization_id=:org AND case_id=:case "
                        " AND event_type='advisor_review') AS audits"
                    ),
                    {"org": ORG, "run": raced.run_id, "case": raced.case_id},
                )
            ).mappings().one()
        assert dict(counts) == {"reviews": 1, "audits": 1}
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_concurrent_confirmations_and_duplicate_successors_have_one_winner() -> None:
    target = fixture(1208)
    review_id = target.identifier("8a000000")
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        await seed_reviewable_case(migrator, target)
        async with api.begin() as connection:
            await request_revision(
                connection,
                target,
                review_id=review_id,
                key_hash=digest("confirm-race-review-key"),
                request_hash=digest("confirm-race-review-request"),
            )
            candidate_id = await prepare_preferred_countries_candidate(connection, target)
        async with api.connect() as first_connection, api.connect() as second_connection:
            first_transaction = await first_connection.begin()
            second_transaction = await second_connection.begin()
            winner = await confirm_candidate(first_connection, target, candidate_id)
            pending = asyncio.create_task(
                confirm_candidate(
                    second_connection,
                    target,
                    candidate_id,
                    verification_offset=1,
                    key_label="confirm-race",
                )
            )
            await first_transaction.commit()
            with pytest.raises(DBAPIError):
                await asyncio.wait_for(pending, timeout=10)
            await second_transaction.rollback()
        assert winner["result_revision"] == 2
        async with migrator.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            revision_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM app.student_case_revisions "
                    "WHERE organization_id=:org AND case_id=:case "
                    "AND superseded_planning_run_id=:run"
                ),
                {"org": ORG, "case": target.case_id, "run": target.run_id},
            )
            with pytest.raises(DBAPIError) as duplicate_revision:
                await connection.execute(
                    text(
                        "INSERT INTO app.student_case_revisions("
                        "organization_id,case_id,revision,schema_version,"
                        "student_preferences,family_preferences,"
                        "revision_requested_by_review_id,superseded_planning_run_id) "
                        "SELECT organization_id,case_id,3,schema_version,"
                        "student_preferences,family_preferences,"
                        "revision_requested_by_review_id,superseded_planning_run_id "
                        "FROM app.student_case_revisions "
                        "WHERE organization_id=:org AND case_id=:case AND revision=2"
                    ),
                    {"org": ORG, "case": target.case_id},
                )
            assert getattr(duplicate_revision.value.orig, "sqlstate", None) == "23505"
        assert revision_count == 1
    finally:
        await api.dispose()
        await migrator.dispose()
