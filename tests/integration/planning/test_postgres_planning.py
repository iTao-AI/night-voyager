# ruff: noqa: E501
from __future__ import annotations

import json
import os
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from night_voyager.planning.fixtures import validate_planning_fixture

pytestmark = pytest.mark.database
DEMO_ORG = UUID("10000000-0000-0000-0000-000000000001")
OTHER_ORG = UUID("10000000-0000-0000-0000-000000000002")
RUN_ID = UUID("70000000-0000-0000-0000-000000000001")


async def set_context(connection: object, organization_id: UUID) -> None:
    await connection.execute(  # type: ignore[attr-defined]
        text("SELECT set_config('night_voyager.organization_id', :org, true)"),
        {"org": str(organization_id)},
    )


async def create_planning_case(connection: AsyncConnection, case_id: UUID) -> None:
    await connection.execute(
        text("SELECT app.publish_case_revision(:org,:case,NULL,1,'{}'::jsonb,'{}'::jsonb)"),
        {"org": DEMO_ORG, "case": case_id},
    )
    await connection.execute(
        text("SELECT app.transition_case(:org,:case,'intake','planning')"),
        {"org": DEMO_ORG, "case": case_id},
    )


async def seed_other_tenant_graph(connection: AsyncConnection) -> None:
    statements = (
        "INSERT INTO app.organizations(id,name,is_synthetic) VALUES(:org,'other synthetic tenant',true) ON CONFLICT DO NOTHING",
        "INSERT INTO app.student_cases(organization_id,id,state) VALUES(:org,'40000000-0000-0000-0000-000000000002','intake') ON CONFLICT DO NOTHING",
        "INSERT INTO app.student_case_revisions VALUES(:org,'40000000-0000-0000-0000-000000000002',1,1,'{}'::jsonb,'{}'::jsonb,clock_timestamp()) ON CONFLICT DO NOTHING",
        "UPDATE app.student_cases SET current_revision=1 WHERE organization_id=:org AND id='40000000-0000-0000-0000-000000000002' AND current_revision IS NULL",
        "INSERT INTO app.source_packs VALUES(:org,'50000000-0000-0000-0000-000000000002',1,1,repeat('a',64),clock_timestamp()) ON CONFLICT DO NOTHING",
        "INSERT INTO app.source_pack_entries VALUES(:org,'50000000-0000-0000-0000-000000000002',1,'51000000-0000-0000-0000-000000000099','source.txt',repeat('b',64),current_date,'synthetic','synthetic','https://example.invalid/other',365,'synthetic_public','synthetic_demo','[\"other_program_fit\"]'::jsonb,'[]'::jsonb) ON CONFLICT DO NOTHING",
        "INSERT INTO app.evidence_refs VALUES(:org,'60000000-0000-0000-0000-000000000099','50000000-0000-0000-0000-000000000002',1,'51000000-0000-0000-0000-000000000099','other_program_fit','accepted_synthetic_demo',repeat('b',64)) ON CONFLICT DO NOTHING",
        "INSERT INTO app.planning_runs(organization_id,id,case_id,case_revision,source_pack_id,source_pack_version,policy_version,evidence_projection_sha256,state,reason_code,output_sha256,is_current) VALUES(:org,'70000000-0000-0000-0000-000000000099','40000000-0000-0000-0000-000000000002',1,'50000000-0000-0000-0000-000000000002',1,'m3a-policy-v1',repeat('c',64),'synthesizing',NULL,NULL,true) ON CONFLICT DO NOTHING",
        "INSERT INTO app.planning_routes VALUES(:org,'70000000-0000-0000-0000-000000000099','71000000-0000-0000-0000-000000000099','australia','blocked','other') ON CONFLICT DO NOTHING",
        "INSERT INTO app.comparison_dimensions VALUES(:org,'70000000-0000-0000-0000-000000000099','71000000-0000-0000-0000-000000000099','72000000-0000-0000-0000-000000000099','program_fit','blocked','other') ON CONFLICT DO NOTHING",
        "INSERT INTO app.comparison_dimension_evidence_refs VALUES(:org,'70000000-0000-0000-0000-000000000099','71000000-0000-0000-0000-000000000099','72000000-0000-0000-0000-000000000099','60000000-0000-0000-0000-000000000099','program_fit') ON CONFLICT DO NOTHING",
        "UPDATE app.planning_runs SET state='blocked',reason_code='other',output_sha256=repeat('d',64) WHERE organization_id=:org AND id='70000000-0000-0000-0000-000000000099'",
    )
    await set_context(connection, OTHER_ORG)
    for statement in statements:
        await connection.execute(text(statement), {"org": OTHER_ORG})


