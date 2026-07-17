from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncTransaction,
    create_async_engine,
)

from night_voyager.collaboration.hashing import canonical_sha256
from night_voyager.planning.fixtures import validate_planning_fixture

pytestmark = pytest.mark.database

ORG_ID = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR_ID = UUID("20000000-0000-0000-0000-000000000001")
STUDENT_ID = UUID("20000000-0000-0000-0000-000000000002")
PARENT_ID = UUID("20000000-0000-0000-0000-000000000003")
PACK_ID = UUID("50000000-0000-0000-0000-000000000001")

CREATE_THREAD_SQL = text(
    "SELECT * FROM app.create_collaboration_thread("
    ":org,:actor,'advisor',:case,:thread,:request_sha256,:key_sha256)"
)
APPEND_MESSAGE_SQL = text(
    "SELECT * FROM app.append_collaboration_message("
    ":org,:actor,:role,:thread,:message,:body,:content_sha256,"
    ":request_sha256,:key_sha256)"
)
PROPOSE_CANDIDATE_SQL = text(
    "SELECT * FROM app.propose_memory_candidate("
    ":org,:actor,'parent',:message,:candidate,1,'family.risk_tolerance',"
    "CAST(:value AS jsonb),:value_sha256,:request_sha256,:key_sha256)"
)
VERIFY_CANDIDATE_SQL = text(
    "SELECT * FROM app.verify_memory_candidate("
    ":org,:actor,:candidate,1,'confirm',:reason,:verification,:fact,"
    ":request_sha256,:key_sha256)"
)
VERIFY_CANDIDATE_DECISION_SQL = text(
    "SELECT * FROM app.verify_memory_candidate("
    ":org,:actor,:candidate,1,:decision,:reason,:verification,"
    "CAST(:fact AS uuid),:request_sha256,:key_sha256)"
)
CREATE_TASK_SQL = text(
    "SELECT * FROM app.create_agent_task("
    ":org,:actor,:case,:task,'generate_planning_run_v1',1,:pack,1,"
    "'m3a-policy-v1',:request_sha256,:key_sha256)"
)


@dataclass(frozen=True)
class CandidateGraph:
    case_id: UUID
    thread_id: UUID
    message_id: UUID
    candidate_id: UUID
    run_id: UUID | None


def resource_id(prefix: str, suffix: int) -> UUID:
    return UUID(f"{prefix}-0000-0000-0000-{suffix:012d}")


