# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from night_voyager.dra.fixtures import (
    build_fixture_candidate_import,
    build_v0_1_6_scenario_candidate_import,
)

pytestmark = pytest.mark.database

ORG = UUID("10000000-0000-0000-0000-000000000001")
CASE = UUID("40000000-0000-0000-0000-000000000003")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
STUDENT = UUID("20000000-0000-0000-0000-000000000002")
PARENT = UUID("20000000-0000-0000-0000-000000000003")
OTHER_ORG = UUID("10000000-0000-0000-0000-000000000099")
IMPORT_SIGNATURE = (
    "uuid, uuid, uuid, uuid, integer, text, text, text, text, text, text, "
    "text, text, text, text, integer, text, jsonb, text, text"
)
OUTCOME_SIGNATURE = "uuid, uuid, uuid"


def run_alembic(*arguments: str, expect_success: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("uv", "run", "alembic", *arguments),
        check=expect_success,
        env=os.environ.copy(),
        text=True,
        capture_output=not expect_success,
    )


def stable_hash(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


async def set_context(
    connection: AsyncConnection,
    *,
    organization_id: UUID = ORG,
    actor_id: UUID = ADVISOR,
    role: str = "advisor",
) -> None:
    for key, value in (
        ("organization_id", organization_id),
        ("actor_id", actor_id),
        ("role", role),
    ):
        await connection.execute(
            text("SELECT set_config(:key,:value,true)"),
            {"key": f"night_voyager.{key}", "value": str(value)},
        )


async def function_contract(name: str, signature: str) -> dict[str, object]:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT pg_get_functiondef(p.oid) AS definition,"
                        "owner.rolname AS owner,p.proacl::text AS acl,"
                        "has_function_privilege('public',p.oid,'EXECUTE') AS public_execute,"
                        "has_function_privilege('night_voyager_api',p.oid,'EXECUTE') AS api_execute,"
                        "has_function_privilege('night_voyager_worker',p.oid,'EXECUTE') AS worker_execute "
                        "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                        "JOIN pg_roles owner ON owner.oid=p.proowner "
                        "WHERE n.nspname='app' AND p.proname=:name "
                        "AND oidvectortypes(p.proargtypes)=:signature"
                    ),
                    {"name": name, "signature": signature},
                )
            ).mappings().one()
        return dict(row)
    finally:
        await engine.dispose()


async def import_candidate(
    *,
    candidate_id: UUID,
    release: str,
    commit: str,
    key_label: str,
) -> None:
    candidate = (
        build_v0_1_6_scenario_candidate_import()
        if release == "v0.1.6"
        else build_fixture_candidate_import()
    )
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await set_context(connection)
            await connection.execute(
                text(
                    "SELECT * FROM app.import_dra_research_candidate("
                    ":org,:actor,:case,:candidate,1,:release,:commit,"
                    "'dra.downstream-consumer.v1',"
                    "'cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157',"
                    "'generic',:identity_hash,:run_id,'research-report.md',"
                    "'research_report_markdown','text/markdown',:artifact_bytes,"
                    ":artifact_sha,CAST(:evidence AS jsonb),:request_hash,:key_hash)"
                ),
                {
                    "org": ORG,
                    "actor": ADVISOR,
                    "case": CASE,
                    "candidate": candidate_id,
                    "release": release,
                    "commit": commit,
                    "identity_hash": candidate.request_identity.request_sha256,
                    "run_id": candidate.run.run_id,
                    "artifact_bytes": candidate.artifact.byte_length,
                    "artifact_sha": candidate.artifact.content_hash,
                    "evidence": json.dumps(
                        [
                            item.model_dump(
                                mode="json", exclude_computed_fields=True
                            )
                            for item in candidate.evidence
                        ]
                    ),
                    "request_hash": stable_hash(f"{key_label}-request"),
                    "key_hash": stable_hash(f"{key_label}-key"),
                },
            )
    finally:
        await engine.dispose()


async def ensure_dra_case() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            exists = await connection.scalar(
                text(
                    "SELECT EXISTS(SELECT 1 FROM app.student_cases "
                    "WHERE organization_id=:org AND id=:case)"
                ),
                {"org": ORG, "case": CASE},
            )
            if not exists:
                await connection.execute(
                    text(
                        "SELECT app.publish_case_revision("
                        ":org,:case,NULL,1,'{}'::jsonb,'{}'::jsonb)"
                    ),
                    {"org": ORG, "case": CASE},
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
                    "student": STUDENT,
                    "parent": PARENT,
                },
            )
    finally:
        await engine.dispose()


