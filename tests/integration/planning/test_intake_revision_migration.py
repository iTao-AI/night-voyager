# ruff: noqa: E501
from __future__ import annotations

import os
import subprocess
import sys
from uuid import uuid4

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, async_sessionmaker, create_async_engine

from night_voyager.api import create_app
from night_voyager.config import Settings
from night_voyager.identity.models import DemoActorChoice
from night_voyager.planning.intake_fixture import INTAKE_DELAY_SOURCE_PACK_ID
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
from tests.integration.tasks.test_http_tasks import ORIGIN, create_payload, mint, mutation_headers

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


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.environ.get("NIGHT_VOYAGER_INTAKE_MIGRATION_TEST") != "true",
    reason="requires separately owned database with no controlled-source Tasks or runs",
)
async def test_missing_source_after_intake_confirmation_returns_bounded_http_conflict_without_writes() -> (
    None
):
    url = os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"]
    await seed_module().seed_demo(url, include_intake_revision=True)
    migrator = create_async_engine(url)
    api_url = os.environ["NIGHT_VOYAGER_API_DATABASE_URL"]
    api = create_async_engine(api_url)
    sessions = async_sessionmaker(api, expire_on_commit=False)
    target = fixture(uuid4().int % 10**12)
    source_rows: dict[str, list[str]] = {}
    tables = ("source_packs", "source_pack_entries", "evidence_refs")
    source_params = {"org": ORG, "pack": INTAKE_DELAY_SOURCE_PACK_ID}

    async def business_snapshot(c: AsyncConnection) -> object:
        await set_context(c, ADVISOR, "advisor")
        return await c.scalar(
            text(
                "SELECT jsonb_build_object("
                "'case',(SELECT to_jsonb(s) FROM app.student_cases s WHERE s.organization_id=:org AND s.id=:case),"
                "'revisions',(SELECT jsonb_agg(to_jsonb(r) ORDER BY r.revision) FROM app.student_case_revisions r WHERE r.organization_id=:org AND r.case_id=:case),"
                "'runs',(SELECT jsonb_agg(to_jsonb(r) ORDER BY r.id) FROM app.planning_runs r WHERE r.organization_id=:org AND r.case_id=:case),"
                "'tasks',(SELECT count(*) FROM app.agent_tasks WHERE organization_id=:org),"
                "'dispatches',(SELECT count(*) FROM internal.agent_task_dispatch WHERE organization_id=:org),"
                "'idempotency',(SELECT count(*) FROM app.idempotency_records WHERE organization_id=:org AND operation='agent_task_create'))"
            ),
            {"org": ORG, "case": target.case_id},
        )

    try:
        await seed_reviewable_case(migrator, target, policy_version="m3a-policy-v1")
        async with api.begin() as c:
            assert await c.scalar(text("SELECT current_user")) == "night_voyager_api"
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
            await confirm_candidate(c, target, candidate)
        advisor = await mint(sessions, DemoActorChoice.ADVISOR)
        async with migrator.begin() as c:
            await set_context(c, ADVISOR, "advisor")
            for table in tables:
                key = "id" if table == "source_packs" else "source_pack_id"
                source_rows[table] = list(
                    (
                        await c.scalars(
                            text(
                                f"SELECT to_jsonb(s)::text FROM app.{table} s WHERE organization_id=:org AND {key}=:pack"
                            ),
                            source_params,
                        )
                    ).all()
                )
            assert len(source_rows["source_packs"]) == 1
            for table in reversed(tables):
                key = "id" if table == "source_packs" else "source_pack_id"
                await c.execute(
                    text(f"DELETE FROM app.{table} WHERE organization_id=:org AND {key}=:pack"),
                    source_params,
                )
            before = await business_snapshot(c)
        settings = Settings.model_validate(
            {
                "environment": "test",
                "database_url": api_url,
                "demo_mode": True,
                "demo_allow_insecure_cookie": True,
                "allowed_origins": [ORIGIN],
                "secret_key": "test-session-secret",
            }
        )
        app = create_app(settings=settings, session_factory=sessions)
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            client.cookies.set("night_voyager_session", advisor.raw_session_token)
            response = await client.post(
                f"/api/v1/cases/{target.case_id}/agent-tasks",
                headers=mutation_headers(advisor, str(uuid4())),
                json=create_payload(
                    expected_case_revision=2, source_pack_id=str(INTAKE_DELAY_SOURCE_PACK_ID)
                ),
            )
        async with migrator.begin() as c:
            assert await business_snapshot(c) == before
        assert response.status_code == 409, response.text
        assert response.json()["code"] == "intake_evidence_unavailable"
    finally:
        if source_rows:
            async with migrator.begin() as c:
                await set_context(c, ADVISOR, "advisor")
                for table in tables:
                    for row in source_rows[table]:
                        await c.execute(
                            text(
                                f"INSERT INTO app.{table} SELECT * FROM jsonb_populate_record(NULL::app.{table},CAST(:row AS jsonb)) ON CONFLICT DO NOTHING"
                            ),
                            {"row": row},
                        )
        await api.dispose()
        await migrator.dispose()
