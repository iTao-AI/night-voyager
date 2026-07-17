from __future__ import annotations

import os
import subprocess
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from night_voyager.planning.fixtures import validate_planning_fixture

pytestmark = pytest.mark.database

ROOT = Path(__file__).resolve().parents[3]
SCENARIO_ENV = "NIGHT_VOYAGER_COLLABORATION_DOWNGRADE_SCENARIO"
SCENARIOS = frozenset(
    {
        "empty",
        "unrelated",
        "table-history",
        "audit-history",
        "idempotency-history",
    }
)
SCENARIO = os.environ.get(SCENARIO_ENV)

ORG_ID = UUID("10000000-0000-0000-0000-000000000531")
CASE_ID = UUID("40000000-0000-0000-0000-000000000531")
THREAD_ID = UUID("42000000-0000-0000-0000-000000000531")
ADVISOR_ID = UUID("20000000-0000-0000-0000-000000000531")
STUDENT_ID = UUID("20000000-0000-0000-0000-000000000532")
PARENT_ID = UUID("20000000-0000-0000-0000-000000000533")
AUDIT_ID = UUID("49000000-0000-0000-0000-000000000531")
LEDGER_RESPONSE_ID = UUID("49000000-0000-0000-0000-000000000532")
TASK_ID = UUID("48000000-0000-0000-0000-000000000531")
PACK_ID = UUID("50000000-0000-0000-0000-000000000531")
COLLABORATION_TABLES = (
    "collaboration_threads",
    "message_events",
    "memory_candidates",
    "memory_candidate_verifications",
    "confirmed_facts",
    "case_revision_confirmed_fact_refs",
)
COLLABORATION_FUNCTIONS = frozenset(
    {
        "reject_collaboration_mutation",
        "serialize_agent_task_case_revision",
        "assert_collaboration_context",
        "validate_collaboration_message",
        "validate_collaboration_fact",
        "create_collaboration_thread",
        "append_collaboration_message",
        "propose_memory_candidate",
        "verify_memory_candidate",
        "read_collaboration_thread",
        "read_collaboration_messages",
        "read_memory_candidates",
        "read_confirmed_facts",
        "seed_demo_collaboration",
    }
)
LEGACY_REVISION_SIGNATURE = "app.publish_case_revision(uuid,uuid,integer,integer,jsonb,jsonb)"
PLANNING_PERSISTENCE_SIGNATURE = (
    "app.persist_planning_result("
    "uuid,uuid,uuid,integer,uuid,integer,text,text,text,text,text,uuid,jsonb)"
)
RUN_GUARD_SIGNATURE = "app.guard_run_transition()"
REFUSAL_MESSAGE = "refusing downgrade: collaboration authority history exists"


async def _set_context(connection: AsyncConnection) -> None:
    for name, value in (
        ("organization_id", ORG_ID),
        ("actor_id", ADVISOR_ID),
        ("role", "advisor"),
    ):
        await connection.execute(
            text("SELECT set_config(:name,:value,true)"),
            {"name": f"night_voyager.{name}", "value": str(value)},
        )


