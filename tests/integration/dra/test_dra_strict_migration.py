# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from night_voyager.dra.fixtures import build_v0_1_6_scenario_candidate_import
from night_voyager.dra.live_models import DraLiveScenarioV2
from night_voyager.planning.fixtures import validate_planning_fixture

pytestmark = pytest.mark.database

ORG = UUID("10000000-0000-0000-0000-000000000001")
CASE = UUID("40000000-0000-0000-0000-000000001011")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
STRICT_ID = UUID("90000000-0000-0000-0000-000000001011")
STRICT_SIGNATURE = (
    "uuid,uuid,uuid,uuid,integer,"
    "text,text,text,text,text,text,text,text,text,text,text,text,text,text,text,"
    "integer,text,jsonb,text,text"
)
LEGACY_REGPROCEDURE = (
    "app.import_dra_research_candidate("
    "uuid,uuid,uuid,uuid,integer,text,text,text,text,text,text,text,text,text,"
    "text,integer,text,jsonb,text,text)"
)
STRICT_REGPROCEDURE = f"app.import_dra_research_candidate({STRICT_SIGNATURE})"
STRICT_COLUMNS = {
    "producer_repository",
    "producer_ref_kind",
    "producer_ref",
    "profile_version",
    "proof_schema",
}


def run_alembic(
    *arguments: str, expect_success: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("uv", "run", "alembic", *arguments),
        check=expect_success,
        env=os.environ.copy(),
        text=True,
        capture_output=not expect_success,
    )


async def set_context(connection: AsyncConnection) -> None:
    for key, value in (
        ("organization_id", ORG),
        ("actor_id", ADVISOR),
        ("role", "advisor"),
    ):
        await connection.execute(
            text("SELECT set_config(:key,:value,true)"),
            {"key": f"night_voyager.{key}", "value": str(value)},
        )


async def ensure_strict_case() -> None:
    fixture_case = validate_planning_fixture().planning_input.case
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "SELECT set_config("
                    "'night_voyager.organization_id',:org,true)"
                ),
                {"org": str(ORG)},
            )
            await connection.execute(
                text(
                    "SELECT app.publish_case_revision(:org,:case,NULL,1,"
                    "CAST(:student AS jsonb),CAST(:family AS jsonb))"
                ),
                {
                    "org": ORG,
                    "case": CASE,
                    "student": fixture_case.student.model_dump_json(),
                    "family": fixture_case.family.model_dump_json(),
                },
            )
            await connection.execute(
                text(
                    "SELECT app.transition_case("
                    ":org,:case,'intake','planning')"
                ),
                {"org": ORG, "case": CASE},
            )
            await connection.execute(
                text(
                    "SELECT app.seed_case_participants("
                    ":org,:case,:advisor,:student,:parent)"
                ),
                {
                    "org": ORG,
                    "case": CASE,
                    "advisor": ADVISOR,
                    "student": UUID(
                        "20000000-0000-0000-0000-000000000002"
                    ),
                    "parent": UUID(
                        "20000000-0000-0000-0000-000000000003"
                    ),
                },
            )
    finally:
        await engine.dispose()


