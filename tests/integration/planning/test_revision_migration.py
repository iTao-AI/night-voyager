# ruff: noqa: E501
from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

pytestmark = pytest.mark.database
ORG = "10000000-0000-0000-0000-000000000001"
ADVISOR = "20000000-0000-0000-0000-000000000001"
STUDENT = "20000000-0000-0000-0000-000000000002"
PARENT = "20000000-0000-0000-0000-000000000003"
PENDING_SIGNATURE = (
    "app.read_connected_journey_fact_pending(uuid,uuid,text,uuid)"
)


def resource(prefix: str, suffix: int) -> str:
    return f"{prefix}-0000-0000-0000-{suffix:012d}"


async def _seed_candidate_case(
    connection: AsyncConnection,
    suffix: int,
    *,
    fact_key: str = "family.budget",
    expired: bool = False,
    stale: bool = False,
    verified: bool = False,
) -> str:
    case_id = resource("4f000000", suffix)
    thread_id = resource("5f000000", suffix)
    message_id = resource("6f000000", suffix)
    candidate_id = resource("7f000000", suffix)
    await connection.execute(
        text(
            "SELECT set_config('night_voyager.organization_id',:org,true)"
        ),
        {"org": ORG},
    )
    source = (
        await connection.execute(
            text(
                "SELECT student_preferences,family_preferences "
                "FROM app.student_case_revisions WHERE organization_id=:org "
                "ORDER BY created_at LIMIT 1"
            ),
            {"org": ORG},
        )
    ).mappings().one()
    await connection.execute(
        text(
            "SELECT app.publish_case_revision("
            ":org,:case,NULL,1,CAST(:student AS jsonb),CAST(:family AS jsonb))"
        ),
        {
            "org": ORG,
            "case": case_id,
            "student": json.dumps(source["student_preferences"]),
            "family": json.dumps(source["family_preferences"]),
        },
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
            "INSERT INTO app.collaboration_threads("
            "organization_id,id,case_id,created_by_actor_id,created_by_role) "
            "VALUES(:org,:thread,:case,:advisor,'advisor')"
        ),
        {
            "org": ORG,
            "thread": thread_id,
            "case": case_id,
            "advisor": ADVISOR,
        },
    )
    await connection.execute(
        text(
            "INSERT INTO app.message_events("
            "organization_id,id,thread_id,case_id,sequence_no,actor_id,"
            "actor_role,body,content_sha256,request_sha256) VALUES("
            ":org,:message,:thread,:case,1,:parent,'parent',"
            "'Synthetic bounded revision proposal.',repeat('a',64),repeat('b',64))"
        ),
        {
            "org": ORG,
            "message": message_id,
            "thread": thread_id,
            "case": case_id,
            "parent": PARENT,
        },
    )
    created = datetime.now(UTC) - (timedelta(days=8) if expired else timedelta())
    await connection.execute(
        text(
            "INSERT INTO app.memory_candidates("
            "organization_id,id,case_id,case_revision,message_event_id,"
            "subject_actor_id,subject_role,proposing_actor_id,proposing_role,"
            "fact_key,proposed_value,value_sha256,request_sha256,created_at,expires_at"
            ") VALUES(:org,:candidate,:case,1,:message,:parent,'parent',"
            ":parent,'parent',:fact_key,'{}'::jsonb,repeat('c',64),"
            "repeat('d',64),:created,:expires)"
        ),
        {
            "org": ORG,
            "candidate": candidate_id,
            "case": case_id,
            "message": message_id,
            "parent": PARENT,
            "fact_key": fact_key,
            "created": created,
            "expires": created + timedelta(days=7),
        },
    )
    if verified:
        await connection.execute(
            text(
                "INSERT INTO app.memory_candidate_verifications("
                "organization_id,id,candidate_id,case_id,advisor_actor_id,"
                "advisor_role,decision,reason,request_sha256) VALUES("
                ":org,:verification,:candidate,:case,:advisor,'advisor',"
                "'reject','Synthetic rejection.',repeat('e',64))"
            ),
            {
                "org": ORG,
                "verification": resource("8f000000", suffix),
                "candidate": candidate_id,
                "case": case_id,
                "advisor": ADVISOR,
            },
        )
    if stale:
        await connection.execute(
            text(
                "SELECT app.publish_case_revision("
                ":org,:case,1,2,CAST(:student AS jsonb),CAST(:family AS jsonb))"
            ),
            {
                "org": ORG,
                "case": case_id,
                "student": json.dumps(source["student_preferences"]),
                "family": json.dumps(source["family_preferences"]),
            },
        )
    return case_id