async def _ensure_base_graph() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    planning_case = validate_planning_fixture().planning_input.case
    try:
        async with engine.begin() as connection:
            await _set_context(connection)
            await connection.execute(
                text(
                    "INSERT INTO app.organizations(id,name,is_synthetic) "
                    "VALUES(:org,'Synthetic collaboration downgrade proof',true) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {"org": ORG_ID},
            )
            for offset, (actor_id, role) in enumerate(
                (
                    (ADVISOR_ID, "advisor"),
                    (STUDENT_ID, "student"),
                    (PARENT_ID, "parent"),
                ),
                start=1,
            ):
                await connection.execute(
                    text(
                        "INSERT INTO app.actors("
                        "id,organization_id,display_name,is_synthetic) "
                        "VALUES(:actor,:org,:display_name,true) "
                        "ON CONFLICT (id) DO NOTHING"
                    ),
                    {
                        "actor": actor_id,
                        "org": ORG_ID,
                        "display_name": f"Synthetic downgrade {role}",
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO app.memberships("
                        "id,organization_id,actor_id,role) "
                        "VALUES(:membership,:org,:actor,:role) "
                        "ON CONFLICT (organization_id,actor_id,role) DO NOTHING"
                    ),
                    {
                        "membership": UUID(f"35000000-0000-0000-0000-{5310 + offset:012d}"),
                        "org": ORG_ID,
                        "actor": actor_id,
                        "role": role,
                    },
                )
            case_exists = await connection.scalar(
                text(
                    "SELECT EXISTS(SELECT 1 FROM app.student_cases "
                    "WHERE organization_id=:org AND id=:case)"
                ),
                {"org": ORG_ID, "case": CASE_ID},
            )
            if not case_exists:
                await connection.execute(
                    text(
                        "SELECT app.publish_case_revision("
                        ":org,:case,NULL,1,CAST(:student AS jsonb),"
                        "CAST(:family AS jsonb))"
                    ),
                    {
                        "org": ORG_ID,
                        "case": CASE_ID,
                        "student": planning_case.student.model_dump_json(),
                        "family": planning_case.family.model_dump_json(),
                    },
                )
            await connection.execute(
                text("SELECT app.seed_case_participants(:org,:case,:advisor,:student,:parent)"),
                {
                    "org": ORG_ID,
                    "case": CASE_ID,
                    "advisor": ADVISOR_ID,
                    "student": STUDENT_ID,
                    "parent": PARENT_ID,
                },
            )
    finally:
        await engine.dispose()


async def _seed_unrelated_history() -> None:
    await _ensure_base_graph()
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await _set_context(connection)
            await connection.execute(
                text(
                    "INSERT INTO app.source_packs("
                    "organization_id,id,version,schema_version,manifest_sha256) "
                    "VALUES(:org,:pack,1,1,repeat('5',64))"
                ),
                {"org": ORG_ID, "pack": PACK_ID},
            )
            await connection.execute(
                text("SELECT app.transition_case(:org,:case,'intake','planning')"),
                {"org": ORG_ID, "case": CASE_ID},
            )
            await connection.execute(
                text(
                    "SELECT * FROM app.create_agent_task("
                    ":org,:actor,:case,:task,'generate_planning_run_v1',1,"
                    ":pack,1,'m3a-policy-v1',repeat('6',64),repeat('7',64))"
                ),
                {
                    "org": ORG_ID,
                    "actor": ADVISOR_ID,
                    "case": CASE_ID,
                    "task": TASK_ID,
                    "pack": PACK_ID,
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO app.audit_events("
                    "organization_id,id,case_id,actor_id,event_type,subject_id,payload) "
                    "VALUES(:org,:audit,:case,:actor,'advisor_review',:subject,"
                    'CAST(\'{"action":"request_revision"}\' AS jsonb))'
                ),
                {
                    "org": ORG_ID,
                    "audit": AUDIT_ID,
                    "case": CASE_ID,
                    "actor": ADVISOR_ID,
                    "subject": LEDGER_RESPONSE_ID,
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO app.idempotency_records("
                    "organization_id,actor_id,operation,key_sha256,request_sha256,"
                    "response_kind,response_id) VALUES("
                    ":org,:actor,'advisor_review',repeat('a',64),repeat('b',64),"
                    "'advisor_review',:response)"
                ),
                {
                    "org": ORG_ID,
                    "actor": ADVISOR_ID,
                    "response": LEDGER_RESPONSE_ID,
                },
            )
    finally:
        await engine.dispose()


async def _seed_table_history() -> None:
    await _ensure_base_graph()
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await _set_context(connection)
            await connection.execute(
                text(
                    "INSERT INTO app.collaboration_threads("
                    "organization_id,id,case_id,created_by_actor_id,created_by_role) "
                    "VALUES(:org,:thread,:case,:advisor,'advisor')"
                ),
                {
                    "org": ORG_ID,
                    "case": CASE_ID,
                    "thread": THREAD_ID,
                    "advisor": ADVISOR_ID,
                },
            )
    finally:
        await engine.dispose()


async def _seed_audit_history() -> None:
    await _ensure_base_graph()
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await _set_context(connection)
            await connection.execute(
                text(
                    "INSERT INTO app.audit_events("
                    "organization_id,id,case_id,actor_id,event_type,subject_id,payload) "
                    "VALUES(:org,:audit,:case,:actor,'memory_candidate_confirmed',"
                    ":subject,jsonb_build_object('revision',2))"
                ),
                {
                    "org": ORG_ID,
                    "audit": AUDIT_ID,
                    "case": CASE_ID,
                    "actor": ADVISOR_ID,
                    "subject": LEDGER_RESPONSE_ID,
                },
            )
    finally:
        await engine.dispose()


async def _seed_idempotency_history() -> None:
    await _ensure_base_graph()
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await _set_context(connection)
            await connection.execute(
                text(
                    "INSERT INTO app.idempotency_records("
                    "organization_id,actor_id,operation,key_sha256,request_sha256,"
                    "response_kind,response_id) VALUES("
                    ":org,:actor,'memory_candidate_verify',repeat('c',64),"
                    "repeat('d',64),'memory_candidate_verification',:response)"
                ),
                {
                    "org": ORG_ID,
                    "actor": ADVISOR_ID,
                    "response": LEDGER_RESPONSE_ID,
                },
            )
    finally:
        await engine.dispose()


def _run_alembic(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["uv", "run", "alembic", *arguments],
        cwd=ROOT,
        env=os.environ.copy(),
        check=False,
        capture_output=True,
        text=True,
    )
    if check:
        assert completed.returncode == 0, (
            f"alembic {' '.join(arguments)} exited {completed.returncode}"
        )
    return completed


async def _migration_head() -> str:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            head = await connection.scalar(text("SELECT version_num FROM alembic_version"))
    finally:
        await engine.dispose()
    assert isinstance(head, str)
    return head


async def _collaboration_catalog() -> dict[str, tuple[bool, bool]]:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            rows = (
                await connection.execute(
                    text(
                        "SELECT relation.relname,relation.relrowsecurity,"
                        "relation.relforcerowsecurity "
                        "FROM pg_class relation JOIN pg_namespace namespace "
                        "ON namespace.oid=relation.relnamespace "
                        "WHERE namespace.nspname='app' AND relation.relname IN ("
                        "'collaboration_threads','message_events','memory_candidates',"
                        "'memory_candidate_verifications','confirmed_facts',"
                        "'case_revision_confirmed_fact_refs')"
                    )
                )
            ).all()
    finally:
        await engine.dispose()
    return {str(name): (bool(enabled), bool(forced)) for name, enabled, forced in rows}


async def _collaboration_function_catalog() -> dict[str, str]:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            rows = (
                await connection.execute(
                    text(
                        "SELECT procedure.proname,pg_get_functiondef(procedure.oid) "
                        "FROM pg_proc procedure JOIN pg_namespace namespace "
                        "ON namespace.oid=procedure.pronamespace "
                        "WHERE namespace.nspname='app' AND procedure.proname IN ("
                        "'reject_collaboration_mutation',"
                        "'serialize_agent_task_case_revision',"
                        "'assert_collaboration_context','validate_collaboration_message',"
                        "'validate_collaboration_fact','create_collaboration_thread',"
                        "'append_collaboration_message','propose_memory_candidate',"
                        "'verify_memory_candidate','read_collaboration_thread',"
                        "'read_collaboration_messages','read_memory_candidates',"
                        "'read_confirmed_facts','seed_demo_collaboration')"
                    )
                )
            ).all()
    finally:
        await engine.dispose()
    return {str(name): str(definition) for name, definition in rows}


async def _collaboration_counts() -> dict[str, int]:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    counts: dict[str, int] = {}
    try:
        async with engine.begin() as connection:
            await _set_context(connection)
            for table in COLLABORATION_TABLES:
                count = await connection.scalar(text(f"SELECT count(*) FROM app.{table}"))
                assert isinstance(count, int)
                counts[table] = count
    finally:
        await engine.dispose()
    return counts


async def _pr_a_history_counts() -> tuple[int, int]:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await _set_context(connection)
            audit_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM app.audit_events "
                    "WHERE organization_id=:org AND event_type IN ("
                    "'memory_candidate_confirmed','memory_candidate_rejected')"
                ),
                {"org": ORG_ID},
            )
            ledger_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM app.idempotency_records "
                    "WHERE organization_id=:org AND operation IN ("
                    "'collaboration_thread_create','collaboration_message_append',"
                    "'memory_candidate_propose','memory_candidate_verify')"
                ),
                {"org": ORG_ID},
            )
    finally:
        await engine.dispose()
    assert isinstance(audit_count, int)
    assert isinstance(ledger_count, int)
    return audit_count, ledger_count


