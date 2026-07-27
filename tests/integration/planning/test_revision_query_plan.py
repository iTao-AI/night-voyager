# ruff: noqa: E501
from __future__ import annotations

import json
import os
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

pytestmark = pytest.mark.database

ORG = UUID("10000000-0000-0000-0000-000000000001")


def resource(prefix: str, suffix: int) -> UUID:
    return UUID(f"{prefix}-0000-0000-0000-{suffix:012d}")


async def set_context(connection: AsyncConnection) -> None:
    await connection.execute(
        text(
            "SELECT set_config('night_voyager.organization_id',"
            "'10000000-0000-0000-0000-000000000001',true)"
        )
    )


async def seed_history(connection: AsyncConnection, suffix: int) -> dict[str, UUID]:
    case_id = resource("4b000000", suffix)
    predecessor = resource("7b000000", suffix)
    successor = resource("7c000000", suffix)
    request_review = resource("8b000000", suffix)
    approval_review = resource("8c000000", suffix)
    task_id = resource("8d000000", suffix)
    brief_id = resource("8e000000", suffix)
    await connection.execute(
        text(
            "INSERT INTO app.student_cases "
            "SELECT (jsonb_populate_record(NULL::app.student_cases,"
            "to_jsonb(template)||jsonb_build_object("
            "'id',CAST(:case AS text),'current_revision',NULL,'state','intake'))).* "
            "FROM app.student_cases template "
            "WHERE template.organization_id=:org ORDER BY template.created_at LIMIT 1"
        ),
        {"org": ORG, "case": str(case_id)},
    )
    await connection.execute(
        text(
            "INSERT INTO app.student_case_revisions "
            "SELECT (jsonb_populate_record(NULL::app.student_case_revisions,"
            "to_jsonb(template)||jsonb_build_object("
            "'case_id',CAST(:case AS text),'revision',1,"
            "'revision_requested_by_review_id',NULL,"
            "'superseded_planning_run_id',NULL))).* "
            "FROM app.student_case_revisions template "
            "WHERE template.organization_id=:org AND template.revision=1 "
            "ORDER BY template.created_at LIMIT 1"
        ),
        {"org": ORG, "case": str(case_id)},
    )
    await connection.execute(
        text(
            "INSERT INTO app.planning_runs "
            "SELECT (jsonb_populate_record(NULL::app.planning_runs,"
            "to_jsonb(template)||jsonb_build_object("
            "'id',CAST(:predecessor AS text),'case_id',CAST(:case AS text),"
            "'case_revision',1,'state','review_required','is_current',false,"
            "'supersedes_run_id',NULL))).* "
            "FROM app.planning_runs template WHERE template.organization_id=:org "
            "ORDER BY template.created_at LIMIT 1"
        ),
        {
            "org": ORG,
            "case": str(case_id),
            "predecessor": str(predecessor),
        },
    )
    await connection.execute(
        text(
            "INSERT INTO app.advisor_reviews("
            "organization_id,id,case_id,case_revision,planning_run_id,"
            "review_version,advisor_actor_id,action,eligible_route_ids,"
            "risk_acceptances,reviewer_notes) VALUES("
            ":org,CAST(:review AS uuid),CAST(:case AS uuid),1,CAST(:run AS uuid),"
            "1,'20000000-0000-0000-0000-000000000001','request_revision',"
            "'[]'::jsonb,'[]'::jsonb,'query plan request')"
        ),
        {
            "org": ORG,
            "case": str(case_id),
            "run": str(predecessor),
            "review": str(request_review),
        },
    )
    await connection.execute(
        text(
            "INSERT INTO app.student_case_revisions "
            "SELECT (jsonb_populate_record(NULL::app.student_case_revisions,"
            "to_jsonb(template)||jsonb_build_object("
            "'case_id',CAST(:case AS text),'revision',2,"
            "'revision_requested_by_review_id',CAST(:review AS text),"
            "'superseded_planning_run_id',CAST(:run AS text)))).* "
            "FROM app.student_case_revisions template "
            "WHERE template.organization_id=:org AND template.revision=1 "
            "ORDER BY template.created_at LIMIT 1"
        ),
        {
            "org": ORG,
            "case": str(case_id),
            "review": str(request_review),
            "run": str(predecessor),
        },
    )
    await connection.execute(
        text(
            "INSERT INTO app.planning_runs "
            "SELECT (jsonb_populate_record(NULL::app.planning_runs,"
            "to_jsonb(template)||jsonb_build_object("
            "'id',CAST(:successor AS text),'case_id',CAST(:case AS text),"
            "'case_revision',2,'state','review_required','is_current',true,"
            "'supersedes_run_id',CAST(:predecessor AS text)))).* "
            "FROM app.planning_runs template WHERE template.organization_id=:org "
            "ORDER BY template.created_at LIMIT 1"
        ),
        {
            "org": ORG,
            "case": str(case_id),
            "predecessor": str(predecessor),
            "successor": str(successor),
        },
    )
    await connection.execute(
        text(
            "INSERT INTO app.advisor_reviews("
            "organization_id,id,case_id,case_revision,planning_run_id,"
            "review_version,advisor_actor_id,action,eligible_route_ids,"
            "risk_acceptances,reviewer_notes) VALUES("
            ":org,CAST(:review AS uuid),CAST(:case AS uuid),2,CAST(:run AS uuid),"
            "1,'20000000-0000-0000-0000-000000000001','approve_for_consultation',"
            "'[]'::jsonb,'[]'::jsonb,'query plan approval')"
        ),
        {
            "org": ORG,
            "case": str(case_id),
            "run": str(successor),
            "review": str(approval_review),
        },
    )
    await connection.execute(
        text(
            "UPDATE app.student_cases "
            "SET current_revision=2,state='planning' "
            "WHERE organization_id=:org AND id=CAST(:case AS uuid)"
        ),
        {"org": ORG, "case": str(case_id)},
    )
    await connection.execute(
        text(
            "INSERT INTO app.agent_tasks "
            "SELECT (jsonb_populate_record(NULL::app.agent_tasks,"
            "to_jsonb(template)||jsonb_build_object("
            "'id',CAST(:task AS text),'case_id',CAST(:case AS text),"
            "'case_revision',2,'state','failed','attempt_count',1,"
            "'lease_owner',NULL,'lease_expires_at',NULL,"
            "'result_planning_run_id',NULL,'terminal_code','query_plan_fixture',"
            "'predecessor_planning_run_id',CAST(:predecessor AS text)))).* "
            "FROM app.agent_tasks template WHERE template.organization_id=:org "
            "ORDER BY template.created_at LIMIT 1"
        ),
        {
            "org": ORG,
            "case": str(case_id),
            "task": str(task_id),
            "predecessor": str(predecessor),
        },
    )
    await connection.execute(
        text(
            "INSERT INTO app.decision_briefs("
            "organization_id,id,case_id,case_revision,planning_run_id,"
            "advisor_review_id,brief_version,policy_version,source_pack_id,"
            "source_pack_version,evidence_projection_sha256,output_sha256,"
            "source_snapshot_date,family_safe_projection,is_current) "
            "SELECT organization_id,CAST(:brief AS uuid),case_id,case_revision,id,"
            "CAST(:review AS uuid),1,policy_version,source_pack_id,"
            "source_pack_version,evidence_projection_sha256,output_sha256,"
            "current_date,'{}'::jsonb,true "
            "FROM app.planning_runs "
            "WHERE organization_id=:org AND id=CAST(:run AS uuid)"
        ),
        {
            "org": ORG,
            "case": str(case_id),
            "run": str(successor),
            "review": str(approval_review),
            "brief": str(brief_id),
        },
    )
    return {
        "case": case_id,
        "predecessor": predecessor,
        "successor": successor,
        "task": task_id,
        "review": approval_review,
        "brief": brief_id,
    }


