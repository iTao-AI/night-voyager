# ruff: noqa: E501
from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.database

TABLES = (
    "timeline_executions",
    "timeline_checkpoints",
    "timeline_checkpoint_attestations",
    "timeline_checkpoint_verifications",
    "timeline_reassessment_requests",
    "timeline_mutation_receipts",
)

SIGNATURES = (
    "app.read_plan_execution_context(uuid,uuid,text,text)",
    "app.read_timeline_execution(uuid,uuid,text,uuid)",
    "app.start_timeline_execution(uuid,uuid,text,uuid,uuid,integer,uuid,uuid,text,text)",
    "app.attest_timeline_checkpoint(uuid,uuid,text,uuid,uuid,integer,integer,text,text,text,text,uuid,uuid,text,text)",
    "app.verify_timeline_checkpoint(uuid,uuid,text,uuid,uuid,uuid,uuid,integer,integer,text,text,uuid,uuid,text,text)",
    "app.request_timeline_reassessment(uuid,uuid,text,uuid,uuid,uuid,uuid,integer,integer,text,uuid,uuid,text,text)",
)


@pytest.mark.asyncio
async def test_0014_is_exact_head_with_forced_rls_and_closed_functions() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
            assert revision == "0014"
            rows = (
                await connection.execute(
                    text(
                        "SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity,"
                        "pg_get_userbyid(c.relowner) AS owner "
                        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                        "WHERE n.nspname='app' AND c.relname=ANY(:tables) "
                        "ORDER BY c.relname"
                    ),
                    {"tables": list(TABLES)},
                )
            ).all()
            assert [row.relname for row in rows] == sorted(TABLES)
            assert all(row.relrowsecurity and row.relforcerowsecurity for row in rows)
            assert all(row.owner == "night_voyager_migrator" for row in rows)

            for signature in SIGNATURES:
                catalog = (
                    await connection.execute(
                        text(
                            "SELECT p.prosecdef,p.proconfig,"
                            "has_function_privilege('public',p.oid,'EXECUTE') public_execute,"
                            "has_function_privilege('night_voyager_api',p.oid,'EXECUTE') api_execute,"
                            "has_function_privilege('night_voyager_worker',p.oid,'EXECUTE') worker_execute "
                            "FROM pg_proc p WHERE p.oid=to_regprocedure(:signature)"
                        ),
                        {"signature": signature},
                    )
                ).mappings().one()
                assert catalog["prosecdef"] is True
                assert catalog["proconfig"] == ["search_path=pg_catalog, pg_temp"]
                assert catalog["public_execute"] is False
                assert catalog["api_execute"] is True
                assert catalog["worker_execute"] is False
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_runtime_roles_have_read_only_table_matrix() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            for table_name in TABLES:
                privileges = (
                    await connection.execute(
                        text(
                            "SELECT "
                            "has_table_privilege('night_voyager_api',:table,'SELECT') api_read,"
                            "has_table_privilege('night_voyager_api',:table,'INSERT,UPDATE,DELETE') api_write,"
                            "has_table_privilege('night_voyager_worker',:table,'SELECT') worker_read,"
                            "has_table_privilege('night_voyager_worker',:table,'INSERT,UPDATE,DELETE') worker_write"
                        ),
                        {"table": f"app.{table_name}"},
                    )
                ).mappings().one()
                assert privileges == {
                    "api_read": True,
                    "api_write": False,
                    "worker_read": False,
                    "worker_write": False,
                }
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_verification_attestation_foreign_key_is_composite_bound() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            definitions = (
                await connection.execute(
                    text(
                        "SELECT pg_get_constraintdef(oid) "
                        "FROM pg_constraint "
                        "WHERE conrelid='app.timeline_checkpoint_verifications'::regclass "
                        "AND contype='f'"
                    )
                )
            ).scalars().all()
            assert any(
                "FOREIGN KEY (organization_id, execution_id, checkpoint_id, attestation_id)"
                in definition
                and "REFERENCES app.timeline_checkpoint_attestations"
                in definition
                for definition in definitions
            )
    finally:
        await engine.dispose()