async def _unrelated_history_counts() -> dict[str, int]:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await _set_context(connection)
            row = (
                await connection.execute(
                    text(
                        "SELECT "
                        "(SELECT count(*) FROM app.audit_events "
                        "WHERE organization_id=:org AND event_type='advisor_review'),"
                        "(SELECT count(*) FROM app.idempotency_records "
                        "WHERE organization_id=:org AND operation='advisor_review'),"
                        "(SELECT count(*) FROM app.idempotency_records "
                        "WHERE organization_id=:org AND operation='agent_task_create'),"
                        "(SELECT count(*) FROM app.agent_tasks "
                        "WHERE organization_id=:org AND id=:task),"
                        "(SELECT count(*) FROM app.agent_task_events "
                        "WHERE organization_id=:org AND task_id=:task)"
                    ),
                    {"org": ORG_ID, "task": TASK_ID},
                )
            ).one()
    finally:
        await engine.dispose()
    labels = (
        "advisor_review_audit",
        "advisor_review_idempotency",
        "agent_task_create_idempotency",
        "agent_tasks",
        "agent_task_events",
    )
    return {label: int(count) for label, count in zip(labels, row, strict=True)}


async def _legacy_writer_api_grant() -> bool:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            granted = await connection.scalar(
                text("SELECT has_function_privilege('night_voyager_api',:signature,'EXECUTE')"),
                {"signature": LEGACY_REVISION_SIGNATURE},
            )
    finally:
        await engine.dispose()
    assert isinstance(granted, bool)
    return granted


