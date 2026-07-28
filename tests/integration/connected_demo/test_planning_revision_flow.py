from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from types import ModuleType
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from night_voyager.connected_demo.models import DemoPhaseV2
from night_voyager.planning.fixtures import validate_planning_fixture

pytestmark = pytest.mark.database

DEMO_ORG = UUID("10000000-0000-0000-0000-000000000001")
HAPPY_CASE_ID = UUID("49000000-0000-0000-0000-000000000001")
BUDGET_CASE_ID = UUID("49000000-0000-0000-0000-000000000002")
HAPPY_THREAD_ID = UUID("4b000000-0000-0000-0000-000000000001")
BUDGET_THREAD_ID = UUID("4b000000-0000-0000-0000-000000000002")
HAPPY_RUN_ID = UUID("79000000-0000-0000-0000-000000000001")
BUDGET_RUN_ID = UUID("79000000-0000-0000-0000-000000000002")
REVISION_RUN_IDS = (HAPPY_RUN_ID, BUDGET_RUN_ID)
HAPPY_TASK_ID = UUID("89000000-0000-0000-0000-000000000001")
BUDGET_TASK_ID = UUID("89000000-0000-0000-0000-000000000002")
REVISION_TASK_IDS = (HAPPY_TASK_ID, BUDGET_TASK_ID)
HAPPY_EXECUTION_ID = UUID("8a000000-0000-0000-0000-000000000001")
EXACT_RANKING_ID = UUID("74000000-0000-0000-0000-000000000001")
SNAPSHOT_TABLES = (
    "planning_routes",
    "comparison_dimensions",
    "comparison_dimension_evidence_refs",
    "cost_evidence",
    "ranking_evidence",
)


