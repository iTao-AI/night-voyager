from __future__ import annotations

import os
from typing import Any, cast

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql.elements import TextClause

DEMO_ORG = "10000000-0000-0000-0000-000000000001"
DEMO_CASE = "40000000-0000-0000-0000-000000000002"
DEMO_PACK = "50000000-0000-0000-0000-000000000001"


def _snapshot_statement() -> TextClause:
    return text(
        "SELECT app.load_persisted_synthetic_planning_snapshot("
        ":org,:case,:revision,:pack,:pack_version,:policy)"
    )


@pytest.mark.database
@pytest.mark.asyncio
async def test_worker_only_persisted_revision_projection_is_registered() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            identity = await connection.scalar(
                text(
                    "SELECT to_regprocedure("
                    "'app.load_persisted_synthetic_planning_snapshot(uuid,uuid,integer,uuid,integer,text)'"
                    ")::text"
                )
            )
            worker_can_execute = await connection.scalar(
                text(
                    "SELECT has_function_privilege("
                    "'night_voyager_worker',"
                    "'app.load_persisted_synthetic_planning_snapshot(uuid,uuid,integer,uuid,integer,text)',"
                    "'EXECUTE')"
                )
            )
            api_can_execute = await connection.scalar(
                text(
                    "SELECT has_function_privilege("
                    "'night_voyager_api',"
                    "'app.load_persisted_synthetic_planning_snapshot(uuid,uuid,integer,uuid,integer,text)',"
                    "'EXECUTE')"
                )
            )
        assert identity is not None
        assert worker_can_execute is True
        assert api_can_execute is False
    finally:
        await engine.dispose()


@pytest.mark.database
@pytest.mark.asyncio
async def test_projection_materializes_exact_persisted_case_and_pins() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": DEMO_ORG},
            )
            payload = cast(
                dict[str, Any],
                await connection.scalar(
                    _snapshot_statement(),
                    {
                        "org": DEMO_ORG,
                        "case": DEMO_CASE,
                        "revision": 1,
                        "pack": DEMO_PACK,
                        "pack_version": 1,
                        "policy": "m3a-policy-v1",
                    },
                ),
            )
        assert isinstance(payload, dict)
        assert set(payload) == {
            "schema_version",
            "organization_id",
            "case",
            "source_pack_id",
            "source_pack_version",
            "policy_version",
        }
        assert payload["schema_version"] == 1
        assert str(payload["organization_id"]) == DEMO_ORG
        assert str(payload["source_pack_id"]) == DEMO_PACK
        assert payload["source_pack_version"] == 1
        assert payload["policy_version"] == "m3a-policy-v1"
        case = cast(dict[str, Any], payload["case"])
        assert isinstance(case, dict)
        assert str(case["case_id"]) == DEMO_CASE
        assert case["revision"] == 1
        assert case["student"] == {
            "schema_version": 1,
            "intended_field": "computing",
            "preferred_countries": ["australia", "japan", "malaysia"],
            "intake": "2027-02",
        }
        family = cast(dict[str, Any], case["family"])
        assert family["risk_tolerance"] == "high"
        assert family["japan_risk_accepted"] is True
        assert family["budget"] == {
            "schema_version": 1,
            "currency": "CNY",
            "period": "program_total",
            "preferred_minor": 34000000,
            "hard_ceiling_minor": 40000000,
            "elasticity_bps": 1000,
            "refused": False,
        }
    finally:
        await engine.dispose()


@pytest.mark.database
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("context_org", "case_id", "revision", "pack_version", "policy", "sqlstate"),
    (
        (
            DEMO_ORG,
            "40000000-0000-0000-0000-000000000099",
            1,
            1,
            "m3a-policy-v1",
            "NV003",
        ),
        (DEMO_ORG, DEMO_CASE, 2, 1, "m3a-policy-v1", "NV003"),
        (DEMO_ORG, DEMO_CASE, 1, 2, "m3a-policy-v1", "NV011"),
        (DEMO_ORG, DEMO_CASE, 1, 1, "wrong-policy", "NV011"),
        (
            "10000000-0000-0000-0000-000000000099",
            DEMO_CASE,
            1,
            1,
            "m3a-policy-v1",
            "NV007",
        ),
    ),
)
async def test_projection_rejects_missing_stale_cross_tenant_or_pin_mismatch(
    context_org: str,
    case_id: str,
    revision: int,
    pack_version: int,
    policy: str,
    sqlstate: str,
) -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": context_org},
            )
            with pytest.raises(DBAPIError) as captured:
                await connection.scalar(
                    _snapshot_statement(),
                    {
                        "org": DEMO_ORG,
                        "case": case_id,
                        "revision": revision,
                        "pack": DEMO_PACK,
                        "pack_version": pack_version,
                        "policy": policy,
                    },
                )
        assert getattr(captured.value.orig, "sqlstate", None) == sqlstate
    finally:
        await engine.dispose()


@pytest.mark.database
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case_id", "countries"),
    (
        ("49000000-0000-0000-0000-000000000001", '["japan","japan"]'),
        ("49000000-0000-0000-0000-000000000002", '["canada"]'),
    ),
)
async def test_projection_rejects_malformed_or_unsupported_country_scope(
    case_id: str, countries: str
) -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": DEMO_ORG},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.student_cases(organization_id,id,state) "
                    "VALUES(:org,:case,'planning')"
                ),
                {"org": DEMO_ORG, "case": case_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.student_case_revisions("
                    "organization_id,case_id,revision,schema_version,"
                    "student_preferences,family_preferences) "
                    "SELECT :org,:case,1,1,"
                    "student_preferences || jsonb_build_object("
                    "'preferred_countries',CAST(:countries AS jsonb)),"
                    "family_preferences "
                    "FROM app.student_case_revisions "
                    "WHERE organization_id=:org AND case_id=:base_case AND revision=1"
                ),
                {
                    "org": DEMO_ORG,
                    "case": case_id,
                    "base_case": DEMO_CASE,
                    "countries": countries,
                },
            )
            await connection.execute(
                text(
                    "UPDATE app.student_cases SET current_revision=1 "
                    "WHERE organization_id=:org AND id=:case"
                ),
                {"org": DEMO_ORG, "case": case_id},
            )
        async with engine.connect() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": DEMO_ORG},
            )
            with pytest.raises(DBAPIError) as captured:
                await connection.scalar(
                    _snapshot_statement(),
                    {
                        "org": DEMO_ORG,
                        "case": case_id,
                        "revision": 1,
                        "pack": DEMO_PACK,
                        "pack_version": 1,
                        "policy": "m3a-policy-v1",
                    },
                )
        assert getattr(captured.value.orig, "sqlstate", None) == "NV011"
    finally:
        await engine.dispose()
