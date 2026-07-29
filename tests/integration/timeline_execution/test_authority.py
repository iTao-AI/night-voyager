# ruff: noqa: E501
from __future__ import annotations

import asyncio
import os
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from night_voyager.identity.demo_seed import (
    PLAN_EXECUTION_CASE_ID,
    PLAN_EXECUTION_HAPPY_ACTORS,
    PLAN_EXECUTION_TIMELINE_ID,
)

pytestmark = pytest.mark.database

ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
STUDENT = UUID("20000000-0000-0000-0000-000000000002")
HAPPY_ADVISOR = PLAN_EXECUTION_HAPPY_ACTORS[0][2]
HAPPY_STUDENT = PLAN_EXECUTION_HAPPY_ACTORS[1][2]
CASE = UUID("40000000-0000-0000-0000-000000000001")
RUN = UUID("70000000-0000-0000-0000-000000000001")
REVIEW = UUID("91000000-0000-0000-0000-000000000001")
BRIEF = UUID("92000000-0000-0000-0000-000000000001")
DECISION = UUID("93000000-0000-0000-0000-000000000001")
DECISION_RECEIPT = UUID("93100000-0000-0000-0000-000000000001")
TIMELINE = UUID("94000000-0000-0000-0000-000000000001")
EXECUTION = UUID("95000000-0000-0000-0000-000000000001")
START_RECEIPT = UUID("95100000-0000-0000-0000-000000000001")
ATTESTATION = UUID("95200000-0000-0000-0000-000000000001")
ATTEST_RECEIPT = UUID("95300000-0000-0000-0000-000000000001")
REASSESSMENT = UUID("95400000-0000-0000-0000-000000000001")
REASSESS_RECEIPT = UUID("95500000-0000-0000-0000-000000000001")


def sqlstate(error: DBAPIError) -> str | None:
    return getattr(error.orig, "sqlstate", None)


async def set_actor(
    connection: AsyncConnection, actor_id: UUID, role: str
) -> None:
    await connection.execute(
        text(
            "SELECT set_config('night_voyager.organization_id',:org,true),"
            "set_config('night_voyager.actor_id',:actor,true),"
            "set_config('night_voyager.role',:role,true)"
        ),
        {"org": str(ORG), "actor": str(actor_id), "role": role},
    )


async def seed_timeline_anchor(connection: AsyncConnection) -> None:
    await set_actor(connection, ADVISOR, "advisor")
    await connection.execute(
        text(
            "INSERT INTO app.advisor_reviews("
            "organization_id,id,case_id,case_revision,planning_run_id,"
            "review_version,advisor_actor_id,action,eligible_route_ids,"
            "risk_acceptances,reviewer_notes) "
            "SELECT organization_id,:review,case_id,case_revision,id,1,:advisor,"
            "'approve_for_consultation','[]','[]','timeline execution fixture' "
            "FROM app.planning_runs WHERE organization_id=:org AND id=:run "
            "ON CONFLICT (organization_id,id) DO NOTHING"
        ),
        {"org": ORG, "run": RUN, "review": REVIEW, "advisor": ADVISOR},
    )
    await connection.execute(
        text(
            "INSERT INTO app.decision_briefs("
            "organization_id,id,case_id,case_revision,planning_run_id,"
            "advisor_review_id,brief_version,policy_version,source_pack_id,"
            "source_pack_version,evidence_projection_sha256,output_sha256,"
            "source_snapshot_date,family_safe_projection,is_current) "
            "SELECT organization_id,:brief,case_id,case_revision,id,:review,1,"
            "policy_version,source_pack_id,source_pack_version,"
            "evidence_projection_sha256,output_sha256,current_date,'{}',true "
            "FROM app.planning_runs WHERE organization_id=:org AND id=:run "
            "ON CONFLICT (organization_id,id) DO NOTHING"
        ),
        {"org": ORG, "run": RUN, "review": REVIEW, "brief": BRIEF},
    )
    await connection.execute(
        text(
            "INSERT INTO app.family_decisions("
            "organization_id,id,receipt_id,case_id,decision_brief_id,brief_version,"
            "selected_route_id,accepted_budget_min_minor,accepted_budget_max_minor,"
            "currency,accepted_trade_offs,decision_made_by_actor_id,"
            "recorded_by_actor_id,source,planning_run_id) "
            "SELECT r.organization_id,:decision,:receipt,r.case_id,:brief,1,p.id,"
            "1,2,'CNY','[]',:student,:student,'direct',r.id "
            "FROM app.planning_runs r JOIN app.planning_routes p ON "
            "(p.organization_id,p.planning_run_id)=(r.organization_id,r.id) "
            "WHERE r.organization_id=:org AND r.id=:run ORDER BY p.country LIMIT 1 "
            "ON CONFLICT (organization_id,id) DO NOTHING"
        ),
        {
            "org": ORG,
            "run": RUN,
            "decision": DECISION,
            "receipt": DECISION_RECEIPT,
            "brief": BRIEF,
            "student": STUDENT,
        },
    )
    await connection.execute(
        text(
            "INSERT INTO app.timeline_plans("
            "organization_id,id,family_decision_id,schema_version,country,intake,milestones) "
            "VALUES(:org,:timeline,:decision,1,'australia','2027-02',"
            "'[{\"key\":\"documents\",\"due_date\":\"2026-09-01\"},"
            "{\"key\":\"application\",\"due_date\":\"2026-10-15\"},"
            "{\"key\":\"visa\",\"due_date\":\"2026-12-15\"},"
            "{\"key\":\"arrival\",\"due_date\":\"2027-01-20\"}]') "
            "ON CONFLICT (organization_id,id) DO NOTHING"
        ),
        {"org": ORG, "timeline": TIMELINE, "decision": DECISION},
    )


