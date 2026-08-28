#!/usr/bin/env python3
"""Verify the connected same-Case browser proof against PostgreSQL."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

DEMO_ORG = UUID("10000000-0000-0000-0000-000000000001")
DEMO_ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
PROOF_KEYS = {
    "schema_version",
    "locale",
    "case_id",
    "case_revision",
    "task_id",
    "decision_id",
    "decision_receipt_id",
    "timeline_plan_id",
    "execution_id",
    "lost_ack_receipt_id",
    "blocked_attestation_id",
    "reassessment_request_id",
    "accepted_receipt_ids",
    "checkpoint_ids",
}


def _canonical_uuid(value: object) -> bool:
    return isinstance(value, str) and str(UUID(value)) == value


def load_proof(path: Path) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise ValueError
        raw: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError
        proof = cast(dict[str, object], raw)
        if set(proof) != PROOF_KEYS:
            raise ValueError
        if proof["schema_version"] != 1 or proof["locale"] not in ("zh-CN", "en"):
            raise ValueError
        if proof["case_revision"] != 2:
            raise ValueError
        uuid_fields = (
            "case_id",
            "task_id",
            "decision_id",
            "decision_receipt_id",
            "timeline_plan_id",
            "execution_id",
            "lost_ack_receipt_id",
            "blocked_attestation_id",
            "reassessment_request_id",
        )
        if not all(_canonical_uuid(proof[field]) for field in uuid_fields):
            raise ValueError
        receipts_value = proof["accepted_receipt_ids"]
        checkpoints_value = proof["checkpoint_ids"]
        if not isinstance(receipts_value, list) or not isinstance(checkpoints_value, list):
            raise ValueError
        receipts = cast(list[object], receipts_value)
        checkpoints = cast(list[object], checkpoints_value)
        if len(receipts) != 4 or len(set(receipts)) != 4:
            raise ValueError
        if len(checkpoints) != 4 or len(set(checkpoints)) != 4:
            raise ValueError
        if not all(_canonical_uuid(item) for item in (*receipts, *checkpoints)):
            raise ValueError
        if proof["lost_ack_receipt_id"] not in receipts:
            raise ValueError
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        raise SystemExit("invalid connected plan execution proof") from error
    return cast(dict[str, Any], proof)


def validate_authority_row(row: dict[str, Any], proof: dict[str, Any]) -> None:
    valid = all(
        (
            row.get("case_id") == proof["case_id"],
            row.get("case_state") == "plan_ready",
            row.get("current_revision") == proof["case_revision"],
            row.get("revision") == proof["case_revision"],
            row.get("brief_case_id") == proof["case_id"],
            row.get("brief_revision") == proof["case_revision"],
            row.get("decision_id") == proof["decision_id"],
            row.get("decision_case_id") == proof["case_id"],
            row.get("decision_brief_id") == row.get("brief_id"),
            row.get("decision_run_id") == row.get("brief_run_id"),
            row.get("decision_receipt_id") == proof["decision_receipt_id"],
            row.get("timeline_plan_id") == proof["timeline_plan_id"],
            row.get("timeline_decision_id") == proof["decision_id"],
            row.get("execution_id") == proof["execution_id"],
            row.get("execution_case_id") == proof["case_id"],
            row.get("execution_case_revision") == proof["case_revision"],
            row.get("execution_decision_id") == proof["decision_id"],
            row.get("execution_decision_receipt_id")
            == proof["decision_receipt_id"],
            row.get("execution_timeline_plan_id") == proof["timeline_plan_id"],
            row.get("execution_state") == "reassessment_required",
        )
    )
    if not valid:
        raise SystemExit("connected plan execution authority mismatch")


async def read_authority(
    connection: AsyncConnection, proof: dict[str, Any]
) -> dict[str, Any]:
    for name, value in (
        ("night_voyager.organization_id", str(DEMO_ORG)),
        ("night_voyager.actor_id", str(DEMO_ADVISOR)),
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
              c.id::text AS case_id,
              c.state AS case_state,
              c.current_revision,
              r.revision,
              b.id::text AS brief_id,
              b.case_id::text AS brief_case_id,
              b.case_revision AS brief_revision,
              b.planning_run_id::text AS brief_run_id,
              d.id::text AS decision_id,
              d.case_id::text AS decision_case_id,
              d.decision_brief_id::text AS decision_brief_id,
              d.planning_run_id::text AS decision_run_id,
              d.receipt_id::text AS decision_receipt_id,
              tp.id::text AS timeline_plan_id,
              tp.family_decision_id::text AS timeline_decision_id,
              e.id::text AS execution_id,
              e.case_id::text AS execution_case_id,
              e.case_revision AS execution_case_revision,
              e.family_decision_id::text AS execution_decision_id,
              e.decision_receipt_id::text AS execution_decision_receipt_id,
              e.timeline_plan_id::text AS execution_timeline_plan_id,
              e.state AS execution_state
            FROM app.student_cases AS c
            JOIN app.student_case_revisions AS r
              ON r.organization_id=c.organization_id
             AND r.case_id=c.id
             AND r.revision=c.current_revision
            JOIN app.decision_briefs AS b
              ON b.organization_id=c.organization_id
             AND b.case_id=c.id
             AND b.case_revision=c.current_revision
            JOIN app.family_decisions AS d
              ON d.organization_id=b.organization_id
             AND d.case_id=b.case_id
             AND d.decision_brief_id=b.id
             AND d.brief_version=b.brief_version
             AND d.planning_run_id=b.planning_run_id
            JOIN app.timeline_plans AS tp
              ON tp.organization_id=d.organization_id
             AND tp.family_decision_id=d.id
            JOIN app.timeline_executions AS e
              ON e.organization_id=tp.organization_id
             AND e.timeline_plan_id=tp.id
            JOIN app.student_case_participants AS p
              ON p.organization_id=c.organization_id
             AND p.case_id=c.id
             AND p.actor_id=:advisor
             AND p.role='advisor'
            WHERE c.organization_id=:org
              AND c.id=CAST(:case_id AS uuid)
              AND c.current_revision=:revision
              AND c.state='plan_ready'
            """
        ),
        {
            "org": DEMO_ORG,
            "advisor": DEMO_ADVISOR,
            "case_id": proof["case_id"],
            "revision": proof["case_revision"],
        },
    )
    rows = result.mappings().all()
    if len(rows) != 1:
        raise SystemExit(
            f"connected plan execution authority mismatch (rows={len(rows)})"
        )
    return dict(rows[0])