async def _legacy_writer_definition() -> str:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            definition = await connection.scalar(
                text("SELECT pg_get_functiondef(to_regprocedure(:signature))"),
                {"signature": LEGACY_REVISION_SIGNATURE},
            )
    finally:
        await engine.dispose()
    assert isinstance(definition, str)
    return definition


async def _planning_persistence_definition() -> str:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            definition = await connection.scalar(
                text("SELECT pg_get_functiondef(to_regprocedure(:signature))"),
                {"signature": PLANNING_PERSISTENCE_SIGNATURE},
            )
    finally:
        await engine.dispose()
    assert isinstance(definition, str)
    return definition


async def _run_guard_definition() -> str:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            definition = await connection.scalar(
                text("SELECT pg_get_functiondef(to_regprocedure(:signature))"),
                {"signature": RUN_GUARD_SIGNATURE},
            )
    finally:
        await engine.dispose()
    assert isinstance(definition, str)
    return definition


async def _shared_ledger_rls_catalog() -> dict[str, tuple[bool, bool]]:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            rows = (
                await connection.execute(
                    text(
                        "SELECT relation.relname,relation.relrowsecurity,"
                        "relation.relforcerowsecurity "
                        "FROM pg_class relation JOIN pg_namespace namespace "
                        "ON namespace.oid=relation.relnamespace "
                        "WHERE namespace.nspname='app' AND relation.relname IN ("
                        "'audit_events','idempotency_records')"
                    )
                )
            ).all()
    finally:
        await engine.dispose()
    return {str(name): (bool(enabled), bool(forced)) for name, enabled, forced in rows}


async def _exercise_legacy_api_writer_at_0006() -> None:
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    planning_case = validate_planning_fixture().planning_input.case
    try:
        async with migrator.begin() as connection:
            await _set_context(connection)
            await connection.execute(
                text(
                    "INSERT INTO app.organizations(id,name,is_synthetic) "
                    "VALUES(:org,'Synthetic empty-boundary downgrade proof',true)"
                ),
                {"org": ORG_ID},
            )
        async with api.begin() as connection:
            await _set_context(connection)
            await connection.execute(
                text(
                    "SELECT app.publish_case_revision("
                    ":org,:case,NULL,1,CAST(:student AS jsonb),CAST(:family AS jsonb))"
                ),
                {
                    "org": ORG_ID,
                    "case": CASE_ID,
                    "student": planning_case.student.model_dump_json(),
                    "family": planning_case.family.model_dump_json(),
                },
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT current_revision FROM app.student_cases "
                        "WHERE organization_id=:org AND id=:case"
                    ),
                    {"org": ORG_ID, "case": CASE_ID},
                )
                == 1
            )
    finally:
        await api.dispose()
        await migrator.dispose()


