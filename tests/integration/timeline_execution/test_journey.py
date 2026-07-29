from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from night_voyager.identity.demo_seed import (
    BLOCKED_PLAN_EXECUTION_CASE_ID,
    BLOCKED_PLAN_EXECUTION_TIMELINE_ID,
    PLAN_EXECUTION_CASE_ID,
    PLAN_EXECUTION_TIMELINE_ID,
)

pytestmark = pytest.mark.database


@pytest.mark.asyncio
async def test_happy_and_blocked_journey_anchors_are_exact_and_empty() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "SELECT set_config("
                    "'night_voyager.organization_id',"
                    "'10000000-0000-0000-0000-000000000001',true)"
                )
            )
            rows = (
                await connection.execute(
                    text(
                        "SELECT c.id,t.id AS timeline_id,count(e.id) AS executions "
                        "FROM app.student_cases c "
                        "JOIN app.family_decisions d ON "
                        "(d.organization_id,d.case_id)=(c.organization_id,c.id) "
                        "JOIN app.timeline_plans t ON "
                        "(t.organization_id,t.family_decision_id)="
                        "(d.organization_id,d.id) "
                        "LEFT JOIN app.timeline_executions e ON "
                        "(e.organization_id,e.timeline_plan_id)="
                        "(t.organization_id,t.id) "
                        "WHERE c.id IN (:happy_case,:blocked_case) "
                        "AND c.state='plan_ready' "
                        "GROUP BY c.id,t.id ORDER BY c.id"
                    ),
                    {
                        "happy_case": PLAN_EXECUTION_CASE_ID,
                        "blocked_case": BLOCKED_PLAN_EXECUTION_CASE_ID,
                    },
                )
            ).all()
            assert rows == [
                (PLAN_EXECUTION_CASE_ID, PLAN_EXECUTION_TIMELINE_ID, 0),
                (
                    BLOCKED_PLAN_EXECUTION_CASE_ID,
                    BLOCKED_PLAN_EXECUTION_TIMELINE_ID,
                    0,
                ),
            ]
            for table in (
                "timeline_checkpoint_attestations",
                "timeline_checkpoint_verifications",
                "timeline_mutation_receipts",
                "timeline_reassessment_requests",
            ):
                assert await connection.scalar(text(f"SELECT count(*) FROM app.{table}")) == 0
    finally:
        await engine.dispose()
