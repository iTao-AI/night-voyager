# ruff: noqa: E501
from __future__ import annotations

import os
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from tests.integration.planning.test_intake_revision_source_pins import seed_module
from tests.integration.planning.test_revision_authority import (
    ADVISOR,
    ORG,
    confirm_candidate,
    digest,
    fixture,
    prepare_preferred_countries_candidate,
    request_revision,
    seed_reviewable_case,
    set_context,
)

pytestmark = pytest.mark.database
FUNCTIONS = (
    "validate_collaboration_fact",
    "verify_memory_candidate",
    "create_agent_task",
    "read_connected_journey_fact_pending",
    "load_persisted_synthetic_planning_snapshot",
)


def migrate(target: str, direction: str = "upgrade") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", direction, target],
        capture_output=True,
        text=True,
        check=False,
    )


async def definitions(c: AsyncConnection) -> list[tuple[object, ...]]:
    rows = (
        await c.execute(
            text(
                "SELECT p.proname,p.oid,pg_get_functiondef(p.oid),p.proacl::text FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='app' AND p.proname=ANY(:names) ORDER BY p.proname"
            ),
            {"names": list(FUNCTIONS)},
        )
    ).all()
    return [tuple(row) for row in rows]


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.environ.get("NIGHT_VOYAGER_INTAKE_MIGRATION_TEST") != "true",
    reason="requires separately owned empty migration database",
)
async def test_additive_intake_upgrade_and_empty_downgrade_restore_exact_bodies_oids_and_grants() -> (
    None
):
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as c:
            assert await c.scalar(text("SELECT version_num FROM alembic_version")) == "0016"
            before = await definitions(c)
        upgraded = migrate("0017")
        assert upgraded.returncode == 0, upgraded.stderr
        async with engine.connect() as c:
            after = await definitions(c)
            assert len(before) == len(after) == 5
            assert [(r[0], r[1], r[3]) for r in after] == [(r[0], r[1], r[3]) for r in before]
            assert all(old[2] != new[2] for old, new in zip(before, after, strict=True))
        restored = migrate("0016", "downgrade")
        assert restored.returncode == 0, restored.stderr
        async with engine.connect() as c:
            assert await definitions(c) == before
        assert migrate("0017").returncode == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.environ.get("NIGHT_VOYAGER_INTAKE_MIGRATION_TEST") != "true",
    reason="requires separately owned database with no intake source",
)
async def test_supported_intake_without_registered_pack_refuses_before_publication() -> None:
    url = os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"]
    await seed_module().seed_demo(url)
    migrator = create_async_engine(url)
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    target = fixture(uuid4().int % 1000000000000)
    try:
        await seed_reviewable_case(migrator, target, policy_version="m3a-policy-v1")
        async with api.begin() as c:
            await request_revision(
                c,
                target,
                review_id=target.identifier("8a000000"),
                key_hash=digest(str(uuid4())),
                request_hash=digest(str(uuid4())),
            )
            candidate = await prepare_preferred_countries_candidate(
                c, target, fact_key="student.intake", value="2028-02"
            )
        from sqlalchemy.exc import DBAPIError

        async with api.begin() as c:
            with pytest.raises(DBAPIError) as missing:
                async with c.begin_nested():
                    await confirm_candidate(c, target, candidate)
            assert getattr(missing.value.orig, "sqlstate", None) == "NV027"
        async with migrator.begin() as c:
            await set_context(c, ADVISOR, "advisor")
            assert (
                await c.scalar(
                    text(
                        "SELECT current_revision FROM app.student_cases WHERE or"
                        "ganization_id=:org AND id=:case"
                    ),
                    {"org": ORG, "case": target.case_id},
                )
                == 1
            )
            assert (
                await c.scalar(
                    text(
                        "SELECT is_current FROM app.planning_runs WHERE organiza"
                        "tion_id=:org AND id=:run"
                    ),
                    {"org": ORG, "run": target.run_id},
                )
                is True
            )
    finally:
        await migrator.dispose()
        await api.dispose()


@pytest.mark.asyncio
async def test_downgrade_refuses_persisted_intake_fixture_before_changing_function_bodies() -> None:
    url = os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"]
    await seed_module().seed_demo(url, include_intake_revision=True)
    engine = create_async_engine(url)
    try:
        async with engine.connect() as c:
            before = await definitions(c)
        refused = migrate("0016", "downgrade")
        assert refused.returncode != 0
        assert "refusing downgrade: controlled intake fixture or lineage exists" in refused.stderr
        async with engine.connect() as c:
            assert await c.scalar(text("SELECT version_num FROM alembic_version")) == "0017"
            assert await definitions(c) == before
    finally:
        await engine.dispose()
