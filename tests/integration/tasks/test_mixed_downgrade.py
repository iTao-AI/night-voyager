# ruff: noqa: E501
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from tests.integration.dra.test_postgres_mixed_snapshot import approved_pack

pytestmark = pytest.mark.database
ROOT = Path(__file__).resolve().parents[3]
ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
PACK = UUID("50000000-0000-0000-0000-000000000001")


async def set_context(connection: AsyncConnection) -> None:
    for name, value in (
        ("night_voyager.organization_id", str(ORG)),
        ("night_voyager.actor_id", str(ADVISOR)),
        ("night_voyager.role", "advisor"),
    ):
        await connection.execute(
            text("SELECT set_config(:name,:value,true)"),
            {"name": name, "value": value},
        )


async def create_mixed_task(
    connection: AsyncConnection,
    *,
    case_id: UUID,
    task_id: UUID,
    version: int,
) -> None:
    await set_context(connection)
    await connection.execute(
        text(
            "SELECT * FROM app.create_agent_task(:org,:actor,:case,:task,"
            "'generate_governed_mixed_planning_run_v1',1,:pack,:version,"
            "'m3a-policy-v1',:request_hash,:key_hash)"
        ),
        {
            "org": ORG,
            "actor": ADVISOR,
            "case": case_id,
            "task": task_id,
            "pack": PACK,
            "version": version,
            "request_hash": hashlib.sha256(str(task_id).encode()).hexdigest(),
            "key_hash": hashlib.sha256(f"key:{task_id}".encode()).hexdigest(),
        },
    )


async def assert_collaboration_authority_is_empty() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            authority_rows = await connection.scalar(
                text(
                    "SELECT "
                    "(SELECT count(*) FROM app.collaboration_threads)+"
                    "(SELECT count(*) FROM app.message_events)+"
                    "(SELECT count(*) FROM app.memory_candidates)+"
                    "(SELECT count(*) FROM app.memory_candidate_verifications)+"
                    "(SELECT count(*) FROM app.confirmed_facts)+"
                    "(SELECT count(*) FROM app.case_revision_confirmed_fact_refs)"
                )
            )
            ledger_rows = await connection.scalar(
                text(
                    "SELECT "
                    "(SELECT count(*) FROM app.idempotency_records WHERE operation IN ("
                    "'collaboration_thread_create','collaboration_message_append',"
                    "'memory_candidate_propose','memory_candidate_verify'))+"
                    "(SELECT count(*) FROM app.audit_events WHERE event_type IN ("
                    "'memory_candidate_confirmed','memory_candidate_rejected'))"
                )
            )
            assert authority_rows == 0
            assert ledger_rows == 0
    finally:
        await engine.dispose()


def alembic(*args: str) -> None:
    subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=ROOT,
        check=True,
        env=os.environ.copy(),
    )