async def _downgrade_snapshot(connection: AsyncConnection) -> dict[str, Any]:
    await connection.execute(
        text(
            "SELECT set_config('night_voyager.organization_id',"
            "'10000000-0000-0000-0000-000000000001',true)"
        )
    )
    snapshot: dict[str, Any] = {}
    snapshot["version"] = await connection.scalar(
        text("SELECT version_num FROM alembic_version")
    )
    snapshot["columns"] = tuple(
        (
            await connection.execute(
                text(
                    "SELECT table_name,column_name,data_type,is_nullable "
                    "FROM information_schema.columns WHERE table_schema IN ('app','internal') "
                    "AND table_name IN ('student_case_revisions','agent_tasks') "
                    "ORDER BY table_name,ordinal_position"
                )
            )
        ).tuples()
    )
    snapshot["constraints"] = tuple(
        (
            await connection.execute(
                text(
                    "SELECT conname,pg_get_constraintdef(oid) FROM pg_constraint "
                    "WHERE connamespace='app'::regnamespace "
                    "AND conrelid IN ('app.student_case_revisions'::regclass,"
                    "'app.agent_tasks'::regclass,'app.advisor_reviews'::regclass,"
                    "'app.planning_runs'::regclass) ORDER BY conname"
                )
            )
        ).tuples()
    )
    snapshot["indexes"] = tuple(
        (
            await connection.execute(
                text(
                    "SELECT schemaname,indexname,indexdef FROM pg_indexes "
                    "WHERE schemaname='app' AND tablename IN "
                    "('student_case_revisions','agent_tasks','advisor_reviews','planning_runs') "
                    "ORDER BY indexname"
                )
            )
        ).tuples()
    )
    snapshot["functions"] = tuple(
        (
            await connection.execute(
                text(
                    "SELECT p.proname,oidvectortypes(p.proargtypes),"
                    "pg_get_functiondef(p.oid),p.proconfig,p.proacl "
                    "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                    "WHERE n.nspname='app' AND p.proname IN "
                    "('review_planning_run','verify_memory_candidate','create_agent_task',"
                    "'finalize_agent_task_result','persist_planning_result',"
                    "'read_connected_journey_fact_pending') "
                    "ORDER BY p.proname,oidvectortypes(p.proargtypes)"
                )
            )
        ).tuples()
    )
    snapshot["rls"] = tuple(
        (
            await connection.execute(
                text(
                    "SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class "
                    "WHERE relnamespace='app'::regnamespace AND relkind='r' "
                    "ORDER BY relname"
                )
            )
        ).tuples()
    )
    snapshot["triggers"] = tuple(
        (
            await connection.execute(
                text(
                    "SELECT c.relname,t.tgname,t.tgenabled FROM pg_trigger t "
                    "JOIN pg_class c ON c.oid=t.tgrelid "
                    "WHERE c.relnamespace='app'::regnamespace AND NOT t.tgisinternal "
                    "ORDER BY c.relname,t.tgname"
                )
            )
        ).tuples()
    )
    for table in (
        "student_case_revisions",
        "agent_tasks",
        "advisor_reviews",
        "planning_runs",
    ):
        snapshot[table] = tuple(
            (
                await connection.execute(
                    text(
                        f"SELECT to_jsonb(row_value)::text FROM app.{table} row_value "  # noqa: S608
                        "ORDER BY to_jsonb(row_value)::text"
                    )
                )
            ).scalars()
        )
    return snapshot


