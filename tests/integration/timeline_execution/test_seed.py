from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from night_voyager.identity.demo_seed import (
    PLAN_EXECUTION_BRIEF_ID,
    PLAN_EXECUTION_CASE_ID,
    PLAN_EXECUTION_DECISION_ID,
    PLAN_EXECUTION_DECISION_RECEIPT_ID,
    PLAN_EXECUTION_REVIEW_ID,
    PLAN_EXECUTION_RUN_ID,
    PLAN_EXECUTION_TIMELINE_ID,
)

pytestmark = pytest.mark.database
DEMO_ORG = "10000000-0000-0000-0000-000000000001"
ADVISOR = "20000000-0000-0000-0000-000000000001"
STUDENT = "20000000-0000-0000-0000-000000000002"
PARENT = "20000000-0000-0000-0000-000000000003"
SOURCE_RUN = "70000000-0000-0000-0000-000000000001"


@pytest.mark.asyncio
async def test_governed_plan_execution_seed_is_exact_and_unstarted() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "SELECT set_config("
                    "'night_voyager.organization_id',:organization_id,true)"
                ),
                {"organization_id": DEMO_ORG},
            )
            fixture = (
                (
                    await connection.execute(
                    text(
                        "SELECT c.state,c.current_revision,r.state AS run_state,"
                        "r.is_current AS run_is_current,a.id AS review_id,"
                        "b.id AS brief_id,b.is_current AS brief_is_current,"
                        "d.id AS decision_id,d.receipt_id,t.id AS timeline_id,"
                        "count(e.id) AS executions "
                        "FROM app.student_cases c "
                        "JOIN app.planning_runs r ON "
                        "(r.organization_id,r.case_id)=(c.organization_id,c.id) "
                        "JOIN app.advisor_reviews a ON "
                        "(a.organization_id,a.planning_run_id)="
                        "(r.organization_id,r.id) "
                        "JOIN app.decision_briefs b ON "
                        "(b.organization_id,b.advisor_review_id)="
                        "(a.organization_id,a.id) "
                        "JOIN app.family_decisions d ON "
                        "(d.organization_id,d.case_id)=(c.organization_id,c.id) "
                        "JOIN app.timeline_plans t ON "
                        "(t.organization_id,t.family_decision_id)="
                        "(d.organization_id,d.id) "
                        "LEFT JOIN app.timeline_executions e ON "
                        "e.organization_id=t.organization_id "
                        "AND e.timeline_plan_id=t.id "
                        "WHERE c.organization_id=:org AND c.id=:case "
                        "GROUP BY c.state,c.current_revision,r.state,r.is_current,"
                        "a.id,b.id,b.is_current,d.id,d.receipt_id,t.id"
                    ),
                    {"org": DEMO_ORG, "case": PLAN_EXECUTION_CASE_ID},
                )
                )
                .mappings()
                .one()
            )
            assert fixture == {
                "state": "plan_ready",
                "current_revision": 1,
                "run_state": "review_required",
                "run_is_current": True,
                "review_id": PLAN_EXECUTION_REVIEW_ID,
                "brief_id": PLAN_EXECUTION_BRIEF_ID,
                "brief_is_current": False,
                "decision_id": PLAN_EXECUTION_DECISION_ID,
                "receipt_id": PLAN_EXECUTION_DECISION_RECEIPT_ID,
                "timeline_id": PLAN_EXECUTION_TIMELINE_ID,
                "executions": 0,
            }
            participant_roles = (
                await connection.scalars(
                    text(
                        "SELECT actor_id::text || ':' || role "
                        "FROM app.student_case_participants "
                        "WHERE organization_id=:org AND case_id=:case "
                        "ORDER BY role"
                    ),
                    {"org": DEMO_ORG, "case": PLAN_EXECUTION_CASE_ID},
                )
            ).all()
            assert participant_roles == [
                f"{ADVISOR}:advisor",
                f"{PARENT}:parent",
                f"{STUDENT}:student",
            ]
            assert await connection.scalar(
                text(
                    "SELECT count(*)=1 FROM app.student_case_revisions "
                    "WHERE organization_id=:org AND case_id=:case AND revision=1"
                ),
                {"org": DEMO_ORG, "case": PLAN_EXECUTION_CASE_ID},
            )
            for table in (
                "planning_routes",
                "comparison_dimensions",
                "comparison_dimension_evidence_refs",
                "cost_evidence",
                "ranking_evidence",
            ):
                assert await connection.scalar(
                    text(
                        f"SELECT (SELECT count(*) FROM app.{table} "
                        "WHERE organization_id=:org AND planning_run_id=:target)="
                        f"(SELECT count(*) FROM app.{table} "
                        "WHERE organization_id=:org AND planning_run_id=:source)"
                    ),
                    {
                        "org": DEMO_ORG,
                        "target": PLAN_EXECUTION_RUN_ID,
                        "source": SOURCE_RUN,
                    },
                )
    finally:
        await engine.dispose()
