#!/usr/bin/env python3
"""Verify the isolated governed fact-to-plan browser proof against PostgreSQL."""

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

PROOF_KEYS = {"schema_version", "case_id", "case_revision", "task_id"}
DEMO_ORGANIZATION_ID = "10000000-0000-0000-0000-000000000001"
DEMO_ADVISOR_ID = "20000000-0000-0000-0000-000000000001"


class BrowserProof(TypedDict):
    schema_version: int
    case_id: str
    case_revision: int
    task_id: str


def load_proof(path: Path) -> BrowserProof:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError
        proof = cast(dict[str, object], raw)
        if set(proof) != PROOF_KEYS:
            raise ValueError
        if proof["schema_version"] != 1 or proof["case_revision"] != 2:
            raise ValueError
        for field in ("case_id", "task_id"):
            value = proof[field]
            if not isinstance(value, str) or str(UUID(value)) != value:
                raise ValueError
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise SystemExit("invalid fact-to-plan proof file") from exc
    return cast(BrowserProof, proof)


def validate_authority_row(row: dict[str, Any], proof: BrowserProof) -> None:
    fact_id = row.get("fact_id")
    task_id = proof["task_id"]
    case_id = proof["case_id"]
    revision = proof["case_revision"]
    run_id = row.get("planning_run_id")
    review_id = row.get("review_id")
    brief_id = row.get("brief_id")
    decision_id = row.get("decision_id")
    task_pin = (
        row.get("skill_definition_id"),
        row.get("skill_version_id"),
        row.get("skill_activation_event_id"),
        row.get("skill_activation_sequence"),
        row.get("runtime_binding_sha256"),
    )
    execution_pin = (
        row.get("execution_definition_id"),
        row.get("execution_version_id"),
        row.get("execution_activation_id"),
        row.get("execution_activation_sequence"),
        row.get("execution_runtime_sha256"),
    )
    valid = all(
        (
            row.get("case_id") == case_id,
            row.get("case_state") == "plan_ready",
            row.get("current_revision") == revision,
            row.get("candidate_revision") == revision - 1,
            row.get("verification_decision") == "confirm",
            row.get("result_fact_id") == fact_id,
            row.get("result_revision") == revision,
            row.get("fact_key") == "family.budget",
            row.get("fact_version") == 1,
            row.get("revision_fact_id") == fact_id,
            row.get("task_id") == task_id,
            row.get("task_case_id") == case_id,
            row.get("operation") == "generate_planning_run_v1",
            row.get("task_revision") == revision,
            row.get("task_state") == "waiting_review",
            all(task_pin),
            task_pin == execution_pin,
            row.get("execution_status") == "succeeded",
            row.get("execution_run_id") == run_id,
            row.get("planning_case_id") == case_id,
            row.get("run_revision") == revision,
            row.get("run_state") == "review_required",
            row.get("review_case_id") == case_id,
            row.get("review_action") == "approve_for_consultation",
            row.get("review_run_id") == run_id,
            row.get("review_revision") == revision,
            row.get("brief_case_id") == case_id,
            row.get("brief_run_id") == run_id,
            row.get("brief_review_id") == review_id,
            row.get("brief_revision") == revision,
            row.get("decision_case_id") == case_id,
            row.get("decision_brief_id") == brief_id,
            row.get("decision_run_id") == run_id,
            row.get("receipt_id") is not None,
            row.get("timeline_decision_id") == decision_id,
            row.get("queued_events") == 1,
            row.get("waiting_review_events") == 1,
            isinstance(row.get("event_count"), int) and row["event_count"] >= 4,
            row.get("dispatch_remaining") == 0,
            row.get("version_runtime_sha256") == row.get("runtime_binding_sha256"),
            row.get("activation_version_id") == row.get("skill_version_id"),
            row.get("activation_sequence") == row.get("skill_activation_sequence"),
        )
    )
    if not valid:
        diagnostics = ",".join(
            (
                f"case_state={row.get('case_state')}",
                f"revision={row.get('current_revision')}",
                f"candidate_revision={row.get('candidate_revision')}",
                f"fact_link={row.get('result_fact_id') == fact_id == row.get('revision_fact_id')}",
                f"task_state={row.get('task_state')}",
                f"task_revision={row.get('task_revision')}",
                f"pin_match={task_pin == execution_pin}",
                f"execution_status={row.get('execution_status')}",
                f"run_state={row.get('run_state')}",
                f"review_action={row.get('review_action')}",
                f"brief_link={row.get('brief_review_id') == review_id}",
                f"decision_link={row.get('decision_brief_id') == brief_id}",
                f"timeline_link={row.get('timeline_decision_id') == decision_id}",
                f"events={row.get('event_count')}",
                f"dispatch={row.get('dispatch_remaining')}",
            )
        )
        raise SystemExit(f"fact-to-plan database authority mismatch ({diagnostics})")


