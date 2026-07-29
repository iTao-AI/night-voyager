from __future__ import annotations

import asyncio
import os

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


async def verify() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "SELECT set_config("
                    "'night_voyager.organization_id',:organization_id,true)"
                ),
                {"organization_id": "10000000-0000-0000-0000-000000000001"},
            )
            exact = await connection.scalar(
                text(
                    "SELECT "
                    "(SELECT count(*)=1 FROM app.student_cases "
                    "WHERE id=:case AND state='plan_ready' "
                    "AND current_revision=1) "
                    "AND (SELECT count(*)=1 FROM app.student_case_revisions "
                    "WHERE case_id=:case AND revision=1) "
                    "AND (SELECT count(*)=1 FROM app.planning_runs "
                    "WHERE case_id=:case AND id=:run "
                    "AND state='review_required' AND is_current) "
                    "AND (SELECT count(*)=1 FROM app.advisor_reviews "
                    "WHERE case_id=:case AND id=:review "
                    "AND planning_run_id=:run) "
                    "AND (SELECT count(*)=1 FROM app.decision_briefs "
                    "WHERE case_id=:case AND id=:brief "
                    "AND advisor_review_id=:review AND NOT is_current) "
                    "AND (SELECT count(*)=1 FROM app.family_decisions "
                    "WHERE case_id=:case AND id=:decision "
                    "AND receipt_id=:receipt AND decision_brief_id=:brief) "
                    "AND (SELECT count(*)=1 FROM app.timeline_plans "
                    "WHERE id=:timeline AND family_decision_id=:decision) "
                    "AND (SELECT count(*)=3 AND count(DISTINCT actor_id)=3 "
                    "FROM app.student_case_participants WHERE case_id=:case) "
                    "AND (SELECT count(*)=0 FROM app.timeline_executions "
                    "WHERE timeline_plan_id=:timeline)"
                ),
                {
                    "case": PLAN_EXECUTION_CASE_ID,
                    "run": PLAN_EXECUTION_RUN_ID,
                    "review": PLAN_EXECUTION_REVIEW_ID,
                    "brief": PLAN_EXECUTION_BRIEF_ID,
                    "decision": PLAN_EXECUTION_DECISION_ID,
                    "receipt": PLAN_EXECUTION_DECISION_RECEIPT_ID,
                    "timeline": PLAN_EXECUTION_TIMELINE_ID,
                },
            )
            if exact is not True:
                raise RuntimeError("governed plan execution fixture is not exact")
            print("timeline execution seed verified")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(verify())