@pytest.mark.asyncio
async def test_api_and_worker_same_tenant_reads_cross_tenant_hidden_and_pool_cleans() -> None:
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with migrator.begin() as connection:
            await seed_other_tenant_graph(connection)
    finally:
        await migrator.dispose()

    for variable in ("NIGHT_VOYAGER_API_DATABASE_URL", "NIGHT_VOYAGER_WORKER_DATABASE_URL"):
        engine = create_async_engine(os.environ[variable], pool_size=1, max_overflow=0)
        try:
            async with engine.begin() as connection:
                assert await connection.scalar(text("SELECT count(*) FROM app.student_cases")) == 0
            async with engine.begin() as connection:
                await set_context(connection, DEMO_ORG)
                assert await connection.scalar(text("SELECT count(*) FROM app.student_cases")) == 1
                assert await connection.scalar(text("SELECT count(*) FROM app.planning_runs")) == 1
                assert (
                    await connection.scalar(
                        text("SELECT count(*) FROM app.student_cases WHERE organization_id=:other"),
                        {"other": OTHER_ORG},
                    )
                    == 0
                )
                joined = await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.planning_runs r JOIN app.planning_routes p ON (p.organization_id,p.planning_run_id)=(r.organization_id,r.id)"
                    )
                )
                assert joined == 3
            async with engine.begin() as connection:
                await set_context(connection, OTHER_ORG)
                assert await connection.scalar(text("SELECT count(*) FROM app.student_cases")) == 1
                assert await connection.scalar(text("SELECT count(*) FROM app.planning_runs")) == 1
                assert await connection.scalar(text("SELECT count(*) FROM app.evidence_refs")) == 1
                assert (
                    await connection.scalar(text("SELECT count(*) FROM app.planning_routes")) == 1
                )
                assert (
                    await connection.scalar(text("SELECT count(*) FROM app.comparison_dimensions"))
                    == 1
                )
            async with engine.begin() as connection:
                assert await connection.scalar(text("SELECT count(*) FROM app.student_cases")) == 0
            async with engine.connect() as connection:
                with pytest.raises(DBAPIError):
                    async with connection.begin():
                        await connection.execute(
                            text(
                                "SELECT set_config('night_voyager.organization_id','invalid',true)"
                            )
                        )
                        await connection.execute(text("SELECT * FROM app.student_cases"))
        finally:
            await engine.dispose()


