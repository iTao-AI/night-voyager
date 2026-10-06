# ruff: noqa: E501
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from tests.integration.planning.test_revision_authority import ADVISOR, ORG, set_context

pytestmark = pytest.mark.database
CASE = "49000000-0000-0000-0000-000000000003"
PACK = "50000000-0000-0000-0000-000000000017"


def seed_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("intake_seed", Path("scripts/seed_demo.py"))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def snapshot(connection: AsyncConnection) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for table in (
        "student_cases",
        "student_case_revisions",
        "confirmed_facts",
        "memory_candidates",
        "memory_candidate_verifications",
        "agent_tasks",
        "planning_runs",
    ):
        column = "id" if table == "student_cases" else "case_id"
        result[table] = cast(
            list[dict[str, Any]],
            await connection.scalar(
                text(
                    f"SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]'::jsonb) "
                    f"FROM app.{table} t WHERE organization_id=:org AND {column}=:case"
                ),
                {"org": ORG, "case": CASE},
            ),
        )
    return result


@pytest.mark.asyncio
async def test_opt_in_intake_seed_is_exact_replay_and_closed_source_authority() -> None:
    url = os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"]
    await seed_module().seed_demo(url, include_intake_revision=True)
    engine = create_async_engine(url)
    try:
        async with engine.begin() as c:
            await set_context(c, ADVISOR, "advisor")
            before = await snapshot(c)
            value = await c.scalar(
                text(
                    "SELECT student_preferences->>'intake' FROM app.student_case_revisions WHERE organization_id=:org AND case_id=:case AND revision=1"
                ),
                {"org": ORG, "case": CASE},
            )
            assert value == "2027-02"
            await c.execute(
                text(
                    "SELECT app.assert_controlled_intake_source(:org,CAST(:p"
                    "ack AS uuid),1,'2028-02')"
                ),
                {"org": ORG, "pack": PACK},
            )
        await seed_module().seed_demo(url, include_intake_revision=True)
        async with engine.begin() as c:
            await set_context(c, ADVISOR, "advisor")
            assert await snapshot(c) == before
            assert before["confirmed_facts"][0]["fact_key"] == "student.intake"
            assert before["confirmed_facts"][0]["value"] == "2027-02"
            assert (
                before["planning_runs"][0]["source_pack_id"]
                == "50000000-0000-0000-0000-000000000001"
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ("API", "WORKER"))
async def test_runtime_roles_cannot_call_closed_source_or_seed_helpers(role: str) -> None:
    engine = create_async_engine(os.environ[f"NIGHT_VOYAGER_{role}_DATABASE_URL"])
    try:
        async with engine.begin() as c:
            await set_context(c, ADVISOR, "advisor")
            assert (
                await c.scalar(
                    text(
                        "SELECT has_function_privilege(current_user,'app.seed_demo_intake_revision(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,jsonb,text,text,text,text)','execute')"
                    )
                )
                is False
            )
            with pytest.raises(DBAPIError) as denied:
                async with c.begin_nested():
                    await c.execute(
                        text(
                            "SELECT app.assert_controlled_intake_source(:org,CAST(:p"
                            "ack AS uuid),1,'2028-02')"
                        ),
                        {"org": ORG, "pack": PACK},
                    )
            assert getattr(denied.value.orig, "sqlstate", None) == "42501"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_source_metadata_drift_cannot_be_repaired_by_seed_replay_or_write_case_history() -> (
    None
):
    url = os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"]
    engine = create_async_engine(url)
    old_publisher = None
    try:
        async with engine.begin() as c:
            await set_context(c, ADVISOR, "advisor")
            before = await snapshot(c)
            old_publisher = await c.scalar(
                text(
                    "SELECT publisher FROM app.source_pack_entries WHERE organization_id=:org AND source_pack_id=CAST(:pack AS uuid) ORDER BY id LIMIT 1"
                ),
                {"org": ORG, "pack": PACK},
            )
            await c.execute(
                text(
                    "UPDATE app.source_pack_entries SET publisher='Unregistered synthetic publisher' WHERE organization_id=:org AND source_pack_id=CAST(:pack AS uuid) AND id='51000000-0000-0000-0000-000000001701'"
                ),
                {"org": ORG, "pack": PACK},
            )
        with pytest.raises(DBAPIError) as drift:
            await seed_module().seed_demo(url, include_intake_revision=True)
        assert getattr(drift.value.orig, "sqlstate", None) == "NV027"
        async with engine.begin() as c:
            await set_context(c, ADVISOR, "advisor")
            assert await snapshot(c) == before
    finally:
        if old_publisher is not None:
            async with engine.begin() as c:
                await set_context(c, ADVISOR, "advisor")
                await c.execute(
                    text(
                        "UPDATE app.source_pack_entries SET publisher=:publisher WHERE organization_id=:org AND id='51000000-0000-0000-0000-000000001701'"
                    ),
                    {"org": ORG, "publisher": old_publisher},
                )
        await engine.dispose()
