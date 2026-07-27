# ruff: noqa: E501
from __future__ import annotations

import os
import subprocess
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

pytestmark = pytest.mark.database


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
                    "'finalize_agent_task_result','persist_planning_result') "
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
    finally:
        await engine.dispose()
    assert version == "0011"
    assert columns == set()
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
