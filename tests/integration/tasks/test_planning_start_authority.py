# ruff: noqa: E501
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from night_voyager.skills.models import SkillKey
from night_voyager.skills.registry import SkillRuntimeRegistry

pytestmark = pytest.mark.database

ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
STUDENT = UUID("20000000-0000-0000-0000-000000000002")
PARENT = UUID("20000000-0000-0000-0000-000000000003")
PACK = UUID("50000000-0000-0000-0000-000000000001")
OTHER_ORG = UUID("19000000-0000-0000-0000-000000000991")
OTHER_ADVISOR = UUID("29000000-0000-0000-0000-000000000991")
OTHER_CASE = UUID("49000000-0000-0000-0000-000000000991")
OTHER_PACK = UUID("59000000-0000-0000-0000-000000000991")
UNSTARTED_CASE = UUID("42000000-0000-0000-0000-000000000901")
START_CASE = UUID("42000000-0000-0000-0000-000000000902")
TASK = UUID("85000000-0000-0000-0000-000000000902")


def skill_manifest() -> str:
    return (
        SkillRuntimeRegistry.load_packaged()
        .get(SkillKey.STUDY_DESTINATION_COMPARE, "1.0.0")
        .model_dump_json(exclude_none=True)
    )


def stale_skill_manifest() -> str:
    manifest = json.loads(skill_manifest())
    manifest["runtime_binding_sha256"] = "0" * 64
    return json.dumps(manifest)


def planning_key(label: str) -> str:
    return hashlib.sha256(f"pr1-planning-start:{label}".encode()).hexdigest()


async def set_api_context(
    connection: AsyncConnection,
    *,
    organization_id: UUID = ORG,
    actor_id: UUID = ADVISOR,
    role: str = "advisor",
) -> None:
    for name, value in (
        ("night_voyager.organization_id", str(organization_id)),
        ("night_voyager.actor_id", str(actor_id)),
        ("night_voyager.role", role),
    ):
        await connection.execute(
            text("SELECT set_config(:name,:value,true)"),
            {"name": name, "value": value},
        )


async def seed_intake_case(case_id: UUID, *, assigned: bool = True) -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            await connection.execute(
                text(
                    "SELECT app.publish_case_revision("
                    ":org,:case,NULL,1,'{}'::jsonb,'{}'::jsonb)"
                ),
                {"org": ORG, "case": case_id},
            )
            if assigned:
                await connection.execute(
                    text(
                        "INSERT INTO app.student_case_participants("
                        "organization_id,case_id,actor_id,role) "
                        "VALUES(:org,:case,:advisor,'advisor'),"
                        "(:org,:case,:parent,'parent')"
                    ),
                    {
                        "org": ORG,
                        "case": case_id,
                        "advisor": ADVISOR,
                        "parent": PARENT,
                    },
                )
    finally:
        await engine.dispose()


async def seed_unsupported_case(case_id: UUID) -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.student_cases(organization_id,id,state) "
                    "VALUES(:org,:case,'advisor_review')"
                ),
                {"org": ORG, "case": case_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.student_case_revisions("
                    "organization_id,case_id,revision,schema_version,"
                    "student_preferences,family_preferences) "
                    "VALUES(:org,:case,1,1,'{}'::jsonb,'{}'::jsonb)"
                ),
                {"org": ORG, "case": case_id},
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
                    "INSERT INTO app.student_case_participants("
                    "organization_id,case_id,actor_id,role) "
                    "VALUES(:org,:case,:advisor,'advisor')"
                ),
                {"org": ORG, "case": case_id, "advisor": ADVISOR},
            )
    finally:
        await engine.dispose()