async def _collaboration_trigger_definition() -> str | None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            definition = await connection.scalar(
                text(
                    "SELECT pg_get_triggerdef(oid) FROM pg_trigger "
                    "WHERE tgname='agent_tasks_collaboration_case_revision' "
                    "AND NOT tgisinternal"
                )
            )
    finally:
        await engine.dispose()
    assert definition is None or isinstance(definition, str)
    return definition


async def _assert_empty_boundary_at_0007() -> None:
    assert await _migration_head() == "0007"
    assert await _collaboration_catalog() == {table: (True, True) for table in COLLABORATION_TABLES}
    assert frozenset(await _collaboration_function_catalog()) == COLLABORATION_FUNCTIONS
    assert await _collaboration_counts() == {table: 0 for table in COLLABORATION_TABLES}
    assert await _legacy_writer_api_grant() is False
    planning_persistence = await _planning_persistence_definition()
    case_lock = planning_persistence.index("FROM app.student_cases selected_case_row")
    assert case_lock < planning_persistence.index("FOR UPDATE", case_lock)
    assert case_lock < planning_persistence.index("UPDATE app.planning_runs")
    assert "app.memory_candidate_verifications verification" in await _run_guard_definition()
    assert await _collaboration_trigger_definition() is not None
    assert await _shared_ledger_rls_catalog() == {
        "audit_events": (True, True),
        "idempotency_records": (True, True),
    }


async def _assert_exact_0006_restore(
    expected_legacy_definition: str,
    expected_planning_persistence_definition: str,
    expected_run_guard_definition: str,
) -> None:
    assert await _migration_head() == "0006"
    assert await _collaboration_catalog() == {}
    assert await _collaboration_function_catalog() == {}
    assert await _legacy_writer_api_grant() is True
    assert await _legacy_writer_definition() == expected_legacy_definition
    assert (
        await _planning_persistence_definition()
        == expected_planning_persistence_definition
    )
    assert await _run_guard_definition() == expected_run_guard_definition
    assert await _collaboration_trigger_definition() is None
    assert await _shared_ledger_rls_catalog() == {
        "audit_events": (True, True),
        "idempotency_records": (True, True),
    }


async def _capture_exact_0006_baseline() -> tuple[str, str, str]:
    await _assert_empty_boundary_at_0007()
    _run_alembic("downgrade", "0001")
    try:
        _run_alembic("upgrade", "0006")
        legacy_definition = await _legacy_writer_definition()
        planning_persistence_definition = await _planning_persistence_definition()
        run_guard_definition = await _run_guard_definition()
        await _assert_exact_0006_restore(
            legacy_definition,
            planning_persistence_definition,
            run_guard_definition,
        )
    finally:
        _run_alembic("upgrade", "head")
    await _assert_empty_boundary_at_0007()
    return legacy_definition, planning_persistence_definition, run_guard_definition


async def _round_trip_empty_boundary(
    expected_legacy_definition: str,
    expected_planning_persistence_definition: str,
    expected_run_guard_definition: str,
) -> None:
    await _assert_empty_boundary_at_0007()
    _run_alembic("downgrade", "0006")
    try:
        await _assert_exact_0006_restore(
            expected_legacy_definition,
            expected_planning_persistence_definition,
            expected_run_guard_definition,
        )
        await _exercise_legacy_api_writer_at_0006()
    finally:
        _run_alembic("upgrade", "head")
    assert await _migration_head() == "0007"
    assert await _collaboration_catalog() == {table: (True, True) for table in COLLABORATION_TABLES}
    assert frozenset(await _collaboration_function_catalog()) == COLLABORATION_FUNCTIONS
    assert await _collaboration_counts() == {table: 0 for table in COLLABORATION_TABLES}
    assert await _legacy_writer_api_grant() is False


async def _round_trip_unrelated_history(
    expected_legacy_definition: str,
    expected_planning_persistence_definition: str,
    expected_run_guard_definition: str,
) -> None:
    await _seed_unrelated_history()
    assert await _collaboration_counts() == {table: 0 for table in COLLABORATION_TABLES}
    assert await _pr_a_history_counts() == (0, 0)
    unrelated = {
        "advisor_review_audit": 1,
        "advisor_review_idempotency": 1,
        "agent_task_create_idempotency": 1,
        "agent_tasks": 1,
        "agent_task_events": 1,
    }
    assert await _unrelated_history_counts() == unrelated
    _run_alembic("downgrade", "0006")
    try:
        await _assert_exact_0006_restore(
            expected_legacy_definition,
            expected_planning_persistence_definition,
            expected_run_guard_definition,
        )
        assert await _pr_a_history_counts() == (0, 0)
        assert await _unrelated_history_counts() == unrelated
    finally:
        _run_alembic("upgrade", "head")
    assert await _migration_head() == "0007"
    assert await _pr_a_history_counts() == (0, 0)
    assert await _unrelated_history_counts() == unrelated
    assert await _collaboration_counts() == {table: 0 for table in COLLABORATION_TABLES}


