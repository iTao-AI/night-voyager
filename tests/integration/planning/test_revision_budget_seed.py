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
CASES = [UUID(f"49000000-0000-0000-0000-{index:012d}") for index in (1, 2)]
SIGNATURE = "app.seed_demo_planning_revision_budget(uuid,uuid)"


async def set_context(connection: AsyncConnection) -> None:
    await connection.execute(
        text("SELECT set_config('night_voyager.organization_id',:org,true)"), {"org": str(ORG)}
    )


async def lineage_snapshot() -> dict[str, tuple[object, ...]]:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await set_context(connection)
            snapshot: dict[str, tuple[object, ...]] = {}
            for table in (
                "message_events",
                "memory_candidates",
                "memory_candidate_verifications",
                "confirmed_facts",
                "case_revision_confirmed_fact_refs",
            ):
                snapshot[table] = tuple(
                    (
                        await connection.execute(
                            text(
                                f"SELECT to_jsonb(r) FROM app.{table} r "
                                "WHERE r.organization_id=:org AND r.case_id=:case "
                                "ORDER BY to_jsonb(r)::text"
                            ),
                            {"org": ORG, "case": CASES[0]},
                        )
                    )
                    .scalars()
                    .all()
                )
            return snapshot
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("case_id", CASES)
async def test_initial_budget_has_exact_lineage_and_precedes_baseline_execution(
    case_id: UUID,
) -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await set_context(connection)
            row = (
                (
                    await connection.execute(
                        text(
                            "SELECT "
                            "f.id,f.value,f.value_sha256,f.fact_version,f.subject_role,f.supersedes_fact_id,f.confirmed_at,m.id"
                            " AS "
                            "message_id,m.sequence_no,m.body,m.content_sha256,m.created_at"
                            " AS "
                            "message_at,c.id AS candidate_id,c.created_at AS "
                            "candidate_at,c.expires_at,c.value_sha256 AS "
                            "candidate_hash,c.request_sha256 "
                            "AS request_hash,v.id AS "
                            "verification_id,v.reason,v.result_revision,v.created_at"
                            " AS "
                            "verification_at,r.case_revision,e.started_at FROM "
                            "app.confirmed_facts f JOIN"
                            " app.message_events m ON "
                            "m.organization_id=f.organization_id AND "
                            "m.id=f.source_message_event_id JOIN "
                            "app.memory_candidates c ON "
                            "c.organization_id=f.organization_id AND "
                            "c.id=f.source_candidate_id JOIN "
                            "app.memory_candidate_verifications v ON "
                            "v.organization_id=f.organization_id "
                            "AND v.result_fact_id=f.id JOIN "
                            "app.case_revision_confirmed_fact_refs r ON "
                            "r.organization_id=f.organization_id AND "
                            "r.confirmed_fact_id=f.id JOIN "
                            "app.agent_tasks t ON "
                            "t.organization_id=f.organization_id AND "
                            "t.case_id=f.case_id JOIN app.agent_executions e ON "
                            "e.organization_id=f.organization_id AND "
                            "e.task_id=t.id WHERE f.organization_id=:org AND "
                            "f.case_id=:case AND "
                            "f.fact_key='family.budget'"
                        ),
                        {"org": ORG, "case": case_id},
                    )
                )
                .mappings()
                .one()
            )
            suffix = int(str(case_id)[-12:]) + 100
            for field, prefix in (
                ("id", "4f"),
                ("message_id", "4c"),
                ("candidate_id", "4d"),
                ("verification_id", "4e"),
            ):
                assert row[field] == UUID(f"{prefix}000000-0000-0000-0000-{suffix:012d}")
            assert row[
                "value"
            ] == validate_planning_fixture().planning_input.case.family.budget.model_dump(
                mode="json"
            )
            assert row["value_sha256"] == row["candidate_hash"] == canonical_sha256(row["value"])
            assert row["body"] == "Synthetic initial family budget."
            assert row["content_sha256"] == hashlib.sha256(row["body"].encode()).hexdigest()
            assert (
                row["request_hash"]
                == hashlib.sha256(f"revision-budget-seed-candidate:{case_id}".encode()).hexdigest()
            )
            assert row["subject_role"] == "parent" and row["supersedes_fact_id"] is None
            assert row["fact_version"] == row["case_revision"] == row["result_revision"] == 1
            assert row["sequence_no"] == 2
            assert row["reason"] == "Synthetic initial budget fact seed."
            assert (
                row["message_at"] < row["candidate_at"] < row["confirmed_at"] <= row["started_at"]
            )
            assert row["verification_at"] == row["confirmed_at"]
            assert (row["expires_at"] - row["candidate_at"]).days == 7
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_budget_seed_helper_catalog_and_migration_phase() -> None:
    phase = os.environ.get("NIGHT_VOYAGER_BUDGET_SEED_PHASE")
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            found = await connection.scalar(
                text("SELECT to_regprocedure(:signature)::text"), {"signature": SIGNATURE}
            )
            if phase == "absent-0015":
                assert found is None
                return
            assert found == SIGNATURE
            catalog = (
                (
                    await connection.execute(
                        text(
                            "SELECT "
                            "p.prosecdef,p.proconfig,has_function_privilege('public',p.oid,'EXECUTE')"
                            " AS "
                            "public,has_function_privilege('night_voyager_api',p.oid,'EXECUTE')"
                            " AS "
                            "api,has_function_privilege('night_voyager_worker',p.oid,'EXECUTE')"
                            " AS worker"
                            " FROM pg_proc p WHERE p.oid=to_regprocedure(:signature)"
                        ),
                        {"signature": SIGNATURE},
                    )
                )
                .mappings()
                .one()
            )
            assert catalog["prosecdef"] is True
            assert catalog["proconfig"] == ["search_path=pg_catalog, pg_temp"]
            assert not catalog["public"] and not catalog["api"] and not catalog["worker"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_student_budget_proposal_is_denied_without_changing_initial_lineage() -> None:
    student = UUID("20000000-0000-0000-0000-000000000002")
    value = validate_planning_fixture().planning_input.case.family.budget.model_dump(mode="json")
    value["hard_ceiling_minor"] = 39000000
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    original_lineage = await lineage_snapshot()
    try:
        async with engine.begin() as connection:
            for key, setting in {
                "organization_id": str(ORG),
                "actor_id": str(student),
                "role": "student",
            }.items():
                await connection.execute(
                    text("SELECT set_config(:key,:value,true)"),
                    {"key": f"night_voyager.{key}", "value": setting},
                )
            statement = text(
                "SELECT projection FROM "
                "app.read_confirmed_facts(:org,:actor,'student',:case,NULL,NULL,NULL,20)"
            )
            parameters = {"org": ORG, "actor": student, "case": CASES[0]}
            before = (await connection.execute(statement, parameters)).scalars().all()
            with pytest.raises(DBAPIError, match="unsupported collaboration fact") as rejected:
                async with connection.begin_nested():
                    await connection.execute(
                        text(
                            "SELECT * FROM "
                            "app.propose_memory_candidate(:org,:actor,'student',:message,:candidate,1,'family.budget',CAST(:value"
                            " AS jsonb),:value_hash,:request_hash,:key_hash)"
                        ),
                        {
                            **parameters,
                            "message": UUID("4c000000-0000-0000-0000-000000000001"),
                            "candidate": UUID("4d000000-0000-0000-0000-000000000199"),
                            "value": json.dumps(value),
                            "value_hash": canonical_sha256(value),
                            "request_hash": hashlib.sha256(b"student-budget-denial").hexdigest(),
                            "key_hash": hashlib.sha256(b"student-budget-denial-key").hexdigest(),
                        },
                    )
            assert getattr(rejected.value.orig, "sqlstate", None) == "NV006"
            assert (await connection.execute(statement, parameters)).scalars().all() == before
        assert await lineage_snapshot() == original_lineage
    finally:
        await engine.dispose()
    for role in ("API", "WORKER"):
        runtime = create_async_engine(os.environ[f"NIGHT_VOYAGER_{role}_DATABASE_URL"])
        try:
            async with runtime.begin() as connection:
                with pytest.raises(DBAPIError, match="permission denied"):
                    await connection.execute(
                        text("SELECT app.seed_demo_planning_revision_budget(:org,:case)"),
                        {"org": ORG, "case": CASES[0]},
                    )
        finally:
            await runtime.dispose()


@pytest.mark.asyncio
async def test_closed_budget_seed_helper_exact_replay_and_atomic_rejection() -> None:
    if os.environ.get("NIGHT_VOYAGER_BUDGET_SEED_PHASE") != "authority-0016":
        pytest.skip("isolated fresh budget helper migration phase only")
    from tests.integration.planning import test_revision_seed_migration as country

    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await set_context(connection)
                await country.seed_anchor(
                    connection, case_id=CASES[0], thread_id=country.HAPPY_THREAD
                )
                await country.call_helper(connection)
                for drift in (
                    "INSERT INTO "
                    "app.message_events(organization_id,id,thread_id,case_id,sequence_no,actor_id,actor_role,body,content_sha256,request_sha256,created_at)"
                    " "
                    "VALUES('10000000-0000-0000-0000-000000000001','4c000000-0000-0000-0000-000000000101','4b000000-0000-0000-0000-000000000001',:case,2,'20000000-0000-0000-0000-000000000003','parent','Synthetic"
                    " initial family "
                    "budget.',repeat('f',64),repeat('a',64),timestamptz "
                    "'2026-01-01 00:00:01+00')",
                    "UPDATE app.student_case_revisions SET "
                    "family_preferences=jsonb_set(family_preferences,'{budget,preferred_minor}','30000000')"
                    " WHERE case_id=:case",
                    "UPDATE app.student_cases SET current_revision=NULL WHERE id=:case",
                ):
                    nested = await connection.begin_nested()
                    try:
                        await connection.execute(text(drift), {"case": CASES[0]})
                        drift_count = await country.authority_count(connection)
                        with pytest.raises(
                            DBAPIError, match="planning revision demo seed mismatch"
                        ):
                            async with connection.begin_nested():
                                await connection.execute(
                                    text(
                                        "SELECT app.seed_demo_planning_revision_budget(:org,:case)"
                                    ),
                                    {"org": ORG, "case": CASES[0]},
                                )
                        assert await country.authority_count(connection) == drift_count
                    finally:
                        await nested.rollback()
                with pytest.raises(DBAPIError, match="planning revision demo seed mismatch"):
                    async with connection.begin_nested():
                        await connection.execute(
                            text("SELECT app.seed_demo_planning_revision_budget(:org,:case)"),
                            {"org": ORG, "case": UUID("49000000-0000-0000-0000-000000000099")},
                        )
                await connection.execute(
                    text("SELECT app.seed_demo_planning_revision_budget(:org,:case)"),
                    {"org": ORG, "case": CASES[0]},
                )
                assert await country.authority_count(connection) == 10
                snapshot = (
                    (
                        await connection.execute(
                            text(
                                "SELECT to_jsonb(f) FROM app.confirmed_facts f WHERE "
                                "case_id=:case ORDER BY id"
                            ),
                            {"case": CASES[0]},
                        )
                    )
                    .scalars()
                    .all()
                )
                await connection.execute(
                    text("SELECT app.seed_demo_planning_revision_budget(:org,:case)"),
                    {"org": ORG, "case": CASES[0]},
                )
                assert (
                    await connection.execute(
                        text(
                            "SELECT to_jsonb(f) FROM app.confirmed_facts f WHERE "
                            "case_id=:case ORDER BY id"
                        ),
                        {"case": CASES[0]},
                    )
                ).scalars().all() == snapshot
                for drift in (
                    "DELETE FROM app.case_revision_confirmed_fact_refs "
                    "WHERE case_id=:case AND "
                    "fact_key='family.budget'",
                    "UPDATE app.memory_candidates SET "
                    "request_sha256=repeat('e',64) WHERE "
                    "case_id=:case AND fact_key='family.budget'",
                    "UPDATE app.memory_candidate_verifications SET "
                    "reason='Different initial "
                    "reason' WHERE case_id=:case AND "
                    "result_fact_id='4f000000-0000-0000-0000-000000000101'",
                ):
                    nested = await connection.begin_nested()
                    try:
                        try:
                            async with connection.begin_nested():
                                await connection.execute(text(drift), {"case": CASES[0]})
                        except DBAPIError as error:
                            assert "immutable collaboration authority record" in str(error)
                            assert await country.authority_count(connection) == 10
                            continue
                        count = await country.authority_count(connection)
                        with pytest.raises(
                            DBAPIError, match="planning revision demo seed mismatch"
                        ):
                            async with connection.begin_nested():
                                await connection.execute(
                                    text(
                                        "SELECT app.seed_demo_planning_revision_budget(:org,:case)"
                                    ),
                                    {"org": ORG, "case": CASES[0]},
                                )
                        assert await country.authority_count(connection) == count
                    finally:
                        await nested.rollback()
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("case_id", CASES)
@pytest.mark.parametrize("role", ["parent", "student"])
async def test_canonical_initial_budget_is_safe_shared_fact_for_real_participants(
    case_id: UUID, role: str
) -> None:
    actor = UUID(f"20000000-0000-0000-0000-{3 if role == 'parent' else 2:012d}")
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            for key, value in {
                "organization_id": str(ORG),
                "actor_id": str(actor),
                "role": role,
            }.items():
                await connection.execute(
                    text("SELECT set_config(:key,:value,true)"),
                    {"key": f"night_voyager.{key}", "value": value},
                )
            rows = (
                (
                    await connection.execute(
                        text(
                            "SELECT projection FROM "
                            "app.read_confirmed_facts(:org,:actor,:role,:case,NULL,NULL,NULL,20)"
                        ),
                        {"org": ORG, "actor": actor, "role": role, "case": case_id},
                    )
                )
                .scalars()
                .all()
            )
            budgets = [row for row in rows if row["fact_key"] == "family.budget"]
            assert len(budgets) == 1
            assert budgets[0][
                "value"
            ] == validate_planning_fixture().planning_input.case.family.budget.model_dump(
                mode="json"
            )
            assert budgets[0]["subject_role"] == "parent"
            assert budgets[0]["fact_version"] == 1
            assert set(budgets[0]) == {
                "schema_version",
                "fact_key",
                "value",
                "fact_version",
                "confirmed_at",
                "subject_role",
                "confirming_advisor_role",
            }
            assert {row["fact_key"] for row in rows} == {
                "student.preferred_countries",
                "family.budget",
            }
    finally:
        await engine.dispose()
