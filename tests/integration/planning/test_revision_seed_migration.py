from __future__ import annotations

import hashlib
import json
import os
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from night_voyager.collaboration.hashing import canonical_sha256
from night_voyager.planning.fixtures import validate_planning_fixture

pytestmark = pytest.mark.database

ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
STUDENT = UUID("20000000-0000-0000-0000-000000000002")
PARENT = UUID("20000000-0000-0000-0000-000000000003")
HAPPY_CASE = UUID("49000000-0000-0000-0000-000000000001")
BUDGET_CASE = UUID("49000000-0000-0000-0000-000000000002")
HAPPY_THREAD = UUID("4b000000-0000-0000-0000-000000000001")
BUDGET_THREAD = UUID("4b000000-0000-0000-0000-000000000002")
HAPPY_MESSAGE = UUID("4c000000-0000-0000-0000-000000000001")
HAPPY_CANDIDATE = UUID("4d000000-0000-0000-0000-000000000001")
HAPPY_VERIFICATION = UUID("4e000000-0000-0000-0000-000000000001")
HAPPY_FACT = UUID("4f000000-0000-0000-0000-000000000001")
SIGNATURE = (
    "app.seed_demo_planning_revision_fact("
    "uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,jsonb,text,text,text,text)"
)
BODY_HASH = hashlib.sha256(
    b"Synthetic initial preferred countries."
).hexdigest()


def _request_hash(kind: str, case_id: UUID) -> str:
    return hashlib.sha256(f"revision-seed-{kind}:{case_id}".encode()).hexdigest()


async def _set_context(connection: AsyncConnection) -> None:
    await connection.execute(
        text("SELECT set_config('night_voyager.organization_id',:org,true)"),
        {"org": str(ORG)},
    )


async def _seed_anchor(
    connection: AsyncConnection,
    *,
    case_id: UUID,
    thread_id: UUID,
) -> None:
    fixture = validate_planning_fixture()
    source_case = fixture.planning_input.case
    await connection.execute(
        text(
            "INSERT INTO app.student_cases(organization_id,id,state) "
            "VALUES(:org,:case,'planning')"
        ),
        {"org": ORG, "case": case_id},
    )
    await connection.execute(
        text(
            "INSERT INTO app.student_case_revisions("
            "organization_id,case_id,revision,schema_version,"
            "student_preferences,family_preferences) "
            "VALUES(:org,:case,1,1,CAST(:student AS jsonb),CAST(:family AS jsonb))"
        ),
        {
            "org": ORG,
            "case": case_id,
            "student": json.dumps(source_case.student.model_dump(mode="json")),
            "family": json.dumps(source_case.family.model_dump(mode="json")),
        },
    )
    await connection.execute(
        text(
            "UPDATE app.student_cases SET current_revision=1 "
            "WHERE organization_id=:org AND id=:case"
        ),
        {"org": ORG, "case": case_id},
    )
    await connection.execute(
        text(
            "SELECT app.seed_case_participants("
            ":org,:case,:advisor,:student,:parent)"
        ),
        {
            "org": ORG,
            "case": case_id,
            "advisor": ADVISOR,
            "student": STUDENT,
            "parent": PARENT,
        },
    )
    await connection.execute(
        text(
            "SELECT app.seed_demo_collaboration("
            ":org,:case,:thread,:advisor,NULL,NULL,NULL,NULL,'primary')"
        ),
        {
            "org": ORG,
            "case": case_id,
            "thread": thread_id,
            "advisor": ADVISOR,
        },
    )


def _helper_parameters() -> dict[str, object]:
    preferred = [
        country.value
        for country in (
            validate_planning_fixture()
            .planning_input.case.student.preferred_countries
        )
    ]
    return {
        "org": ORG,
        "case": HAPPY_CASE,
        "thread": HAPPY_THREAD,
        "advisor": ADVISOR,
        "student": STUDENT,
        "message": HAPPY_MESSAGE,
        "candidate": HAPPY_CANDIDATE,
        "verification": HAPPY_VERIFICATION,
        "fact": HAPPY_FACT,
        "preferred": json.dumps(preferred),
        "value_hash": canonical_sha256(preferred),
        "message_hash": _request_hash("message", HAPPY_CASE),
        "candidate_hash": _request_hash("candidate", HAPPY_CASE),
        "verification_hash": _request_hash("verification", HAPPY_CASE),
    }


async def _call_helper(
    connection: AsyncConnection,
    parameters: dict[str, object] | None = None,
) -> None:
    await connection.execute(
        text(
            "SELECT app.seed_demo_planning_revision_fact("
            ":org,:case,:thread,:advisor,:student,:message,:candidate,"
            ":verification,:fact,CAST(:preferred AS jsonb),:value_hash,"
            ":message_hash,:candidate_hash,:verification_hash)"
        ),
        parameters or _helper_parameters(),
    )


