# ruff: noqa: E501
from __future__ import annotations

import os
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

pytestmark = pytest.mark.database

ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
STUDENT = UUID("20000000-0000-0000-0000-000000000002")
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
                    ":org,:actor,'student',:timeline,:execution,:receipt,"
                    "repeat('a',64),repeat('b',64))"
                ),
                {
                    "org": ORG,
                    "actor": STUDENT,
                    "timeline": TIMELINE,
                    "execution": EXECUTION,
                    "receipt": START_RECEIPT,
                },
            )
            replay = await connection.scalar(
                text(
                    "SELECT app.start_timeline_execution("
                    ":org,:actor,'student',:timeline,gen_random_uuid(),gen_random_uuid(),"
                    "repeat('a',64),repeat('b',64))"
                ),
                {"org": ORG, "actor": STUDENT, "timeline": TIMELINE},
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
            blocked = await connection.scalar(
                text(
                    "SELECT app.attest_timeline_checkpoint("
                    ":org,:actor,'student',:execution,:checkpoint,1,1,"
                    "'blocked','work_blocked','documents_status_confirmed',"
                    "'deadline_at_risk',:attestation,:receipt,repeat('c',64),repeat('d',64))"
                ),
                {
                    "org": ORG,
                    "actor": STUDENT,
                    "execution": EXECUTION,
                    "checkpoint": checkpoint_id,
                    "attestation": ATTESTATION,
                    "receipt": ATTEST_RECEIPT,
                },
            )
            assert blocked["result_kind"] == "timeline_checkpoint_attested"

        async with api.begin() as connection:
            await set_actor(connection, ADVISOR, "advisor")
            reassessed = await connection.scalar(
                text(
                    "SELECT app.request_timeline_reassessment("
                    ":org,:actor,'advisor',:execution,:checkpoint,:attestation,2,2,"
                    "'blocked_attestation',:reassessment,:receipt,"
                    "repeat('e',64),repeat('f',64))"
                ),
                {
                    "org": ORG,
                    "actor": ADVISOR,
                    "execution": EXECUTION,
                    "checkpoint": checkpoint_id,
                    "attestation": ATTESTATION,
                    "reassessment": REASSESSMENT,
                    "receipt": REASSESS_RECEIPT,
                },
            )
            assert reassessed["result_kind"] == "timeline_reassessment_requested"

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