def stable_hash(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


async def set_context(
    connection: AsyncConnection,
    *,
    actor_id: UUID,
    role: str,
) -> None:
    for key, value in (
        ("organization_id", ORG_ID),
        ("actor_id", actor_id),
        ("role", role),
    ):
        await connection.execute(
            text("SELECT set_config(:key,:value,true)"),
            {"key": f"night_voyager.{key}", "value": str(value)},
        )


async def set_migrator_context(connection: AsyncConnection) -> None:
    await connection.execute(
        text("SELECT set_config('night_voyager.organization_id',:org,true)"),
        {"org": str(ORG_ID)},
    )


async def ensure_case(
    migrator: AsyncEngine,
    case_id: UUID,
    *,
    planning_run_id: UUID | None = None,
) -> None:
    fixture_case = validate_planning_fixture().planning_input.case
    async with migrator.begin() as connection:
        await set_migrator_context(connection)
        exists = await connection.scalar(
            text(
                "SELECT EXISTS(SELECT 1 FROM app.student_cases "
                "WHERE organization_id=:org AND id=:case)"
            ),
            {"org": ORG_ID, "case": case_id},
        )
        if exists:
            raise AssertionError(f"concurrency fixture Case already exists: {case_id}")
        await connection.execute(
            text(
                "INSERT INTO app.organizations(id,name,is_synthetic) "
                "VALUES(:org,'Synthetic collaboration concurrency proof',true) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"org": ORG_ID},
        )
        for index, (actor_id, role) in enumerate(
            (
                (ADVISOR_ID, "advisor"),
                (STUDENT_ID, "student"),
                (PARENT_ID, "parent"),
            ),
            start=1,
        ):
            await connection.execute(
                text(
                    "INSERT INTO app.actors(id,organization_id,display_name,is_synthetic) "
                    "VALUES(:actor,:org,:name,true) ON CONFLICT (id) DO NOTHING"
                ),
                {
                    "actor": actor_id,
                    "org": ORG_ID,
                    "name": f"Synthetic concurrency {role}",
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO app.memberships(id,organization_id,actor_id,role) "
                    "VALUES(:membership,:org,:actor,:role) "
                    "ON CONFLICT (organization_id,actor_id,role) DO NOTHING"
                ),
                {
                    "membership": resource_id("36000000", index),
                    "org": ORG_ID,
                    "actor": actor_id,
                    "role": role,
                },
            )
        await connection.execute(
            text(
                "INSERT INTO app.source_packs("
                "organization_id,id,version,schema_version,manifest_sha256) "
                "VALUES(:org,:pack,1,1,repeat('a',64)) ON CONFLICT DO NOTHING"
            ),
            {"org": ORG_ID, "pack": PACK_ID},
        )
        await connection.execute(
            text(
                "SELECT app.publish_case_revision("
                ":org,:case,NULL,1,CAST(:student AS jsonb),CAST(:family AS jsonb))"
            ),
            {
                "org": ORG_ID,
                "case": case_id,
                "student": json.dumps(fixture_case.student.model_dump(mode="json")),
                "family": json.dumps(fixture_case.family.model_dump(mode="json")),
            },
        )
        await connection.execute(
            text("SELECT app.seed_case_participants(:org,:case,:advisor,:student,:parent)"),
            {
                "org": ORG_ID,
                "case": case_id,
                "advisor": ADVISOR_ID,
                "student": STUDENT_ID,
                "parent": PARENT_ID,
            },
        )
        if planning_run_id is not None:
            state = await connection.scalar(
                text("SELECT state FROM app.student_cases WHERE organization_id=:org AND id=:case"),
                {"org": ORG_ID, "case": case_id},
            )
            if state == "intake":
                await connection.execute(
                    text("SELECT app.transition_case(:org,:case,'intake','planning')"),
                    {"org": ORG_ID, "case": case_id},
                )
            await connection.execute(
                text(
                    "INSERT INTO app.planning_runs("
                    "organization_id,id,case_id,case_revision,source_pack_id,"
                    "source_pack_version,policy_version,evidence_projection_sha256,"
                    "state,is_current) VALUES("
                    ":org,:run,:case,1,:pack,1,'m3a-policy-v1',repeat('b',64),"
                    "'synthesizing',true) ON CONFLICT DO NOTHING"
                ),
                {
                    "org": ORG_ID,
                    "run": planning_run_id,
                    "case": case_id,
                    "pack": PACK_ID,
                },
            )


async def create_thread(
    connection: AsyncConnection,
    *,
    case_id: UUID,
    thread_id: UUID,
    request_sha256: str,
    key_sha256: str,
) -> dict[str, object]:
    result = await connection.execute(
        CREATE_THREAD_SQL,
        {
            "org": ORG_ID,
            "actor": ADVISOR_ID,
            "case": case_id,
            "thread": thread_id,
            "request_sha256": request_sha256,
            "key_sha256": key_sha256,
        },
    )
    return dict(result.mappings().one())


async def append_message(
    connection: AsyncConnection,
    *,
    thread_id: UUID,
    message_id: UUID,
    body: str,
    request_sha256: str,
    key_sha256: str,
) -> dict[str, object]:
    result = await connection.execute(
        APPEND_MESSAGE_SQL,
        {
            "org": ORG_ID,
            "actor": PARENT_ID,
            "role": "parent",
            "thread": thread_id,
            "message": message_id,
            "body": body,
            "content_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "request_sha256": request_sha256,
            "key_sha256": key_sha256,
        },
    )
    return dict(result.mappings().one())


async def propose_candidate(
    connection: AsyncConnection,
    *,
    message_id: UUID,
    candidate_id: UUID,
    request_sha256: str,
    key_sha256: str,
) -> dict[str, object]:
    result = await connection.execute(
        PROPOSE_CANDIDATE_SQL,
        {
            "org": ORG_ID,
            "actor": PARENT_ID,
            "message": message_id,
            "candidate": candidate_id,
            "value": json.dumps("high"),
            "value_sha256": canonical_sha256("high"),
            "request_sha256": request_sha256,
            "key_sha256": key_sha256,
        },
    )
    return dict(result.mappings().one())


async def verify_candidate(
    connection: AsyncConnection,
    *,
    candidate_id: UUID,
    verification_id: UUID,
    fact_id: UUID,
    request_sha256: str,
    key_sha256: str,
) -> dict[str, object]:
    result = await connection.execute(
        VERIFY_CANDIDATE_SQL,
        {
            "org": ORG_ID,
            "actor": ADVISOR_ID,
            "candidate": candidate_id,
            "reason": "The participant confirmed this bounded preference.",
            "verification": verification_id,
            "fact": fact_id,
            "request_sha256": request_sha256,
            "key_sha256": key_sha256,
        },
    )
    return dict(result.mappings().one())


async def verify_candidate_decision(
    connection: AsyncConnection,
    *,
    candidate_id: UUID,
    decision: str,
    verification_id: UUID,
    fact_id: UUID | None,
    request_sha256: str,
    key_sha256: str,
) -> dict[str, object]:
    result = await connection.execute(
        VERIFY_CANDIDATE_DECISION_SQL,
        {
            "org": ORG_ID,
            "actor": ADVISOR_ID,
            "candidate": candidate_id,
            "decision": decision,
            "reason": "The advisor resolved this bounded preference.",
            "verification": verification_id,
            "fact": fact_id,
            "request_sha256": request_sha256,
            "key_sha256": key_sha256,
        },
    )
    return dict(result.mappings().one())


async def create_task(
    connection: AsyncConnection,
    *,
    case_id: UUID,
    task_id: UUID,
    request_sha256: str,
    key_sha256: str,
) -> dict[str, object]:
    result = await connection.execute(
        CREATE_TASK_SQL,
        {
            "org": ORG_ID,
            "actor": ADVISOR_ID,
            "case": case_id,
            "task": task_id,
            "pack": PACK_ID,
            "request_sha256": request_sha256,
            "key_sha256": key_sha256,
        },
    )
    return dict(result.mappings().one())


async def prepare_thread(
    migrator: AsyncEngine,
    api: AsyncEngine,
    suffix: int,
    *,
    planning_run_id: UUID | None = None,
) -> tuple[UUID, UUID]:
    case_id = resource_id("40000000", suffix)
    thread_id = resource_id("90000000", suffix)
    await ensure_case(migrator, case_id, planning_run_id=planning_run_id)
    async with api.begin() as connection:
        await set_context(connection, actor_id=ADVISOR_ID, role="advisor")
        await create_thread(
            connection,
            case_id=case_id,
            thread_id=thread_id,
            request_sha256=stable_hash(f"thread-request-{suffix}"),
            key_sha256=stable_hash(f"thread-key-{suffix}"),
        )
    return case_id, thread_id


async def prepare_source_message(
    migrator: AsyncEngine,
    api: AsyncEngine,
    suffix: int,
    *,
    planning_run_id: UUID | None = None,
) -> tuple[UUID, UUID, UUID]:
    case_id, thread_id = await prepare_thread(
        migrator,
        api,
        suffix,
        planning_run_id=planning_run_id,
    )
    message_id = resource_id("91000000", suffix)
    async with api.begin() as connection:
        await set_context(connection, actor_id=PARENT_ID, role="parent")
        await append_message(
            connection,
            thread_id=thread_id,
            message_id=message_id,
            body=f"Synthetic bounded preference {suffix}.",
            request_sha256=stable_hash(f"message-request-{suffix}"),
            key_sha256=stable_hash(f"message-key-{suffix}"),
        )
    return case_id, thread_id, message_id


async def prepare_candidate(
    migrator: AsyncEngine,
    api: AsyncEngine,
    suffix: int,
    *,
    planning: bool = False,
) -> CandidateGraph:
    run_id = resource_id("70000000", suffix) if planning else None
    case_id, thread_id, message_id = await prepare_source_message(
        migrator,
        api,
        suffix,
        planning_run_id=run_id,
    )
    candidate_id = resource_id("92000000", suffix)
    async with api.begin() as connection:
        await set_context(connection, actor_id=PARENT_ID, role="parent")
        await propose_candidate(
            connection,
            message_id=message_id,
            candidate_id=candidate_id,
            request_sha256=stable_hash(f"candidate-request-{suffix}"),
            key_sha256=stable_hash(f"candidate-key-{suffix}"),
        )
    return CandidateGraph(
        case_id=case_id,
        thread_id=thread_id,
        message_id=message_id,
        candidate_id=candidate_id,
        run_id=run_id,
    )


async def backend_pid(connection: AsyncConnection) -> int:
    return int(cast(int, await connection.scalar(text("SELECT pg_backend_pid()"))))


async def wait_until_blocked(
    inspector: AsyncConnection,
    *,
    blocked_pid: int,
    blocker_pid: int,
    pending: asyncio.Task[object],
) -> None:
    async with asyncio.timeout(10):
        while True:
            if pending.done():
                pending.result()
                raise AssertionError("the contender completed without waiting for the lock")
            blockers = cast(
                list[int] | None,
                await inspector.scalar(
                    text("SELECT pg_blocking_pids(:blocked_pid)"),
                    {"blocked_pid": blocked_pid},
                ),
            )
            if blockers is not None and blocker_pid in blockers:
                return


async def rollback_if_active(*transactions: AsyncTransaction) -> None:
    for transaction in transactions:
        if transaction.is_active:
            await transaction.rollback()


async def cancel_if_pending(task: asyncio.Task[Any] | None) -> None:
    if task is not None and not task.done():
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def ledger_summary(
    connection: AsyncConnection,
    *,
    operation: str,
    first_key: str,
    second_key: str,
) -> RowMapping:
    return (
        (
            await connection.execute(
                text(
                    "SELECT count(*) AS record_count,count(DISTINCT response_id) AS response_count "
                    "FROM app.idempotency_records WHERE organization_id=:org "
                    "AND actor_id IN (:advisor,:parent) AND operation=:operation "
                    "AND key_sha256 IN (:first_key,:second_key)"
                ),
                {
                    "org": ORG_ID,
                    "advisor": ADVISOR_ID,
                    "parent": PARENT_ID,
                    "operation": operation,
                    "first_key": first_key,
                    "second_key": second_key,
                },
            )
        )
        .mappings()
        .one()
    )


@pytest.mark.parametrize("same_key", (True, False), ids=("same-key", "different-key"))
@pytest.mark.asyncio
async def test_thread_create_idempotency_races_serialize_to_one_thread(
    same_key: bool,
) -> None:
    suffix = 1411 if same_key else 1412
    case_id = resource_id("40000000", suffix)
    first_thread = resource_id("90000000", suffix * 10 + 1)
    second_thread = resource_id("90000000", suffix * 10 + 2)
    request_hash = stable_hash(f"thread-race-request-{suffix}")
    first_key = stable_hash(f"thread-race-key-{suffix}-a")
    second_key = first_key if same_key else stable_hash(f"thread-race-key-{suffix}-b")
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    second_call: asyncio.Task[dict[str, object]] | None = None
    try:
        await ensure_case(migrator, case_id)
        async with api.connect() as first, api.connect() as second, migrator.connect() as inspector:
            first_transaction = await first.begin()
            second_transaction = await second.begin()
            try:
                await set_context(first, actor_id=ADVISOR_ID, role="advisor")
                await set_context(second, actor_id=ADVISOR_ID, role="advisor")
                first_pid = await backend_pid(first)
                second_pid = await backend_pid(second)
                first_result = await create_thread(
                    first,
                    case_id=case_id,
                    thread_id=first_thread,
                    request_sha256=request_hash,
                    key_sha256=first_key,
                )
                second_call = asyncio.create_task(
                    create_thread(
                        second,
                        case_id=case_id,
                        thread_id=second_thread,
                        request_sha256=request_hash,
                        key_sha256=second_key,
                    )
                )
                await wait_until_blocked(
                    inspector,
                    blocked_pid=second_pid,
                    blocker_pid=first_pid,
                    pending=second_call,
                )
                await first_transaction.commit()
                second_result = await second_call
                await second_transaction.commit()
            finally:
                await cancel_if_pending(second_call)
                await rollback_if_active(first_transaction, second_transaction)
        assert first_result["replayed"] is False
        assert second_result["replayed"] is same_key
        assert first_result["thread_id"] == first_thread
        assert second_result["thread_id"] == first_thread
        async with migrator.begin() as connection:
            await set_migrator_context(connection)
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.collaboration_threads "
                        "WHERE organization_id=:org AND case_id=:case"
                    ),
                    {"org": ORG_ID, "case": case_id},
                )
                == 1
            )
            ledger = await ledger_summary(
                connection,
                operation="collaboration_thread_create",
                first_key=first_key,
                second_key=second_key,
            )
            assert ledger["record_count"] == (1 if same_key else 2)
            assert ledger["response_count"] == 1
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.parametrize("decision", ("confirm", "reject"))
@pytest.mark.asyncio
async def test_worker_finalize_waits_for_case_before_verifier_current_run(
    decision: str,
) -> None:
    suffix = 1452 if decision == "confirm" else 1453
    task_id = resource_id("80000000", suffix)
    result_run_id = resource_id("70000001", suffix)
    verification_id = resource_id("93000000", suffix)
    fact_id = resource_id("94000000", suffix) if decision == "confirm" else None
    worker_name = f"deadlock-worker-{decision}"
    verification_request_sha256 = stable_hash(f"deadlock-verification-request-{decision}")
    verification_key_sha256 = stable_hash(f"deadlock-verification-key-{decision}")
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    worker = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    verification_call: asyncio.Task[dict[str, object]] | None = None
    finalize_call: asyncio.Task[str] | None = None
    try:
        graph = await prepare_candidate(migrator, api, suffix, planning=True)
        assert graph.run_id is not None
        async with migrator.begin() as connection:
            await set_migrator_context(connection)
            await connection.execute(
                text(
                    "UPDATE app.planning_runs SET state='blocked',"
                    "reason_code='missing_evidence',output_sha256=repeat('d',64) "
                    "WHERE organization_id=:org AND id=:run"
                ),
                {"org": ORG_ID, "run": graph.run_id},
            )
        async with api.begin() as connection:
            await set_context(connection, actor_id=ADVISOR_ID, role="advisor")
            await create_task(
                connection,
                case_id=graph.case_id,
                task_id=task_id,
                request_sha256=stable_hash(f"deadlock-task-request-{decision}"),
                key_sha256=stable_hash(f"deadlock-task-key-{decision}"),
            )
        async with migrator.begin() as connection:
            await set_migrator_context(connection)
            await connection.execute(
                text(
                    "UPDATE internal.agent_task_dispatch SET available_at='-infinity' "
                    "WHERE organization_id=:org AND task_id=:task"
                ),
                {"org": ORG_ID, "task": task_id},
            )
        async with worker.begin() as connection:
            claim = (
                (
                    await connection.execute(
                        text("SELECT * FROM app.claim_agent_task(:worker)"),
                        {"worker": worker_name},
                    )
                )
                .mappings()
                .one()
            )
            assert claim.task_id == task_id
            assert claim.lease_generation == 1
            await connection.execute(
                text("SELECT app.start_agent_task(:org,:task,:worker,1,repeat('a',64))"),
                {"org": ORG_ID, "task": task_id, "worker": worker_name},
            )

        async with (
            migrator.connect() as candidate_blocker,
            api.connect() as verifier,
            worker.connect() as finalizer,
            migrator.connect() as inspector,
        ):
            blocker_transaction = await candidate_blocker.begin()
            verifier_transaction = await verifier.begin()
            finalizer_transaction = await finalizer.begin()
            try:
                await set_migrator_context(candidate_blocker)
                await set_migrator_context(inspector)
                await set_context(verifier, actor_id=ADVISOR_ID, role="advisor")
                await finalizer.execute(
                    text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                    {"org": str(ORG_ID)},
                )
                await verifier.execute(text("SET LOCAL statement_timeout = '10s'"))
                await finalizer.execute(text("SET LOCAL statement_timeout = '10s'"))
                blocker_pid = await backend_pid(candidate_blocker)
                verifier_pid = await backend_pid(verifier)
                finalizer_pid = await backend_pid(finalizer)
                locked_candidate = await candidate_blocker.scalar(
                    text(
                        "SELECT id FROM app.memory_candidates "
                        "WHERE organization_id=:org AND id=:candidate FOR UPDATE"
                    ),
                    {"org": ORG_ID, "candidate": graph.candidate_id},
                )
                assert locked_candidate == graph.candidate_id

                verification_call = asyncio.create_task(
                    verify_candidate_decision(
                        verifier,
                        candidate_id=graph.candidate_id,
                        decision=decision,
                        verification_id=verification_id,
                        fact_id=fact_id,
                        request_sha256=verification_request_sha256,
                        key_sha256=verification_key_sha256,
                    )
                )
                await wait_until_blocked(
                    inspector,
                    blocked_pid=verifier_pid,
                    blocker_pid=blocker_pid,
                    pending=verification_call,
                )

                async def finalize() -> str:
                    result = await finalizer.scalar(
                        text(
                            "SELECT app.finalize_agent_task_result("
                            ":org,:task,:worker,1,:run,repeat('e',64),'blocked',"
                            "'missing_evidence',repeat('f',64),"
                            '\'{"routes":[],"costs":[],"rankings":[]}\'::jsonb,'
                            ":supersedes)"
                        ),
                        {
                            "org": ORG_ID,
                            "task": task_id,
                            "worker": worker_name,
                            "run": result_run_id,
                            "supersedes": graph.run_id,
                        },
                    )
                    return cast(str, result)

                finalize_call = asyncio.create_task(finalize())
                await wait_until_blocked(
                    inspector,
                    blocked_pid=finalizer_pid,
                    blocker_pid=verifier_pid,
                    pending=finalize_call,
                )

                unlocked_run = await inspector.scalar(
                    text(
                        "SELECT id FROM app.planning_runs "
                        "WHERE organization_id=:org AND id=:run FOR UPDATE NOWAIT"
                    ),
                    {"org": ORG_ID, "run": graph.run_id},
                )
                assert unlocked_run == graph.run_id
                await inspector.rollback()
                await blocker_transaction.rollback()

                if decision == "confirm":
                    with pytest.raises(DBAPIError) as raised:
                        async with asyncio.timeout(10):
                            await verification_call
                    sqlstate = getattr(raised.value.orig, "sqlstate", None)
                    assert sqlstate != "40P01"
                    assert sqlstate == "NV014"
                    await verifier_transaction.rollback()
                else:
                    try:
                        async with asyncio.timeout(10):
                            verification = await verification_call
                    except DBAPIError as error:
                        assert getattr(error.orig, "sqlstate", None) != "40P01"
                        raise
                    assert verification["decision"] == "reject"
                    assert verification["result_fact_id"] is None
                    assert verification["result_revision"] is None
                    await verifier_transaction.commit()

                try:
                    async with asyncio.timeout(10):
                        finalized_state = await finalize_call
                except DBAPIError as error:
                    assert getattr(error.orig, "sqlstate", None) != "40P01"
                    raise
                assert finalized_state == "blocked"
                await finalizer_transaction.commit()
            finally:
                await cancel_if_pending(verification_call)
                await cancel_if_pending(finalize_call)
                await rollback_if_active(
                    blocker_transaction,
                    verifier_transaction,
                    finalizer_transaction,
                )

        async with migrator.begin() as connection:
            await set_migrator_context(connection)
            state = (
                (
                    await connection.execute(
                        text(
                            "SELECT current_revision,"
                            "(SELECT count(*) FROM app.memory_candidate_verifications "
                            " WHERE organization_id=:org AND candidate_id=:candidate) "
                            " AS verification_count,"
                            "(SELECT count(*) FROM app.confirmed_facts "
                            " WHERE organization_id=:org AND case_id=:case) AS fact_count,"
                            "(SELECT count(*) FROM app.case_revision_confirmed_fact_refs "
                            " WHERE organization_id=:org AND case_id=:case) AS ref_count,"
                            "(SELECT count(*) FROM app.idempotency_records "
                            " WHERE organization_id=:org AND actor_id=:actor "
                            " AND operation='memory_candidate_verify' "
                            " AND key_sha256=:key_sha256) AS ledger_count,"
                            "(SELECT count(*) FROM app.audit_events "
                            " WHERE organization_id=:org AND case_id=:case "
                            " AND subject_id=:verification) AS audit_count "
                            "FROM app.student_cases "
                            "WHERE organization_id=:org AND id=:case"
                        ),
                        {
                            "org": ORG_ID,
                            "actor": ADVISOR_ID,
                            "case": graph.case_id,
                            "candidate": graph.candidate_id,
                            "key_sha256": verification_key_sha256,
                            "verification": verification_id,
                        },
                    )
                )
                .mappings()
                .one()
            )
            assert state.current_revision == 1
            assert state.verification_count == (0 if decision == "confirm" else 1)
            assert state.fact_count == 0
            assert state.ref_count == 0
            assert state.ledger_count == (0 if decision == "confirm" else 1)
            assert state.audit_count == (0 if decision == "confirm" else 1)
            if decision == "reject":
                assert (
                    await connection.scalar(
                        text(
                            "SELECT decision FROM app.memory_candidate_verifications "
                            "WHERE organization_id=:org AND candidate_id=:candidate"
                        ),
                        {"org": ORG_ID, "candidate": graph.candidate_id},
                    )
                    == "reject"
                )
            task = (
                (
                    await connection.execute(
                        text(
                            "SELECT state,result_planning_run_id,lease_owner "
                            "FROM app.agent_tasks WHERE organization_id=:org AND id=:task"
                        ),
                        {"org": ORG_ID, "task": task_id},
                    )
                )
                .mappings()
                .one()
            )
            assert dict(task) == {
                "state": "blocked",
                "result_planning_run_id": result_run_id,
                "lease_owner": None,
            }
            run_currentness = (
                (
                    await connection.execute(
                        text(
                            "SELECT id,is_current FROM app.planning_runs "
                            "WHERE organization_id=:org AND id IN (:old_run,:new_run) "
                            "ORDER BY id"
                        ),
                        {
                            "org": ORG_ID,
                            "old_run": graph.run_id,
                            "new_run": result_run_id,
                        },
                    )
                )
                .mappings()
                .all()
            )
            assert {row.id: row.is_current for row in run_currentness} == {
                graph.run_id: False,
                result_run_id: True,
            }
    finally:
        await api.dispose()
        await worker.dispose()
        await migrator.dispose()