@pytest.mark.asyncio
async def test_start_blocked_reassessment_and_exact_receipt_replay() -> None:
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with migrator.begin() as connection:
            await seed_timeline_anchor(connection)

        async with api.begin() as connection:
            await set_actor(connection, STUDENT, "student")
            first = await connection.scalar(
                text(
                    "SELECT app.start_timeline_execution("
                    ":org,:actor,'student',:timeline,:case,1,:execution,:receipt,"
                    "repeat('a',64),repeat('b',64))"
                ),
                {
                    "org": ORG,
                    "actor": STUDENT,
                    "timeline": TIMELINE,
                    "case": CASE,
                    "execution": EXECUTION,
                    "receipt": START_RECEIPT,
                },
            )
            replay = await connection.scalar(
                text(
                    "SELECT app.start_timeline_execution("
                    ":org,:actor,'student',:timeline,:case,1,"
                    "gen_random_uuid(),gen_random_uuid(),"
                    "repeat('a',64),repeat('b',64))"
                ),
                {"org": ORG, "actor": STUDENT, "timeline": TIMELINE, "case": CASE},
            )
            assert first == replay
            checkpoints = (
                await connection.execute(
                    text(
                        "SELECT id,milestone_key,accountable_role,state,row_version "
                        "FROM app.timeline_checkpoints WHERE organization_id=:org "
                        "AND execution_id=:execution ORDER BY ordinal"
                    ),
                    {"org": ORG, "execution": EXECUTION},
                )
            ).all()
            assert [(row.milestone_key, row.accountable_role, row.state) for row in checkpoints] == [
                ("documents", "student", "in_progress"),
                ("application", "student", "pending"),
                ("visa", "student", "pending"),
                ("arrival", "parent", "pending"),
            ]
            checkpoint_id = checkpoints[0].id
            savepoint = await connection.begin_nested()
            with pytest.raises(DBAPIError) as failure:
                await connection.scalar(
                    text(
                        "SELECT app.attest_timeline_checkpoint("
                        ":org,:actor,'student',:wrong_case,:execution,:checkpoint,1,1,"
                        "'blocked','work_blocked','documents_status_confirmed',"
                        "'deadline_at_risk',gen_random_uuid(),gen_random_uuid(),"
                        "repeat('0',64),repeat('1',64))"
                    ),
                    {
                        "org": ORG,
                        "actor": STUDENT,
                        "wrong_case": PLAN_EXECUTION_CASE_ID,
                        "execution": EXECUTION,
                        "checkpoint": checkpoint_id,
                    },
                )
            assert sqlstate(failure.value) == "NV003"
            await savepoint.rollback()
            blocked = await connection.scalar(
                text(
                    "SELECT app.attest_timeline_checkpoint("
                    ":org,:actor,'student',:case,:execution,:checkpoint,1,1,"
                    "'blocked','work_blocked','documents_status_confirmed',"
                    "'deadline_at_risk',:attestation,:receipt,repeat('c',64),repeat('d',64))"
                ),
                {
                    "org": ORG,
                    "actor": STUDENT,
                    "case": CASE,
                    "execution": EXECUTION,
                    "checkpoint": checkpoint_id,
                    "attestation": ATTESTATION,
                    "receipt": ATTEST_RECEIPT,
                },
            )
            assert blocked["result_kind"] == "timeline_checkpoint_attested"

        async with migrator.begin() as connection:
            await set_actor(connection, ADVISOR, "advisor")
            savepoint = await connection.begin_nested()
            with pytest.raises(DBAPIError) as failure:
                await connection.execute(
                    text(
                        "INSERT INTO app.timeline_reassessment_requests("
                        "organization_id,reassessment_id,execution_id,checkpoint_id,"
                        "advisor_actor_id,trigger,trigger_reference_id,"
                        "observed_execution_version,observed_checkpoint_version,"
                        "request_sha256,accepted_database_date,"
                        "accepted_trigger_projection_sha256,handoff_schema_version,"
                        "predecessor_case_id,predecessor_case_revision,"
                        "predecessor_decision_id,predecessor_decision_receipt_id,"
                        "predecessor_timeline_plan_id,predecessor_execution_id,"
                        "predecessor_checkpoint_id,owner_role,successor_status) "
                        "VALUES(:org,gen_random_uuid(),:execution,:checkpoint,:advisor,"
                        "'blocked_attestation',:attestation,2,2,repeat('2',64),"
                        "CURRENT_DATE,repeat('3',64),1,:wrong_case,1,:decision,"
                        ":decision_receipt,:timeline,:execution,:checkpoint,'advisor',"
                        "'pending_future_authorization')"
                    ),
                    {
                        "org": ORG,
                        "execution": EXECUTION,
                        "checkpoint": checkpoint_id,
                        "advisor": ADVISOR,
                        "attestation": ATTESTATION,
                        "wrong_case": PLAN_EXECUTION_CASE_ID,
                        "decision": DECISION,
                        "decision_receipt": DECISION_RECEIPT,
                        "timeline": TIMELINE,
                    },
                )
            assert sqlstate(failure.value) == "23503"
            await savepoint.rollback()

        async with api.begin() as connection:
            await set_actor(connection, ADVISOR, "advisor")
            reassessed = await connection.scalar(
                text(
                    "SELECT app.request_timeline_reassessment("
                    ":org,:actor,'advisor',:case,:execution,:checkpoint,:attestation,2,2,"
                    "'blocked_attestation',:reassessment,:receipt,"
                    "repeat('e',64),repeat('f',64))"
                ),
                {
                    "org": ORG,
                    "actor": ADVISOR,
                    "case": CASE,
                    "execution": EXECUTION,
                    "checkpoint": checkpoint_id,
                    "attestation": ATTESTATION,
                    "reassessment": REASSESSMENT,
                    "receipt": REASSESS_RECEIPT,
                },
            )
            assert reassessed["result_kind"] == "timeline_reassessment_requested"
            savepoint = await connection.begin_nested()
            with pytest.raises(DBAPIError) as failure:
                await connection.scalar(
                    text(
                        "SELECT app.request_timeline_reassessment("
                        ":org,:actor,'advisor',:wrong_case,:execution,:checkpoint,"
                        ":attestation,2,2,'blocked_attestation',gen_random_uuid(),"
                        "gen_random_uuid(),repeat('e',64),repeat('0',64))"
                    ),
                    {
                        "org": ORG,
                        "actor": ADVISOR,
                        "wrong_case": PLAN_EXECUTION_CASE_ID,
                        "execution": EXECUTION,
                        "checkpoint": checkpoint_id,
                        "attestation": ATTESTATION,
                    },
                )
            assert sqlstate(failure.value) == "NV008"
            await savepoint.rollback()

        async with migrator.connect() as connection:
            await set_actor(connection, ADVISOR, "advisor")
            row = (
                await connection.execute(
                    text(
                        "SELECT accepted_database_date,predecessor_case_id,"
                        "predecessor_execution_id,owner_role,successor_status "
                        "FROM app.timeline_reassessment_requests "
                        "WHERE organization_id=:org AND reassessment_id=:id"
                    ),
                    {"org": ORG, "id": REASSESSMENT},
                )
            ).one()
            assert row.predecessor_case_id == CASE
            assert row.predecessor_execution_id == EXECUTION
            assert row.owner_role == "advisor"
            assert row.successor_status == "pending_future_authorization"
            assert await connection.scalar(
                text(
                    "SELECT count(*) FROM app.student_case_revisions "
                    "WHERE organization_id=:org AND case_id=:case"
                ),
                {"org": ORG, "case": CASE},
            ) == 1
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_concurrent_same_key_start_returns_the_original_receipt() -> None:
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    condition = asyncio.Condition()
    ready = 0

    async def start(execution: UUID, receipt: UUID) -> object:
        nonlocal ready
        async with api.begin() as connection:
            await set_actor(connection, HAPPY_STUDENT, "student")
            async with condition:
                ready += 1
                if ready == 2:
                    condition.notify_all()
                else:
                    await condition.wait_for(lambda: ready == 2)
            return await connection.scalar(
                text(
                    "SELECT app.start_timeline_execution("
                    ":org,:actor,'student',:timeline,:case,1,:execution,:receipt,"
                    "repeat('1',64),repeat('2',64))"
                ),
                {
                    "org": ORG,
                    "actor": HAPPY_STUDENT,
                    "timeline": PLAN_EXECUTION_TIMELINE_ID,
                    "case": PLAN_EXECUTION_CASE_ID,
                    "execution": execution,
                    "receipt": receipt,
                },
            )

    try:
        first, second = await asyncio.gather(
            start(UUID(int=1001), UUID(int=1002)),
            start(UUID(int=1003), UUID(int=1004)),
        )
        assert first == second
        async with api.connect() as connection:
            await set_actor(connection, HAPPY_STUDENT, "student")
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.timeline_executions "
                        "WHERE organization_id=:org AND timeline_plan_id=:timeline"
                    ),
                    {"org": ORG, "timeline": PLAN_EXECUTION_TIMELINE_ID},
                )
                == 1
            )
    finally:
        await api.dispose()


