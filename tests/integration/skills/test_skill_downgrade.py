from __future__ import annotations

import asyncio
import os
import subprocess
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
CASE = UUID("40000000-0000-0000-0000-000000000002")
PACK = UUID("50000000-0000-0000-0000-000000000001")
LEGACY_TASK = UUID("49000000-0000-0000-0000-000000000008")
PR_A_WAITING_REVIEW_TASK = UUID("48000000-0000-0000-0000-000000000002")
OLD_CREATE_SIGNATURE = (
    "app.create_agent_task(uuid,uuid,uuid,uuid,text,integer,uuid,integer,text,text,text)"
)
NEW_CREATE_SIGNATURE = (
    "app.create_agent_task(uuid,uuid,uuid,uuid,text,integer,uuid,integer,text,jsonb,text,text)"
)


def _alembic(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = {**os.environ, "PYTHONUNBUFFERED": "1"}
    return subprocess.run(
        ["uv", "run", "alembic", *arguments],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )


def _alembic_result(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = {**os.environ, "PYTHONUNBUFFERED": "1"}
    return subprocess.run(
        ["uv", "run", "alembic", *arguments],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def _seed_demo() -> None:
    subprocess.run(
        [
            "uv",
            "run",
            "--no-editable",
            "python",
            "scripts/seed_demo.py",
            "--without-collaboration",
        ],
        check=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )


async def _replace_seed_content_digest(digest: str) -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": "10000000-0000-0000-0000-000000000001"},
            )
            await connection.execute(
                text("ALTER TABLE app.skill_versions DISABLE TRIGGER skill_versions_immutable")
            )
            await connection.execute(
                text(
                    "UPDATE app.skill_versions SET content_sha256=:digest,"
                    "manifest_projection=jsonb_set(manifest_projection,"
                    "'{content_sha256}',to_jsonb(CAST(:digest AS text))) "
                    "WHERE skill_key='study-destination-compare' "
                    "AND semantic_version='1.0.0'"
                ),
                {"digest": digest},
            )
            await connection.execute(
                text("ALTER TABLE app.skill_versions ENABLE TRIGGER skill_versions_immutable")
            )
    finally:
        await engine.dispose()


async def _assert_exact_0007_boundary_and_create_legacy_task() -> None:
    inspector = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with inspector.begin() as connection:
            tables = (
                (
                    await connection.execute(
                        text(
                            "SELECT table_name FROM information_schema.tables "
                            "WHERE table_schema='app' AND table_name LIKE 'skill_%'"
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert tables == []
            assert await connection.scalar(
                text("SELECT to_regprocedure(:signature) IS NOT NULL"),
                {"signature": OLD_CREATE_SIGNATURE},
            )
            assert not await connection.scalar(
                text("SELECT to_regprocedure(:signature) IS NOT NULL"),
                {"signature": NEW_CREATE_SIGNATURE},
            )
            assert await connection.scalar(
                text("SELECT to_regprocedure('app.claim_agent_task(text)') IS NOT NULL")
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM information_schema.columns "
                        "WHERE table_schema='app' "
                        "AND table_name IN ('agent_tasks','agent_executions') "
                        "AND column_name IN ('skill_definition_id','skill_version_id',"
                        "'skill_activation_event_id','skill_activation_sequence',"
                        "'runtime_binding_sha256')"
                    )
                )
                == 0
            )
            index_definition = await connection.scalar(
                text("SELECT pg_get_indexdef('app.agent_tasks_one_effective_operation'::regclass)")
            )
            assert index_definition is not None
            for field in (
                "organization_id",
                "case_id",
                "operation",
                "case_revision",
                "source_pack_id",
                "source_pack_version",
                "policy_version",
            ):
                assert field in index_definition
            assert "skill_definition_id" not in index_definition
            assert "runtime_binding_sha256" not in index_definition
            privileges = (
                await connection.execute(
                    text(
                        "SELECT "
                        "has_function_privilege('night_voyager_api',:old_create,'EXECUTE'),"
                        "has_function_privilege('night_voyager_worker',:old_create,'EXECUTE'),"
                        "has_function_privilege('night_voyager_api',"
                        "'app.claim_agent_task(text)','EXECUTE'),"
                        "has_function_privilege('night_voyager_worker',"
                        "'app.claim_agent_task(text)','EXECUTE')"
                    ),
                    {"old_create": OLD_CREATE_SIGNATURE},
                )
            ).one()
            assert tuple(privileges) == (True, False, False, True)
            public_grants = await connection.scalar(
                text(
                    "SELECT count(*) FROM pg_proc p "
                    "CROSS JOIN LATERAL aclexplode(COALESCE("
                    "p.proacl,acldefault('f',p.proowner))) acl "
                    "WHERE p.oid IN (to_regprocedure(:old_create),"
                    "to_regprocedure('app.claim_agent_task(text)')) "
                    "AND acl.grantee=0 AND acl.privilege_type='EXECUTE'"
                ),
                {"old_create": OLD_CREATE_SIGNATURE},
            )
            assert public_grants == 0

        async with api.begin() as connection:
            for name, value in (
                ("night_voyager.organization_id", str(ORG)),
                ("night_voyager.actor_id", str(ADVISOR)),
                ("night_voyager.role", "advisor"),
            ):
                await connection.execute(
                    text("SELECT set_config(:name,:value,true)"),
                    {"name": name, "value": value},
                )
            created = (
                (
                    await connection.execute(
                        text(
                            "SELECT * FROM app.create_agent_task(:org,:actor,:case,:task,"
                            "'generate_planning_run_v1',1,:pack,1,'m3a-policy-v1',"
                            "repeat('a',64),repeat('b',64))"
                        ),
                        {
                            "org": ORG,
                            "actor": ADVISOR,
                            "case": CASE,
                            "task": LEGACY_TASK,
                            "pack": PACK,
                        },
                    )
                )
                .mappings()
                .one()
            )
            assert dict(created) == {
                "task_id": LEGACY_TASK,
                "row_version": 1,
                "state": "queued",
                "attempt_count": 0,
                "replayed": False,
            }
    finally:
        await api.dispose()
        await inspector.dispose()


async def _assert_legacy_upgrade_is_fenced() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            task = (
                (
                    await connection.execute(
                        text(
                            "SELECT state,terminal_code,skill_definition_id,skill_version_id,"
                            "skill_activation_event_id,skill_activation_sequence,"
                            "runtime_binding_sha256 FROM app.agent_tasks "
                            "WHERE organization_id=:org AND id=:task"
                        ),
                        {"org": ORG, "task": LEGACY_TASK},
                    )
                )
                .mappings()
                .one()
            )
            assert dict(task) == {
                "state": "cancelled",
                "terminal_code": "legacy_unpinned",
                "skill_definition_id": None,
                "skill_version_id": None,
                "skill_activation_event_id": None,
                "skill_activation_sequence": None,
                "runtime_binding_sha256": None,
            }
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM internal.agent_task_dispatch "
                        "WHERE organization_id=:org AND task_id=:task"
                    ),
                    {"org": ORG, "task": LEGACY_TASK},
                )
                == 0
            )
            event = (
                (
                    await connection.execute(
                        text(
                            "SELECT event_code,public_status,public_code FROM "
                            "app.agent_task_events WHERE organization_id=:org "
                            "AND task_id=:task ORDER BY event_sequence DESC LIMIT 1"
                        ),
                        {"org": ORG, "task": LEGACY_TASK},
                    )
                )
                .mappings()
                .one()
            )
            assert dict(event) == {
                "event_code": "cancelled",
                "public_status": "cancelled",
                "public_code": "legacy_unpinned",
            }
            pr_a_task = (
                (
                    await connection.execute(
                        text(
                            "SELECT state,terminal_code,skill_definition_id,skill_version_id,"
                            "skill_activation_event_id,skill_activation_sequence,"
                            "runtime_binding_sha256 FROM app.agent_tasks "
                            "WHERE organization_id=:org AND id=:task"
                        ),
                        {"org": ORG, "task": PR_A_WAITING_REVIEW_TASK},
                    )
                )
                .mappings()
                .one()
            )
            assert dict(pr_a_task) == {
                "state": "waiting_review",
                "terminal_code": None,
                "skill_definition_id": None,
                "skill_version_id": None,
                "skill_activation_event_id": None,
                "skill_activation_sequence": None,
                "runtime_binding_sha256": None,
            }
    finally:
        await engine.dispose()


@pytest.mark.database
def test_empty_skill_boundary_downgrades_to_exact_0007_and_reupgrades() -> None:
    assert "0008" in _alembic("current").stdout

    _alembic("downgrade", "0007")
    assert "0007" in _alembic("current").stdout
    asyncio.run(_assert_exact_0007_boundary_and_create_legacy_task())

    _alembic("upgrade", "head")
    assert "0008" in _alembic("current").stdout
    asyncio.run(_assert_legacy_upgrade_is_fenced())
    _seed_demo()


@pytest.mark.database
def test_downgrade_refuses_seed_rows_with_noncanonical_digest() -> None:
    canonical_digest = "db3c04cc7a5826e9a68c671078e91fc8a4f9bf98f75c3be9af6c9af3a03c8444"
    asyncio.run(_replace_seed_content_digest("f" * 64))
    result = _alembic_result("downgrade", "0007")
    try:
        assert result.returncode != 0
        assert "refusing downgrade: Skill governance or runtime pin history exists" in result.stderr
        assert "0008" in _alembic("current").stdout
    finally:
        if "0007" in _alembic("current").stdout:
            _alembic("upgrade", "head")
            _seed_demo()
        else:
            asyncio.run(_replace_seed_content_digest(canonical_digest))