async def seed_other_tenant_without_activation() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(OTHER_ORG)},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.organizations(id,name,is_synthetic) "
                    "VALUES(:org,'Planning-start negative tenant',true)"
                ),
                {"org": OTHER_ORG},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.actors(id,organization_id,display_name,is_synthetic) "
                    "VALUES(:actor,:org,'Planning-start negative advisor',true)"
                ),
                {"org": OTHER_ORG, "actor": OTHER_ADVISOR},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.memberships("
                    "id,organization_id,actor_id,role) "
                    "VALUES('39000000-0000-0000-0000-000000000991',"
                    ":org,:actor,'advisor')"
                ),
                {"org": OTHER_ORG, "actor": OTHER_ADVISOR},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.source_packs("
                    "organization_id,id,version,schema_version,manifest_sha256) "
                    "VALUES(:org,:pack,1,1,repeat('9',64))"
                ),
                {"org": OTHER_ORG, "pack": OTHER_PACK},
            )
            await connection.execute(
                text(
                    "SELECT app.publish_case_revision("
                    ":org,:case,NULL,1,'{}'::jsonb,'{}'::jsonb)"
                ),
                {"org": OTHER_ORG, "case": OTHER_CASE},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.student_case_participants("
                    "organization_id,case_id,actor_id,role) "
                    "VALUES(:org,:case,:actor,'advisor')"
                ),
                {"org": OTHER_ORG, "case": OTHER_CASE, "actor": OTHER_ADVISOR},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.skill_definitions("
                    "organization_id,id,skill_key,owner_actor_id,owner_role,binding_kind) "
                    "VALUES(:org,'89000000-0000-0000-0000-000000000991',"
                    "'study-destination-compare',:actor,'advisor','planning_runtime')"
                ),
                {"org": OTHER_ORG, "actor": OTHER_ADVISOR},
            )
    finally:
        await engine.dispose()


async def create_task(
    connection: AsyncConnection,
    *,
    case_id: UUID,
    task_id: UUID,
    key_hash: str,
    organization_id: UUID = ORG,
    actor_id: UUID = ADVISOR,
    operation: str = "generate_planning_run_v1",
    revision: int = 1,
    pack_id: UUID = PACK,
    pack_version: int = 1,
    manifest: str | None = None,
    request_hash: str | None = None,
) -> CursorResult[Any]:
    return await connection.execute(
        text(
            "SELECT * FROM app.create_agent_task("
            ":org,:actor,:case,:task,:operation,:revision,:pack,:pack_version,"
            "'m3a-policy-v1',CAST(:manifest AS jsonb),:request_hash,:key_hash)"
        ),
        {
            "org": organization_id,
            "actor": actor_id,
            "case": case_id,
            "task": task_id,
            "operation": operation,
            "revision": revision,
            "pack": pack_id,
            "pack_version": pack_version,
            "manifest": manifest if manifest is not None else skill_manifest(),
            "request_hash": request_hash or "a" * 64,
            "key_hash": key_hash,
        },
    )


async def authority_projection(
    connection: AsyncConnection,
    case_id: UUID,
    *,
    organization_id: UUID = ORG,
) -> dict[str, object]:
    row = (
        await connection.execute(
            text(
                "SELECT c.state,"
                "(SELECT count(*) FROM app.agent_tasks t "
                " WHERE t.organization_id=c.organization_id AND t.case_id=c.id) AS tasks,"
                "(SELECT count(*) FROM app.agent_tasks t "
                " WHERE t.organization_id=c.organization_id AND t.case_id=c.id "
                " AND t.skill_definition_id IS NOT NULL "
                " AND t.skill_version_id IS NOT NULL "
                " AND t.skill_activation_event_id IS NOT NULL "
                " AND t.skill_activation_sequence IS NOT NULL "
                " AND t.runtime_binding_sha256 IS NOT NULL) AS pins,"
                "(SELECT count(*) FROM internal.agent_task_dispatch d "
                " JOIN app.agent_tasks t ON t.organization_id=d.organization_id "
                " AND t.id=d.task_id WHERE t.organization_id=c.organization_id "
                " AND t.case_id=c.id) AS dispatches,"
                "(SELECT count(*) FROM app.agent_task_events e "
                " JOIN app.agent_tasks t ON t.organization_id=e.organization_id "
                " AND t.id=e.task_id WHERE t.organization_id=c.organization_id "
                " AND t.case_id=c.id) AS events,"
                "(SELECT count(*) FROM app.idempotency_records i "
                " WHERE i.organization_id=c.organization_id "
                " AND i.operation='agent_task_create' AND EXISTS ("
                "   SELECT 1 FROM app.agent_tasks t WHERE t.organization_id=i.organization_id "
                "   AND t.id=i.response_id AND t.case_id=c.id)) AS idempotency,"
                "(SELECT count(*) FROM app.agent_executions e "
                " JOIN app.agent_tasks t ON t.organization_id=e.organization_id "
                " AND t.id=e.task_id WHERE t.organization_id=c.organization_id "
                " AND t.case_id=c.id) AS executions "
                "FROM app.student_cases c WHERE c.organization_id=:org AND c.id=:case"
            ),
            {"org": organization_id, "case": case_id},
        )
    ).mappings().one()
    return dict(row)