@pytest.mark.asyncio
async def test_downgrade_freezes_nonterminal_mixed_tasks_and_preserves_terminal_audit() -> None:
    await assert_collaboration_authority_is_empty()
    # 0008 owns versioned Skill pins and must refuse pinned history. Prove the
    # pre-existing 0006 mixed-task downgrade only after a clean 0008 -> 0007
    # downgrade has restored the exact legacy task signature.
    alembic("downgrade", "0007")
    running_case, running_version = await approved_pack(1401)
    queued_case, queued_version = await approved_pack(1402)
    terminal_case, terminal_version = await approved_pack(1403)
    running_task = UUID("80000000-0000-0000-0000-000000001401")
    queued_task = UUID("80000000-0000-0000-0000-000000001402")
    terminal_task = UUID("80000000-0000-0000-0000-000000001403")

    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    worker = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    try:
        async with api.begin() as connection:
            await create_mixed_task(
                connection,
                case_id=running_case,
                task_id=running_task,
                version=running_version,
            )
        async with worker.begin() as connection:
            claimed = (
                await connection.execute(
                    text("SELECT * FROM app.claim_agent_task('downgrade-running')")
                )
            ).mappings().one()
            assert claimed.task_id == running_task
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            await connection.execute(
                text(
                    "SELECT app.start_agent_task(:org,:task,'downgrade-running',1,repeat('a',64))"
                ),
                {"org": ORG, "task": running_task},
            )
        async with api.begin() as connection:
            await create_mixed_task(
                connection,
                case_id=queued_case,
                task_id=queued_task,
                version=queued_version,
            )
        async with api.begin() as connection:
            await create_mixed_task(
                connection,
                case_id=terminal_case,
                task_id=terminal_task,
                version=terminal_version,
            )
            cancelled = (
                await connection.execute(
                    text(
                        "SELECT * FROM app.cancel_agent_task(:org,:actor,:task,1,"
                        ":request_hash,:key_hash)"
                    ),
                    {
                        "org": ORG,
                        "actor": ADVISOR,
                        "task": terminal_task,
                        "request_hash": hashlib.sha256(
                            f"cancel:{terminal_task}".encode()
                        ).hexdigest(),
                        "key_hash": hashlib.sha256(
                            f"cancel-key:{terminal_task}".encode()
                        ).hexdigest(),
                    },
                )
            ).mappings().one()
            assert cancelled.state == "cancelled"
    finally:
        await api.dispose()
        await worker.dispose()

    try:
        alembic("downgrade", "0005")
        inspector = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
        downgraded_worker = create_async_engine(
            os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"]
        )
        try:
            async with inspector.begin() as connection:
                await connection.execute(
                    text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                    {"org": str(ORG)},
                )
                rows = (
                    await connection.execute(
                        text(
                            "SELECT id,state,lease_owner,lease_expires_at,terminal_code "
                            "FROM app.agent_tasks WHERE organization_id=:org AND id IN "
                            "(:running,:queued,:terminal) ORDER BY id"
                        ),
                        {
                            "org": ORG,
                            "running": running_task,
                            "queued": queued_task,
                            "terminal": terminal_task,
                        },
                    )
                ).mappings().all()
                assert [dict(row) for row in rows] == [
                    {
                        "id": running_task,
                        "state": "cancelled",
                        "lease_owner": None,
                        "lease_expires_at": None,
                        "terminal_code": "migration_downgrade",
                    },
                    {
                        "id": queued_task,
                        "state": "cancelled",
                        "lease_owner": None,
                        "lease_expires_at": None,
                        "terminal_code": "migration_downgrade",
                    },
                    {
                        "id": terminal_task,
                        "state": "cancelled",
                        "lease_owner": None,
                        "lease_expires_at": None,
                        "terminal_code": "cancelled",
                    },
                ]
                assert await connection.scalar(
                    text(
                        "SELECT count(*) FROM internal.agent_task_dispatch "
                        "WHERE organization_id=:org AND task_id IN (:running,:queued)"
                    ),
                    {"org": ORG, "running": running_task, "queued": queued_task},
                ) == 0
                execution = (
                    await connection.execute(
                        text(
                            "SELECT adapter_id,adapter_version,status,public_code "
                            "FROM app.agent_executions WHERE organization_id=:org "
                            "AND task_id=:task"
                        ),
                        {"org": ORG, "task": running_task},
                    )
                ).mappings().one()
                assert dict(execution) == {
                    "adapter_id": "governed_mixed_planning",
                    "adapter_version": "dra-mixed-v1",
                    "status": "cancelled",
                    "public_code": "migration_downgrade",
                }
                assert await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.agent_task_events "
                        "WHERE organization_id=:org AND task_id=:terminal"
                    ),
                    {"org": ORG, "terminal": terminal_task},
                ) == 2

            async with downgraded_worker.begin() as connection:
                assert (
                    await connection.execute(
                        text("SELECT * FROM app.claim_agent_task('downgrade-old-worker')")
                    )
                ).mappings().all() == []

            async with inspector.connect() as connection:
                with pytest.raises(DBAPIError) as rejected:
                    async with connection.begin():
                        await connection.execute(
                            text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                            {"org": str(ORG)},
                        )
                        await connection.execute(
                            text(
                                "INSERT INTO app.agent_tasks(organization_id,id,case_id,operation,"
                                "case_revision,source_pack_id,source_pack_version,policy_version,"
                                "request_sha256,created_by_actor_id,state) VALUES(:org,:task,:case,"
                                "'generate_governed_mixed_planning_run_v1',1,:pack,:version,"
                                "'m3a-policy-v1',repeat('e',64),:actor,'queued')"
                            ),
                            {
                                "org": ORG,
                                "task": UUID("80000000-0000-0000-0000-000000001499"),
                                "case": queued_case,
                                "pack": PACK,
                                "version": queued_version,
                                "actor": ADVISOR,
                            },
                        )
                assert getattr(rejected.value.orig, "sqlstate", None) == "23514"
        finally:
            await inspector.dispose()
            await downgraded_worker.dispose()
    finally:
        alembic("upgrade", "head")

    verifier = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    try:
        async with verifier.begin() as connection:
            assert await connection.scalar(
                text(
                    "SELECT has_function_privilege(current_user,"
                    "'app.load_governed_mixed_planning_snapshot(uuid,uuid,integer,uuid,integer,text)',"
                    "'EXECUTE')"
                )
            ) is True
    finally:
        await verifier.dispose()