async def _assert_history_refuses_downgrade() -> None:
    before_tables = await _collaboration_counts()
    before_pr_a_history = await _pr_a_history_counts()
    before_catalog = await _collaboration_catalog()
    before_functions = await _collaboration_function_catalog()
    before_trigger = await _collaboration_trigger_definition()
    before_shared_rls = await _shared_ledger_rls_catalog()
    assert before_catalog == {table: (True, True) for table in COLLABORATION_TABLES}
    assert frozenset(before_functions) == COLLABORATION_FUNCTIONS
    assert before_trigger is not None
    assert before_shared_rls == {
        "audit_events": (True, True),
        "idempotency_records": (True, True),
    }
    assert await _legacy_writer_api_grant() is False
    refused = _run_alembic("downgrade", "0006", check=False)
    assert refused.returncode != 0
    assert REFUSAL_MESSAGE in f"{refused.stdout}\n{refused.stderr}"
    assert await _migration_head() == "0007"
    assert await _collaboration_counts() == before_tables
    assert await _pr_a_history_counts() == before_pr_a_history
    assert await _collaboration_catalog() == before_catalog
    assert await _collaboration_function_catalog() == before_functions
    assert await _collaboration_trigger_definition() == before_trigger
    assert await _shared_ledger_rls_catalog() == before_shared_rls
    assert await _legacy_writer_api_grant() is False


def test_collaboration_downgrade_scenario_contract_is_explicit() -> None:
    assert not SCENARIOS.symmetric_difference(
        {
            "empty",
            "unrelated",
            "table-history",
            "audit-history",
            "idempotency-history",
        }
    )
    source = Path(__file__).read_text(encoding="utf-8")
    baseline = source[
        source.index("async def _capture_exact_0006_baseline") : source.index(
            "async def _round_trip_empty_boundary"
        )
    ]
    assert baseline.index('_run_alembic("downgrade", "0001")') < baseline.index(
        '_run_alembic("upgrade", "0006")'
    )


@pytest.mark.skipif(
    SCENARIO not in SCENARIOS,
    reason=f"set {SCENARIO_ENV} to one isolated downgrade scenario",
)
@pytest.mark.asyncio
async def test_collaboration_downgrade_scenario_is_isolated_and_fail_closed() -> None:
    assert SCENARIO in SCENARIOS
    (
        expected_legacy_definition,
        expected_planning_persistence_definition,
        expected_run_guard_definition,
    ) = await _capture_exact_0006_baseline()
    if SCENARIO == "empty":
        await _round_trip_empty_boundary(
            expected_legacy_definition,
            expected_planning_persistence_definition,
            expected_run_guard_definition,
        )
    elif SCENARIO == "unrelated":
        await _round_trip_unrelated_history(
            expected_legacy_definition,
            expected_planning_persistence_definition,
            expected_run_guard_definition,
        )
    elif SCENARIO == "table-history":
        await _seed_table_history()
        counts = await _collaboration_counts()
        assert counts == {
            "collaboration_threads": 1,
            "message_events": 0,
            "memory_candidates": 0,
            "memory_candidate_verifications": 0,
            "confirmed_facts": 0,
            "case_revision_confirmed_fact_refs": 0,
        }
        assert await _pr_a_history_counts() == (0, 0)
        await _assert_history_refuses_downgrade()
    elif SCENARIO == "audit-history":
        await _seed_audit_history()
        assert await _collaboration_counts() == {table: 0 for table in COLLABORATION_TABLES}
        assert await _pr_a_history_counts() == (1, 0)
        await _assert_history_refuses_downgrade()
    else:
        assert SCENARIO == "idempotency-history"
        await _seed_idempotency_history()
        assert await _collaboration_counts() == {table: 0 for table in COLLABORATION_TABLES}
        assert await _pr_a_history_counts() == (0, 1)
        await _assert_history_refuses_downgrade()
