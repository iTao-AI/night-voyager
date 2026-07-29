from __future__ import annotations

import os
import subprocess

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.database

ROTATE_SIGNATURE = (
    "auth.rotate_demo_session(bytea,bytea,text,uuid,bytea,bytea,timestamp with time zone)"
)


def _alembic(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("uv", "run", "alembic", *arguments),
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.mark.asyncio
async def test_0015_catalog_is_closed_and_runtime_roles_keep_function_only_authority() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            assert await connection.scalar(
                text("SELECT version_num FROM alembic_version")
            ) == "0015"
            constraints = dict(
                (
                    await connection.execute(
                        text(
                            "SELECT conname,pg_get_constraintdef(oid) "
                            "FROM pg_constraint "
                            "WHERE conrelid='auth.demo_principals'::regclass "
                            "AND conname IN ("
                            "'demo_principals_demo_key_check',"
                            "'demo_principals_identity_unique')"
                        )
                    )
                ).all()
            )
            assert set(constraints) == {
                "demo_principals_demo_key_check",
                "demo_principals_identity_unique",
            }
            check = constraints["demo_principals_demo_key_check"]
            for demo_key in (
                "advisor",
                "student",
                "parent",
                "plan_execution_happy_advisor",
                "plan_execution_happy_student",
                "plan_execution_happy_parent",
                "plan_execution_blocked_advisor",
                "plan_execution_blocked_student",
                "plan_execution_blocked_parent",
            ):
                assert demo_key in check
            function = (
                await connection.execute(
                    text(
                        "SELECT prosecdef,proconfig,"
                        "has_function_privilege('public',oid,'EXECUTE') public_execute,"
                        "has_function_privilege('night_voyager_api',oid,'EXECUTE') api_execute,"
                        "has_function_privilege("
                        "'night_voyager_worker',oid,'EXECUTE') worker_execute "
                        "FROM pg_proc WHERE oid=to_regprocedure(:signature)"
                    ),
                    {"signature": ROTATE_SIGNATURE},
                )
            ).mappings().one()
            assert function == {
                "prosecdef": True,
                "proconfig": ["search_path=pg_catalog, pg_temp"],
                "public_execute": False,
                "api_execute": True,
                "worker_execute": False,
            }
            for role in ("night_voyager_api", "night_voyager_worker"):
                assert await connection.scalar(
                    text(
                        "SELECT has_table_privilege("
                        ":role,'auth.demo_principals','INSERT,UPDATE,DELETE') "
                        "OR has_table_privilege("
                        ":role,'auth.demo_sessions','INSERT,UPDATE,DELETE')"
                    ),
                    {"role": role},
                ) is False
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_empty_0015_downgrade_and_reupgrade_restore_exact_catalog() -> None:
    if os.environ.get("NIGHT_VOYAGER_IDENTITY_MIGRATION_PHASE") != "empty":
        pytest.skip("isolated empty identity migration phase only")
    result = _alembic("downgrade", "0014")
    assert result.returncode == 0, result.stderr
    assert _alembic("current").stdout.strip().startswith("0014")
    result = _alembic("upgrade", "head")
    assert result.returncode == 0, result.stderr
    assert _alembic("current").stdout.strip().startswith("0015")


@pytest.mark.asyncio
async def test_seeded_0015_downgrade_refuses_before_catalog_mutation() -> None:
    if os.environ.get("NIGHT_VOYAGER_IDENTITY_MIGRATION_PHASE") != "seeded":
        pytest.skip("isolated seeded identity migration phase only")
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            before = (
                await connection.execute(
                    text(
                        "SELECT "
                        "(SELECT version_num FROM alembic_version) revision,"
                        "(SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                        "WHERE conrelid='auth.demo_principals'::regclass "
                        "AND conname='demo_principals_demo_key_check') check_definition,"
                        "(SELECT pg_get_functiondef(oid) FROM pg_proc "
                        "WHERE oid=to_regprocedure(:signature)) function_definition,"
                        "(SELECT count(*) FROM auth.demo_principals) principals"
                    ),
                    {"signature": ROTATE_SIGNATURE},
                )
            ).mappings().one()
        result = _alembic("downgrade", "0014")
        assert result.returncode != 0
        assert "0015 plan execution demo identity exists" in result.stderr
        async with engine.connect() as connection:
            after = (
                await connection.execute(
                    text(
                        "SELECT "
                        "(SELECT version_num FROM alembic_version) revision,"
                        "(SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                        "WHERE conrelid='auth.demo_principals'::regclass "
                        "AND conname='demo_principals_demo_key_check') check_definition,"
                        "(SELECT pg_get_functiondef(oid) FROM pg_proc "
                        "WHERE oid=to_regprocedure(:signature)) function_definition,"
                        "(SELECT count(*) FROM auth.demo_principals) principals"
                    ),
                    {"signature": ROTATE_SIGNATURE},
                )
            ).mappings().one()
        assert after == before
        assert after["revision"] == "0015"
    finally:
        await engine.dispose()