async def _authority_count(connection: AsyncConnection) -> int:
    value = await connection.scalar(
        text(
            "SELECT "
            "(SELECT count(*) FROM app.message_events WHERE organization_id=:org "
            "AND case_id=:case)+"
            "(SELECT count(*) FROM app.memory_candidates WHERE organization_id=:org "
            "AND case_id=:case)+"
            "(SELECT count(*) FROM app.memory_candidate_verifications "
            "WHERE organization_id=:org AND case_id=:case)+"
            "(SELECT count(*) FROM app.confirmed_facts WHERE organization_id=:org "
            "AND case_id=:case)+"
            "(SELECT count(*) FROM app.case_revision_confirmed_fact_refs "
            "WHERE organization_id=:org AND case_id=:case)"
        ),
        {"org": ORG, "case": HAPPY_CASE},
    )
    assert isinstance(value, int)
    return value


@pytest.mark.asyncio
async def test_planning_revision_seed_helper_migration_phase() -> None:
    phase = os.environ.get("NIGHT_VOYAGER_REVISION_SEED_MIGRATION_PHASE")
    if phase is None:
        pytest.skip("isolated planning revision seed migration phase only")
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            helper = await connection.scalar(
                text("SELECT to_regprocedure(:signature)::text"),
                {"signature": SIGNATURE},
            )
            if phase in {"absent-0012", "safe-downgrade-0012"}:
                assert helper is None
                return

            assert phase in {"authority-0013", "restored-0013"}
            assert helper == SIGNATURE
            catalog = (
                await connection.execute(
                    text(
                        "SELECT p.prosecdef,p.proconfig,p.proacl,"
                        "has_function_privilege('public',p.oid,'EXECUTE') AS public_execute,"
                        "has_function_privilege('night_voyager_api',p.oid,'EXECUTE') "
                        "AS api_execute,"
                        "has_function_privilege('night_voyager_worker',p.oid,'EXECUTE') "
                        "AS worker_execute "
                        "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                        "WHERE n.nspname='app' "
                        "AND p.oid=to_regprocedure(:signature)"
                    ),
                    {"signature": SIGNATURE},
                )
            ).mappings().one()
            assert catalog["prosecdef"] is True
            assert catalog["proconfig"] == ["search_path=pg_catalog, pg_temp"]
            assert catalog["public_execute"] is False
            assert catalog["api_execute"] is False
            assert catalog["worker_execute"] is False
            if phase == "restored-0013":
                return

        async with engine.begin() as connection:
            await _set_context(connection)
            await _seed_anchor(
                connection,
                case_id=HAPPY_CASE,
                thread_id=HAPPY_THREAD,
            )
            await _seed_anchor(
                connection,
                case_id=BUDGET_CASE,
                thread_id=BUDGET_THREAD,
            )

            for setup_sql, setup_parameters in (
                (
                    "INSERT INTO app.message_events("
                    "organization_id,id,thread_id,case_id,sequence_no,actor_id,"
                    "actor_role,body,content_sha256,request_sha256,created_at) "
                    "VALUES(:org,:message,:thread,:case,1,:student,'student',"
                    "'Synthetic initial preferred countries.',:body_hash,:message_hash,"
                    "timestamptz '2026-01-01 00:00:01+00')",
                    {
                        **_helper_parameters(),
                        "body_hash": BODY_HASH,
                    },
                ),
                (
                    "INSERT INTO app.message_events("
                    "organization_id,id,thread_id,case_id,sequence_no,actor_id,"
                    "actor_role,body,content_sha256,request_sha256,created_at) "
                    "VALUES(:org,:message,:thread,:case,1,:student,'student',"
                    "'Drifted synthetic body.',repeat('f',64),:message_hash,"
                    "timestamptz '2026-01-01 00:00:01+00')",
                    _helper_parameters(),
                ),
                (
                    "INSERT INTO app.message_events("
                    "organization_id,id,thread_id,case_id,sequence_no,actor_id,"
                    "actor_role,body,content_sha256,request_sha256,created_at) "
                    "VALUES(:org,:message,:budget_thread,:budget_case,1,:student,"
                    "'student','Synthetic collision.',repeat('e',64),repeat('d',64),"
                    "timestamptz '2026-01-01 00:00:01+00')",
                    {
                        **_helper_parameters(),
                        "budget_thread": BUDGET_THREAD,
                        "budget_case": BUDGET_CASE,
                    },
                ),
            ):
                nested = await connection.begin_nested()
                try:
                    await connection.execute(
                        text(setup_sql),
                        setup_parameters,
                    )
                    with pytest.raises(
                        DBAPIError,
                        match="planning revision demo seed mismatch",
                    ):
                        await _call_helper(connection)
                finally:
                    await nested.rollback()
                assert await _authority_count(connection) == 0

            invalid = _helper_parameters()
            invalid["value_hash"] = "f" * 64
            nested = await connection.begin_nested()
            try:
                with pytest.raises(
                    DBAPIError,
                    match="planning revision demo seed mismatch",
                ):
                    await _call_helper(connection, invalid)
            finally:
                await nested.rollback()
            assert await _authority_count(connection) == 0

            await _call_helper(connection)
            assert await _authority_count(connection) == 5
            await _call_helper(connection)
            assert await _authority_count(connection) == 5
    finally:
        await engine.dispose()