@pytest.mark.asyncio
async def test_deadline_reassessment_rejects_an_overdue_future_checkpoint() -> None:
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with migrator.begin() as connection:
            await set_actor(connection, STUDENT, "student")
            execution = await connection.scalar(
                text(
                    "SELECT id FROM app.timeline_executions "
                    "WHERE organization_id=:org AND timeline_plan_id=:timeline"
                ),
                {"org": ORG, "timeline": PLAN_EXECUTION_TIMELINE_ID},
            )
            future = await connection.scalar(
                text(
                    "UPDATE app.timeline_checkpoints SET due_date=CURRENT_DATE-1 "
                    "WHERE organization_id=:org AND execution_id=:execution "
                    "AND ordinal=2 RETURNING id"
                ),
                {"org": ORG, "execution": execution},
            )
        async with api.begin() as connection:
            await set_actor(connection, HAPPY_ADVISOR, "advisor")
            with pytest.raises(DBAPIError) as failure:
                await connection.scalar(
                    text(
                        "SELECT app.request_timeline_reassessment("
                        ":org,:actor,'advisor',:case,:execution,:checkpoint,NULL,1,1,"
                        "'deadline_elapsed',gen_random_uuid(),gen_random_uuid(),"
                        "repeat('3',64),repeat('4',64))"
                    ),
                    {
                        "org": ORG,
                        "actor": HAPPY_ADVISOR,
                        "case": PLAN_EXECUTION_CASE_ID,
                        "execution": execution,
                        "checkpoint": future,
                    },
                )
            assert sqlstate(failure.value) == "NV023", str(failure.value)
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_read_rejects_two_executions_for_one_case() -> None:
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with migrator.connect() as connection:
            transaction = await connection.begin()
            try:
                await set_actor(connection, HAPPY_STUDENT, "student")
                await connection.execute(
                    text(
                        "ALTER TABLE app.timeline_executions DROP CONSTRAINT "
                        "timeline_executions_organization_id_timeline_plan_id_key"
                    ),
                )
                await connection.execute(
                    text(
                        "INSERT INTO app.timeline_executions("
                        "organization_id,id,case_id,case_revision,family_decision_id,"
                        "decision_receipt_id,timeline_plan_id,schema_version,state,row_version) "
                        "SELECT organization_id,:execution,case_id,case_revision,"
                        "family_decision_id,decision_receipt_id,timeline_plan_id,"
                        "1,'active',1 "
                        "FROM app.timeline_executions WHERE organization_id=:org "
                        "AND timeline_plan_id=:source"
                    ),
                    {
                        "org": ORG,
                        "execution": UUID(int=1011),
                        "source": PLAN_EXECUTION_TIMELINE_ID,
                    },
                )
                with pytest.raises(DBAPIError) as failure:
                    await connection.scalar(
                        text(
                            "SELECT app.read_timeline_execution("
                            ":org,:actor,'student',:case)"
                        ),
                        {
                            "org": ORG,
                            "actor": HAPPY_STUDENT,
                            "case": PLAN_EXECUTION_CASE_ID,
                        },
                    )
                assert sqlstate(failure.value) == "NV006"
            finally:
                await transaction.rollback()
    finally:
        await migrator.dispose()


