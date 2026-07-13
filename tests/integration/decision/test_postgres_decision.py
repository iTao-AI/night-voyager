from __future__ import annotations

import json
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import date
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

pytestmark = pytest.mark.database
ORG = UUID("10000000-0000-0000-0000-000000000001")
CASE = UUID("40000000-0000-0000-0000-000000000001")
RUN = UUID("70000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
PARENT = UUID("20000000-0000-0000-0000-000000000003")
AUSTRALIA = UUID("71000000-0000-0000-0000-000000000001")
OTHER_ORG = UUID("10000000-0000-0000-0000-000000000002")
UNLINKED_EVIDENCE = UUID("60000000-0000-0000-0000-000000000097")


async def context(connection: AsyncConnection, actor: UUID, role: str) -> None:
    for key, value in (("organization_id", ORG), ("actor_id", actor), ("role", role)):
        await connection.execute(
            text("SELECT set_config(:key,:value,true)"),
            {"key": f"night_voyager.{key}", "value": str(value)},
        )


@asynccontextmanager
async def rollback_connection(engine: AsyncEngine) -> AsyncGenerator[AsyncConnection]:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            yield connection
        finally:
            if transaction.is_active:
                await transaction.rollback()


def review_sql() -> str:
    return (
        "SELECT * FROM app.review_planning_run("
        ":org,:actor,:case,:run,1,'approve_for_consultation',:review,"
        "CAST(:eligible AS jsonb),CAST(:risks AS jsonb),NULL,:brief,CAST(:projection AS jsonb),"
        ":source_date,:key_hash,:request_hash)"
    )


def canonical_projection(
    risks: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "eligible_route_ids": [str(AUSTRALIA)],
        "routes": [
            {
                "route_id": str(AUSTRALIA),
                "country": "australia",
                "outcome": "recommended_with_condition",
                "reason_code": "complete_cost_and_fx_within_boundary",
            },
            {
                "route_id": "71000000-0000-0000-0000-000000000002",
                "country": "japan",
                "outcome": "conditional",
                "reason_code": "synthetic_high_risk_alternative",
            },
            {
                "route_id": "71000000-0000-0000-0000-000000000003",
                "country": "malaysia",
                "outcome": "blocked",
                "reason_code": "direct_program_fit_evidence_absent",
            },
        ],
        "intake": "2027-02",
        "accepted_evidence_risks": risks or [],
        "synthetic_proof": True,
    }


@pytest.mark.asyncio
async def test_api_role_rejects_projection_and_source_date_mismatch() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with rollback_connection(engine) as connection:
            await context(connection, ADVISOR, "advisor")
            with pytest.raises(DBAPIError) as raised:
                await connection.execute(
                    text(review_sql()),
                    {
                        "org": ORG,
                        "actor": ADVISOR,
                        "case": CASE,
                        "run": RUN,
                        "review": UUID("80000000-0000-0000-0000-000000000101"),
                        "brief": UUID("81000000-0000-0000-0000-000000000101"),
                        "eligible": json.dumps([str(AUSTRALIA)]),
                        "risks": "[]",
                        "projection": json.dumps(
                            {
                                "schema_version": 1,
                                "eligible_route_ids": [
                                    "71000000-0000-0000-0000-000000000002"
                                ],
                                "routes": [],
                                "intake": "2027-02",
                                "accepted_evidence_risks": [],
                                "synthetic_proof": True,
                            }
                        ),
                        "source_date": date(2099, 1, 1),
                        "key_hash": "a" * 64,
                        "request_hash": "b" * 64,
                    },
                )
            assert getattr(raised.value.orig, "sqlstate", None) == "NV006"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_api_role_rejects_caller_controlled_timeline() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with rollback_connection(engine) as connection:
            await context(connection, ADVISOR, "advisor")
            projection = canonical_projection()
            brief = UUID("81000000-0000-0000-0000-000000000102")
            await connection.execute(
                text(review_sql()),
                {
                    "org": ORG,
                    "actor": ADVISOR,
                    "case": CASE,
                    "run": RUN,
                    "review": UUID("80000000-0000-0000-0000-000000000102"),
                    "brief": brief,
                    "eligible": json.dumps([str(AUSTRALIA)]),
                    "risks": "[]",
                    "projection": json.dumps(projection),
                    "source_date": date(2026, 7, 1),
                    "key_hash": "c" * 64,
                    "request_hash": "d" * 64,
                },
            )
            await context(connection, PARENT, "parent")
            with pytest.raises(DBAPIError) as raised:
                await connection.execute(
                    text(
                        "SELECT * FROM app.decide_family_brief("
                        ":org,:actor,'parent',:brief,1,:decision,:receipt,:route,30000000,"
                        "40000000,'CNY','[\"budget_elasticity\"]'::jsonb,:actor,'direct',"
                        ":timeline,CAST(:milestones AS jsonb),:key_hash,:request_hash)"
                    ),
                    {
                        "org": ORG,
                        "actor": PARENT,
                        "brief": brief,
                        "decision": UUID("82000000-0000-0000-0000-000000000102"),
                        "receipt": UUID("83000000-0000-0000-0000-000000000102"),
                        "route": AUSTRALIA,
                        "timeline": UUID("84000000-0000-0000-0000-000000000102"),
                        "milestones": json.dumps(
                            [{"key": "caller_controlled", "due_date": "2099-12-31"}]
                        ),
                        "key_hash": "e" * 64,
                        "request_hash": "f" * 64,
                    },
                )
            assert getattr(raised.value.orig, "sqlstate", None) == "NV006"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_api_role_allows_only_bounded_advisor_recorded_decision() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with rollback_connection(engine) as connection:
            await context(connection, ADVISOR, "advisor")
            brief = UUID("81000000-0000-0000-0000-000000000103")
            linked_risk = {
                "evidence_id": "60000000-0000-0000-0000-000000000005",
                "kind": "unverified",
                "reason": "explicit audited Japan alternative risk",
            }
            await connection.execute(
                text(review_sql()),
                {
                    "org": ORG,
                    "actor": ADVISOR,
                    "case": CASE,
                    "run": RUN,
                    "review": UUID("80000000-0000-0000-0000-000000000103"),
                    "brief": brief,
                    "eligible": json.dumps([str(AUSTRALIA)]),
                    "risks": json.dumps([linked_risk]),
                    "projection": json.dumps(canonical_projection([linked_risk])),
                    "source_date": date(2026, 7, 1),
                    "key_hash": "a1" * 32,
                    "request_hash": "b1" * 32,
                },
            )
            row = (
                await connection.execute(
                    text(
                        "SELECT * FROM app.decide_family_brief("
                        ":org,:actor,'advisor',:brief,1,:decision,:receipt,:route,30000000,"
                        "40000000,'CNY','[\"budget_elasticity\"]'::jsonb,:made_by,"
                        "'family_consultation',:timeline,CAST(:milestones AS jsonb),"
                        ":key_hash,:request_hash)"
                    ),
                    {
                        "org": ORG,
                        "actor": ADVISOR,
                        "brief": brief,
                        "decision": UUID("82000000-0000-0000-0000-000000000103"),
                        "receipt": UUID("83000000-0000-0000-0000-000000000103"),
                        "route": AUSTRALIA,
                        "made_by": PARENT,
                        "timeline": UUID("84000000-0000-0000-0000-000000000103"),
                        "milestones": json.dumps(
                            [
                                {"key": "documents", "due_date": "2026-09-01"},
                                {"key": "application", "due_date": "2026-10-15"},
                                {"key": "visa", "due_date": "2026-12-15"},
                                {"key": "arrival", "due_date": "2027-01-20"},
                            ]
                        ),
                        "key_hash": "c1" * 32,
                        "request_hash": "d1" * 32,
                    },
                )
            ).mappings().one()
            assert row["replayed"] is False
            assert (
                await connection.scalar(
                    text("SELECT state FROM app.student_cases WHERE id=:case"),
                    {"case": CASE},
                )
                == "plan_ready"
            )
    finally:
        await engine.dispose()


@pytest.mark.parametrize("action", ["reject", "request_revision"])
@pytest.mark.asyncio
async def test_api_role_records_nonapproval_without_brief(action: str) -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with rollback_connection(engine) as connection:
            await context(connection, ADVISOR, "advisor")
            row = (
                await connection.execute(
                    text(
                        "SELECT * FROM app.review_planning_run("
                        ":org,:actor,:case,:run,1,:action,:review,'[]'::jsonb,'[]'::jsonb,"
                        "'bounded note',NULL,'{}'::jsonb,'1970-01-01',:key_hash,:request_hash)"
                    ),
                    {
                        "org": ORG,
                        "actor": ADVISOR,
                        "case": CASE,
                        "run": RUN,
                        "action": action,
                        "review": UUID(
                            "80000000-0000-0000-0000-000000000201"
                            if action == "reject"
                            else "80000000-0000-0000-0000-000000000202"
                        ),
                        "key_hash": ("1" if action == "reject" else "2") * 64,
                        "request_hash": "3" * 64,
                    },
                )
            ).mappings().one()
            assert row["brief_id"] is None
            assert row["case_state"] == "planning"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_api_role_rejects_wrong_role_stale_run_and_cross_run_risk() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            await context(connection, PARENT, "parent")
            with pytest.raises(DBAPIError) as wrong_role:
                await connection.execute(
                    text(review_sql()),
                    {
                        "org": ORG,
                        "actor": PARENT,
                        "case": CASE,
                        "run": RUN,
                        "review": UUID(int=301),
                        "brief": UUID(int=302),
                        "eligible": json.dumps([str(AUSTRALIA)]),
                        "risks": "[]",
                        "projection": "{}",
                        "source_date": date(2026, 7, 1),
                        "key_hash": "4" * 64,
                        "request_hash": "5" * 64,
                    },
                )
            assert getattr(wrong_role.value.orig, "sqlstate", None) == "NV007"
            await transaction.rollback()

            transaction = await connection.begin()
            await context(connection, ADVISOR, "advisor")
            with pytest.raises(DBAPIError) as stale:
                await connection.execute(
                    text(review_sql().replace(":run,1", ":run,2")),
                    {
                        "org": ORG,
                        "actor": ADVISOR,
                        "case": CASE,
                        "run": RUN,
                        "review": UUID(int=303),
                        "brief": UUID(int=304),
                        "eligible": json.dumps([str(AUSTRALIA)]),
                        "risks": "[]",
                        "projection": "{}",
                        "source_date": date(2026, 7, 1),
                        "key_hash": "6" * 64,
                        "request_hash": "7" * 64,
                    },
                )
            assert getattr(stale.value.orig, "sqlstate", None) == "NV003"
            await transaction.rollback()

            transaction = await connection.begin()
            await context(connection, ADVISOR, "advisor")
            with pytest.raises(DBAPIError) as cross_run_risk:
                await connection.execute(
                    text(review_sql()),
                    {
                        "org": ORG,
                        "actor": ADVISOR,
                        "case": CASE,
                        "run": RUN,
                        "review": UUID(int=305),
                        "brief": UUID(int=306),
                        "eligible": json.dumps([str(AUSTRALIA)]),
                        "risks": json.dumps(
                            [
                                {
                                    "evidence_id": "60000000-0000-0000-0000-000000000099",
                                    "kind": "optional",
                                    "reason": "explicit synthetic cross-run probe",
                                }
                            ]
                        ),
                        "projection": "{}",
                        "source_date": date(2026, 7, 1),
                        "key_hash": "8" * 64,
                        "request_hash": "9" * 64,
                    },
                )
            assert getattr(cross_run_risk.value.orig, "sqlstate", None) == "NV006"
            await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_api_role_rejects_same_pack_evidence_not_linked_to_reviewed_run() -> None:
    migration_engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with migration_engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.evidence_refs(organization_id,id,source_pack_id,"
                    "source_pack_version,source_entry_id,claim,authority,source_sha256) "
                    "SELECT organization_id,:evidence,source_pack_id,source_pack_version,id,"
                    "'malaysia_context','accepted_synthetic_demo',sha256 "
                    "FROM app.source_pack_entries WHERE organization_id=:org AND "
                    "source_pack_id='50000000-0000-0000-0000-000000000001' AND "
                    "source_pack_version=1 AND id='51000000-0000-0000-0000-000000000003' "
                    "ON CONFLICT DO NOTHING"
                ),
                {"org": ORG, "evidence": UNLINKED_EVIDENCE},
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.evidence_refs WHERE organization_id=:org "
                        "AND id=:evidence AND source_pack_id="
                        "'50000000-0000-0000-0000-000000000001' "
                        "AND source_pack_version=1 AND claim='malaysia_context'"
                    ),
                    {"org": ORG, "evidence": UNLINKED_EVIDENCE},
                )
                == 1
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT (SELECT count(*) FROM app.comparison_dimension_evidence_refs "
                        "WHERE organization_id=:org AND planning_run_id=:run "
                        "AND evidence_ref_id=:evidence) + "
                        "(SELECT count(*) FROM app.cost_evidence WHERE organization_id=:org "
                        "AND planning_run_id=:run AND :evidence IN "
                        "(tuition_evidence_id,living_evidence_id,fx_evidence_id)) + "
                        "(SELECT count(*) FROM app.ranking_evidence WHERE organization_id=:org "
                        "AND planning_run_id=:run AND evidence_ref_id=:evidence)"
                    ),
                    {"org": ORG, "run": RUN, "evidence": UNLINKED_EVIDENCE},
                )
                == 0
            )
    finally:
        await migration_engine.dispose()

    risk = {
        "evidence_id": str(UNLINKED_EVIDENCE),
        "kind": "optional",
        "reason": "same-pack evidence is absent from the reviewed projection",
    }
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with rollback_connection(engine) as connection:
            await context(connection, ADVISOR, "advisor")
            savepoint = await connection.begin_nested()
            with pytest.raises(DBAPIError) as rejected:
                await connection.execute(
                    text(review_sql()),
                    {
                        "org": ORG,
                        "actor": ADVISOR,
                        "case": CASE,
                        "run": RUN,
                        "review": UUID(int=307),
                        "brief": UUID(int=308),
                        "eligible": json.dumps([str(AUSTRALIA)]),
                        "risks": json.dumps([risk]),
                        "projection": json.dumps(canonical_projection([risk])),
                        "source_date": date(2026, 7, 1),
                        "key_hash": "aa" * 32,
                        "request_hash": "bb" * 32,
                    },
                )
            assert getattr(rejected.value.orig, "sqlstate", None) == "NV006"
            await savepoint.rollback()
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.advisor_reviews WHERE organization_id=:org "
                        "AND id=:review"
                    ),
                    {"org": ORG, "review": UUID(int=307)},
                )
                == 0
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.decision_briefs WHERE organization_id=:org "
                        "AND id=:brief"
                    ),
                    {"org": ORG, "brief": UUID(int=308)},
                )
                == 0
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_m3b_rows_are_hidden_across_real_tenants_and_api_cannot_write_tables() -> None:
    migration_engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with migration_engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(OTHER_ORG)},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.organizations(id,name,is_synthetic) "
                    "VALUES(:org,'Other synthetic tenant',true) ON CONFLICT DO NOTHING"
                ),
                {"org": OTHER_ORG},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.student_cases(organization_id,id,state,current_revision) "
                    "VALUES(:org,'40000000-0000-0000-0000-000000000002','intake',NULL) "
                    "ON CONFLICT DO NOTHING"
                ),
                {"org": OTHER_ORG},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.actors(id,organization_id,display_name,is_synthetic) "
                    "VALUES('20000000-0000-0000-0000-000000000099',:org,"
                    "'Other synthetic advisor',true) ON CONFLICT DO NOTHING"
                ),
                {"org": OTHER_ORG},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.memberships(id,organization_id,actor_id,role) "
                    "VALUES('30000000-0000-0000-0000-000000000099',:org,"
                    "'20000000-0000-0000-0000-000000000099','advisor') "
                    "ON CONFLICT (organization_id,actor_id,role) DO NOTHING"
                ),
                {"org": OTHER_ORG},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.student_case_participants "
                    "VALUES(:org,'40000000-0000-0000-0000-000000000002',"
                    "'20000000-0000-0000-0000-000000000099','advisor') ON CONFLICT DO NOTHING"
                ),
                {"org": OTHER_ORG},
            )
    finally:
        await migration_engine.dispose()

    engine = create_async_engine(
        os.environ["NIGHT_VOYAGER_API_DATABASE_URL"], pool_size=1, max_overflow=0
    )
    try:
        async with rollback_connection(engine) as connection:
            await context(connection, ADVISOR, "advisor")
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.student_case_participants "
                        "WHERE organization_id=:other"
                    ),
                    {"other": OTHER_ORG},
                )
                == 0
            )
            with pytest.raises(DBAPIError) as denied:
                await connection.execute(
                    text(
                        "INSERT INTO app.student_case_participants "
                        "VALUES(:org,:case,:actor,'advisor')"
                    ),
                    {"org": ORG, "case": CASE, "actor": ADVISOR},
                )
            assert getattr(denied.value.orig, "sqlstate", None) == "42501"
        async with rollback_connection(engine) as connection:
            assert await connection.scalar(text("SELECT count(*) FROM app.audit_events")) == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_api_role_cannot_update_append_only_review_directly() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with rollback_connection(engine) as connection:
            await context(connection, ADVISOR, "advisor")
            with pytest.raises(DBAPIError) as denied:
                await connection.execute(text("UPDATE app.advisor_reviews SET reviewer_notes='x'"))
            assert getattr(denied.value.orig, "sqlstate", None) == "42501"
    finally:
        await engine.dispose()
