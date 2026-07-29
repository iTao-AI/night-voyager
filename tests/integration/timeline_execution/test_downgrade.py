from __future__ import annotations

import os
import subprocess

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.database


def _alembic(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("uv", "run", "alembic", *arguments),
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.mark.asyncio
async def test_empty_0014_downgrade_and_reupgrade_are_exact() -> None:
    if os.environ.get("NIGHT_VOYAGER_TIMELINE_MIGRATION_PHASE") != "empty":
        pytest.skip("isolated empty timeline migration phase only")
    result = _alembic("downgrade", "0013")
    assert result.returncode == 0, result.stderr
    assert _alembic("current").stdout.strip().startswith("0013")
    result = _alembic("upgrade", "0014")
    assert result.returncode == 0, result.stderr
    assert _alembic("current").stdout.strip().startswith("0014")


@pytest.mark.asyncio
async def test_0014_downgrade_refuses_history_before_catalog_mutation() -> None:
    if os.environ.get("NIGHT_VOYAGER_TIMELINE_MIGRATION_PHASE") != "history":
        pytest.skip("isolated history timeline migration phase only")
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "SELECT set_config('night_voyager.organization_id',"
                    "'10000000-0000-0000-0000-000000000001',true)"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO app.advisor_reviews("
                    "organization_id,id,case_id,case_revision,planning_run_id,"
                    "review_version,advisor_actor_id,action,eligible_route_ids,"
                    "risk_acceptances,reviewer_notes) "
                    "SELECT organization_id,"
                    "'91000000-0000-0000-0000-000000000001',case_id,case_revision,id,"
                    "1,'20000000-0000-0000-0000-000000000001',"
                    "'approve_for_consultation','[]','[]','timeline downgrade fixture' "
                    "FROM app.planning_runs "
                    "WHERE organization_id="
                    "'10000000-0000-0000-0000-000000000001' "
                    "AND id='70000000-0000-0000-0000-000000000001'"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO app.decision_briefs("
                    "organization_id,id,case_id,case_revision,planning_run_id,"
                    "advisor_review_id,brief_version,policy_version,source_pack_id,"
                    "source_pack_version,evidence_projection_sha256,output_sha256,"
                    "source_snapshot_date,family_safe_projection,is_current) "
                    "SELECT organization_id,"
                    "'92000000-0000-0000-0000-000000000001',case_id,case_revision,id,"
                    "'91000000-0000-0000-0000-000000000001',1,policy_version,"
                    "source_pack_id,source_pack_version,evidence_projection_sha256,"
                    "output_sha256,current_date,'{}',true "
                    "FROM app.planning_runs "
                    "WHERE organization_id="
                    "'10000000-0000-0000-0000-000000000001' "
                    "AND id='70000000-0000-0000-0000-000000000001'"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO app.family_decisions("
                    "organization_id,id,receipt_id,case_id,decision_brief_id,"
                    "brief_version,selected_route_id,accepted_budget_min_minor,"
                    "accepted_budget_max_minor,currency,accepted_trade_offs,"
                    "decision_made_by_actor_id,recorded_by_actor_id,source,"
                    "planning_run_id) "
                    "SELECT r.organization_id,"
                    "'93000000-0000-0000-0000-000000000001',"
                    "'93100000-0000-0000-0000-000000000001',r.case_id,"
                    "'92000000-0000-0000-0000-000000000001',1,p.id,"
                    "1,2,'CNY','[]',"
                    "'20000000-0000-0000-0000-000000000003',"
                    "'20000000-0000-0000-0000-000000000003','direct',r.id "
                    "FROM app.planning_runs r "
                    "JOIN app.planning_routes p ON "
                    "(p.organization_id,p.planning_run_id)=(r.organization_id,r.id) "
                    "WHERE r.organization_id="
                    "'10000000-0000-0000-0000-000000000001' "
                    "AND r.id='70000000-0000-0000-0000-000000000001' "
                    "ORDER BY p.country LIMIT 1"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO app.timeline_plans("
                    "organization_id,id,family_decision_id,schema_version,"
                    "country,intake,milestones) "
                    "VALUES("
                    "'10000000-0000-0000-0000-000000000001',"
                    "'94000000-0000-0000-0000-000000000001',"
                    "'93000000-0000-0000-0000-000000000001',1,"
                    "'australia','2027-02','[]')"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO app.timeline_executions("
                    "organization_id,id,case_id,case_revision,family_decision_id,"
                    "decision_receipt_id,timeline_plan_id,schema_version,state,row_version) "
                    "SELECT t.organization_id,"
                    "'95000000-0000-0000-0000-000000000001',d.case_id,"
                    "c.current_revision,d.id,d.receipt_id,t.id,1,'active',1 "
                    "FROM app.timeline_plans t "
                    "JOIN app.family_decisions d ON "
                    "(d.organization_id,d.id)=(t.organization_id,t.family_decision_id) "
                    "JOIN app.student_cases c ON "
                    "(c.organization_id,c.id)=(d.organization_id,d.case_id) "
                    "LIMIT 1"
                )
            )
        result = _alembic("downgrade", "0013")
        assert result.returncode != 0
        assert "refusing downgrade: timeline execution history exists" in result.stderr
        async with engine.connect() as connection:
            assert await connection.scalar(
                text("SELECT version_num FROM alembic_version")
            ) == "0014"
            assert await connection.scalar(
                text("SELECT to_regclass('app.timeline_executions')::text")
            ) == "app.timeline_executions"
    finally:
        await engine.dispose()