@pytest.mark.asyncio
async def test_verification_rejects_an_attestation_from_another_checkpoint() -> None:
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with migrator.connect() as connection:
            transaction = await connection.begin()
            try:
                await set_actor(connection, ADVISOR, "advisor")
                second = await connection.scalar(
                    text(
                        "SELECT id FROM app.timeline_checkpoints "
                        "WHERE organization_id=:org AND execution_id=:execution "
                        "AND ordinal=2"
                    ),
                    {"org": ORG, "execution": EXECUTION},
                )
                with pytest.raises(DBAPIError) as failure:
                    await connection.execute(
                        text(
                            "INSERT INTO app.timeline_checkpoint_verifications("
                            "organization_id,verification_id,execution_id,checkpoint_id,"
                            "attestation_id,advisor_actor_id,action,reason_code,"
                            "observed_execution_version,observed_checkpoint_version,"
                            "request_sha256) VALUES("
                            ":org,gen_random_uuid(),:execution,:checkpoint,:attestation,"
                            ":advisor,'verify','attestation_verified',2,1,repeat('5',64))"
                        ),
                        {
                            "org": ORG,
                            "execution": EXECUTION,
                            "checkpoint": second,
                            "attestation": ATTESTATION,
                            "advisor": ADVISOR,
                        },
                    )
                assert sqlstate(failure.value) == "23503"
            finally:
                await transaction.rollback()
    finally:
        await migrator.dispose()


