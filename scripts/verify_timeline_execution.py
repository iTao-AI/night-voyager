from __future__ import annotations

import argparse
import asyncio
import os
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from night_voyager.identity.demo_seed import (
    BLOCKED_PLAN_EXECUTION_BRIEF_ID,
    BLOCKED_PLAN_EXECUTION_CASE_ID,
    BLOCKED_PLAN_EXECUTION_DECISION_ID,
    BLOCKED_PLAN_EXECUTION_DECISION_RECEIPT_ID,
    BLOCKED_PLAN_EXECUTION_REVIEW_ID,
    BLOCKED_PLAN_EXECUTION_RUN_ID,
    BLOCKED_PLAN_EXECUTION_TIMELINE_ID,
    PLAN_EXECUTION_BLOCKED_ACTORS,
    PLAN_EXECUTION_BRIEF_ID,
    PLAN_EXECUTION_CASE_ID,
    PLAN_EXECUTION_DECISION_ID,
    PLAN_EXECUTION_DECISION_RECEIPT_ID,
    PLAN_EXECUTION_HAPPY_ACTORS,
    PLAN_EXECUTION_REVIEW_ID,
    PLAN_EXECUTION_RUN_ID,
    PLAN_EXECUTION_TIMELINE_ID,
)

DEMO_ORG = UUID("10000000-0000-0000-0000-000000000001")
DEMO_ADVISOR = PLAN_EXECUTION_HAPPY_ACTORS[0][2]
DEMO_STUDENT = PLAN_EXECUTION_HAPPY_ACTORS[1][2]
DEMO_PARENT = PLAN_EXECUTION_HAPPY_ACTORS[2][2]

SEED_SCENARIOS = (
    (
        "happy",
        PLAN_EXECUTION_CASE_ID,
        PLAN_EXECUTION_RUN_ID,
        PLAN_EXECUTION_REVIEW_ID,
        PLAN_EXECUTION_BRIEF_ID,
        PLAN_EXECUTION_DECISION_ID,
        PLAN_EXECUTION_DECISION_RECEIPT_ID,
        PLAN_EXECUTION_TIMELINE_ID,
        PLAN_EXECUTION_HAPPY_ACTORS,
    ),
    (
        "blocked",
        BLOCKED_PLAN_EXECUTION_CASE_ID,
        BLOCKED_PLAN_EXECUTION_RUN_ID,
        BLOCKED_PLAN_EXECUTION_REVIEW_ID,
        BLOCKED_PLAN_EXECUTION_BRIEF_ID,
        BLOCKED_PLAN_EXECUTION_DECISION_ID,
        BLOCKED_PLAN_EXECUTION_DECISION_RECEIPT_ID,
        BLOCKED_PLAN_EXECUTION_TIMELINE_ID,
        PLAN_EXECUTION_BLOCKED_ACTORS,
    ),
)


def parse_expectation(argv: Sequence[str] | None = None) -> str:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument(
        "--expect",
        choices=("seed", "completed"),
        default="seed",
    )
    return str(parser.parse_args(argv).expect)


async def _verify_seed(connection: AsyncConnection) -> None:
    for (
        scenario,
        case_id,
        run_id,
        review_id,
        brief_id,
        decision_id,
        receipt_id,
        timeline_id,
        actors,
    ) in SEED_SCENARIOS:
        exact = await connection.scalar(
            text(
                "SELECT "
                "(SELECT count(*)=1 FROM app.student_cases "
                "WHERE id=:case AND state='plan_ready' AND current_revision=1) "
                "AND (SELECT count(*)=1 FROM app.student_case_revisions "
                "WHERE case_id=:case AND revision=1) "
                "AND (SELECT count(*)=1 FROM app.planning_runs "
                "WHERE case_id=:case AND id=:run "
                "AND state='review_required' AND is_current) "
                "AND (SELECT count(*)=1 FROM app.advisor_reviews "
                "WHERE case_id=:case AND id=:review "
                "AND planning_run_id=:run AND advisor_actor_id=:advisor) "
                "AND (SELECT count(*)=1 FROM app.decision_briefs "
                "WHERE case_id=:case AND id=:brief "
                "AND advisor_review_id=:review AND NOT is_current) "
                "AND (SELECT count(*)=1 FROM app.family_decisions "
                "WHERE case_id=:case AND id=:decision "
                "AND receipt_id=:receipt AND decision_brief_id=:brief "
                "AND decision_made_by_actor_id=:parent) "
                "AND (SELECT count(*)=1 FROM app.timeline_plans "
                "WHERE id=:timeline AND family_decision_id=:decision) "
                "AND (SELECT count(*)=3 AND count(DISTINCT actor_id)=3 "
                "FROM app.student_case_participants WHERE case_id=:case) "
                "AND (SELECT count(*)=3 FROM auth.demo_principals "
                "WHERE actor_id IN (:advisor,:student,:parent)) "
                "AND (SELECT count(*)=0 FROM app.timeline_executions "
                "WHERE timeline_plan_id=:timeline) "
                "AND (SELECT count(*)=0 FROM app.agent_tasks WHERE case_id=:case)"
            ),
            {
                "case": case_id,
                "run": run_id,
                "review": review_id,
                "brief": brief_id,
                "decision": decision_id,
                "receipt": receipt_id,
                "timeline": timeline_id,
                "advisor": actors[0][2],
                "student": actors[1][2],
                "parent": actors[2][2],
            },
        )
        if exact is not True:
            raise RuntimeError(f"{scenario} plan execution fixture is not exact")
    for table in (
        "timeline_checkpoint_attestations",
        "timeline_checkpoint_verifications",
        "timeline_mutation_receipts",
        "timeline_reassessment_requests",
    ):
        count = await connection.scalar(text(f"SELECT count(*) FROM app.{table}"))
        if count != 0:
            raise RuntimeError(f"seed contains unexpected {table}")
    print("timeline execution seed verified")