def load_verifier():
    path = Path("scripts/verify_planning_revision_flow.py")
    spec = importlib.util.spec_from_file_location(
        "verify_planning_revision_flow", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_seed_demo() -> ModuleType:
    path = Path("scripts/seed_demo.py")
    spec = importlib.util.spec_from_file_location("planning_revision_seed_demo", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _snapshot_revision_planning_output(
    connection: AsyncConnection,
) -> dict[str, tuple[object, ...]]:
    snapshot: dict[str, tuple[object, ...]] = {}
    scopes: tuple[tuple[str, str, dict[str, object]], ...] = (
        ("student_cases", "id=ANY(:cases)", {"cases": list((HAPPY_CASE_ID, BUDGET_CASE_ID))}),
        (
            "student_case_revisions",
            "case_id=ANY(:cases)",
            {"cases": list((HAPPY_CASE_ID, BUDGET_CASE_ID))},
        ),
        (
            "student_case_participants",
            "case_id=ANY(:cases)",
            {"cases": list((HAPPY_CASE_ID, BUDGET_CASE_ID))},
        ),
        (
            "collaboration_threads",
            "case_id=ANY(:cases)",
            {"cases": list((HAPPY_CASE_ID, BUDGET_CASE_ID))},
        ),
        (
            "message_events",
            "case_id=ANY(:cases)",
            {"cases": list((HAPPY_CASE_ID, BUDGET_CASE_ID))},
        ),
        (
            "memory_candidates",
            "case_id=ANY(:cases)",
            {"cases": list((HAPPY_CASE_ID, BUDGET_CASE_ID))},
        ),
        (
            "memory_candidate_verifications",
            "case_id=ANY(:cases)",
            {"cases": list((HAPPY_CASE_ID, BUDGET_CASE_ID))},
        ),
        (
            "confirmed_facts",
            "case_id=ANY(:cases)",
            {"cases": list((HAPPY_CASE_ID, BUDGET_CASE_ID))},
        ),
        (
            "case_revision_confirmed_fact_refs",
            "case_id=ANY(:cases)",
            {"cases": list((HAPPY_CASE_ID, BUDGET_CASE_ID))},
        ),
        ("planning_runs", "id=ANY(:runs)", {"runs": list(REVISION_RUN_IDS)}),
        (
            "agent_tasks",
            "id=ANY(:tasks)",
            {"tasks": list(REVISION_TASK_IDS)},
        ),
        (
            "agent_executions",
            "task_id=ANY(:tasks)",
            {"tasks": list(REVISION_TASK_IDS)},
        ),
        (
            "agent_task_events",
            "task_id=ANY(:tasks)",
            {"tasks": list(REVISION_TASK_IDS)},
        ),
    )
    for table, predicate, parameters in scopes:
        rows = await connection.execute(
            text(
                f"SELECT to_jsonb(selected) FROM (SELECT * FROM app.{table} "
                f"WHERE organization_id=:org AND {predicate}"
                ") AS selected ORDER BY to_jsonb(selected)::text"
            ),
            {"org": DEMO_ORG, **parameters},
        )
        snapshot[table] = tuple(rows.scalars())
    for table in SNAPSHOT_TABLES:
        child_rows = await connection.execute(
            text(
                f"SELECT to_jsonb(selected) FROM (SELECT * FROM app.{table} "
                "WHERE organization_id=:org AND planning_run_id=ANY(:runs)"
                ") AS selected ORDER BY to_jsonb(selected)::text"
            ),
            {"org": DEMO_ORG, "runs": list(REVISION_RUN_IDS)},
        )
        snapshot[table] = tuple(child_rows.scalars())
    return snapshot


def _verified_row(*, blocked: bool) -> dict[str, object]:
    return {
        "case_id": str(BUDGET_CASE_ID if blocked else HAPPY_CASE_ID),
        "state": "planning" if blocked else "plan_ready",
        "current_revision": 2,
        "revision_predecessor": "4d000000-0000-0000-0000-000000000001",
        "task_predecessor": "4d000000-0000-0000-0000-000000000001",
        "task_run": "4d000000-0000-0000-0000-000000000002",
        "run_predecessor": "4d000000-0000-0000-0000-000000000001",
        "current_run_state": "blocked" if blocked else "review_required",
        "revision_count": 2,
        "candidate_count": 2,
        "confirmed_fact_count": 2,
        "run_count": 2,
        "current_run_count": 1,
        "revised_task_count": 1,
        "execution_count": 1 if blocked else 2,
        "task_event_count": 4 if blocked else 7,
        "request_review_count": 1,
        "approval_review_count": 0 if blocked else 1,
        "brief_count": 0 if blocked else 1,
        "decision_count": 0 if blocked else 1,
        "receipt_count": 0 if blocked else 1,
        "timeline_count": 0 if blocked else 1,
    }


def _identity(*, blocked: bool) -> dict[str, str]:
    return {
        "case_id": str(BUDGET_CASE_ID if blocked else HAPPY_CASE_ID),
        "request_review_id": "4e000000-0000-0000-0000-000000000001",
        "predecessor_run_id": "4d000000-0000-0000-0000-000000000001",
        "task_id": "4f000000-0000-0000-0000-000000000001",
        "current_run_id": "4d000000-0000-0000-0000-000000000002",
    }


def test_revision_browser_proof_parser_and_exact_count_validation(tmp_path: Path) -> None:
    verifier = load_verifier()
    proof_path = tmp_path / "proof.json"
    proof_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "locale": "zh-CN",
                "happy": _identity(blocked=False),
                "blocked": _identity(blocked=True),
            }
        ),
        encoding="utf-8",
    )
    proof = verifier.load_proof(proof_path)
    verifier.validate_happy(_verified_row(blocked=False), proof["happy"])
    verifier.validate_blocked(_verified_row(blocked=True), proof["blocked"])


@pytest.mark.parametrize(
    ("field", "value"),
    (("candidate_count", 1), ("execution_count", 1), ("task_event_count", 6)),
)
def test_revision_happy_verifier_fails_closed_on_count_drift(
    field: str, value: int
) -> None:
    verifier = load_verifier()
    row = _verified_row(blocked=False)
    row[field] = value
    with pytest.raises(SystemExit):
        verifier.validate_happy(row, _identity(blocked=False))


def test_revision_journey_phase_contract_is_closed() -> None:
    assert tuple(phase.value for phase in DemoPhaseV2) == (
        "task_ready",
        "active_task",
        "review_required",
        "revision_requested",
        "revision_fact_pending",
        "replan_required",
        "revision_task_active",
        "revision_review_required",
        "revision_blocked",
        "family_review",
        "plan_ready",
        "terminal_task_failure",
    )