async def catalog_snapshot() -> dict[str, object]:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            columns = (
                await connection.execute(
                    text(
                        "SELECT column_name,data_type,is_nullable,column_default "
                        "FROM information_schema.columns "
                        "WHERE table_schema='app' AND table_name='dra_research_candidates' "
                        "ORDER BY ordinal_position"
                    )
                )
            ).all()
            constraints = (
                await connection.execute(
                    text(
                        "SELECT conname,pg_get_constraintdef(oid) "
                        "FROM pg_constraint WHERE conrelid="
                        "'app.dra_research_candidates'::regclass ORDER BY conname"
                    )
                )
            ).all()
            indexes = (
                await connection.execute(
                    text(
                        "SELECT indexname,indexdef FROM pg_indexes "
                        "WHERE schemaname='app' "
                        "AND tablename='dra_research_candidates' "
                        "ORDER BY indexname"
                    )
                )
            ).all()
            functions = (
                await connection.execute(
                    text(
                        "SELECT p.oid::regprocedure::text,pg_get_functiondef(p.oid),"
                        "p.proacl::text,p.proconfig "
                        "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                        "WHERE n.nspname='app' AND p.proname IN "
                        "('import_dra_research_candidate','project_dra_live_outcome') "
                        "ORDER BY p.oid::regprocedure::text"
                    )
                )
            ).all()
            raw_guards = (
                await connection.execute(
                    text(
                        "SELECT c.relforcerowsecurity,t.tgenabled "
                        "FROM pg_class c JOIN pg_trigger t ON t.tgrelid=c.oid "
                        "WHERE c.oid='app.dra_research_candidates'::regclass "
                        "AND t.tgname='dra_research_candidates_immutable'"
                    )
                )
            ).one()
            trigger_flag = raw_guards[1]
            guards = (
                raw_guards[0],
                (
                    trigger_flag.decode()
                    if isinstance(trigger_flag, bytes)
                    else trigger_flag
                ),
            )
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            rows = (
                await connection.execute(
                    text(
                        "SELECT to_jsonb(c) - 'created_at' "
                        "FROM app.dra_research_candidates c ORDER BY id"
                    )
                )
            ).scalars().all()
            version = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        return {
            "columns": columns,
            "constraints": constraints,
            "indexes": indexes,
            "functions": functions,
            "guards": guards,
            "rows": rows,
            "version": version,
        }
    finally:
        await engine.dispose()


async def import_authority_snapshot() -> list[tuple[str, bool, bool, bool]]:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        "SELECT p.oid::regprocedure::text,"
                        "has_function_privilege("
                        "'night_voyager_api',p.oid,'EXECUTE'),"
                        "has_function_privilege("
                        "'night_voyager_worker',p.oid,'EXECUTE'),"
                        "NOT EXISTS("
                        "SELECT 1 FROM aclexplode(COALESCE("
                        "p.proacl,acldefault('f',p.proowner))) acl "
                        "WHERE acl.grantee=0 "
                        "AND acl.privilege_type='EXECUTE') "
                        "FROM pg_proc p WHERE p.oid IN ("
                        "to_regprocedure(:legacy)::oid,"
                        "to_regprocedure(:strict)::oid) "
                        "ORDER BY p.oid::regprocedure::text"
                    ),
                    {
                        "legacy": LEGACY_REGPROCEDURE,
                        "strict": STRICT_REGPROCEDURE,
                    },
                )
            ).all()
            return [
                (str(row[0]), bool(row[1]), bool(row[2]), bool(row[3]))
                for row in rows
            ]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_0011_injected_failure_rolls_back_catalog_rows_and_guards() -> None:
    run_alembic("downgrade", "0010")
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "CREATE FUNCTION app.import_dra_research_candidate("
                    "uuid,uuid,uuid,uuid,integer,"
                    "text,text,text,text,text,text,text,text,text,text,text,text,text,text,text,"
                    "integer,text,jsonb,text,text"
                    ") RETURNS TABLE(candidate_id uuid,replayed boolean) "
                    "LANGUAGE sql AS $$ SELECT NULL::uuid,false $$"
                )
            )
    finally:
        await engine.dispose()
    before = await catalog_snapshot()
    failed = run_alembic("upgrade", "0011", expect_success=False)
    assert failed.returncode != 0
    assert await catalog_snapshot() == before

    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "DROP FUNCTION app.import_dra_research_candidate("
                    + STRICT_SIGNATURE
                    + ")"
                )
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_0011_safe_downgrade_restores_0010_then_reupgrades() -> None:
    run_alembic("downgrade", "0010")
    before_0010 = await catalog_snapshot()
    run_alembic("upgrade", "0011")
    upgraded = await catalog_snapshot()
    assert upgraded["version"] == "0011"
    upgraded_columns = cast(list[tuple[str, ...]], upgraded["columns"])
    assert {row[0] for row in upgraded_columns} >= STRICT_COLUMNS
    assert upgraded["guards"] == (True, "O")
    authority = await import_authority_snapshot()
    assert [row[0] for row in authority] == sorted(
        (LEGACY_REGPROCEDURE, STRICT_REGPROCEDURE)
    )
    assert all(row[1:] == (True, False, True) for row in authority)

    run_alembic("downgrade", "0010")
    assert await catalog_snapshot() == before_0010
    run_alembic("upgrade", "0011")