@pytest.mark.asyncio
async def test_revision_lineage_columns_and_indexes_exist() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            columns = set(
                (
                    await connection.execute(
                        text(
                            "SELECT table_name||'.'||column_name "
                            "FROM information_schema.columns "
                            "WHERE table_schema='app' AND ("
                            "(table_name='student_case_revisions' AND column_name IN "
                            "('revision_requested_by_review_id','superseded_planning_run_id')) OR "
                            "(table_name='agent_tasks' AND column_name='predecessor_planning_run_id'))"
                        )
                    )
                ).scalars()
            )
            indexes = set(
                (
                    await connection.execute(
                        text(
                            "SELECT indexname FROM pg_indexes WHERE schemaname='app' "
                            "AND indexname IN ("
                            "'student_case_revisions_one_planning_successor',"
                            "'planning_runs_one_successor',"
                            "'advisor_reviews_one_request_revision_per_run',"
                            "'agent_tasks_case_revision_read_idx',"
                            "'advisor_reviews_case_revision_run_idx')"
                        )
                    )
                ).scalars()
            )
            constraint_rows = (
                await connection.execute(
                    text(
                        "SELECT conname,pg_get_constraintdef(oid) "
                        "FROM pg_constraint WHERE connamespace='app'::regnamespace "
                        "AND conname IN ("
                        "'student_case_revisions_review_fk',"
                        "'student_case_revisions_predecessor_fk',"
                        "'agent_tasks_predecessor_fk')"
                    )
                )
            ).all()
            constraints = {str(row[0]): str(row[1]) for row in constraint_rows}
    finally:
        await engine.dispose()

    assert columns == {
        "student_case_revisions.revision_requested_by_review_id",
        "student_case_revisions.superseded_planning_run_id",
        "agent_tasks.predecessor_planning_run_id",
    }
    assert indexes == {
        "student_case_revisions_one_planning_successor",
        "planning_runs_one_successor",
        "advisor_reviews_one_request_revision_per_run",
        "agent_tasks_case_revision_read_idx",
        "advisor_reviews_case_revision_run_idx",
    }
    assert constraints == {
        "student_case_revisions_review_fk": (
            "FOREIGN KEY (organization_id, case_id, revision_requested_by_review_id) "
            "REFERENCES app.advisor_reviews(organization_id, case_id, id)"
        ),
        "student_case_revisions_predecessor_fk": (
            "FOREIGN KEY (organization_id, case_id, superseded_planning_run_id) "
            "REFERENCES app.planning_runs(organization_id, case_id, id)"
        ),
        "agent_tasks_predecessor_fk": (
            "FOREIGN KEY (organization_id, case_id, predecessor_planning_run_id) "
            "REFERENCES app.planning_runs(organization_id, case_id, id)"
        ),
    }


@pytest.mark.asyncio
async def test_revision_authority_function_acl_and_search_paths_are_closed() -> None:
    names = {
        "review_planning_run",
        "verify_memory_candidate",
        "create_agent_task",
        "finalize_agent_task_result",
        "persist_planning_result",
    }
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        "SELECT p.proname,p.proconfig,"
                        "has_function_privilege('night_voyager_api',p.oid,'EXECUTE'),"
                        "has_function_privilege('night_voyager_worker',p.oid,'EXECUTE'),"
                        "has_function_privilege('public',p.oid,'EXECUTE') "
                        "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                        "WHERE n.nspname='app' AND p.proname=ANY(:names) "
                        "ORDER BY p.proname"
                    ),
                    {"names": sorted(names)},
                )
            ).all()
    finally:
        await engine.dispose()

    assert {row[0] for row in rows} == names
    assert all(row[1] == ["search_path=pg_catalog, pg_temp"] for row in rows)
    authority = {row[0]: (bool(row[2]), bool(row[3]), bool(row[4])) for row in rows}
    assert authority["review_planning_run"] == (True, False, False)
    assert authority["verify_memory_candidate"] == (True, False, False)
    assert authority["create_agent_task"] == (True, False, False)
    assert authority["finalize_agent_task_result"] == (False, True, False)
    assert authority["persist_planning_result"] == (False, False, False)