async def verify_database(connection: AsyncConnection, proof: dict[str, Any]) -> None:
    execution_id = UUID(proof["execution_id"])
    case_id = UUID(proof["case_id"])
    checkpoints = [UUID(value) for value in proof["checkpoint_ids"]]
    receipts = [UUID(value) for value in proof["accepted_receipt_ids"]]

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
        raise SystemExit("connected plan execution checkpoint mismatch")

    actual_receipts = set(
        (
            await connection.scalars(
                text(
                    "SELECT receipt_id FROM app.timeline_mutation_receipts "
                    "WHERE organization_id=:org AND execution_id=:execution "
                    "ORDER BY created_at,receipt_id"
                ),
                {"org": DEMO_ORG, "execution": execution_id},
            )
        ).all()
    )
    if actual_receipts != set(receipts):
        raise SystemExit("connected plan execution receipt mismatch")

    counts = await connection.execute(
        text(
            "SELECT "
            "(SELECT count(*) FROM app.timeline_checkpoint_attestations "
            "WHERE organization_id=:org AND execution_id=:execution)=2 AS attestations,"
            "(SELECT count(*) FROM app.timeline_checkpoint_verifications "
            "WHERE organization_id=:org AND execution_id=:execution)=0 AS verifications,"
            "(SELECT count(*) FROM app.timeline_reassessment_requests "
            "WHERE organization_id=:org AND execution_id=:execution)=1 AS reassessments,"
            "(SELECT count(*) FROM app.timeline_mutation_receipts "
            "WHERE organization_id=:org AND execution_id=:execution)=4 AS receipts,"
            "(SELECT count(*) FROM app.idempotency_records i "
            "JOIN app.timeline_mutation_receipts m "
            "ON m.organization_id=i.organization_id AND m.receipt_id=i.response_id "
            "WHERE i.organization_id=:org AND m.execution_id=:execution)=4 AS idempotency,"
            "(SELECT count(*) FROM app.family_decisions "
            "WHERE organization_id=:org AND case_id=:case_id)=1 AS decisions,"
            "(SELECT count(*) FROM app.timeline_plans tp "
            "JOIN app.family_decisions d ON d.organization_id=tp.organization_id "
            "AND d.id=tp.family_decision_id "
            "WHERE tp.organization_id=:org AND d.case_id=:case_id)=1 AS timelines"
        ),
        {"org": DEMO_ORG, "case_id": case_id, "execution": execution_id},
    )
    counts_row = counts.mappings().one()
    if not all(counts_row.values()):
        raise SystemExit("connected plan execution count mismatch")

    blocked = (
        await connection.execute(
            text(
                "SELECT attestation_id FROM app.timeline_checkpoint_attestations "
                "WHERE organization_id=:org AND execution_id=:execution "
                "AND attestation_kind='blocked'"
            ),
            {"org": DEMO_ORG, "execution": execution_id},
        )
    ).mappings().all()
    if len(blocked) != 1 or str(blocked[0]["attestation_id"]) != proof["blocked_attestation_id"]:
        raise SystemExit("connected plan execution blocker mismatch")

    reassessment = (
        await connection.execute(
            text(
                "SELECT reassessment_id::text,execution_id::text,checkpoint_id::text,"
                "advisor_actor_id::text,trigger,trigger_reference_id::text,"
                "predecessor_case_id::text,predecessor_case_revision,"
                "predecessor_decision_id::text,predecessor_decision_receipt_id::text,"
                "predecessor_timeline_plan_id::text,predecessor_execution_id::text,"
                "predecessor_checkpoint_id::text,owner_role,successor_status "
                "FROM app.timeline_reassessment_requests "
                "WHERE organization_id=:org AND execution_id=:execution"
            ),
            {"org": DEMO_ORG, "execution": execution_id},
        )
    ).mappings().all()
    if len(reassessment) != 1:
        raise SystemExit("connected plan execution reassessment mismatch")
    request = dict(reassessment[0])
    expected = {
        "reassessment_id": proof["reassessment_request_id"],
        "execution_id": proof["execution_id"],
        "checkpoint_id": proof["checkpoint_ids"][0],
        "advisor_actor_id": str(DEMO_ADVISOR),
        "trigger": "blocked_attestation",
        "trigger_reference_id": proof["blocked_attestation_id"],
        "predecessor_case_id": proof["case_id"],
        "predecessor_case_revision": proof["case_revision"],
        "predecessor_decision_id": proof["decision_id"],
        "predecessor_decision_receipt_id": proof["decision_receipt_id"],
        "predecessor_timeline_plan_id": proof["timeline_plan_id"],
        "predecessor_execution_id": proof["execution_id"],
        "predecessor_checkpoint_id": proof["checkpoint_ids"][0],
        "owner_role": "advisor",
        "successor_status": "pending_future_authorization",
    }
    if request != expected:
        raise SystemExit("connected plan execution reassessment identity mismatch")


async def verify(path: Path, database_url: str) -> None:
    proof = load_proof(path)
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            row = await read_authority(connection, proof)
            validate_authority_row(row, proof)
            await verify_database(connection, proof)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--proof-file", type=Path, required=True)
    args = parser.parse_args()
    database_url = os.environ.get("NIGHT_VOYAGER_MIGRATION_DATABASE_URL")
    if not database_url:
        raise SystemExit("NIGHT_VOYAGER_MIGRATION_DATABASE_URL is required")
    asyncio.run(verify(args.proof_file, database_url))
    print("compose-proof: connected same-Case plan execution database proof passed")


if __name__ == "__main__":
    main()