@pytest.mark.asyncio
async def test_case_revision_cas_succeeds_then_stale_conflicts() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    case_id = UUID("40000000-0000-0000-0000-000000000099")
    try:
        async with engine.begin() as connection:
            await set_context(connection, DEMO_ORG)
            await connection.execute(
                text("SELECT app.publish_case_revision(:org,:case,NULL,1,'{}'::jsonb,'{}'::jsonb)"),
                {"org": DEMO_ORG, "case": case_id},
            )
        async with engine.connect() as connection:
            with pytest.raises(DBAPIError) as captured:
                async with connection.begin():
                    await set_context(connection, DEMO_ORG)
                    await connection.execute(
                        text(
                            "SELECT app.publish_case_revision(:org,:case,NULL,2,'{}'::jsonb,'{}'::jsonb)"
                        ),
                        {"org": DEMO_ORG, "case": case_id},
                    )
            assert getattr(captured.value.orig, "sqlstate", None) == "NV003"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_current_revision_cannot_reference_missing_revision() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            with pytest.raises(DBAPIError) as captured:
                async with connection.begin():
                    await set_context(connection, DEMO_ORG)
                    await connection.execute(
                        text(
                            "UPDATE app.student_cases SET current_revision=999 WHERE organization_id=:org AND id='40000000-0000-0000-0000-000000000001'"
                        ),
                        {"org": DEMO_ORG},
                    )
            assert getattr(captured.value.orig, "sqlstate", None) == "NV003"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_seeded_review_required_run_advances_case_to_advisor_review() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await set_context(connection, DEMO_ORG)
            assert (
                await connection.scalar(
                    text(
                        "SELECT state FROM app.student_cases WHERE organization_id=:org AND id='40000000-0000-0000-0000-000000000001'"
                    ),
                    {"org": DEMO_ORG},
                )
                == "advisor_review"
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_state", ("blocked", "failed"))
async def test_only_review_required_result_publication_advances_case(
    terminal_state: str,
) -> None:
    suffix = 81 if terminal_state == "blocked" else 82
    case_id = UUID(f"40000000-0000-0000-0000-{suffix:012d}")
    run_id = UUID(f"70000000-0000-0000-0000-{suffix:012d}")
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await set_context(connection, DEMO_ORG)
            await create_planning_case(connection, case_id)
            await connection.execute(
                text(
                    "SELECT app.persist_planning_result(:org,:run,:case,1,'50000000-0000-0000-0000-000000000001',1,'m3a-policy-v1',repeat('a',64),:state,'negative-result',repeat('b',64),NULL,'{\"routes\":[],\"costs\":[],\"rankings\":[]}'::jsonb)"
                ),
                {"org": DEMO_ORG, "run": run_id, "case": case_id, "state": terminal_state},
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT state FROM app.student_cases WHERE organization_id=:org AND id=:case"
                    ),
                    {"org": DEMO_ORG, "case": case_id},
                )
                == "planning"
            )
        async with engine.connect() as connection:
            with pytest.raises(DBAPIError):
                async with connection.begin():
                    await set_context(connection, DEMO_ORG)
                    await connection.execute(
                        text("SELECT app.transition_case(:org,:case,'planning','advisor_review')"),
                        {"org": DEMO_ORG, "case": case_id},
                    )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_review_required_publication_atomically_hands_off_current_case() -> None:
    fixture = validate_planning_fixture()
    case_id = UUID("40000000-0000-0000-0000-000000000083")
    run_id = UUID("70000000-0000-0000-0000-000000000083")
    output = json.dumps(
        {
            "routes": [item.model_dump(mode="json") for item in fixture.result.routes],
            "costs": [item.model_dump(mode="json") for item in fixture.planning_input.costs],
            "rankings": [item.model_dump(mode="json") for item in fixture.planning_input.rankings],
        }
    )
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await set_context(connection, DEMO_ORG)
            await create_planning_case(connection, case_id)
            await connection.execute(
                text(
                    "SELECT app.persist_planning_result(:org,:run,:case,1,'50000000-0000-0000-0000-000000000001',1,'m3a-policy-v1',:evidence_hash,'review_required',:reason,:output_hash,NULL,CAST(:output AS jsonb))"
                ),
                {
                    "org": DEMO_ORG,
                    "run": run_id,
                    "case": case_id,
                    "evidence_hash": fixture.evidence_projection_sha256,
                    "reason": fixture.result.reason_code,
                    "output_hash": fixture.output_sha256,
                    "output": output,
                },
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT state FROM app.student_cases WHERE organization_id=:org AND id=:case"
                    ),
                    {"org": DEMO_ORG, "case": case_id},
                )
                == "advisor_review"
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_direct_handoff_rejects_no_run_noncurrent_and_stale_run() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    cases = (
        (UUID("40000000-0000-0000-0000-000000000084"), "none"),
        (UUID("40000000-0000-0000-0000-000000000085"), "noncurrent"),
        (UUID("40000000-0000-0000-0000-000000000086"), "stale"),
    )
    try:
        async with engine.begin() as connection:
            await set_context(connection, DEMO_ORG)
            for index, (case_id, mode) in enumerate(cases, start=84):
                await connection.execute(
                    text(
                        "INSERT INTO app.student_cases(organization_id,id,state) VALUES(:org,:case,'planning')"
                    ),
                    {"org": DEMO_ORG, "case": case_id},
                )
                await connection.execute(
                    text(
                        "INSERT INTO app.student_case_revisions VALUES(:org,:case,1,1,'{}'::jsonb,'{}'::jsonb,clock_timestamp())"
                    ),
                    {"org": DEMO_ORG, "case": case_id},
                )
                await connection.execute(
                    text(
                        "UPDATE app.student_cases SET current_revision=1 WHERE organization_id=:org AND id=:case"
                    ),
                    {"org": DEMO_ORG, "case": case_id},
                )
                if mode != "none":
                    await connection.execute(
                        text(
                            "INSERT INTO app.planning_runs(organization_id,id,case_id,case_revision,source_pack_id,source_pack_version,policy_version,evidence_projection_sha256,state,reason_code,output_sha256,is_current) VALUES(:org,:run,:case,1,'50000000-0000-0000-0000-000000000001',1,'m3a-policy-v1',repeat('a',64),'review_required','test',repeat('b',64),:current)"
                        ),
                        {
                            "org": DEMO_ORG,
                            "run": UUID(f"70000000-0000-0000-0000-{index:012d}"),
                            "case": case_id,
                            "current": mode != "noncurrent",
                        },
                    )
                if mode == "stale":
                    await connection.execute(
                        text(
                            "INSERT INTO app.student_case_revisions VALUES(:org,:case,2,1,'{}'::jsonb,'{}'::jsonb,clock_timestamp())"
                        ),
                        {"org": DEMO_ORG, "case": case_id},
                    )
                    await connection.execute(
                        text(
                            "UPDATE app.student_cases SET current_revision=2 WHERE organization_id=:org AND id=:case"
                        ),
                        {"org": DEMO_ORG, "case": case_id},
                    )
    finally:
        await engine.dispose()

    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        for case_id, _ in cases:
            async with api.connect() as connection:
                with pytest.raises(DBAPIError):
                    async with connection.begin():
                        await set_context(connection, DEMO_ORG)
                        await connection.execute(
                            text(
                                "SELECT app.transition_case(:org,:case,'planning','advisor_review')"
                            ),
                            {"org": DEMO_ORG, "case": case_id},
                        )
    finally:
        await api.dispose()