async def read_authority(database_url: str, proof: BrowserProof) -> dict[str, Any]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            for name, value in (
                ("night_voyager.organization_id", DEMO_ORGANIZATION_ID),
                ("night_voyager.actor_id", DEMO_ADVISOR_ID),
                ("night_voyager.role", "advisor"),
            ):
                await connection.execute(
                    text("SELECT set_config(:name,:value,false)"),
                    {"name": name, "value": value},
                )
            result = await connection.execute(
                text(
                    """
                    SELECT
                      c.id::text AS case_id, c.state AS case_state,
                      c.current_revision,
                      mc.id::text AS candidate_id, mc.case_revision AS candidate_revision,
                      mv.decision AS verification_decision,
                      mv.result_fact_id::text AS result_fact_id,
                      mv.result_revision,
                      cf.id::text AS fact_id, cf.fact_key, cf.fact_version,
                      cr.confirmed_fact_id::text AS revision_fact_id,
                      t.id::text AS task_id, t.case_id::text AS task_case_id,
                      t.operation, t.case_revision AS task_revision, t.state AS task_state,
                      t.skill_definition_id::text AS skill_definition_id,
                      t.skill_version_id::text AS skill_version_id,
                      t.skill_activation_event_id::text AS skill_activation_event_id,
                      t.skill_activation_sequence,
                      t.runtime_binding_sha256,
                      ex.status AS execution_status,
                      ex.result_planning_run_id::text AS execution_run_id,
                      ex.skill_definition_id::text AS execution_definition_id,
                      ex.skill_version_id::text AS execution_version_id,
                      ex.skill_activation_event_id::text AS execution_activation_id,
                      ex.skill_activation_sequence AS execution_activation_sequence,
                      ex.runtime_binding_sha256 AS execution_runtime_sha256,
                      pr.id::text AS planning_run_id,
                      pr.case_id::text AS planning_case_id,
                      pr.case_revision AS run_revision, pr.state AS run_state,
                      ar.id::text AS review_id, ar.case_id::text AS review_case_id,
                      ar.action AS review_action,
                      ar.planning_run_id::text AS review_run_id,
                      ar.case_revision AS review_revision,
                      db.id::text AS brief_id, db.case_id::text AS brief_case_id,
                      db.planning_run_id::text AS brief_run_id,
                      db.advisor_review_id::text AS brief_review_id,
                      db.case_revision AS brief_revision,
                      fd.id::text AS decision_id, fd.case_id::text AS decision_case_id,
                      fd.decision_brief_id::text AS decision_brief_id,
                      fd.planning_run_id::text AS decision_run_id,
                      fd.receipt_id::text AS receipt_id,
                      tp.family_decision_id::text AS timeline_decision_id,
                      (SELECT count(*)::integer FROM app.agent_task_events e
                        WHERE e.organization_id=t.organization_id AND e.task_id=t.id
                          AND e.event_code='queued') AS queued_events,
                      (SELECT count(*)::integer FROM app.agent_task_events e
                        WHERE e.organization_id=t.organization_id AND e.task_id=t.id
                          AND e.event_code='waiting_review') AS waiting_review_events,
                      (SELECT count(*)::integer FROM app.agent_task_events e
                        WHERE e.organization_id=t.organization_id AND e.task_id=t.id)
                        AS event_count,
                      (SELECT count(*)::integer FROM internal.agent_task_dispatch d
                        WHERE d.organization_id=t.organization_id AND d.task_id=t.id)
                        AS dispatch_remaining,
                      sv.runtime_binding_sha256 AS version_runtime_sha256,
                      sa.activated_version_id::text AS activation_version_id,
                      sa.activation_sequence
                    FROM app.student_cases c
                    JOIN app.memory_candidates mc
                      ON mc.organization_id=c.organization_id AND mc.case_id=c.id
                    JOIN app.memory_candidate_verifications mv
                      ON mv.organization_id=mc.organization_id AND mv.candidate_id=mc.id
                    JOIN app.confirmed_facts cf
                      ON cf.organization_id=mv.organization_id AND cf.id=mv.result_fact_id
                    JOIN app.case_revision_confirmed_fact_refs cr
                      ON cr.organization_id=c.organization_id AND cr.case_id=c.id
                     AND cr.case_revision=c.current_revision
                     AND cr.confirmed_fact_id=cf.id
                    JOIN app.agent_tasks t
                      ON t.organization_id=c.organization_id AND t.case_id=c.id
                     AND t.case_revision=c.current_revision
                    JOIN app.agent_executions ex
                      ON ex.organization_id=t.organization_id AND ex.task_id=t.id
                     AND ex.status='succeeded'
                    JOIN app.planning_runs pr
                      ON pr.organization_id=t.organization_id
                     AND pr.id=t.result_planning_run_id
                    JOIN app.advisor_reviews ar
                      ON ar.organization_id=pr.organization_id
                     AND ar.planning_run_id=pr.id
                    JOIN app.decision_briefs db
                      ON db.organization_id=ar.organization_id
                     AND db.advisor_review_id=ar.id
                    JOIN app.family_decisions fd
                      ON fd.organization_id=db.organization_id
                     AND fd.decision_brief_id=db.id
                    JOIN app.timeline_plans tp
                      ON tp.organization_id=fd.organization_id
                     AND tp.family_decision_id=fd.id
                    JOIN app.skill_versions sv
                      ON sv.organization_id=t.organization_id
                     AND sv.definition_id=t.skill_definition_id
                     AND sv.id=t.skill_version_id
                    JOIN app.skill_activation_events sa
                      ON sa.organization_id=t.organization_id
                     AND sa.definition_id=t.skill_definition_id
                     AND sa.id=t.skill_activation_event_id
                    WHERE c.id=CAST(:case_id AS uuid)
                      AND t.id=CAST(:task_id AS uuid)
                    """
                ),
                {"case_id": proof["case_id"], "task_id": proof["task_id"]},
            )
            rows = result.mappings().all()
            if len(rows) != 1:
                raise SystemExit(f"fact-to-plan database authority mismatch (rows={len(rows)})")
            return dict(rows[0])
    finally:
        await engine.dispose()


async def verify(path: Path, database_url: str) -> int:
    proof = load_proof(path)
    row = await read_authority(database_url, proof)
    validate_authority_row(row, proof)
    return int(row["event_count"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof-file", type=Path, required=True)
    args = parser.parse_args()
    database_url = os.environ.get("NIGHT_VOYAGER_MIGRATION_DATABASE_URL")
    if not database_url:
        raise SystemExit("NIGHT_VOYAGER_MIGRATION_DATABASE_URL is required")
    event_count = asyncio.run(verify(args.proof_file, database_url))
    print(
        "compose-proof: governed fact-to-plan database authority passed "
        f"revision=2 events={event_count}"
    )


if __name__ == "__main__":
    main()
