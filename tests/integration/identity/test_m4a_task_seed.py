from __future__ import annotations

import os
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.database
DEMO_ORG = UUID("10000000-0000-0000-0000-000000000001")
CASE_ID = UUID("40000000-0000-0000-0000-000000000001")
TASK_CASE_ID = UUID("40000000-0000-0000-0000-000000000002")
RUN_ID = UUID("70000000-0000-0000-0000-000000000001")


@pytest.mark.asyncio
async def test_explicit_seed_keeps_golden_run_and_adds_separate_task_ready_case() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(DEMO_ORG)},
            )
            task_case = (
                await connection.execute(
                    text(
                        "SELECT state,current_revision FROM app.student_cases "
                        "WHERE organization_id=:org AND id=:case"
                    ),
                    {"org": DEMO_ORG, "case": TASK_CASE_ID},
                )
            ).mappings().one()
            assert dict(task_case) == {"state": "planning", "current_revision": 1}
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.student_case_participants "
                        "WHERE organization_id=:org AND case_id=:case AND role='advisor'"
                    ),
                    {"org": DEMO_ORG, "case": TASK_CASE_ID},
                )
                == 1
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.planning_runs "
                        "WHERE organization_id=:org AND case_id=:case"
                    ),
                    {"org": DEMO_ORG, "case": TASK_CASE_ID},
                )
                == 0
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.planning_runs "
                        "WHERE organization_id=:org AND case_id=:case AND id=:run"
                    ),
                    {"org": DEMO_ORG, "case": CASE_ID, "run": RUN_ID},
                )
                == 1
            )
    finally:
        await engine.dispose()