@pytest.mark.asyncio
async def test_finalize_replay_authority_compiles_on_fresh_0012_upgrade() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT p.prosecdef,p.proconfig,"
                        "has_function_privilege('night_voyager_api',p.oid,'EXECUTE'),"
                        "has_function_privilege('night_voyager_worker',p.oid,'EXECUTE'),"
                        "has_function_privilege('public',p.oid,'EXECUTE'),"
                        "pg_get_functiondef(p.oid) "
                        "FROM pg_proc p "
                        "WHERE p.oid=to_regprocedure("
                        "'app.finalize_agent_task_result("
                        "uuid,uuid,text,bigint,uuid,text,text,text,text,jsonb,uuid)')"
                    )
                )
            ).one()
    finally:
        await engine.dispose()

    function_sql = str(row[5])
    assert row[0] is True
    assert row[1] == ["search_path=pg_catalog, pg_temp"]
    assert tuple(bool(value) for value in row[2:5]) == (False, True, False)
    for token in (
        "selected.lease_generation IS DISTINCT FROM p_generation",
        "run_row.state=p_state",
        "run_row.reason_code IS NOT DISTINCT FROM p_reason",
        "run_row.evidence_projection_sha256=p_evidence_hash",
        "run_row.output_sha256=p_output_hash",
        "run_row.supersedes_run_id IS NOT DISTINCT FROM p_supersedes",
        "execution_row.lease_generation=p_generation",
        "execution_row.result_planning_run_id=p_run",
        "execution_row.public_code IS NOT DISTINCT FROM p_reason",
    ):
        assert token in function_sql


@pytest.mark.asyncio
async def test_participant_safe_pending_fact_projection_is_exact_and_role_equal() -> None:
    migration = create_async_engine(
        os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"]
    )
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    worker = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    try:
        async with migration.begin() as connection:
            pending = await _seed_candidate_case(connection, 1511)
            verified = await _seed_candidate_case(
                connection, 1512, verified=True
            )
            expired = await _seed_candidate_case(
                connection, 1513, expired=True
            )
            stale = await _seed_candidate_case(connection, 1514, stale=True)
            unrelated = await _seed_candidate_case(
                connection, 1515, fact_key="family.risk_tolerance"
            )
        async with api.begin() as connection:
            for actor, role in (
                (ADVISOR, "advisor"),
                (STUDENT, "student"),
                (PARENT, "parent"),
            ):
                for name, value in (
                    ("night_voyager.organization_id", ORG),
                    ("night_voyager.actor_id", actor),
                    ("night_voyager.role", role),
                ):
                    await connection.execute(
                        text("SELECT set_config(:name,:value,true)"),
                        {"name": name, "value": value},
                    )
                observed = await connection.scalar(
                    text(
                        "SELECT app.read_connected_journey_fact_pending("
                        ":org,:actor,:role,:case)"
                    ),
                    {
                        "org": ORG,
                        "actor": actor,
                        "role": role,
                        "case": pending,
                    },
                )
                assert observed is True
            for case_id in (verified, expired, stale, unrelated):
                observed = await connection.scalar(
                    text(
                        "SELECT app.read_connected_journey_fact_pending("
                        ":org,:actor,'parent',:case)"
                    ),
                    {
                        "org": ORG,
                        "actor": PARENT,
                        "case": case_id,
                    },
                )
                assert observed is False
            for name, value in (
                ("night_voyager.organization_id", ORG),
                ("night_voyager.actor_id", resource("2f000000", 1511)),
                ("night_voyager.role", "advisor"),
            ):
                await connection.execute(
                    text("SELECT set_config(:name,:value,true)"),
                    {"name": name, "value": value},
                )
            with pytest.raises(DBAPIError, match="collaboration resource unavailable"):
                await connection.scalar(
                    text(
                        "SELECT app.read_connected_journey_fact_pending("
                        ":org,:actor,'advisor',:case)"
                    ),
                    {
                        "org": ORG,
                        "actor": resource("2f000000", 1511),
                        "case": pending,
                    },
                )
        async with api.begin() as connection:
            other_org = resource("1f000000", 1511)
            for name, value in (
                ("night_voyager.organization_id", other_org),
                ("night_voyager.actor_id", ADVISOR),
                ("night_voyager.role", "advisor"),
            ):
                await connection.execute(
                    text("SELECT set_config(:name,:value,true)"),
                    {"name": name, "value": value},
                )
            with pytest.raises(DBAPIError, match="collaboration resource unavailable"):
                await connection.scalar(
                    text(
                        "SELECT app.read_connected_journey_fact_pending("
                        ":org,:actor,'advisor',:case)"
                    ),
                    {
                        "org": other_org,
                        "actor": ADVISOR,
                        "case": pending,
                    },
                )
        for table in ("memory_candidates", "memory_candidate_verifications"):
            async with api.connect() as connection:
                with pytest.raises(DBAPIError, match="permission denied"):
                    await connection.scalar(
                        text(f"SELECT count(*) FROM app.{table}")  # noqa: S608
                    )
        async with worker.connect() as connection:
            allowed = await connection.scalar(
                text(
                    "SELECT has_function_privilege("
                    "current_user,:signature,'EXECUTE')"
                ),
                {"signature": PENDING_SIGNATURE},
            )
            assert allowed is False
    finally:
        await worker.dispose()
        await api.dispose()
        await migration.dispose()