def plan_text(plan: Any) -> str:
    return json.dumps(plan, sort_keys=True)


@pytest.mark.asyncio
async def test_revision_history_queries_are_exact_and_named_indexes_are_usable() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await set_context(connection)
            histories = [await seed_history(connection, suffix) for suffix in range(1301, 1313)]
            for table in (
                "student_case_revisions",
                "planning_runs",
                "agent_tasks",
                "advisor_reviews",
                "decision_briefs",
            ):
                await connection.execute(text(f"ANALYZE app.{table}"))
            target = histories[-1]
            queries = {
                "revision": (
                    "SELECT revision FROM app.student_case_revisions "
                    "WHERE organization_id=:org AND case_id=:case AND revision=2",
                    {"org": ORG, "case": target["case"]},
                    (2,),
                    "student_case_revisions_pkey",
                    None,
                ),
                "lineage": (
                    "SELECT case_id,revision FROM app.student_case_revisions "
                    "WHERE organization_id=:org "
                    "AND superseded_planning_run_id=:predecessor "
                    "AND superseded_planning_run_id IS NOT NULL "
                    "ORDER BY organization_id,case_id,superseded_planning_run_id",
                    {
                        "org": ORG,
                        "predecessor": target["predecessor"],
                    },
                    (target["case"], 2),
                    "student_case_revisions_one_planning_successor",
                    None,
                ),
                "task": (
                    "SELECT id,predecessor_planning_run_id FROM app.agent_tasks "
                    "WHERE organization_id=:org AND case_id=:case AND case_revision=2 "
                    "ORDER BY created_at DESC,id LIMIT 1",
                    {"org": ORG, "case": target["case"]},
                    (target["task"], target["predecessor"]),
                    "agent_tasks_case_revision_read_idx",
                    None,
                ),
                "review": (
                    "SELECT review_row.id,brief.id,brief.planning_run_id "
                    "FROM app.advisor_reviews review_row "
                    "JOIN app.decision_briefs brief "
                    "ON (brief.organization_id,brief.advisor_review_id)="
                    "(review_row.organization_id,review_row.id) "
                    "WHERE review_row.organization_id=:org "
                    "AND review_row.case_id=:case AND review_row.case_revision=2 "
                    "AND brief.planning_run_id=review_row.planning_run_id "
                    "AND brief.is_current "
                    "ORDER BY review_row.review_version DESC LIMIT 1",
                    {
                        "org": ORG,
                        "case": target["case"],
                    },
                    (target["review"], target["brief"], target["successor"]),
                    "advisor_reviews_case_revision_run_idx",
                    "SELECT id FROM app.advisor_reviews "
                    "WHERE organization_id=:org AND case_id=:case "
                    "AND case_revision=2 "
                    "ORDER BY organization_id,case_id,case_revision,"
                    "planning_run_id,review_version DESC",
                ),
            }
            definition_rows = (
                await connection.execute(
                    text(
                        "SELECT indexname,indexdef FROM pg_indexes "
                        "WHERE schemaname='app' AND indexname IN ("
                        "'student_case_revisions_pkey',"
                        "'student_case_revisions_one_planning_successor',"
                        "'agent_tasks_case_revision_read_idx',"
                        "'advisor_reviews_case_revision_run_idx')"
                    )
                )
            ).all()
            definitions = {str(row[0]): str(row[1]) for row in definition_rows}
            assert set(definitions) == {
                "student_case_revisions_pkey",
                "student_case_revisions_one_planning_successor",
                "agent_tasks_case_revision_read_idx",
                "advisor_reviews_case_revision_run_idx",
            }
            for query_name, (
                query,
                parameters,
                expected,
                index_name,
                forced_query,
            ) in queries.items():
                row = (
                    await connection.execute(text(query), parameters)
                ).one_or_none()
                assert row is not None, query_name
                assert tuple(row) == expected
                natural = await connection.scalar(
                    text(f"EXPLAIN (FORMAT JSON) {query}"), parameters
                )
                assert natural is not None
                await connection.execute(text("SET LOCAL enable_seqscan=off"))
                await connection.execute(text("SET LOCAL enable_sort=off"))
                forced = await connection.scalar(
                    text(f"EXPLAIN (FORMAT JSON) {forced_query or query}"),
                    parameters,
                )
                assert index_name in plan_text(forced)
    finally:
        await engine.dispose()
