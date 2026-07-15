# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
import os
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import create_async_engine

from night_voyager.planning.fixtures import validate_planning_fixture
from night_voyager.planning.mixed import materialize_governed_mixed_input
from night_voyager.planning.trusted import GovernedMixedSnapshotV1

from .test_postgres_candidate_promotion import (
    ADVISOR,
    IMPORT_SQL,
    ORG,
    PACK,
    VERIFY_SQL,
    import_params,
    set_context,
    verify_params,
)

pytestmark = pytest.mark.database
SNAPSHOT_SQL = "SELECT app.load_governed_mixed_planning_snapshot(:org,:case,1,:pack,:version,'m3a-policy-v1')"


def case_id_for(suffix: int) -> UUID:
    return UUID(f"40000000-0000-0000-0000-{suffix:012d}")


async def ensure_mixed_case(case_id: UUID) -> None:
    fixture_case = validate_planning_fixture().planning_input.case
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
                {"org": ORG, "case": case_id},
            )
            if exists:
                return
            await connection.execute(
                text(
                    "SELECT app.publish_case_revision(:org,:case,NULL,1,"
                    "CAST(:student AS jsonb),CAST(:family AS jsonb))"
                ),
                {
                    "org": ORG,
                    "case": case_id,
                    "student": fixture_case.student.model_dump_json(),
                    "family": fixture_case.family.model_dump_json(),
                },
            )
            await connection.execute(
                text("SELECT app.transition_case(:org,:case,'intake','planning')"),
                {"org": ORG, "case": case_id},
            )
            await connection.execute(
                text("SELECT app.seed_case_participants(:org,:case,:advisor,:student,:parent)"),
                {
                    "org": ORG,
                    "case": case_id,
                    "advisor": ADVISOR,
                    "student": UUID("20000000-0000-0000-0000-000000000002"),
                    "parent": UUID("20000000-0000-0000-0000-000000000003"),
                },
            )
    finally:
        await engine.dispose()


async def approved_pack(suffix: int) -> tuple[UUID, int]:
    case_id = case_id_for(suffix)
    await ensure_mixed_case(case_id)
    candidate = UUID(f"92000000-0000-0000-0000-{suffix:012d}")
    verification = UUID(f"93000000-0000-0000-0000-{suffix:012d}")
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            await connection.execute(
                text(IMPORT_SQL),
                import_params(
                    candidate,
                    request_hash=hashlib.sha256(f"import-{suffix}".encode()).hexdigest(),
                    key_hash=hashlib.sha256(f"import-key-{suffix}".encode()).hexdigest(),
                    case_id=case_id,
                ),
            )
            result = (
                await connection.execute(
                    text(VERIFY_SQL),
                    verify_params(
                        candidate,
                        verification,
                        decision="approve",
                        request_hash=hashlib.sha256(f"verify-{suffix}".encode()).hexdigest(),
                        key_hash=hashlib.sha256(f"verify-key-{suffix}".encode()).hexdigest(),
                        case_id=case_id,
                    ),
                )
            ).mappings().one()
            return case_id, int(result["promoted_source_pack_version"])
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_worker_loads_only_the_approved_bounded_snapshot() -> None:
    case_id, version = await approved_pack(801)
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            payload = await connection.scalar(
                text(SNAPSHOT_SQL),
                    {"org": ORG, "case": case_id, "pack": PACK, "version": version},
            )
            snapshot = GovernedMixedSnapshotV1.model_validate_json(json.dumps(payload))
            planning_input = materialize_governed_mixed_input(snapshot)
            assert planning_input.case.case_id == case_id
            assert planning_input.source_pack.version == version
            assert [item.claim for item in planning_input.evidence].count("australia_program_fit") == 1
            assert sum(item.authority.value == "externally_verified" for item in planning_input.evidence) == 1
            assert set(payload) == {
                "schema_version",
                "organization_id",
                "case",
                "source_pack",
                "evidence",
                "verification_decision",
                "verification_claim",
                "verification_evidence_role",
                "baseline_source_pack_id",
                "baseline_source_pack_version",
                "baseline_manifest_sha256",
                "baseline_raw_manifest_sha256",
                "promoted_source_pack_version",
                "promoted_source_entry_id",
                "promoted_evidence_id",
            }
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ("stale_case", "wrong_pack", "missing_verification"))
async def test_snapshot_fails_closed_for_stale_or_unapproved_pins(mutation: str) -> None:
    suffix = {"stale_case": 811, "wrong_pack": 812, "missing_verification": 813}[mutation]
    case_id, version = await approved_pack(suffix)
    params: dict[str, object] = {"org": ORG, "case": case_id, "pack": PACK, "version": version}
    if mutation == "stale_case":
        params["case"] = UUID("40000000-0000-0000-0000-000000000099")
    elif mutation == "wrong_pack":
        params["pack"] = UUID("50000000-0000-0000-0000-000000000099")
    else:
        params["version"] = 1
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            with pytest.raises(DBAPIError) as raised:
                async with connection.begin():
                    await connection.execute(
                        text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                        {"org": str(ORG)},
                    )
                    await connection.execute(text(SNAPSHOT_SQL), params)
            assert getattr(raised.value.orig, "sqlstate", None) in {"NV003", "NV011"}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_api_cannot_load_snapshot_and_worker_cannot_promote_or_write_dra_tables() -> None:
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    worker = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    try:
        async with api.connect() as connection:
            with pytest.raises(ProgrammingError):
                async with connection.begin():
                    await set_context(connection, ADVISOR, "advisor")
                    await connection.execute(
                        text(SNAPSHOT_SQL),
                        {"org": ORG, "case": case_id_for(899), "pack": PACK, "version": 1},
                    )
        async with worker.connect() as connection:
            forbidden_execute = (
                await connection.execute(
                    text(
                        "SELECT p.proname,has_function_privilege(current_user,p.oid,'EXECUTE') "
                        "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                        "WHERE n.nspname='app' AND p.proname IN "
                        "('import_dra_research_candidate','verify_and_promote_dra_candidate') "
                        "ORDER BY p.proname"
                    )
                )
            ).all()
            assert forbidden_execute == [
                ("import_dra_research_candidate", False),
                ("verify_and_promote_dra_candidate", False),
            ]
            await connection.commit()
            for statement in (
                "DELETE FROM app.dra_research_candidates WHERE organization_id=:org",
                "DELETE FROM app.external_evidence_verifications WHERE organization_id=:org",
            ):
                with pytest.raises(ProgrammingError):
                    async with connection.begin():
                        await connection.execute(text(statement), {"org": ORG})
    finally:
        await api.dispose()
        await worker.dispose()
