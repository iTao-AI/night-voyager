from __future__ import annotations

import json
import os
from typing import Any, cast
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.sql.elements import TextClause

from night_voyager.adapters.deterministic_planning import DeterministicPlanningAdapter
from night_voyager.adapters.governed_mixed_planning import GovernedMixedPlanningAdapter
from night_voyager.adapters.router import PlanningAdapterRouter
from night_voyager.identity.models import ActorContext, ActorRole
from night_voyager.planning.fixtures import validate_planning_fixture
from night_voyager.planning.mixed_postgres import PostgresMixedPlanningRepository
from night_voyager.planning.synthetic_postgres import (
    PersistedSyntheticSnapshotRepository,
)
from night_voyager.skills.registry import SkillRuntimeRegistry
from night_voyager.tasks.application import CreateTaskCommand, TaskService
from night_voyager.tasks.models import PlanningOperation
from night_voyager.tasks.postgres import (
    PostgresTaskRepository,
    postgres_worker_repository_factory,
)
from night_voyager.tasks.worker import TaskWorker
from tests.integration.dra.test_postgres_mixed_snapshot import approved_pack

DEMO_ORG = "10000000-0000-0000-0000-000000000001"
DEMO_CASE = "40000000-0000-0000-0000-000000000002"
DEMO_PACK = "50000000-0000-0000-0000-000000000001"
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
STUDENT = UUID("20000000-0000-0000-0000-000000000002")
PARENT = UUID("20000000-0000-0000-0000-000000000003")
PLANNING_FIXTURE = validate_planning_fixture().planning_input


def registry() -> SkillRuntimeRegistry:
    return SkillRuntimeRegistry.load_packaged()


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


async def _seed_selected_case(case_id: UUID, countries: tuple[str, ...]) -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    student = PLANNING_FIXTURE.case.student.model_dump(mode="json")
    student["preferred_countries"] = list(countries)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": DEMO_ORG},
            )
            await connection.execute(
                text(
                    "SELECT app.publish_case_revision("
                    ":org,:case,NULL,1,CAST(:student AS jsonb),CAST(:family AS jsonb))"
                ),
                {
                    "org": DEMO_ORG,
                    "case": case_id,
                    "student": json.dumps(student),
                    "family": PLANNING_FIXTURE.case.family.model_dump_json(),
                },
            )
            await connection.execute(
                text("SELECT app.transition_case(:org,:case,'intake','planning')"),
                {"org": DEMO_ORG, "case": case_id},
            )
            await connection.execute(
                text("SELECT app.seed_case_participants(:org,:case,:advisor,:student,:parent)"),
                {
                    "org": DEMO_ORG,
                    "case": case_id,
                    "advisor": ADVISOR,
                    "student": STUDENT,
                    "parent": PARENT,
                },
            )
    finally:
        await engine.dispose()