async def candidate_identity(candidate_id: UUID) -> tuple[str, str]:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            row = (
                await connection.execute(
                    text(
                        "SELECT producer_release,producer_commit "
                        "FROM app.dra_research_candidates "
                        "WHERE organization_id=:org AND id=:candidate"
                    ),
                    {"org": ORG, "candidate": candidate_id},
                )
            ).one()
        return str(row.producer_release), str(row.producer_commit)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_0010_closed_producer_lifecycle_and_outcome_read_boundary() -> None:
    historical_id = UUID("90000000-0000-0000-0000-000000001001")
    live_id = UUID("90000000-0000-0000-0000-000000001006")
    baseline = await function_contract("import_dra_research_candidate", IMPORT_SIGNATURE)
    assert baseline["owner"] == "night_voyager_migrator"
    assert baseline["public_execute"] is False
    assert baseline["api_execute"] is True
    assert baseline["worker_execute"] is False

    await ensure_dra_case()
    await import_candidate(
        candidate_id=historical_id,
        release="v0.1.3",
        commit="87b2a8e335385eb865086f7a69fe2b190567cfa2",
        key_label="historical-before-upgrade",
    )
    run_alembic("upgrade", "0010")
    assert await candidate_identity(historical_id) == (
        "v0.1.3",
        "87b2a8e335385eb865086f7a69fe2b190567cfa2",
    )

    upgraded = await function_contract("import_dra_research_candidate", IMPORT_SIGNATURE)
    assert upgraded["definition"] != baseline["definition"]
    assert upgraded["owner"] == baseline["owner"]
    assert upgraded["acl"] == baseline["acl"]
    outcome = await function_contract("project_dra_live_outcome", OUTCOME_SIGNATURE)
    assert outcome == {
        "definition": outcome["definition"],
        "owner": "night_voyager_migrator",
        "acl": outcome["acl"],
        "public_execute": False,
        "api_execute": True,
        "worker_execute": False,
    }

    run_alembic("downgrade", "0009")
    assert await function_contract("import_dra_research_candidate", IMPORT_SIGNATURE) == baseline
    run_alembic("upgrade", "0010")

    await import_candidate(
        candidate_id=live_id,
        release="v0.1.6",
        commit="7d43324b469cb5e445c2e8be83af3be4d841cf1c",
        key_label="live-after-reupgrade",
    )
    assert await candidate_identity(live_id) == (
        "v0.1.6",
        "7d43324b469cb5e445c2e8be83af3be4d841cf1c",
    )

    for index, (release, commit) in enumerate(
        (
            ("v0.1.3", "87b2a8e335385eb865086f7a69fe2b190567cfa2"),
            ("v0.1.3", "7d43324b469cb5e445c2e8be83af3be4d841cf1c"),
            ("v0.1.6", "87b2a8e335385eb865086f7a69fe2b190567cfa2"),
        ),
        start=1,
    ):
        with pytest.raises(DBAPIError):
            await import_candidate(
                candidate_id=UUID(f"90000000-0000-0000-0000-{1000 + index:012d}"),
                release=release,
                commit=commit,
                key_label=f"rejected-{index}",
            )

    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with api.begin() as connection:
            await set_context(connection)
            projection = (
                await connection.execute(
                    text(
                        "SELECT * FROM app.project_dra_live_outcome("
                        ":org,:actor,:candidate)"
                    ),
                    {"org": ORG, "actor": ADVISOR, "candidate": live_id},
                )
            ).mappings().one()
            assert projection["candidate_id"] == live_id
            assert projection["producer_release"] == "v0.1.6"
            assert projection["verification_count"] == 0
            assert projection["governed_task_count"] == 0
            assert projection["advisor_review_count"] == 0
            assert projection["family_decision_count"] == 0
            assert projection["timeline_plan_count"] == 0

        async with api.begin() as connection:
            await set_context(connection, organization_id=OTHER_ORG)
            with pytest.raises(DBAPIError):
                await connection.execute(
                    text(
                        "SELECT * FROM app.project_dra_live_outcome("
                        ":org,:actor,:candidate)"
                    ),
                    {"org": ORG, "actor": ADVISOR, "candidate": live_id},
                )
    finally:
        await api.dispose()

    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with migrator.connect() as connection:
            forced = (
                await connection.execute(
                    text(
                        "SELECT relname,relrowsecurity,relforcerowsecurity "
                        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                        "WHERE n.nspname='app' AND relname=ANY(:tables) "
                        "ORDER BY relname"
                    ),
                    {
                        "tables": [
                            "dra_research_candidates",
                            "external_evidence_verifications",
                        ]
                    },
                )
            ).all()
            assert forced == [
                ("dra_research_candidates", True, True),
                ("external_evidence_verifications", True, True),
            ]
    finally:
        await migrator.dispose()

    refused = run_alembic("downgrade", "0009", expect_success=False)
    assert refused.returncode != 0
    assert "refusing downgrade: DRA v0.1.6 candidate history exists" in (
        refused.stdout + refused.stderr
    )
    current = run_alembic("current")
    assert current.returncode == 0