async def cancel_task(task_id: UUID) -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await set_api_context(connection)
            await connection.execute(
                text(
                    "SELECT * FROM app.cancel_agent_task("
                    ":org,:actor,:task,1,:request_hash,:key_hash)"
                ),
                {
                    "org": ORG,
                    "actor": ADVISOR,
                    "task": task_id,
                    "request_hash": hashlib.sha256(
                        f"cancel-request:{task_id}".encode()
                    ).hexdigest(),
                    "key_hash": hashlib.sha256(
                        f"cancel-key:{task_id}".encode()
                    ).hexdigest(),
                },
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_intake_case_has_no_task_before_explicit_planning_start() -> None:
    await seed_intake_case(UNSTARTED_CASE)
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await set_api_context(connection)
            assert await connection.scalar(
                text(
                    "SELECT state FROM app.student_cases "
                    "WHERE organization_id=:org AND id=:case"
                ),
                {"org": ORG, "case": UNSTARTED_CASE},
            ) == "intake"
            assert await connection.scalar(
                text(
                    "SELECT count(*) FROM app.agent_tasks "
                    "WHERE organization_id=:org AND case_id=:case"
                ),
                {"org": ORG, "case": UNSTARTED_CASE},
            ) == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_first_deterministic_task_atomically_starts_planning() -> None:
    await seed_intake_case(START_CASE)
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with api.begin() as connection:
            await set_api_context(connection)
            created = (
                await connection.execute(
                    text(
                        "SELECT * FROM app.create_agent_task("
                        ":org,:actor,:case,:task,'generate_planning_run_v1',1,"
                        ":pack,1,'m3a-policy-v1',CAST(:manifest AS jsonb),"
                        ":request_hash,:key_hash)"
                    ),
                    {
                        "org": ORG,
                        "actor": ADVISOR,
                        "case": START_CASE,
                        "task": TASK,
                        "pack": PACK,
                        "manifest": skill_manifest(),
                        "request_hash": "a" * 64,
                        "key_hash": planning_key("first-deterministic"),
                    },
                )
            ).mappings().one()
            assert dict(created) == {
                "task_id": TASK,
                "row_version": 1,
                "state": "queued",
                "attempt_count": 0,
                "replayed": False,
            }

        async with migrator.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            assert await connection.scalar(
                text(
                    "SELECT state FROM app.student_cases "
                    "WHERE organization_id=:org AND id=:case"
                ),
                {"org": ORG, "case": START_CASE},
            ) == "planning"
            counts = (
                await connection.execute(
                    text(
                        "SELECT "
                        "(SELECT count(*) FROM app.agent_tasks "
                        " WHERE organization_id=:org AND id=:task) AS tasks,"
                        "(SELECT count(*) FROM internal.agent_task_dispatch "
                        " WHERE organization_id=:org AND task_id=:task) AS dispatches,"
                        "(SELECT count(*) FROM app.agent_task_events "
                        " WHERE organization_id=:org AND task_id=:task "
                        "   AND event_sequence=1 AND event_code='queued') AS events,"
                        "(SELECT count(*) FROM app.idempotency_records "
                        " WHERE organization_id=:org AND operation='agent_task_create' "
                        "   AND response_id=:task) AS idempotency"
                    ),
                    {"org": ORG, "task": TASK},
                )
            ).mappings().one()
            assert tuple(counts.values()) == (1, 1, 1, 1)
        await cancel_task(TASK)
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_replay_precedes_new_write_validation_and_mismatch_stays_bounded() -> None:
    case_id = UUID("42000000-0000-0000-0000-000000000903")
    task_id = UUID("85000000-0000-0000-0000-000000000903")
    await seed_intake_case(case_id)
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with api.begin() as connection:
            await set_api_context(connection)
            created = (
                await create_task(
                    connection,
                    case_id=case_id,
                    task_id=task_id,
                    key_hash=planning_key("replay"),
                )
            ).mappings().one()
            assert created.replayed is False

        async with api.begin() as connection:
            await set_api_context(connection)
            replayed = (
                await create_task(
                    connection,
                    case_id=case_id,
                    task_id=UUID(int=903),
                    key_hash=planning_key("replay"),
                    revision=99,
                    pack_id=UUID(int=999),
                    manifest="{}",
                )
            ).mappings().one()
            assert replayed.task_id == task_id
            assert replayed.replayed is True

        async with api.connect() as connection:
            with pytest.raises(DBAPIError) as mismatch:
                async with connection.begin():
                    await set_api_context(connection)
                    await create_task(
                        connection,
                        case_id=case_id,
                        task_id=UUID(int=904),
                        key_hash=planning_key("replay"),
                        request_hash="d" * 64,
                    )
            assert getattr(mismatch.value.orig, "sqlstate", None) == "NV008"

        async with migrator.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            assert await authority_projection(connection, case_id) == {
                "state": "planning",
                "tasks": 1,
                "pins": 1,
                "dispatches": 1,
                "events": 1,
                "idempotency": 1,
                "executions": 0,
            }
        await cancel_task(task_id)
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_authority_negative_matrix_leaves_intake_without_task_residue() -> None:
    cases = {
        "wrong_role": UUID("42000000-0000-0000-0000-000000000910"),
        "student": UUID("42000000-0000-0000-0000-000000000918"),
        "unassigned": UUID("42000000-0000-0000-0000-000000000911"),
        "stale_revision": UUID("42000000-0000-0000-0000-000000000912"),
        "source_pack": UUID("42000000-0000-0000-0000-000000000913"),
        "manifest": UUID("42000000-0000-0000-0000-000000000914"),
        "malformed_manifest": UUID("42000000-0000-0000-0000-000000000915"),
        "mixed": UUID("42000000-0000-0000-0000-000000000916"),
        "stale_pin": UUID("42000000-0000-0000-0000-000000000919"),
    }
    for label, case_id in cases.items():
        await seed_intake_case(case_id, assigned=label != "unassigned")
    unsupported = UUID("42000000-0000-0000-0000-000000000917")
    await seed_unsupported_case(unsupported)
    await seed_other_tenant_without_activation()

    scenarios = (
        ("wrong_role", cases["wrong_role"], PARENT, "parent", PARENT, 1, PACK, 1, None, "generate_planning_run_v1", "NV007", ORG),
        ("student", cases["student"], STUDENT, "student", STUDENT, 1, PACK, 1, None, "generate_planning_run_v1", "NV007", ORG),
        ("unassigned", cases["unassigned"], ADVISOR, "advisor", ADVISOR, 1, PACK, 1, None, "generate_planning_run_v1", "NV007", ORG),
        ("cross_tenant", OTHER_CASE, ADVISOR, "advisor", OTHER_ADVISOR, 1, OTHER_PACK, 1, None, "generate_planning_run_v1", "NV007", OTHER_ORG),
        ("stale_revision", cases["stale_revision"], ADVISOR, "advisor", ADVISOR, 2, PACK, 1, None, "generate_planning_run_v1", "NV003", ORG),
        ("source_pack", cases["source_pack"], ADVISOR, "advisor", ADVISOR, 1, UUID(int=913), 1, None, "generate_planning_run_v1", "NV003", ORG),
        ("manifest", cases["manifest"], ADVISOR, "advisor", ADVISOR, 1, PACK, 1, "{}", "generate_planning_run_v1", "NV022", ORG),
        ("malformed_manifest", cases["malformed_manifest"], ADVISOR, "advisor", ADVISOR, 1, PACK, 1, "[]", "generate_planning_run_v1", "NV006", ORG),
        ("mixed", cases["mixed"], ADVISOR, "advisor", ADVISOR, 1, PACK, 1, None, "generate_governed_mixed_planning_run_v1", "NV003", ORG),
        ("stale_pin", cases["stale_pin"], ADVISOR, "advisor", ADVISOR, 1, PACK, 1, stale_skill_manifest(), "generate_planning_run_v1", "NV022", ORG),
        ("unsupported", unsupported, ADVISOR, "advisor", ADVISOR, 1, PACK, 1, None, "generate_planning_run_v1", "NV003", ORG),
        ("missing_activation", OTHER_CASE, OTHER_ADVISOR, "advisor", OTHER_ADVISOR, 1, OTHER_PACK, 1, None, "generate_planning_run_v1", "NV015", OTHER_ORG),
    )

    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        for index, scenario in enumerate(scenarios, start=1):
            (
                label,
                case_id,
                context_actor,
                context_role,
                call_actor,
                revision,
                pack_id,
                pack_version,
                manifest,
                operation,
                expected,
                organization_id,
            ) = scenario
            async with api.connect() as connection:
                try:
                    async with connection.begin():
                        await set_api_context(
                            connection,
                            organization_id=(
                                OTHER_ORG if label == "missing_activation" else ORG
                            ),
                            actor_id=context_actor,
                            role=context_role,
                        )
                        await create_task(
                            connection,
                            organization_id=organization_id,
                            actor_id=call_actor,
                            case_id=case_id,
                            task_id=UUID(f"85000000-0000-0000-0000-{910 + index:012d}"),
                            key_hash=planning_key(f"negative:{label}"),
                            revision=revision,
                            pack_id=pack_id,
                            pack_version=pack_version,
                            manifest=manifest,
                            operation=operation,
                        )
                except DBAPIError as rejected:
                    assert getattr(rejected.orig, "sqlstate", None) == expected, label
                else:
                    pytest.fail(f"{label} unexpectedly created a task")

            async with migrator.begin() as connection:
                await connection.execute(
                    text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                    {"org": str(organization_id)},
                )
                projection = await authority_projection(
                    connection, case_id, organization_id=organization_id
                )
                assert projection == {
                    "state": "advisor_review" if label == "unsupported" else "intake",
                    "tasks": 0,
                    "pins": 0,
                    "dispatches": 0,
                    "events": 0,
                    "idempotency": 0,
                    "executions": 0,
                }, label
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_two_first_requests_serialize_to_one_complete_authority_set() -> None:
    case_id = UUID("42000000-0000-0000-0000-000000000920")
    first_task = UUID("85000000-0000-0000-0000-000000000920")
    second_task = UUID("85000000-0000-0000-0000-000000000921")
    await seed_intake_case(case_id)
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])

    async def attempt_create(task_id: UUID, key_hash: str) -> tuple[str, UUID | str]:
        async with api.connect() as connection:
            try:
                async with connection.begin():
                    await set_api_context(connection)
                    created = (
                        await create_task(
                            connection,
                            case_id=case_id,
                            task_id=task_id,
                            key_hash=key_hash,
                        )
                    ).mappings().one()
                return "created", created.task_id
            except DBAPIError as conflict:
                return "rejected", str(getattr(conflict.orig, "sqlstate", None))

    try:
        async with migrator.connect() as lock_connection, lock_connection.begin():
            await lock_connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            await lock_connection.execute(
                text(
                    "SELECT id FROM app.student_cases "
                    "WHERE organization_id=:org AND id=:case FOR UPDATE"
                ),
                {"org": ORG, "case": case_id},
            )
            first = asyncio.create_task(
                attempt_create(first_task, planning_key("concurrent:first"))
            )
            second = asyncio.create_task(
                attempt_create(second_task, planning_key("concurrent:second"))
            )
            await asyncio.sleep(0.1)
            assert not first.done()
            assert not second.done()
        results = await asyncio.wait_for(
            asyncio.gather(first, second), timeout=5
        )
        assert sorted(result[0] for result in results) == ["created", "rejected"]
        assert {result[1] for result in results if result[0] == "rejected"} == {"NV009"}
        winning_task = next(
            result[1] for result in results if result[0] == "created"
        )
        assert isinstance(winning_task, UUID)

        async with migrator.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            assert await authority_projection(connection, case_id) == {
                "state": "planning",
                "tasks": 1,
                "pins": 1,
                "dispatches": 1,
                "events": 1,
                "idempotency": 1,
                "executions": 0,
            }
        await cancel_task(winning_task)
    finally:
        await api.dispose()
        await migrator.dispose()


