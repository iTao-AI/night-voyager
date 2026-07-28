from __future__ import annotations

import os
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from night_voyager.connected_demo.models import DemoPhaseV2

pytestmark = pytest.mark.database

DEMO_ORG = UUID("10000000-0000-0000-0000-000000000001")
HAPPY_CASE_ID = UUID("49000000-0000-0000-0000-000000000001")
BUDGET_CASE_ID = UUID("49000000-0000-0000-0000-000000000002")
HAPPY_THREAD_ID = UUID("4b000000-0000-0000-0000-000000000001")
BUDGET_THREAD_ID = UUID("4b000000-0000-0000-0000-000000000002")


def test_revision_journey_phase_contract_is_closed() -> None:
    assert tuple(phase.value for phase in DemoPhaseV2) == (
        "task_ready",
        "active_task",
        "review_required",
        "revision_requested",
        "revision_fact_pending",
        "replan_required",
        "revision_task_active",
        "revision_review_required",
        "revision_blocked",
        "family_review",
        "plan_ready",
        "terminal_task_failure",
    )


@pytest.mark.asyncio
async def test_revision_journey_seed_is_deterministic_and_pre_authority_only() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,false)"),
                {"org": str(DEMO_ORG)},
            )
            cases = (
                await connection.execute(
                    text(
                        "SELECT c.id,c.state,c.current_revision,"
                        "count(DISTINCT r.id)::integer AS run_count,"
                        "count(DISTINCT t.id)::integer AS task_count,"
                        "count(DISTINCT review.id)::integer AS review_count,"
                        "count(DISTINCT decision.id)::integer AS decision_count "
                        "FROM app.student_cases c "
                        "JOIN app.student_case_revisions revision "
                        "ON revision.organization_id=c.organization_id "
                        "AND revision.case_id=c.id "
                        "AND revision.revision=c.current_revision "
                        "JOIN app.planning_runs r "
                        "ON r.organization_id=c.organization_id "
                        "AND r.case_id=c.id AND r.case_revision=1 AND r.is_current "
                        "JOIN app.agent_tasks t "
                        "ON t.organization_id=c.organization_id "
                        "AND t.case_id=c.id AND t.case_revision=1 "
                        "AND t.result_planning_run_id=r.id "
                        "LEFT JOIN app.advisor_reviews review "
                        "ON review.organization_id=c.organization_id "
                        "AND review.case_id=c.id "
                        "LEFT JOIN app.family_decisions decision "
                        "ON decision.organization_id=c.organization_id "
                        "AND decision.case_id=c.id "
                        "WHERE c.organization_id=:org AND c.id=ANY(:cases) "
                        "GROUP BY c.id,c.state,c.current_revision ORDER BY c.id"
                    ),
                    {"org": DEMO_ORG, "cases": [HAPPY_CASE_ID, BUDGET_CASE_ID]},
                )
            ).mappings().all()
            threads = (
                await connection.execute(
                    text(
                        "SELECT id,case_id FROM app.collaboration_threads "
                        "WHERE organization_id=:org AND id=ANY(:threads) ORDER BY id"
                    ),
                    {
                        "org": DEMO_ORG,
                        "threads": [HAPPY_THREAD_ID, BUDGET_THREAD_ID],
                    },
                )
            ).mappings().all()
        assert [row["id"] for row in cases] == [HAPPY_CASE_ID, BUDGET_CASE_ID]
        assert all(row["state"] == "advisor_review" for row in cases)
        assert all(row["current_revision"] == 1 for row in cases)
        assert all(row["run_count"] == 1 and row["task_count"] == 1 for row in cases)
        assert all(
            row["review_count"] == 0 and row["decision_count"] == 0 for row in cases
        )
        assert [(row["id"], row["case_id"]) for row in threads] == [
            (HAPPY_THREAD_ID, HAPPY_CASE_ID),
            (BUDGET_THREAD_ID, BUDGET_CASE_ID),
        ]
    finally:
        await engine.dispose()