@pytest.mark.parametrize("same_key", (True, False), ids=("same-key", "different-key"))
@pytest.mark.asyncio
async def test_message_append_idempotency_races_preserve_gap_free_sequence(
    same_key: bool,
) -> None:
    suffix = 1413 if same_key else 1414
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    first_message = resource_id("91000000", suffix * 10 + 1)
    second_message = resource_id("91000000", suffix * 10 + 2)
    body = "A bounded family preference for the concurrency proof."
    request_hash = stable_hash(f"message-race-request-{suffix}")
    first_key = stable_hash(f"message-race-key-{suffix}-a")
    second_key = first_key if same_key else stable_hash(f"message-race-key-{suffix}-b")
    second_call: asyncio.Task[dict[str, object]] | None = None
    try:
        _, thread_id = await prepare_thread(migrator, api, suffix)
        async with api.connect() as first, api.connect() as second, migrator.connect() as inspector:
            first_transaction = await first.begin()
            second_transaction = await second.begin()
            try:
                await set_context(first, actor_id=PARENT_ID, role="parent")
                await set_context(second, actor_id=PARENT_ID, role="parent")
                first_pid = await backend_pid(first)
                second_pid = await backend_pid(second)
                first_result = await append_message(
                    first,
                    thread_id=thread_id,
                    message_id=first_message,
                    body=body,
                    request_sha256=request_hash,
                    key_sha256=first_key,
                )
                second_call = asyncio.create_task(
                    append_message(
                        second,
                        thread_id=thread_id,
                        message_id=second_message,
                        body=body,
                        request_sha256=request_hash,
                        key_sha256=second_key,
                    )
                )
                await wait_until_blocked(
                    inspector,
                    blocked_pid=second_pid,
                    blocker_pid=first_pid,
                    pending=second_call,
                )
                await first_transaction.commit()
                second_result = await second_call
                await second_transaction.commit()
            finally:
                await cancel_if_pending(second_call)
                await rollback_if_active(first_transaction, second_transaction)
        assert first_result["replayed"] is False
        assert second_result["replayed"] is same_key
        assert first_result["message_event_id"] == first_message
        assert second_result["message_event_id"] == (first_message if same_key else second_message)
        expected_sequences = [1] if same_key else [1, 2]
        async with migrator.begin() as connection:
            await set_migrator_context(connection)
            sequences = list(
                (
                    await connection.execute(
                        text(
                            "SELECT sequence_no FROM app.message_events "
                            "WHERE organization_id=:org AND thread_id=:thread "
                            "ORDER BY sequence_no"
                        ),
                        {"org": ORG_ID, "thread": thread_id},
                    )
                ).scalars()
            )
            assert sequences == expected_sequences
            ledger = await ledger_summary(
                connection,
                operation="collaboration_message_append",
                first_key=first_key,
                second_key=second_key,
            )
            assert ledger["record_count"] == (1 if same_key else 2)
            assert ledger["response_count"] == (1 if same_key else 2)
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.parametrize("same_key", (True, False), ids=("same-key", "different-key"))
@pytest.mark.asyncio
async def test_candidate_proposal_idempotency_races_keep_one_candidate_per_message(
    same_key: bool,
) -> None:
    suffix = 1415 if same_key else 1416
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    first_candidate = resource_id("92000000", suffix * 10 + 1)
    second_candidate = resource_id("92000000", suffix * 10 + 2)
    request_hash = stable_hash(f"candidate-race-request-{suffix}")
    first_key = stable_hash(f"candidate-race-key-{suffix}-a")
    second_key = first_key if same_key else stable_hash(f"candidate-race-key-{suffix}-b")
    second_call: asyncio.Task[dict[str, object]] | None = None
    try:
        _, _, message_id = await prepare_source_message(migrator, api, suffix)
        async with api.connect() as first, api.connect() as second, migrator.connect() as inspector:
            first_transaction = await first.begin()
            second_transaction = await second.begin()
            try:
                await set_context(first, actor_id=PARENT_ID, role="parent")
                await set_context(second, actor_id=PARENT_ID, role="parent")
                first_pid = await backend_pid(first)
                second_pid = await backend_pid(second)
                first_result = await propose_candidate(
                    first,
                    message_id=message_id,
                    candidate_id=first_candidate,
                    request_sha256=request_hash,
                    key_sha256=first_key,
                )
                second_call = asyncio.create_task(
                    propose_candidate(
                        second,
                        message_id=message_id,
                        candidate_id=second_candidate,
                        request_sha256=request_hash,
                        key_sha256=second_key,
                    )
                )
                await wait_until_blocked(
                    inspector,
                    blocked_pid=second_pid,
                    blocker_pid=first_pid,
                    pending=second_call,
                )
                await first_transaction.commit()
                second_result = await second_call
                await second_transaction.commit()
            finally:
                await cancel_if_pending(second_call)
                await rollback_if_active(first_transaction, second_transaction)
        assert first_result["replayed"] is False
        assert second_result["replayed"] is same_key
        async with migrator.begin() as connection:
            await set_migrator_context(connection)
            candidates = (
                (
                    await connection.execute(
                        text(
                            "SELECT id FROM app.memory_candidates "
                            "WHERE organization_id=:org AND message_event_id=:message"
                        ),
                        {"org": ORG_ID, "message": message_id},
                    )
                )
                .scalars()
                .all()
            )
            assert candidates == [first_candidate]
            ledger = await ledger_summary(
                connection,
                operation="memory_candidate_propose",
                first_key=first_key,
                second_key=second_key,
            )
            assert ledger["record_count"] == (1 if same_key else 2)
            assert ledger["response_count"] == 1
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_eight_simultaneous_appends_have_one_contiguous_sequence() -> None:
    suffix = 1420
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(
        os.environ["NIGHT_VOYAGER_API_DATABASE_URL"],
        pool_size=8,
        max_overflow=0,
    )
    try:
        _, thread_id = await prepare_thread(migrator, api, suffix)
        barrier = asyncio.Barrier(8)

        async def append(index: int) -> dict[str, object]:
            async with api.begin() as connection:
                await set_context(connection, actor_id=PARENT_ID, role="parent")
                await barrier.wait()
                body = f"Concurrent bounded message {index}."
                return await append_message(
                    connection,
                    thread_id=thread_id,
                    message_id=resource_id("91000000", suffix * 100 + index),
                    body=body,
                    request_sha256=stable_hash(f"eight-message-request-{index}"),
                    key_sha256=stable_hash(f"eight-message-key-{index}"),
                )

        results = await asyncio.wait_for(
            asyncio.gather(*(append(index) for index in range(1, 9))),
            timeout=20,
        )
        assert sorted(cast(int, result["sequence_no"]) for result in results) == list(range(1, 9))
        assert len({result["message_event_id"] for result in results}) == 8
        async with migrator.begin() as connection:
            await set_migrator_context(connection)
            sequences = list(
                (
                    await connection.execute(
                        text(
                            "SELECT sequence_no FROM app.message_events "
                            "WHERE organization_id=:org AND thread_id=:thread "
                            "ORDER BY sequence_no"
                        ),
                        {"org": ORG_ID, "thread": thread_id},
                    )
                ).scalars()
            )
            assert sequences == list(range(1, 9))
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_two_first_confirmations_serialize_to_one_terminal_result() -> None:
    suffix = 1430
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    second_call: asyncio.Task[dict[str, object]] | None = None
    try:
        graph = await prepare_candidate(migrator, api, suffix)
        async with api.connect() as first, api.connect() as second, migrator.connect() as inspector:
            first_transaction = await first.begin()
            second_transaction = await second.begin()
            try:
                await set_context(first, actor_id=ADVISOR_ID, role="advisor")
                await set_context(second, actor_id=ADVISOR_ID, role="advisor")
                first_pid = await backend_pid(first)
                second_pid = await backend_pid(second)
                first_verification = resource_id("93000000", suffix * 10 + 1)
                first_fact = resource_id("94000000", suffix * 10 + 1)
                first_result = await verify_candidate(
                    first,
                    candidate_id=graph.candidate_id,
                    verification_id=first_verification,
                    fact_id=first_fact,
                    request_sha256=stable_hash("first-confirmation-request"),
                    key_sha256=stable_hash("first-confirmation-key"),
                )
                second_call = asyncio.create_task(
                    verify_candidate(
                        second,
                        candidate_id=graph.candidate_id,
                        verification_id=resource_id("93000000", suffix * 10 + 2),
                        fact_id=resource_id("94000000", suffix * 10 + 2),
                        request_sha256=stable_hash("second-confirmation-request"),
                        key_sha256=stable_hash("second-confirmation-key"),
                    )
                )
                await wait_until_blocked(
                    inspector,
                    blocked_pid=second_pid,
                    blocker_pid=first_pid,
                    pending=second_call,
                )
                await first_transaction.commit()
                with pytest.raises(DBAPIError) as raised:
                    await second_call
                assert getattr(raised.value.orig, "sqlstate", None) == "NV012"
                await second_transaction.rollback()
            finally:
                await cancel_if_pending(second_call)
                await rollback_if_active(first_transaction, second_transaction)
        assert first_result["verification_id"] == first_verification
        assert first_result["result_fact_id"] == first_fact
        assert first_result["result_revision"] == 2
        async with migrator.begin() as connection:
            await set_migrator_context(connection)
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.memory_candidate_verifications "
                        "WHERE organization_id=:org AND candidate_id=:candidate"
                    ),
                    {"org": ORG_ID, "candidate": graph.candidate_id},
                )
                == 1
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.confirmed_facts "
                        "WHERE organization_id=:org AND case_id=:case"
                    ),
                    {"org": ORG_ID, "case": graph.case_id},
                )
                == 1
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT current_revision FROM app.student_cases "
                        "WHERE organization_id=:org AND id=:case"
                    ),
                    {"org": ORG_ID, "case": graph.case_id},
                )
                == 2
            )
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_proposal_waits_for_confirmation_then_fails_stale() -> None:
    suffix = 1440
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    proposal_call: asyncio.Task[dict[str, object]] | None = None
    try:
        graph = await prepare_candidate(migrator, api, suffix)
        second_message = resource_id("91000000", suffix * 10 + 2)
        async with api.begin() as connection:
            await set_context(connection, actor_id=PARENT_ID, role="parent")
            await append_message(
                connection,
                thread_id=graph.thread_id,
                message_id=second_message,
                body="A second bounded preference remains pinned to revision one.",
                request_sha256=stable_hash("proposal-lock-message-request"),
                key_sha256=stable_hash("proposal-lock-message-key"),
            )
        stale_candidate = resource_id("92000000", suffix * 10 + 2)
        stale_key = stable_hash("proposal-lock-candidate-key")
        async with (
            api.connect() as confirmer,
            api.connect() as proposer,
            migrator.connect() as inspector,
        ):
            confirm_transaction = await confirmer.begin()
            proposal_transaction = await proposer.begin()
            try:
                await set_context(confirmer, actor_id=ADVISOR_ID, role="advisor")
                await set_context(proposer, actor_id=PARENT_ID, role="parent")
                confirmer_pid = await backend_pid(confirmer)
                proposer_pid = await backend_pid(proposer)
                await verify_candidate(
                    confirmer,
                    candidate_id=graph.candidate_id,
                    verification_id=resource_id("93000000", suffix),
                    fact_id=resource_id("94000000", suffix),
                    request_sha256=stable_hash("proposal-lock-confirm-request"),
                    key_sha256=stable_hash("proposal-lock-confirm-key"),
                )
                proposal_call = asyncio.create_task(
                    propose_candidate(
                        proposer,
                        message_id=second_message,
                        candidate_id=stale_candidate,
                        request_sha256=stable_hash("proposal-lock-candidate-request"),
                        key_sha256=stale_key,
                    )
                )
                await wait_until_blocked(
                    inspector,
                    blocked_pid=proposer_pid,
                    blocker_pid=confirmer_pid,
                    pending=proposal_call,
                )
                await confirm_transaction.commit()
                with pytest.raises(DBAPIError) as raised:
                    await proposal_call
                assert getattr(raised.value.orig, "sqlstate", None) == "NV003"
                await proposal_transaction.rollback()
            finally:
                await cancel_if_pending(proposal_call)
                await rollback_if_active(confirm_transaction, proposal_transaction)
        async with migrator.begin() as connection:
            await set_migrator_context(connection)
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.memory_candidates "
                        "WHERE organization_id=:org AND id=:candidate"
                    ),
                    {"org": ORG_ID, "candidate": stale_candidate},
                )
                == 0
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.idempotency_records "
                        "WHERE organization_id=:org AND actor_id=:actor "
                        "AND operation='memory_candidate_propose' AND key_sha256=:key"
                    ),
                    {"org": ORG_ID, "actor": PARENT_ID, "key": stale_key},
                )
                == 0
            )
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_task_creation_first_blocks_confirmation_after_case_lock_wait() -> None:
    suffix = 1450
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    confirmation_call: asyncio.Task[dict[str, object]] | None = None
    try:
        graph = await prepare_candidate(migrator, api, suffix, planning=True)
        task_id = resource_id("80000000", suffix)
        async with (
            api.connect() as task_connection,
            api.connect() as confirmation_connection,
            migrator.connect() as inspector,
        ):
            task_transaction = await task_connection.begin()
            confirmation_transaction = await confirmation_connection.begin()
            try:
                await set_context(task_connection, actor_id=ADVISOR_ID, role="advisor")
                await set_context(
                    confirmation_connection,
                    actor_id=ADVISOR_ID,
                    role="advisor",
                )
                task_pid = await backend_pid(task_connection)
                confirmation_pid = await backend_pid(confirmation_connection)
                await create_task(
                    task_connection,
                    case_id=graph.case_id,
                    task_id=task_id,
                    request_sha256=stable_hash("task-first-request"),
                    key_sha256=stable_hash("task-first-key"),
                )
                confirmation_call = asyncio.create_task(
                    verify_candidate(
                        confirmation_connection,
                        candidate_id=graph.candidate_id,
                        verification_id=resource_id("93000000", suffix),
                        fact_id=resource_id("94000000", suffix),
                        request_sha256=stable_hash("task-first-confirm-request"),
                        key_sha256=stable_hash("task-first-confirm-key"),
                    )
                )
                await wait_until_blocked(
                    inspector,
                    blocked_pid=confirmation_pid,
                    blocker_pid=task_pid,
                    pending=confirmation_call,
                )
                await task_transaction.commit()
                with pytest.raises(DBAPIError) as raised:
                    await confirmation_call
                assert getattr(raised.value.orig, "sqlstate", None) == "NV014"
                await confirmation_transaction.rollback()
            finally:
                await cancel_if_pending(confirmation_call)
                await rollback_if_active(task_transaction, confirmation_transaction)
        async with migrator.begin() as connection:
            await set_migrator_context(connection)
            assert (
                await connection.scalar(
                    text(
                        "SELECT current_revision FROM app.student_cases "
                        "WHERE organization_id=:org AND id=:case"
                    ),
                    {"org": ORG_ID, "case": graph.case_id},
                )
                == 1
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.memory_candidate_verifications "
                        "WHERE organization_id=:org AND candidate_id=:candidate"
                    ),
                    {"org": ORG_ID, "candidate": graph.candidate_id},
                )
                == 0
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.agent_tasks "
                        "WHERE organization_id=:org AND id=:task AND state='queued'"
                    ),
                    {"org": ORG_ID, "task": task_id},
                )
                == 1
            )
        async with api.begin() as connection:
            await set_context(connection, actor_id=ADVISOR_ID, role="advisor")
            cancelled = (
                await connection.execute(
                    text(
                        "SELECT * FROM app.cancel_agent_task("
                        ":org,:actor,:task,1,:request_sha256,:key_sha256)"
                    ),
                    {
                        "org": ORG_ID,
                        "actor": ADVISOR_ID,
                        "task": task_id,
                        "request_sha256": stable_hash("task-first-cancel-request"),
                        "key_sha256": stable_hash("task-first-cancel-key"),
                    },
                )
            ).mappings().one()
            assert cancelled.state == "cancelled"
        async with migrator.begin() as connection:
            await set_migrator_context(connection)
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM internal.agent_task_dispatch "
                        "WHERE organization_id=:org AND task_id=:task"
                    ),
                    {"org": ORG_ID, "task": task_id},
                )
                == 0
            )
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_confirmation_first_makes_waiting_old_revision_task_stale() -> None:
    suffix = 1451
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    task_call: asyncio.Task[dict[str, object]] | None = None
    task_key = stable_hash("confirm-first-task-key")
    task_id = resource_id("80000000", suffix)
    try:
        graph = await prepare_candidate(migrator, api, suffix, planning=True)
        assert graph.run_id is not None
        async with (
            api.connect() as confirmation_connection,
            api.connect() as task_connection,
            migrator.connect() as inspector,
        ):
            confirmation_transaction = await confirmation_connection.begin()
            task_transaction = await task_connection.begin()
            try:
                await set_context(
                    confirmation_connection,
                    actor_id=ADVISOR_ID,
                    role="advisor",
                )
                await set_context(task_connection, actor_id=ADVISOR_ID, role="advisor")
                confirmation_pid = await backend_pid(confirmation_connection)
                task_pid = await backend_pid(task_connection)
                confirmation = await verify_candidate(
                    confirmation_connection,
                    candidate_id=graph.candidate_id,
                    verification_id=resource_id("93000000", suffix),
                    fact_id=resource_id("94000000", suffix),
                    request_sha256=stable_hash("confirm-first-request"),
                    key_sha256=stable_hash("confirm-first-key"),
                )
                task_call = asyncio.create_task(
                    create_task(
                        task_connection,
                        case_id=graph.case_id,
                        task_id=task_id,
                        request_sha256=stable_hash("confirm-first-task-request"),
                        key_sha256=task_key,
                    )
                )
                await wait_until_blocked(
                    inspector,
                    blocked_pid=task_pid,
                    blocker_pid=confirmation_pid,
                    pending=task_call,
                )
                await confirmation_transaction.commit()
                with pytest.raises(DBAPIError) as raised:
                    await task_call
                assert getattr(raised.value.orig, "sqlstate", None) == "NV003"
                await task_transaction.rollback()
            finally:
                await cancel_if_pending(task_call)
                await rollback_if_active(confirmation_transaction, task_transaction)
        assert confirmation["result_revision"] == 2
        async with migrator.begin() as connection:
            await set_migrator_context(connection)
            assert (
                await connection.scalar(
                    text(
                        "SELECT current_revision FROM app.student_cases "
                        "WHERE organization_id=:org AND id=:case"
                    ),
                    {"org": ORG_ID, "case": graph.case_id},
                )
                == 2
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT is_current FROM app.planning_runs "
                        "WHERE organization_id=:org AND id=:run"
                    ),
                    {"org": ORG_ID, "run": graph.run_id},
                )
                is False
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.agent_tasks "
                        "WHERE organization_id=:org AND id=:task"
                    ),
                    {"org": ORG_ID, "task": task_id},
                )
                == 0
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.idempotency_records "
                        "WHERE organization_id=:org AND actor_id=:actor "
                        "AND operation='agent_task_create' AND key_sha256=:key"
                    ),
                    {"org": ORG_ID, "actor": ADVISOR_ID, "key": task_key},
                )
                == 0
            )
    finally:
        await api.dispose()
        await migrator.dispose()