@pytest.mark.asyncio
async def test_api_persists_complete_result_and_supersedes_current_run_atomically() -> None:
    fixture = validate_planning_fixture()
    case_id = UUID("40000000-0000-0000-0000-000000000087")
    old_run = UUID("70000000-0000-0000-0000-000000000087")
    new_run = UUID("70000000-0000-0000-0000-000000000097")
    output = json.dumps(
        {
            "routes": [item.model_dump(mode="json") for item in fixture.result.routes],
            "costs": [item.model_dump(mode="json") for item in fixture.planning_input.costs],
            "rankings": [item.model_dump(mode="json") for item in fixture.planning_input.rankings],
        }
    )
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await set_context(connection, DEMO_ORG)
            await create_planning_case(connection, case_id)
            await connection.execute(
                text(
                    "SELECT app.persist_planning_result(:org,:run,:case,1,'50000000-0000-0000-0000-000000000001',1,'m3a-policy-v1',repeat('a',64),'blocked','initial-block',repeat('b',64),NULL,'{\"routes\":[],\"costs\":[],\"rankings\":[]}'::jsonb)"
                ),
                {"org": DEMO_ORG, "run": old_run, "case": case_id},
            )
            await connection.execute(
                text(
                    "SELECT app.persist_planning_result(:org,:run,:case,1,'50000000-0000-0000-0000-000000000001',1,'m3a-policy-v1',:evidence_hash,'review_required',:reason,:output_hash,:supersedes,CAST(:output AS jsonb))"
                ),
                {
                    "org": DEMO_ORG,
                    "run": new_run,
                    "case": case_id,
                    "evidence_hash": fixture.evidence_projection_sha256,
                    "reason": fixture.result.reason_code,
                    "output_hash": fixture.output_sha256,
                    "supersedes": old_run,
                    "output": output,
                },
            )
            assert (
                await connection.scalar(
                    text("SELECT count(*) FROM app.planning_routes WHERE planning_run_id=:run"),
                    {"run": new_run},
                )
                == 3
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.comparison_dimension_evidence_refs WHERE planning_run_id=:run"
                    ),
                    {"run": new_run},
                )
                == 6
            )
            assert (
                await connection.scalar(
                    text("SELECT count(*) FROM app.cost_evidence WHERE planning_run_id=:run"),
                    {"run": new_run},
                )
                == 1
            )
            assert (
                await connection.scalar(
                    text("SELECT is_current FROM app.planning_runs WHERE id=:run"),
                    {"run": old_run},
                )
                is False
            )
            assert (
                await connection.scalar(
                    text("SELECT state FROM app.student_cases WHERE id=:case"),
                    {"case": case_id},
                )
                == "advisor_review"
            )
            assert (
                await connection.scalar(
                    text("SELECT count(*) FROM app.ranking_evidence WHERE planning_run_id=:run"),
                    {"run": new_run},
                )
                == 1
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_terminal_run_and_children_are_immutable_for_api_role() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        for statement in (
            "UPDATE app.planning_runs SET state='failed',reason_code='rewrite',output_sha256=repeat('f',64) WHERE id=:run",
            "INSERT INTO app.planning_routes(organization_id,planning_run_id,id,country,outcome,reason_code) VALUES(:org,:run,'71000000-0000-0000-0000-000000000099','malaysia','conditional','late')",
            "INSERT INTO app.cost_evidence(organization_id,planning_run_id,id,country,intake,period,currency,tuition_minor,living_minor,fx_rate,fx_source,fx_date,tuition_evidence_id,living_evidence_id,fx_evidence_id) SELECT :org,:run,'73000000-0000-0000-0000-000000000099','australia','2027-02','program_total','AUD',1,1,1,'late',current_date,id,id,id FROM app.evidence_refs LIMIT 1",
        ):
            async with engine.connect() as connection:
                with pytest.raises(DBAPIError):
                    async with connection.begin():
                        await set_context(connection, DEMO_ORG)
                        await connection.execute(text(statement), {"org": DEMO_ORG, "run": RUN_ID})
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_source_hash_mismatch_is_rejected_by_database_trigger() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            with pytest.raises(DBAPIError) as captured:
                async with connection.begin():
                    await set_context(connection, DEMO_ORG)
                    await connection.execute(
                        text(
                            "INSERT INTO app.evidence_refs(organization_id,id,source_pack_id,source_pack_version,source_entry_id,claim,authority,source_sha256) VALUES(:org,'60000000-0000-0000-0000-000000000099','50000000-0000-0000-0000-000000000001',1,'51000000-0000-0000-0000-000000000001','australia_program_fit','accepted_synthetic_demo',repeat('f',64))"
                        ),
                        {"org": DEMO_ORG},
                    )
            assert getattr(captured.value.orig, "sqlstate", None) == "NV004"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_cross_pack_evidence_link_is_rejected_by_database_trigger() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            with pytest.raises(DBAPIError) as captured:
                async with connection.begin():
                    await set_context(connection, DEMO_ORG)
                    statements = (
                        "INSERT INTO app.source_packs VALUES(:org,'50000000-0000-0000-0000-000000000001',2,1,repeat('e',64),clock_timestamp())",
                        "INSERT INTO app.source_pack_entries VALUES(:org,'50000000-0000-0000-0000-000000000001',2,'51000000-0000-0000-0000-000000000098','other.txt',repeat('e',64),current_date,'synthetic','synthetic','https://example.invalid/cross-pack',365,'synthetic_public','synthetic_demo','[\"australia_program_fit\"]'::jsonb,'[]'::jsonb)",
                        "INSERT INTO app.evidence_refs VALUES(:org,'60000000-0000-0000-0000-000000000098','50000000-0000-0000-0000-000000000001',2,'51000000-0000-0000-0000-000000000098','australia_program_fit','accepted_synthetic_demo',repeat('e',64))",
                        "INSERT INTO app.planning_runs(organization_id,id,case_id,case_revision,source_pack_id,source_pack_version,policy_version,evidence_projection_sha256,state,is_current) VALUES(:org,'70000000-0000-0000-0000-000000000098','40000000-0000-0000-0000-000000000001',1,'50000000-0000-0000-0000-000000000001',1,'m3a-policy-v1',repeat('e',64),'synthesizing',false)",
                        "INSERT INTO app.planning_routes VALUES(:org,'70000000-0000-0000-0000-000000000098','71000000-0000-0000-0000-000000000098','australia','blocked','cross-pack-test')",
                        "INSERT INTO app.comparison_dimensions VALUES(:org,'70000000-0000-0000-0000-000000000098','71000000-0000-0000-0000-000000000098','72000000-0000-0000-0000-000000000098','program_fit','blocked','cross-pack-test')",
                    )
                    for statement in statements:
                        await connection.execute(text(statement), {"org": DEMO_ORG})
                    await connection.execute(
                        text(
                            "INSERT INTO app.comparison_dimension_evidence_refs VALUES(:org,'70000000-0000-0000-0000-000000000098','71000000-0000-0000-0000-000000000098','72000000-0000-0000-0000-000000000098','60000000-0000-0000-0000-000000000098','program_fit')"
                        ),
                        {"org": DEMO_ORG},
                    )
            assert getattr(captured.value.orig, "sqlstate", None) == "NV004"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_worker_and_api_have_no_direct_m3a_write_authority() -> None:
    for variable in ("NIGHT_VOYAGER_API_DATABASE_URL", "NIGHT_VOYAGER_WORKER_DATABASE_URL"):
        engine = create_async_engine(os.environ[variable])
        try:
            async with engine.connect() as connection:
                with pytest.raises(DBAPIError):
                    async with connection.begin():
                        await set_context(connection, DEMO_ORG)
                        await connection.execute(text("DELETE FROM app.evidence_refs"))
                if variable == "NIGHT_VOYAGER_WORKER_DATABASE_URL":
                    with pytest.raises(DBAPIError):
                        async with connection.begin():
                            await set_context(connection, DEMO_ORG)
                            await connection.execute(
                                text(
                                    "SELECT app.transition_case(:org,'40000000-0000-0000-0000-000000000001','planning','advisor_review')"
                                ),
                                {"org": DEMO_ORG},
                            )
        finally:
            await engine.dispose()