async def _execute_selected_case(
    *,
    case_id: UUID,
    task_id: UUID,
    operation: PlanningOperation,
    source_pack_version: int,
) -> UUID:
    api_engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    worker_engine = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    api_sessions = async_sessionmaker(api_engine, expire_on_commit=False)
    worker_sessions = async_sessionmaker(worker_engine, expire_on_commit=False)
    try:
        async with api_sessions() as session, session.begin():
            for name, value in (
                ("night_voyager.organization_id", DEMO_ORG),
                ("night_voyager.actor_id", str(ADVISOR)),
                ("night_voyager.role", "advisor"),
            ):
                await session.execute(
                    text("SELECT set_config(:name,:value,true)"),
                    {"name": name, "value": value},
                )
            created = await TaskService(
                PostgresTaskRepository(session),
                registry=registry(),
                id_factory=lambda: task_id,
            ).create(
                ActorContext(UUID(DEMO_ORG), ADVISOR, ActorRole.ADVISOR, UUID(int=1)),
                CreateTaskCommand(
                    case_id=case_id,
                    operation=operation,
                    expected_case_revision=1,
                    source_pack_id=UUID(DEMO_PACK),
                    source_pack_version=source_pack_version,
                ),
                f"selected-case-{task_id}",
            )
            assert created["skill_pin"] is not None
        worker = TaskWorker(
            postgres_worker_repository_factory(worker_sessions),
            PlanningAdapterRouter(
                synthetic=DeterministicPlanningAdapter(
                    PersistedSyntheticSnapshotRepository(worker_sessions)
                ),
                mixed=GovernedMixedPlanningAdapter(
                    PostgresMixedPlanningRepository(worker_sessions)
                ),
            ),
            registry(),
            worker_id=f"selected-case-{task_id}",
        )
        assert await worker.run_once() is True
        async with api_engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": DEMO_ORG},
            )
            task = (
                await connection.execute(
                    text(
                        "SELECT state,result_planning_run_id FROM app.agent_tasks "
                        "WHERE organization_id=:org AND id=:task"
                    ),
                    {"org": DEMO_ORG, "task": task_id},
                )
            ).mappings().one()
        assert task.state == (
            "blocked" if operation == "generate_planning_run_v1" else "waiting_review"
        )
        run_id = task.result_planning_run_id
        assert isinstance(run_id, UUID)
        return run_id
    finally:
        await api_engine.dispose()
        await worker_engine.dispose()


@pytest.mark.database
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("suffix", "operation", "countries"),
    (
        (1601, "generate_planning_run_v1", ("japan",)),
        (
            1602,
            "generate_governed_mixed_planning_run_v1",
            ("australia", "japan"),
        ),
    ),
)
async def test_real_worker_persists_only_selected_country_product_rows(
    suffix: int,
    operation: PlanningOperation,
    countries: tuple[str, ...],
) -> None:
    case_id = UUID(f"40000000-0000-0000-0000-{suffix:012d}")
    task_id = UUID(f"80000000-0000-0000-0000-{suffix:012d}")
    await _seed_selected_case(case_id, countries)
    source_pack_version = 1
    if operation == "generate_governed_mixed_planning_run_v1":
        approved_case, source_pack_version = await approved_pack(suffix)
        assert approved_case == case_id
    run_id = await _execute_selected_case(
        case_id=case_id,
        task_id=task_id,
        operation=operation,
        source_pack_version=source_pack_version,
    )

    inspector = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with inspector.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": DEMO_ORG},
            )
            row = (
                (
                    await connection.execute(
                        text(
                            "SELECT "
                            "(SELECT array_agg(country ORDER BY country) "
                            "FROM app.planning_routes WHERE organization_id=:org "
                            "AND planning_run_id=:run) AS routes,"
                            "(SELECT array_agg(country ORDER BY country) "
                            "FROM app.cost_evidence WHERE organization_id=:org "
                            "AND planning_run_id=:run) AS costs,"
                            "(SELECT array_agg(country ORDER BY country) "
                            "FROM app.ranking_evidence WHERE organization_id=:org "
                            "AND planning_run_id=:run) AS rankings,"
                            "(SELECT array_agg(DISTINCT route.country ORDER BY route.country) "
                            "FROM app.comparison_dimension_evidence_refs ref "
                            "JOIN app.planning_routes route "
                            "ON route.organization_id=ref.organization_id "
                            "AND route.planning_run_id=ref.planning_run_id "
                            "AND route.id=ref.route_id "
                            "WHERE ref.organization_id=:org "
                            "AND ref.planning_run_id=:run) AS evidence_routes"
                        ),
                        {"org": DEMO_ORG, "run": run_id},
                    )
                )
                .mappings()
                .one()
            )
        expected = sorted(countries)
        expected_baseline_rows = ["australia"] if "australia" in countries else []
        assert row.routes == expected
        assert (row.costs or []) == expected_baseline_rows
        assert (row.rankings or []) == expected_baseline_rows
        assert row.evidence_routes == expected
        assert "malaysia" not in row.routes
        if countries == ("japan",):
            assert "australia" not in row.routes
    finally:
        await inspector.dispose()