@pytest.mark.asyncio
async def test_revision_journey_seed_is_deterministic_and_pre_authority_only() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,false)"),
                {"org": str(DEMO_ORG)},
            )
            cases = (
                await connection.execute(
                    text(
                        "SELECT c.id,c.state,c.current_revision,"
                        "count(DISTINCT r.id)::integer AS run_count,"
                        "count(DISTINCT t.id)::integer AS task_count,"
                        "count(DISTINCT review.id)::integer AS review_count,"
                        "count(DISTINCT decision.id)::integer AS decision_count "
                        "FROM app.student_cases c "
                        "JOIN app.student_case_revisions revision "
                        "ON revision.organization_id=c.organization_id "
                        "AND revision.case_id=c.id "
                        "AND revision.revision=c.current_revision "
                        "JOIN app.planning_runs r "
                        "ON r.organization_id=c.organization_id "
                        "AND r.case_id=c.id AND r.case_revision=1 AND r.is_current "
                        "JOIN app.agent_tasks t "
                        "ON t.organization_id=c.organization_id "
                        "AND t.case_id=c.id AND t.case_revision=1 "
                        "AND t.result_planning_run_id=r.id "
                        "LEFT JOIN app.advisor_reviews review "
                        "ON review.organization_id=c.organization_id "
                        "AND review.case_id=c.id "
                        "LEFT JOIN app.family_decisions decision "
                        "ON decision.organization_id=c.organization_id "
                        "AND decision.case_id=c.id "
                        "WHERE c.organization_id=:org AND c.id=ANY(:cases) "
                        "GROUP BY c.id,c.state,c.current_revision ORDER BY c.id"
                    ),
                    {"org": DEMO_ORG, "cases": [HAPPY_CASE_ID, BUDGET_CASE_ID]},
                )
            ).mappings().all()
            threads = (
                await connection.execute(
                    text(
                        "SELECT id,case_id FROM app.collaboration_threads "
                        "WHERE organization_id=:org AND id=ANY(:threads) ORDER BY id"
                    ),
                    {
                        "org": DEMO_ORG,
                        "threads": [HAPPY_THREAD_ID, BUDGET_THREAD_ID],
                    },
                )
            ).mappings().all()
        assert [row["id"] for row in cases] == [HAPPY_CASE_ID, BUDGET_CASE_ID]
        assert all(row["state"] == "advisor_review" for row in cases)
        assert all(row["current_revision"] == 1 for row in cases)
        assert all(row["run_count"] == 1 and row["task_count"] == 1 for row in cases)
        assert all(
            row["review_count"] == 0 and row["decision_count"] == 0 for row in cases
        )
        assert [(row["id"], row["case_id"]) for row in threads] == [
            (HAPPY_THREAD_ID, HAPPY_CASE_ID),
            (BUDGET_THREAD_ID, BUDGET_CASE_ID),
        ]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_revision_journey_seed_replay_preserves_terminal_snapshot_exactly() -> None:
    database_url = os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"]
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,false)"),
                {"org": str(DEMO_ORG)},
            )
            before = await _snapshot_revision_planning_output(connection)
        assert len(before["planning_runs"]) == 2
        assert len(before["agent_tasks"]) == 2
        assert len(before["agent_executions"]) == 2
        assert len(before["agent_task_events"]) == 2
        assert all(before[table] for table in SNAPSHOT_TABLES)

        await load_seed_demo().seed_demo(database_url)

        async with engine.connect() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,false)"),
                {"org": str(DEMO_ORG)},
            )
            after = await _snapshot_revision_planning_output(connection)
        assert after == before
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_revision_journey_seed_replay_rejects_missing_snapshot_child_without_repair() -> (
    None
):
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    seed_demo = load_seed_demo()
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.execute(
                    text(
                        "SELECT set_config("
                        "'night_voyager.organization_id',:org,true)"
                    ),
                    {"org": str(DEMO_ORG)},
                )
                deleted_ranking_id = (
                    await connection.execute(
                        text(
                            "DELETE FROM app.ranking_evidence "
                            "WHERE organization_id=:org AND planning_run_id=:run "
                            "AND id=:ranking RETURNING id"
                        ),
                        {
                            "org": DEMO_ORG,
                            "run": HAPPY_RUN_ID,
                            "ranking": EXACT_RANKING_ID,
                        },
                    )
                ).scalar_one()
                missing_count = await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.ranking_evidence "
                        "WHERE organization_id=:org AND planning_run_id=:run"
                    ),
                    {"org": DEMO_ORG, "run": HAPPY_RUN_ID},
                )

                with pytest.raises(
                    RuntimeError,
                    match="demo planning revision snapshot seed mismatch",
                ):
                    await seed_demo._seed_planning_revision_cases(
                        connection, validate_planning_fixture()
                    )

                assert (
                    await connection.scalar(
                        text(
                            "SELECT count(*) FROM app.ranking_evidence "
                            "WHERE organization_id=:org AND planning_run_id=:run"
                        ),
                        {"org": DEMO_ORG, "run": HAPPY_RUN_ID},
                    )
                    == missing_count
                )
                assert (
                    await connection.scalar(
                        text(
                            "SELECT count(*) FROM app.ranking_evidence "
                            "WHERE organization_id=:org AND planning_run_id=:run "
                            "AND id=:ranking"
                        ),
                        {
                            "org": DEMO_ORG,
                            "run": HAPPY_RUN_ID,
                            "ranking": deleted_ranking_id,
                        },
                    )
                    == 0
                )
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("missing_field", "missing_value"),
    (
        ("task_id", UUID("89000000-0000-0000-0000-000000000099")),
        ("execution_id", UUID("8a000000-0000-0000-0000-000000000099")),
        ("event_sequence", 2),
    ),
)
async def test_revision_journey_seed_replay_rejects_missing_task_authority_without_repair(
    missing_field: str, missing_value: object
) -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    seed_demo = load_seed_demo()
    fixture = validate_planning_fixture()
    spec: dict[str, Any] = dict(seed_demo.PLANNING_REVISION_CASES[0])
    spec[missing_field] = missing_value
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.execute(
                    text(
                        "SELECT set_config("
                        "'night_voyager.organization_id',:org,true)"
                    ),
                    {"org": str(DEMO_ORG)},
                )
                before = await _snapshot_revision_planning_output(connection)
                with pytest.raises(
                    RuntimeError,
                    match="demo planning revision fixture seed mismatch",
                ):
                    await seed_demo._assert_exact_planning_revision_fixture(
                        connection, fixture, spec
                    )
                after = await _snapshot_revision_planning_output(connection)
                assert after == before
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_revision_journey_seed_replay_rejects_task_identity_drift_without_repair() -> (
    None
):
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    seed_demo = load_seed_demo()
    fixture = validate_planning_fixture()
    drifted_request_sha256 = "f" * 64
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.execute(
                    text(
                        "SELECT set_config("
                        "'night_voyager.organization_id',:org,true)"
                    ),
                    {"org": str(DEMO_ORG)},
                )
                await connection.execute(
                    text(
                        "UPDATE app.agent_tasks SET request_sha256=:drift "
                        "WHERE organization_id=:org AND id=:task"
                    ),
                    {
                        "org": DEMO_ORG,
                        "task": HAPPY_TASK_ID,
                        "drift": drifted_request_sha256,
                    },
                )
                with pytest.raises(
                    RuntimeError,
                    match="demo planning revision fixture seed mismatch",
                ):
                    await seed_demo._assert_exact_planning_revision_fixture(
                        connection,
                        fixture,
                        dict(seed_demo.PLANNING_REVISION_CASES[0]),
                    )
                assert (
                    await connection.scalar(
                        text(
                            "SELECT request_sha256 FROM app.agent_tasks "
                            "WHERE organization_id=:org AND id=:task"
                        ),
                        {"org": DEMO_ORG, "task": HAPPY_TASK_ID},
                    )
                    == drifted_request_sha256
                )
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