@pytest.mark.asyncio
async def test_pending_fact_projection_exact_identity_and_acl_are_closed() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT oidvectortypes(p.proargtypes),p.prosecdef,p.proconfig,"
                        "has_function_privilege('night_voyager_api',p.oid,'EXECUTE'),"
                        "has_function_privilege('night_voyager_worker',p.oid,'EXECUTE'),"
                        "has_function_privilege('public',p.oid,'EXECUTE') "
                        "FROM pg_proc p WHERE p.oid=to_regprocedure(:signature)"
                    ),
                    {"signature": PENDING_SIGNATURE},
                )
            ).one()
    finally:
        await engine.dispose()
    assert row[0] == "uuid, uuid, text, uuid"
    assert row[1] is True
    assert row[2] == ["search_path=pg_catalog, pg_temp"]
    assert tuple(bool(value) for value in row[3:]) == (True, False, False)


@pytest.mark.asyncio
async def test_safe_downgrade_restores_exact_0011_surface() -> None:
    if os.environ.get("NIGHT_VOYAGER_REVISION_MIGRATION_PHASE") != "safe-0011":
        pytest.skip("isolated safe-downgrade phase only")
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            version = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            columns = set(
                (
                    await connection.execute(
                        text(
                            "SELECT table_name||'.'||column_name "
                            "FROM information_schema.columns WHERE table_schema='app' AND ("
                            "(table_name='student_case_revisions' AND column_name IN "
                            "('revision_requested_by_review_id','superseded_planning_run_id')) OR "
                            "(table_name='agent_tasks' AND column_name='predecessor_planning_run_id'))"
                        )
                    )
                ).scalars()
            )
            persist_acl = (
                await connection.execute(
                    text(
                        "SELECT "
                        "has_function_privilege('night_voyager_api',p.oid,'EXECUTE'),"
                        "has_function_privilege('night_voyager_worker',p.oid,'EXECUTE'),"
                        "has_function_privilege('public',p.oid,'EXECUTE') "
                        "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                        "WHERE n.nspname='app' AND p.proname='persist_planning_result'"
                    )
                )
            ).one()
            pending_function = await connection.scalar(
                text(
                    "SELECT to_regprocedure("
                    "'app.read_connected_journey_fact_pending(uuid,uuid,text,uuid)')"
                )
            )
    finally:
        await engine.dispose()
    assert version == "0011"
    assert columns == set()
    assert pending_function is None
    assert tuple(bool(value) for value in persist_acl) == (True, False, False)


@pytest.mark.asyncio
async def test_refused_downgrade_preserves_exact_catalog_and_rows() -> None:
    if os.environ.get("NIGHT_VOYAGER_REVISION_MIGRATION_PHASE") != "refusal":
        pytest.skip("isolated refused-downgrade phase only")
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "SELECT set_config('night_voyager.organization_id',"
                    "'10000000-0000-0000-0000-000000000001',true)"
                )
            )
            lineage_exists = await connection.scalar(
                text(
                    "SELECT EXISTS(SELECT 1 FROM app.student_case_revisions "
                    "WHERE superseded_planning_run_id IS NOT NULL)"
                )
            )
            assert lineage_exists is True
        async with engine.connect() as connection:
            before = await _downgrade_snapshot(connection)
        result = subprocess.run(
            ("uv", "run", "alembic", "downgrade", "0011"),
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        assert result.returncode != 0
        assert "refusing downgrade: planning revision lineage exists" in (
            result.stdout + result.stderr
        )
        async with engine.connect() as connection:
            after = await _downgrade_snapshot(connection)
    finally:
        await engine.dispose()
    assert after == before