ROLLBACK_BOUNDARIES = {
    "case_update": ("app.student_cases", "BEFORE UPDATE", "WHEN (NEW.state='planning')"),
    "task_insert": ("app.agent_tasks", "BEFORE INSERT", ""),
    "dispatch_insert": ("internal.agent_task_dispatch", "BEFORE INSERT", ""),
    "event_insert": ("app.agent_task_events", "BEFORE INSERT", ""),
    "idempotency_insert": (
        "app.idempotency_records",
        "BEFORE INSERT",
        "WHEN (NEW.operation='agent_task_create')",
    ),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", tuple(ROLLBACK_BOUNDARIES))
async def test_failure_at_each_write_boundary_rolls_back_case_and_all_residue(
    boundary: str,
) -> None:
    index = tuple(ROLLBACK_BOUNDARIES).index(boundary) + 1
    case_id = UUID(f"42000000-0000-0000-0000-{930 + index:012d}")
    task_id = UUID(f"85000000-0000-0000-0000-{930 + index:012d}")
    function_name = f"test_fail_planning_start_{boundary}"
    trigger_name = f"test_fail_planning_start_{boundary}"
    table, timing, when = ROLLBACK_BOUNDARIES[boundary]
    await seed_intake_case(case_id)
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with migrator.begin() as connection:
            await connection.execute(
                text(
                    f"CREATE FUNCTION app.{function_name}() RETURNS trigger "
                    "LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$ "
                    "BEGIN RAISE EXCEPTION USING ERRCODE='P0001', "
                    f"MESSAGE='injected {boundary} failure'; END; $$"
                )
            )
            await connection.execute(
                text(
                    f"CREATE TRIGGER {trigger_name} {timing} ON {table} "
                    f"FOR EACH ROW {when} EXECUTE FUNCTION app.{function_name}()"
                )
            )

        async with api.connect() as connection:
            with pytest.raises(DBAPIError) as failed:
                async with connection.begin():
                    await set_api_context(connection)
                    await create_task(
                        connection,
                        case_id=case_id,
                        task_id=task_id,
                        key_hash=planning_key(f"rollback:{boundary}"),
                    )
            assert getattr(failed.value.orig, "sqlstate", None) == "P0001"

        async with migrator.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            assert await authority_projection(connection, case_id) == {
                "state": "intake",
                "tasks": 0,
                "pins": 0,
                "dispatches": 0,
                "events": 0,
                "idempotency": 0,
                "executions": 0,
            }
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.idempotency_records "
                        "WHERE organization_id=:org AND operation='agent_task_create' "
                        "AND response_id=:task"
                    ),
                    {"org": ORG, "task": task_id},
                )
                == 0
            )
    finally:
        async with migrator.begin() as connection:
            await connection.execute(text(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table}"))
            await connection.execute(text(f"DROP FUNCTION IF EXISTS app.{function_name}()"))
        await api.dispose()
        await migrator.dispose()
