"""Bounded synthetic acceptance producer; never mutates a Task into terminal state."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from night_voyager.adapters.protocols import AdapterFailure, AdapterFailureCode
from night_voyager.config import Settings
from night_voyager.tasks.policy import classify_adapter_outcome

ORG = UUID("10000000-0000-0000-0000-000000000001")


async def run(task: UUID, code: str, proof: Path, action: str) -> None:
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    settings = Settings()
    if not settings.demo_mode or settings.environment not in {"development", "test"}:
        raise RuntimeError("acceptance producer requires an explicit synthetic demo environment")
    worker = (
        create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
        if action == "produce"
        else None
    )
    try:
        async with migrator.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            target = (
                (
                    await connection.execute(
                        text(
                            "SELECT case_id,case_revision FROM app.agent_tasks "
                            "WHERE organization_id=:org AND id=:task"
                        ),
                        {"org": ORG, "task": task},
                    )
                )
                .mappings()
                .one()
            )
            allowed_cases = {
                UUID("49000000-0000-0000-0000-000000000001"),
                UUID("49000000-0000-0000-0000-000000000002"),
            }
            if target["case_id"] not in allowed_cases or target["case_revision"] != 2:
                raise RuntimeError("acceptance producer only targets the canonical revision Cases")
        if action == "unknown-negative":
            # Explicit controlled negative only; never counted as a real producer.
            async with migrator.begin() as connection:
                await connection.execute(
                    text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                    {"org": str(ORG)},
                )
                changed = (
                    (
                        await connection.execute(
                            text(
                                "UPDATE app.agent_tasks SET terminal_code='provider_unknown' WHERE "
                                "organization_id=:org AND id=:task AND state='failed' AND "
                                "terminal_code='invalid_schema' RETURNING id,case_id,case_revision,"
                                "state,terminal_code"
                            ),
                            {"org": ORG, "task": task},
                        )
                    )
                    .mappings()
                    .one()
                )
                if changed["id"] != task or changed["terminal_code"] != "provider_unknown":
                    raise RuntimeError(
                        "controlled unknown negative did not change its exact source"
                    )
            proof.with_name("unknown-negative-native.json").write_text(
                json.dumps(
                    {"schema_version": 1, "controlled_negative": True, **dict(changed)},
                    default=str,
                    sort_keys=True,
                )
            )
            print(
                "controlled-unknown-negative: exact provider_unknown source; "
                "no success producer claim"
            )
            return
        if action == "verify-source":
            original = json.loads(proof.read_text())["snapshot"]
            async with migrator.begin() as connection:
                await connection.execute(
                    text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                    {"org": str(ORG)},
                )
                row = (
                    (
                        await connection.execute(
                            text(
                                "SELECT to_jsonb(t) AS task, (SELECT jsonb_agg(to_jsonb(e) "
                                "ORDER BY "
                                "event_sequence) FROM app.agent_task_events e WHERE "
                                "e.organization_id=t.organization_id AND e.task_id=t.id) AS "
                                "events, "
                                "(SELECT jsonb_agg(to_jsonb(x) ORDER BY attempt_no) FROM "
                                "app.agent_executions x WHERE "
                                "x.organization_id=t.organization_id AND "
                                "x.task_id=t.id) AS executions FROM app.agent_tasks t WHERE "
                                "organization_id=:org AND id=:task"
                            ),
                            {"org": ORG, "task": task},
                        )
                    )
                    .mappings()
                    .one()
                )
                if dict(row) != original:
                    raise RuntimeError("recovery changed the old Task/events/executions")
            print(
                "native-source-diagnostics: exact snapshot equality "
                "after fresh result and family receipt"
            )
            return
        async with migrator.begin() as connection:
            # Test scheduling control only: the actual task transitions use worker authority.
            await connection.execute(
                text(
                    "UPDATE internal.agent_task_dispatch SET "
                    "available_at=clock_timestamp()+interval '1 day' WHERE task_id<>:task"
                ),
                {"task": task},
            )
        assert worker is not None
        async with worker.begin() as connection:
            claim = (
                (
                    await connection.execute(
                        text("SELECT * FROM app.claim_agent_task('customer-recovery-proof')")
                    )
                )
                .mappings()
                .one()
            )
            if claim["task_id"] != task:
                raise RuntimeError("proof did not claim its exact queued task")
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            params = {"org": ORG, "task": task, "generation": claim["lease_generation"]}
            await connection.execute(
                text(
                    "SELECT "
                    "app.start_agent_task(:org,:task,'customer-recovery-proof',:generation,:hash)"
                ),
                {**params, "hash": "a" * 64},
            )
            decision = classify_adapter_outcome(
                AdapterFailure(code=AdapterFailureCode(code)), attempt_no=1
            )
            await connection.execute(
                text(
                    "SELECT "
                    "app.fail_agent_task(:org,:task,'customer-recovery-proof',:generation,:code,:retryable,false)"
                ),
                {**params, "code": code, "retryable": decision.retryable},
            )
        async with migrator.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            row = (
                (
                    await connection.execute(
                        text(
                            "SELECT to_jsonb(t) AS task, (SELECT jsonb_agg(to_jsonb(e) ORDER BY "
                            "event_sequence) FROM app.agent_task_events e WHERE "
                            "e.organization_id=t.organization_id AND e.task_id=t.id) AS events, "
                            "(SELECT jsonb_agg(to_jsonb(x) ORDER BY attempt_no) FROM "
                            "app.agent_executions x WHERE x.organization_id=t.organization_id AND "
                            "x.task_id=t.id) AS executions FROM app.agent_tasks t WHERE "
                            "organization_id=:org AND id=:task"
                        ),
                        {"org": ORG, "task": task},
                    )
                )
                .mappings()
                .one()
            )
            snapshot = dict(row)
        encoded = json.dumps(snapshot, sort_keys=True, default=str).encode()
        proof.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "producer": "classifier/claim/start/fail",
                    "source_task_id": str(task),
                    "failure_code": code,
                    "state": snapshot["task"]["state"],
                    "diagnostics_sha256": hashlib.sha256(encoded).hexdigest(),
                    "snapshot": snapshot,
                },
                default=str,
            )
            + "\n"
        )
        print(f"native-terminal-producer code={code} state={snapshot['task']['state']} task={task}")
    finally:
        await migrator.dispose()
        if worker is not None:
            await worker.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=UUID, required=True)
    parser.add_argument(
        "--code", choices=["deadline_exceeded", "invalid_schema"], default="deadline_exceeded"
    )
    parser.add_argument(
        "--action", choices=["produce", "verify-source", "unknown-negative"], default="produce"
    )
    parser.add_argument("--proof", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.task, args.code, args.proof, args.action))


if __name__ == "__main__":
    main()
