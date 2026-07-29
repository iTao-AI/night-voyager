from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast
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


def _load_proof(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("plan execution proof must be a regular file")
    raw_value = cast(object, json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(raw_value, dict):
        raise RuntimeError("invalid plan execution proof")
    value = cast(dict[str, object], raw_value)
    expected = {
        "schema_version",
        "locale",
        "scenario",
        "case_id",
        "timeline_plan_id",
        "execution_id",
        "accepted_receipt_ids",
        "checkpoint_ids",
        "reassessment_request_id",
    }
    if (
        set(value) != expected
        or value["schema_version"] != 1
        or value["locale"] not in ("zh-CN", "en")
        or value["scenario"] not in ("happy", "blocked")
        or not isinstance(value["accepted_receipt_ids"], list)
        or not isinstance(value["checkpoint_ids"], list)
    ):
        raise RuntimeError("invalid plan execution proof")
    receipt_values = cast(list[object], value["accepted_receipt_ids"])
    checkpoint_values = cast(list[object], value["checkpoint_ids"])
    try:
        for key in ("case_id", "timeline_plan_id", "execution_id"):
            UUID(str(value[key]))
        for item in (*receipt_values, *checkpoint_values):
            UUID(str(item))
        if value["reassessment_request_id"] is not None:
            UUID(str(value["reassessment_request_id"]))
    except (TypeError, ValueError) as error:
        raise RuntimeError("invalid plan execution proof") from error
    if len(set(receipt_values)) != len(receipt_values):
        raise RuntimeError("invalid plan execution proof")
    if len(set(checkpoint_values)) != 4:
        raise RuntimeError("invalid plan execution proof")
    return cast(dict[str, Any], value)


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


async def _verify_proof(connection: AsyncConnection, proof: dict[str, Any]) -> None:
    scenario = str(proof["scenario"])
    expected_case = (
        PLAN_EXECUTION_CASE_ID
        if scenario == "happy"
        else BLOCKED_PLAN_EXECUTION_CASE_ID
    )
    expected_timeline = (
        PLAN_EXECUTION_TIMELINE_ID
        if scenario == "happy"
        else BLOCKED_PLAN_EXECUTION_TIMELINE_ID
    )
    if (
        proof["case_id"] != str(expected_case)
        or proof["timeline_plan_id"] != str(expected_timeline)
    ):
        raise RuntimeError("plan execution proof anchor mismatch")
    execution_id = UUID(str(proof["execution_id"]))
    receipts = [UUID(str(value)) for value in proof["accepted_receipt_ids"]]
    checkpoints = [UUID(str(value)) for value in proof["checkpoint_ids"]]
    expected_state = "completed" if scenario == "happy" else "reassessment_required"
    execution_exact = await connection.scalar(
        text(
            "SELECT count(*)=1 FROM app.timeline_executions "
            "WHERE organization_id=:org AND id=:execution AND case_id=:case "
            "AND timeline_plan_id=:timeline AND state=:state"
        ),
        {
            "org": DEMO_ORG,
            "execution": execution_id,
            "case": expected_case,
            "timeline": expected_timeline,
            "state": expected_state,
        },
    )
    if execution_exact is not True:
        raise RuntimeError("plan execution proof state mismatch")
    actual_checkpoints = (
        await connection.scalars(
            text(
                "SELECT id FROM app.timeline_checkpoints "
                "WHERE organization_id=:org AND execution_id=:execution "
                "ORDER BY ordinal"
            ),
            {"org": DEMO_ORG, "execution": execution_id},
        )
    ).all()
    if actual_checkpoints != checkpoints:
        raise RuntimeError("plan execution proof checkpoint mismatch")
    actual_receipts = set(
        (
            await connection.scalars(
                text(
                    "SELECT receipt_id FROM app.timeline_mutation_receipts "
                    "WHERE organization_id=:org AND execution_id=:execution"
                ),
                {"org": DEMO_ORG, "execution": execution_id},
            )
        ).all()
    )
    if actual_receipts != set(receipts):
        raise RuntimeError("plan execution proof receipt mismatch")
    if scenario == "happy":
        exact = await connection.scalar(
            text(
                "SELECT "
                "(SELECT count(*) FROM app.timeline_checkpoint_attestations "
                "WHERE execution_id=:execution)=6 "
                "AND (SELECT count(*) FROM app.timeline_checkpoint_verifications "
                "WHERE execution_id=:execution)=5 "
                "AND (SELECT count(*) FROM app.timeline_reassessment_requests "
                "WHERE execution_id=:execution)=0 "
                "AND (SELECT count(*) FROM app.idempotency_records i "
                "WHERE i.response_id IN ("
                "SELECT receipt_id FROM app.timeline_mutation_receipts "
                "WHERE execution_id=:execution))="
                "(SELECT count(*) FROM app.timeline_mutation_receipts "
                "WHERE execution_id=:execution)"
            ),
            {"execution": execution_id},
        )
        if exact is not True or proof["reassessment_request_id"] is not None:
            raise RuntimeError("happy plan execution proof mismatch")
    else:
        reassessment_id = UUID(str(proof["reassessment_request_id"]))
        exact = await connection.scalar(
            text(
                "SELECT "
                "(SELECT count(*) FROM app.timeline_checkpoint_attestations "
                "WHERE execution_id=:execution AND attestation_kind='blocked')=1 "
                "AND (SELECT count(*) FROM app.timeline_checkpoint_verifications "
                "WHERE execution_id=:execution)=0 "
                "AND (SELECT count(*) FROM app.timeline_reassessment_requests "
                "WHERE execution_id=:execution AND reassessment_id=:reassessment "
                "AND successor_status='pending_future_authorization')=1 "
                "AND (SELECT count(*) FROM app.agent_tasks WHERE case_id=:case)=0 "
                "AND (SELECT count(*) FROM app.planning_runs WHERE case_id=:case)=1 "
                "AND (SELECT count(*) FROM app.family_decisions WHERE case_id=:case)=1 "
                "AND (SELECT count(*) FROM app.timeline_plans plan "
                "JOIN app.family_decisions decision "
                "ON (decision.organization_id,decision.id)="
                "(plan.organization_id,plan.family_decision_id) "
                "WHERE decision.case_id=:case)=1"
            ),
            {
                "execution": execution_id,
                "reassessment": reassessment_id,
                "case": expected_case,
            },
        )
        if exact is not True:
            raise RuntimeError("blocked plan execution proof mismatch")
    print(
        "timeline execution browser database proof verified "
        f"locale={proof['locale']} scenario={scenario}"
    )


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


async def verify_proof(path: Path) -> None:
    proof = _load_proof(path)
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "SELECT set_config("
                    "'night_voyager.organization_id',:organization_id,true)"
                ),
                {"organization_id": str(DEMO_ORG)},
            )
            await _verify_proof(connection, proof)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    cli = argparse.ArgumentParser(allow_abbrev=False)
    cli.add_argument("--expect", choices=("seed", "completed"), default="seed")
    cli.add_argument("--proof-file", type=Path)
    arguments = cli.parse_args()
    if arguments.proof_file is not None:
        asyncio.run(verify_proof(arguments.proof_file))
    else:
        asyncio.run(verify(str(arguments.expect)))