@pytest.mark.asyncio
async def test_postgresql_binds_case_revision_and_multi_assignment_subject() -> None:
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        for actor, supplied_case, revision, expected in (
            (STUDENT, CASE, 1, "NV003"),
            (HAPPY_STUDENT, PLAN_EXECUTION_CASE_ID, 2, "NV020"),
        ):
            async with api.begin() as connection:
                await set_actor(connection, actor, "student")
                with pytest.raises(DBAPIError) as failure:
                    await connection.scalar(
                        text(
                            "SELECT app.start_timeline_execution("
                            ":org,:actor,'student',:timeline,:case,:revision,"
                            "gen_random_uuid(),gen_random_uuid(),"
                            "repeat('6',64),repeat('7',64))"
                        ),
                        {
                            "org": ORG,
                            "actor": actor,
                            "timeline": PLAN_EXECUTION_TIMELINE_ID,
                            "case": supplied_case,
                            "revision": revision,
                        },
                    )
                assert sqlstate(failure.value) == expected

        async with api.begin() as connection:
            await set_actor(connection, ADVISOR, "advisor")
            assigned_cases = await connection.scalar(
                text(
                    "SELECT count(DISTINCT case_id) "
                    "FROM app.student_case_participants "
                    "WHERE organization_id=:org AND actor_id=:actor "
                    "AND role='advisor' AND case_id IN (:case,:other_case)"
                ),
                {
                    "org": ORG,
                    "actor": ADVISOR,
                    "case": CASE,
                    "other_case": PLAN_EXECUTION_CASE_ID,
                },
            )
            assert assigned_cases == 1
            with pytest.raises(DBAPIError) as failure:
                await connection.scalar(
                    text(
                        "SELECT app.request_timeline_reassessment("
                        ":org,:actor,'advisor',:wrong_case,:execution,:checkpoint,"
                        ":attestation,2,2,'blocked_attestation',"
                        "gen_random_uuid(),gen_random_uuid(),"
                        "repeat('8',64),repeat('9',64))"
                    ),
                    {
                        "org": ORG,
                        "actor": ADVISOR,
                        "wrong_case": PLAN_EXECUTION_CASE_ID,
                        "execution": EXECUTION,
                        "checkpoint": UUID(int=1),
                        "attestation": ATTESTATION,
                    },
                )
            assert sqlstate(failure.value) == "NV003"
    finally:
        await api.dispose()
