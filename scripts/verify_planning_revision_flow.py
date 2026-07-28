#!/usr/bin/env python3
"""Verify one bounded planning-revision browser proof against PostgreSQL."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any, TypedDict, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DEMO_ORG = UUID("10000000-0000-0000-0000-000000000001")
DEMO_ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
ROOT_KEYS = {"schema_version", "locale", "happy", "blocked"}
FLOW_KEYS = {
    "case_id",
    "request_review_id",
    "predecessor_run_id",
    "task_id",
    "current_run_id",
}


class FlowIdentity(TypedDict):
    case_id: str
    request_review_id: str
    predecessor_run_id: str
    task_id: str
    current_run_id: str


class BrowserProof(TypedDict):
    schema_version: int
    locale: str
    happy: FlowIdentity
    blocked: FlowIdentity


def _uuid_string(value: object) -> bool:
    return isinstance(value, str) and str(UUID(value)) == value


def load_proof(path: Path) -> BrowserProof:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError
        proof = cast(dict[str, object], raw)
        if set(proof) != ROOT_KEYS:
            raise ValueError
        if proof["schema_version"] != 1 or proof["locale"] not in {"zh-CN", "en"}:
            raise ValueError
        for lane in ("happy", "blocked"):
            identity_raw = proof[lane]
            if not isinstance(identity_raw, dict):
                raise ValueError
            identity = cast(dict[str, object], identity_raw)
            if set(identity) != FLOW_KEYS or not all(
                _uuid_string(value) for value in identity.values()
            ):
                raise ValueError
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise SystemExit("invalid planning revision proof file") from exc
    return cast(BrowserProof, proof)


async def _read_flow(
    database_url: str, identity: FlowIdentity
) -> dict[str, Any]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            for name, value in (
                ("night_voyager.organization_id", str(DEMO_ORG)),
                ("night_voyager.actor_id", str(DEMO_ADVISOR)),
                ("night_voyager.role", "advisor"),
            ):
                await connection.execute(
                    text("SELECT set_config(:name,:value,false)"),
                    {"name": name, "value": value},
                )
            row = (
                await connection.execute(
                    text(
                        "SELECT c.id::text AS case_id,c.state,c.current_revision,"
                        "revision.superseded_planning_run_id::text AS revision_predecessor,"
                        "task.predecessor_planning_run_id::text AS task_predecessor,"
                        "task.result_planning_run_id::text AS task_run,"
                        "current_run.supersedes_run_id::text AS run_predecessor,"
                        "current_run.state AS current_run_state,"
                        "(SELECT count(*)::integer FROM app.student_case_revisions item "
                        "WHERE item.organization_id=c.organization_id "
                        "AND item.case_id=c.id) AS revision_count,"
                        "(SELECT count(*)::integer FROM app.memory_candidates item "
                        "WHERE item.organization_id=c.organization_id "
                        "AND item.case_id=c.id) AS candidate_count,"
                        "(SELECT count(*)::integer FROM app.confirmed_facts item "
                        "WHERE item.organization_id=c.organization_id "
                        "AND item.case_id=c.id) AS confirmed_fact_count,"
                        "(SELECT count(*)::integer FROM app.planning_runs item "
                        "WHERE item.organization_id=c.organization_id "
                        "AND item.case_id=c.id) AS run_count,"
                        "(SELECT count(*)::integer FROM app.planning_runs item "
                        "WHERE item.organization_id=c.organization_id "
                        "AND item.case_id=c.id AND item.is_current) AS current_run_count,"
                        "(SELECT count(*)::integer FROM app.agent_tasks item "
                        "WHERE item.organization_id=c.organization_id "
                        "AND item.case_id=c.id AND item.case_revision=2) AS revised_task_count,"
                        "(SELECT count(*)::integer FROM app.agent_executions item "
                        "WHERE item.organization_id=c.organization_id "
                        "AND item.task_id=task.id) AS execution_count,"
                        "(SELECT count(*)::integer FROM app.agent_task_events item "
                        "WHERE item.organization_id=c.organization_id "
                        "AND item.task_id=task.id) AS task_event_count,"
                        "(SELECT count(*)::integer FROM app.advisor_reviews item "
                        "WHERE item.organization_id=c.organization_id "
                        "AND item.case_id=c.id AND item.action='request_revision') "
                        "AS request_review_count,"
                        "(SELECT count(*)::integer FROM app.advisor_reviews item "
                        "WHERE item.organization_id=c.organization_id "
                        "AND item.case_id=c.id AND item.action='approve_for_consultation') "
                        "AS approval_review_count,"
                        "(SELECT count(*)::integer FROM app.decision_briefs item "
                        "WHERE item.organization_id=c.organization_id "
                        "AND item.case_id=c.id) AS brief_count,"
                        "(SELECT count(*)::integer FROM app.family_decisions item "
                        "WHERE item.organization_id=c.organization_id "
                        "AND item.case_id=c.id) AS decision_count,"
                        "(SELECT count(DISTINCT item.receipt_id)::integer "
                        "FROM app.family_decisions item "
                        "WHERE item.organization_id=c.organization_id "
                        "AND item.case_id=c.id "
                        "AND item.receipt_id IS NOT NULL) AS receipt_count,"
                        "(SELECT count(*)::integer FROM app.timeline_plans item "
                        "JOIN app.family_decisions decision "
                        "ON decision.organization_id=item.organization_id "
                        "AND decision.id=item.family_decision_id "
                        "WHERE decision.organization_id=c.organization_id "
                        "AND decision.case_id=c.id) AS timeline_count "
                        "FROM app.student_cases c "
                        "JOIN app.student_case_revisions revision "
                        "ON revision.organization_id=c.organization_id "
                        "AND revision.case_id=c.id AND revision.revision=2 "
                        "JOIN app.agent_tasks task "
                        "ON task.organization_id=c.organization_id "
                        "AND task.id=:task AND task.case_id=c.id "
                        "AND task.case_revision=2 "
                        "JOIN app.planning_runs current_run "
                        "ON current_run.organization_id=task.organization_id "
                        "AND current_run.id=task.result_planning_run_id "
                        "WHERE c.organization_id=:org AND c.id=:case "
                        "AND EXISTS(SELECT 1 FROM app.advisor_reviews request_review "
                        "WHERE request_review.organization_id=c.organization_id "
                        "AND request_review.id=:request_review "
                        "AND request_review.case_id=c.id "
                        "AND request_review.action='request_revision')"
                    ),
                    {
                        "org": DEMO_ORG,
                        "case": UUID(identity["case_id"]),
                        "task": UUID(identity["task_id"]),
                        "request_review": UUID(identity["request_review_id"]),
                    },
                )
            ).mappings().one_or_none()
        if row is None:
            raise SystemExit("planning revision database authority is unavailable")
        return dict(row)
    finally:
        await engine.dispose()


def _validate_identity(row: dict[str, Any], identity: FlowIdentity) -> None:
    predecessor = identity["predecessor_run_id"]
    current = identity["current_run_id"]
    if not all(
        (
            row["case_id"] == identity["case_id"],
            row["current_revision"] == 2,
            row["revision_predecessor"] == predecessor,
            row["task_predecessor"] == predecessor,
            row["run_predecessor"] == predecessor,
            row["task_run"] == current,
            row["revision_count"] == 2,
            row["candidate_count"] == 2,
            row["confirmed_fact_count"] == 2,
            row["run_count"] == 2,
            row["current_run_count"] == 1,
            row["revised_task_count"] == 1,
            row["request_review_count"] == 1,
        )
    ):
        raise SystemExit("planning revision lineage or duplicate authority mismatch")


def validate_happy(row: dict[str, Any], identity: FlowIdentity) -> None:
    _validate_identity(row, identity)
    if not all(
        (
            row["state"] == "plan_ready",
            row["current_run_state"] == "review_required",
            row["approval_review_count"] == 1,
            row["execution_count"] == 2,
            row["task_event_count"] == 7,
            row["brief_count"] == 1,
            row["decision_count"] == 1,
            row["receipt_count"] == 1,
            row["timeline_count"] == 1,
        )
    ):
        raise SystemExit("planning revision happy-path authority mismatch")


def validate_blocked(row: dict[str, Any], identity: FlowIdentity) -> None:
    _validate_identity(row, identity)
    if not all(
        (
            row["state"] == "planning",
            row["current_run_state"] == "blocked",
            row["approval_review_count"] == 0,
            row["execution_count"] == 1,
            row["task_event_count"] == 4,
            row["brief_count"] == 0,
            row["decision_count"] == 0,
            row["receipt_count"] == 0,
            row["timeline_count"] == 0,
        )
    ):
        raise SystemExit("planning revision blocked-path authority mismatch")


async def verify(database_url: str, proof: BrowserProof) -> None:
    happy = await _read_flow(database_url, proof["happy"])
    blocked = await _read_flow(database_url, proof["blocked"])
    validate_happy(happy, proof["happy"])
    validate_blocked(blocked, proof["blocked"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof-file", type=Path, required=True)
    arguments = parser.parse_args()
    database_url = os.environ.get("NIGHT_VOYAGER_MIGRATION_DATABASE_URL")
    if database_url is None:
        raise SystemExit("NIGHT_VOYAGER_MIGRATION_DATABASE_URL is required")
    proof = load_proof(arguments.proof_file)
    asyncio.run(verify(database_url, proof))
    print(
        "planning revision proof verified: exact happy and blocked lineage retained"
    )


if __name__ == "__main__":
    main()