@pytest.mark.asyncio
async def test_0011_strict_import_projection_and_refusal_are_closed() -> None:
    run_alembic("downgrade", "0010")
    run_alembic("upgrade", "0011")
    await ensure_strict_case()
    scenario = DraLiveScenarioV2.model_validate_json(
        Path("fixtures/dra/live-closure-scenario-v2.json").read_bytes()
    )
    legacy = build_v0_1_6_scenario_candidate_import()
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await set_context(connection)
            parameters = {
                "org": ORG,
                "actor": ADVISOR,
                "case": CASE,
                "candidate": STRICT_ID,
                "repository": scenario.producer.repository,
                "ref_kind": scenario.producer.ref_kind,
                "ref": scenario.producer.ref,
                "release": None,
                "commit": scenario.producer.commit,
                "schema": scenario.producer.consumer_contract_schema,
                "fixture": scenario.producer.consumer_fixture_sha256,
                "profile": scenario.producer.profile_id,
                "profile_version": scenario.profile_manifest.profile_version,
                "proof_schema": scenario.producer.proof_schema,
                "identity_hash": scenario.request_identity.request_sha256,
                "run_id": scenario.status.run_id,
                "artifact_bytes": scenario.canonical_artifact.byte_length,
                "artifact_sha": scenario.canonical_artifact.content_hash,
                    "evidence": json.dumps(
                    [
                        {
                            key: value
                            for key, value in row.model_dump(mode="json").items()
                            if key not in {"run_id", "segment_id"}
                        }
                        for row in scenario.evidence
                    ]
                    ),
                    "request_hash": hashlib.sha256(
                        b"strict-migration-import-request"
                    ).hexdigest(),
                    "key_hash": hashlib.sha256(
                        b"strict-migration-import-key"
                    ).hexdigest(),
            }
            sql = text(
                "SELECT * FROM app.import_dra_research_candidate("
                ":org,:actor,:case,:candidate,1,:repository,:ref_kind,:ref,"
                ":release,:commit,:schema,:fixture,:profile,:profile_version,"
                ":proof_schema,:identity_hash,:run_id,'research-report.md',"
                "'research_report_markdown','text/markdown',:artifact_bytes,"
                ":artifact_sha,CAST(:evidence AS jsonb),:request_hash,:key_hash)"
            )
            row = (await connection.execute(sql, parameters)).one()
            assert row == (STRICT_ID, False)
            replay = (await connection.execute(sql, parameters)).one()
            assert replay == (STRICT_ID, True)

        async with engine.begin() as connection:
            await set_context(connection)
            with pytest.raises(DBAPIError) as captured:
                await connection.execute(
                    sql,
                    parameters
                    | {
                        "candidate": UUID(
                            "90000000-0000-0000-0000-000000001012"
                        ),
                        "release": "v0.1.6",
                        "request_hash": hashlib.sha256(
                            b"strict-migration-mixed-request"
                        ).hexdigest(),
                        "key_hash": hashlib.sha256(
                            b"strict-migration-mixed-key"
                        ).hexdigest(),
                    },
                )
            assert getattr(captured.value.orig, "sqlstate", None) == "NV011"
    finally:
        await engine.dispose()

    inspector = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with inspector.begin() as connection:
            await set_context(connection)
            projection = (
                await connection.execute(
                    text(
                        "SELECT * FROM app.project_dra_live_outcome("
                        ":org,:actor,:candidate)"
                    ),
                    {"org": ORG, "actor": ADVISOR, "candidate": STRICT_ID},
                )
            ).mappings().one()
            assert projection["producer_repository"] == scenario.producer.repository
            assert projection["producer_ref_kind"] == "commit"
            assert projection["producer_release"] is None
            assert projection["profile_version"] == "1"
            assert projection["proof_schema"] == "dra.strict-citation-profile.v1"
            assert projection["request_identity_sha256"] == (
                scenario.request_identity.request_sha256
            )
            assert legacy.producer.release == "v0.1.6"
    finally:
        await inspector.dispose()

    before_refusal = await catalog_snapshot()
    refused = run_alembic("downgrade", "0010", expect_success=False)
    assert refused.returncode != 0
    assert "refusing downgrade: DRA strict candidate history exists" in (
        refused.stdout + refused.stderr
    )
    assert await catalog_snapshot() == before_refusal