async def _verify_completed(connection: AsyncConnection) -> None:
    exact = await connection.scalar(
        text(
            "WITH expected_checkpoints(ordinal,milestone_key,due_date,"
            "accountable_role) AS (VALUES "
            "(1,'documents',date '2026-09-01','student'),"
            "(2,'application',date '2026-10-15','student'),"
            "(3,'visa',date '2026-12-15','student'),"
            "(4,'arrival',date '2027-01-20','parent')), "
            "execution AS (SELECT e.* FROM app.timeline_executions e "
            "WHERE e.organization_id=:org AND e.timeline_plan_id=:timeline) "
            "SELECT "
            "(SELECT count(*)=1 FROM app.student_cases "
            "WHERE organization_id=:org AND id=:case AND state='plan_ready' "
            "AND current_revision=1) "
            "AND (SELECT count(*)=1 FROM app.student_case_revisions "
            "WHERE organization_id=:org AND case_id=:case AND revision=1) "
            "AND (SELECT count(*)=1 FROM app.planning_runs "
            "WHERE organization_id=:org AND case_id=:case AND id=:run "
            "AND state='review_required' AND is_current) "
            "AND (SELECT count(*)=1 FROM app.advisor_reviews "
            "WHERE organization_id=:org AND case_id=:case AND id=:review "
            "AND planning_run_id=:run AND advisor_actor_id=:advisor) "
            "AND (SELECT count(*)=1 FROM app.decision_briefs "
            "WHERE organization_id=:org AND case_id=:case AND id=:brief "
            "AND advisor_review_id=:review AND NOT is_current) "
            "AND (SELECT count(*)=1 FROM app.family_decisions "
            "WHERE organization_id=:org AND case_id=:case AND id=:decision "
            "AND receipt_id=:receipt AND decision_brief_id=:brief) "
            "AND (SELECT count(*)=1 FROM app.timeline_plans "
            "WHERE organization_id=:org AND id=:timeline "
            "AND family_decision_id=:decision AND schema_version=1) "
            "AND (SELECT count(*)=1 FROM execution "
            "WHERE case_id=:case AND case_revision=1 "
            "AND family_decision_id=:decision "
            "AND decision_receipt_id=:receipt "
            "AND schema_version=1 AND state='completed') "
            "AND (SELECT count(*)=4 FROM app.timeline_checkpoints c "
            "JOIN execution e ON e.organization_id=c.organization_id "
            "AND e.id=c.execution_id) "
            "AND NOT EXISTS (SELECT 1 FROM app.timeline_checkpoints c "
            "JOIN execution e ON e.organization_id=c.organization_id "
            "AND e.id=c.execution_id "
            "LEFT JOIN expected_checkpoints expected "
            "ON expected.ordinal=c.ordinal "
            "AND expected.milestone_key=c.milestone_key "
            "AND expected.due_date=c.due_date "
            "AND expected.accountable_role=c.accountable_role "
            "WHERE expected.ordinal IS NULL OR c.state<>'verified') "
            "AND (SELECT count(*)=4 FROM app.timeline_checkpoint_attestations a "
            "JOIN execution e ON e.organization_id=a.organization_id "
            "AND e.id=a.execution_id) "
            "AND NOT EXISTS (SELECT 1 "
            "FROM app.timeline_checkpoint_attestations a "
            "JOIN app.timeline_checkpoints c "
            "ON c.organization_id=a.organization_id "
            "AND c.execution_id=a.execution_id AND c.id=a.checkpoint_id "
            "JOIN execution e ON e.organization_id=c.organization_id "
            "AND e.id=c.execution_id "
            "WHERE a.attestation_kind<>'completion' "
            "OR a.status_code<>'ready_for_advisor' "
            "OR a.attestation_code<>c.milestone_key||'_status_confirmed' "
            "OR a.reason_code<>'not_applicable' "
            "OR a.reporter_role<>c.accountable_role "
            "OR a.reporter_actor_id<>CASE c.accountable_role "
            "WHEN 'student' THEN CAST(:student AS uuid) "
            "ELSE CAST(:parent AS uuid) END) "
            "AND (SELECT count(*)=4 FROM app.timeline_checkpoint_verifications v "
            "JOIN execution e ON e.organization_id=v.organization_id "
            "AND e.id=v.execution_id) "
            "AND NOT EXISTS (SELECT 1 "
            "FROM app.timeline_checkpoint_verifications v "
            "JOIN app.timeline_checkpoint_attestations a "
            "ON a.organization_id=v.organization_id "
            "AND a.execution_id=v.execution_id "
            "AND a.checkpoint_id=v.checkpoint_id "
            "AND a.attestation_id=v.attestation_id "
            "JOIN execution e ON e.organization_id=v.organization_id "
            "AND e.id=v.execution_id "
            "WHERE v.action<>'verify' "
            "OR v.reason_code<>'attestation_verified' "
            "OR v.advisor_actor_id<>CAST(:advisor AS uuid)) "
            "AND (SELECT count(*)=0 "
            "FROM app.timeline_checkpoint_attestations a "
            "JOIN execution e ON e.organization_id=a.organization_id "
            "AND e.id=a.execution_id "
            "WHERE a.attestation_kind IN ('progress','blocked')) "
            "AND (SELECT count(*)=0 "
            "FROM app.timeline_checkpoint_verifications v "
            "JOIN execution e ON e.organization_id=v.organization_id "
            "AND e.id=v.execution_id WHERE v.action='request_update') "
            "AND (SELECT count(*)=0 FROM app.timeline_reassessment_requests r "
            "JOIN execution e ON e.organization_id=r.organization_id "
            "AND e.id=r.execution_id) "
            "AND (SELECT count(*)=9 FROM app.timeline_mutation_receipts m "
            "JOIN execution e ON e.organization_id=m.organization_id "
            "AND e.id=m.execution_id WHERE m.schema_version=1) "
            "AND (SELECT count(*)=1 FROM app.timeline_mutation_receipts m "
            "JOIN execution e ON e.organization_id=m.organization_id "
            "AND e.id=m.execution_id WHERE m.operation='start' "
            "AND m.result_kind='timeline_execution_started') "
            "AND (SELECT count(*)=4 FROM app.timeline_mutation_receipts m "
            "JOIN execution e ON e.organization_id=m.organization_id "
            "AND e.id=m.execution_id WHERE m.operation='attest' "
            "AND m.result_kind='timeline_checkpoint_attested') "
            "AND (SELECT count(*)=4 FROM app.timeline_mutation_receipts m "
            "JOIN execution e ON e.organization_id=m.organization_id "
            "AND e.id=m.execution_id WHERE m.operation='verify' "
            "AND m.result_kind='timeline_checkpoint_verified')"
        ),
        {
            "org": DEMO_ORG,
            "case": PLAN_EXECUTION_CASE_ID,
            "run": PLAN_EXECUTION_RUN_ID,
            "review": PLAN_EXECUTION_REVIEW_ID,
            "brief": PLAN_EXECUTION_BRIEF_ID,
            "decision": PLAN_EXECUTION_DECISION_ID,
            "receipt": PLAN_EXECUTION_DECISION_RECEIPT_ID,
            "timeline": PLAN_EXECUTION_TIMELINE_ID,
            "advisor": DEMO_ADVISOR,
            "student": DEMO_STUDENT,
            "parent": DEMO_PARENT,
        },
    )
    if exact is not True:
        raise RuntimeError("governed plan execution completed state is not exact")
    print("timeline execution completed verified")


async def verify(expectation: str = "seed") -> None:
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
            if expectation == "completed":
                await _verify_completed(connection)
            else:
                await _verify_seed(connection)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(verify(parse_expectation()))
