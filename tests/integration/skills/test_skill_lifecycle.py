from __future__ import annotations

import asyncio
import os
import subprocess
from hashlib import sha256
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from night_voyager.planning.fixtures import validate_planning_fixture
from night_voyager.skills.evaluation import SkillEvaluator
from night_voyager.skills.models import SkillKey, canonical_sha256
from night_voyager.skills.registry import SkillRuntimeRegistry

ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
STUDENT = UUID("20000000-0000-0000-0000-000000000002")
PARENT = UUID("20000000-0000-0000-0000-000000000003")
PACK = UUID("50000000-0000-0000-0000-000000000001")
LIFECYCLE_CASES = (
    UUID("8f000000-0000-0000-0000-000000000001"),
    UUID("8f000000-0000-0000-0000-000000000002"),
    UUID("8f000000-0000-0000-0000-000000000003"),
)
CANDIDATE = UUID("8f100000-0000-0000-0000-000000000001")
EVALUATION = UUID("8f200000-0000-0000-0000-000000000001")
PROMOTION = UUID("8f300000-0000-0000-0000-000000000001")
ROLLBACK = UUID("8f300000-0000-0000-0000-000000000002")
CONCURRENT_CANDIDATE = UUID("8f100000-0000-0000-0000-000000000010")
CONCURRENT_EVALUATION = UUID("8f200000-0000-0000-0000-000000000010")
CONCURRENT_EVENTS = (
    UUID("8f300000-0000-0000-0000-000000000010"),
    UUID("8f300000-0000-0000-0000-000000000011"),
)
RACE_CASES = (
    UUID("8f000000-0000-0000-0000-000000000020"),
    UUID("8f000000-0000-0000-0000-000000000021"),
)
RACE_TASKS = (
    UUID("8f400000-0000-0000-0000-000000000020"),
    UUID("8f400000-0000-0000-0000-000000000021"),
)
RACE_CANDIDATES = (
    UUID("8f100000-0000-0000-0000-000000000020"),
    UUID("8f100000-0000-0000-0000-000000000021"),
)
RACE_EVALUATIONS = (
    UUID("8f200000-0000-0000-0000-000000000020"),
    UUID("8f200000-0000-0000-0000-000000000021"),
)
RACE_EVENTS = (
    UUID("8f300000-0000-0000-0000-000000000020"),
    UUID("8f300000-0000-0000-0000-000000000021"),
)


def _key_sha256(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _json(value: object) -> str:
    import json

    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


async def _set_advisor_context(connection: AsyncConnection) -> None:
    for setting, value in (
        ("night_voyager.organization_id", str(ORG)),
        ("night_voyager.actor_id", str(ADVISOR)),
        ("night_voyager.role", "advisor"),
    ):
        await connection.execute(
            text("SELECT set_config(:setting,:value,true)"),
            {"setting": setting, "value": value},
        )


def _manifest(version: str) -> dict[str, object]:
    return (
        SkillRuntimeRegistry.load_packaged()
        .get(SkillKey.STUDY_DESTINATION_COMPARE, version)
        .model_dump(mode="json", exclude_none=True)
    )


def _evaluation() -> dict[str, object]:
    registry = SkillRuntimeRegistry.load_packaged()
    return (
        SkillEvaluator.load_packaged(registry)
        .evaluate(SkillKey.STUDY_DESTINATION_COMPARE, "1.0.1")
        .model_dump(mode="json")
    )


def registration_command(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "uv",
            "run",
            "--no-editable",
            "python",
            "scripts/register_skill_version.py",
            *arguments,
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )


async def reset_nonseed_skill_history() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": "10000000-0000-0000-0000-000000000001"},
            )
            guarded = (
                ("idempotency_records", "idempotency_records_immutable"),
                ("agent_task_events", "agent_task_events_immutable"),
                ("skill_activation_events", "skill_activation_events_immutable"),
                (
                    "skill_evaluation_results",
                    "skill_evaluation_results_immutable",
                ),
                ("skill_change_candidates", "skill_change_candidates_immutable"),
                ("skill_versions", "skill_versions_immutable"),
            )
            for table, trigger in guarded:
                await connection.execute(text(f"ALTER TABLE app.{table} DISABLE TRIGGER {trigger}"))
            await connection.execute(
                text(
                    "DELETE FROM internal.agent_task_dispatch "
                    "WHERE organization_id=:org AND task_id=ANY(:tasks)"
                ),
                {"org": str(ORG), "tasks": list(RACE_TASKS)},
            )
            await connection.execute(
                text(
                    "DELETE FROM app.agent_task_events "
                    "WHERE organization_id=:org AND task_id=ANY(:tasks)"
                ),
                {"org": str(ORG), "tasks": list(RACE_TASKS)},
            )
            await connection.execute(
                text(
                    "DELETE FROM app.idempotency_records WHERE organization_id=:org "
                    "AND (operation IN ('skill_candidate_create',"
                    "'skill_candidate_evaluate','skill_candidate_promote',"
                    "'skill_activation_rollback') OR "
                    "(operation='agent_task_create' AND response_id=ANY(:tasks)))"
                ),
                {"org": str(ORG), "tasks": list(RACE_TASKS)},
            )
            await connection.execute(
                text(
                    "DELETE FROM app.agent_tasks "
                    "WHERE organization_id=:org AND id=ANY(:tasks)"
                ),
                {"org": str(ORG), "tasks": list(RACE_TASKS)},
            )
            for statement in (
                "DELETE FROM app.skill_activation_events WHERE organization_id=:org "
                "AND event_kind<>'seed'",
                "DELETE FROM app.skill_evaluation_results WHERE organization_id=:org "
                "AND NOT is_seed",
                "DELETE FROM app.skill_change_candidates WHERE organization_id=:org",
                "DELETE FROM app.skill_versions WHERE organization_id=:org AND NOT is_seed",
            ):
                await connection.execute(text(statement), {"org": str(ORG)})
            for table, trigger in reversed(guarded):
                await connection.execute(text(f"ALTER TABLE app.{table} ENABLE TRIGGER {trigger}"))
    finally:
        await engine.dispose()


async def _create_candidate(
    connection: AsyncConnection,
    *,
    candidate_id: UUID,
    suffix: str,
) -> None:
    request_hash = canonical_sha256(
        {
            "candidate_id": str(candidate_id),
            "skill_key": "study-destination-compare",
            "version": "1.0.1",
            "suffix": suffix,
        }
    )
    row = (
        (
            await connection.execute(
                text(
                    "SELECT * FROM app.create_skill_change_candidate("
                    ":org,:actor,'study-destination-compare',:candidate,'1.0.1',"
                    "'maintainer_proposal',:reason,NULL,CAST(:manifest AS jsonb),"
                    ":request_hash,:key_hash)"
                ),
                {
                    "org": ORG,
                    "actor": ADVISOR,
                    "candidate": candidate_id,
                    "reason": f"Lifecycle candidate {suffix}",
                    "manifest": _json(_manifest("1.0.1")),
                    "request_hash": request_hash,
                    "key_hash": _key_sha256(f"lifecycle-candidate-{suffix}"),
                },
            )
        )
        .mappings()
        .one()
    )
    assert row["candidate_id"] == candidate_id
    assert row["replayed"] is False


async def _record_evaluation(
    connection: AsyncConnection,
    *,
    candidate_id: UUID,
    evaluation_id: UUID,
    suffix: str,
) -> None:
    result = _evaluation()
    row = (
        (
            await connection.execute(
                text(
                    "SELECT * FROM app.record_skill_candidate_evaluation("
                    ":org,:actor,:candidate,:evaluation,CAST(:result AS jsonb),"
                    ":request_hash,:key_hash)"
                ),
                {
                    "org": ORG,
                    "actor": ADVISOR,
                    "candidate": candidate_id,
                    "evaluation": evaluation_id,
                    "result": _json(result),
                    "request_hash": canonical_sha256(result),
                    "key_hash": _key_sha256(f"lifecycle-evaluation-{suffix}"),
                },
            )
        )
        .mappings()
        .one()
    )
    assert row["evaluation_id"] == evaluation_id
    assert row["status"] == "passed"
    assert row["replayed"] is False


async def _promote(
    connection: AsyncConnection,
    *,
    candidate_id: UUID,
    event_id: UUID,
    suffix: str,
) -> None:
    row = (
        (
            await connection.execute(
                text(
                    "SELECT * FROM app.promote_skill_change_candidate("
                    ":org,:actor,:candidate,:event,'1.0.0',1,:reason,"
                    "CAST(:manifest AS jsonb),:request_hash,:key_hash)"
                ),
                {
                    "org": ORG,
                    "actor": ADVISOR,
                    "candidate": candidate_id,
                    "event": event_id,
                    "reason": f"Promote deterministic compatibility {suffix}",
                    "manifest": _json(_manifest("1.0.1")),
                    "request_hash": canonical_sha256({"event": str(event_id), "suffix": suffix}),
                    "key_hash": _key_sha256(f"lifecycle-promote-{suffix}"),
                },
            )
        )
        .mappings()
        .one()
    )
    assert row["activation_event_id"] == event_id
    assert row["activation_sequence"] == 2
    assert row["replayed"] is False


async def _rollback(
    connection: AsyncConnection,
    *,
    event_id: UUID,
    suffix: str,
) -> None:
    row = (
        (
            await connection.execute(
                text(
                    "SELECT * FROM app.rollback_skill_activation("
                    ":org,:actor,'study-destination-compare',:event,'1.0.0',"
                    "'1.0.1',2,:reason,CAST(:manifest AS jsonb),"
                    ":request_hash,:key_hash)"
                ),
                {
                    "org": ORG,
                    "actor": ADVISOR,
                    "event": event_id,
                    "reason": f"Restore canonical runtime {suffix}",
                    "manifest": _json(_manifest("1.0.0")),
                    "request_hash": canonical_sha256({"event": str(event_id), "suffix": suffix}),
                    "key_hash": _key_sha256(f"lifecycle-rollback-{suffix}"),
                },
            )
        )
        .mappings()
        .one()
    )
    assert row["activation_event_id"] == event_id
    assert row["activation_sequence"] == 3
    assert row["replayed"] is False


async def _create_task(
    connection: AsyncConnection,
    *,
    case_id: UUID,
    task_id: UUID,
    manifest_version: str,
    suffix: str,
) -> None:
    row = (
        (
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
                    "case": case_id,
                    "task": task_id,
                    "pack": PACK,
                    "manifest": _json(_manifest(manifest_version)),
                    "request_hash": canonical_sha256({"case_id": str(case_id), "suffix": suffix}),
                    "key_hash": _key_sha256(f"lifecycle-task-{suffix}"),
                },
            )
        )
        .mappings()
        .one()
    )
    assert row["task_id"] == task_id
    assert row["state"] == "queued"


async def _publish_planning_case(connection: AsyncConnection, case_id: UUID) -> None:
    fixture_case = validate_planning_fixture().planning_input.case
    await connection.execute(
        text(
            "SELECT app.publish_case_revision("
            ":org,:case,NULL,1,CAST(:student AS jsonb),CAST(:family AS jsonb))"
        ),
        {
            "org": ORG,
            "case": case_id,
            "student": _json(fixture_case.student.model_dump(mode="json")),
            "family": _json(fixture_case.family.model_dump(mode="json")),
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
            "student": STUDENT,
            "parent": PARENT,
        },
    )


async def _wait_until_blocked(
    observer: AsyncConnection,
    *,
    blocked_pid: int,
    blocker_pid: int,
) -> None:
    for _attempt in range(100):
        blockers = await observer.scalar(
            text("SELECT pg_blocking_pids(:blocked_pid)"),
            {"blocked_pid": blocked_pid},
        )
        if blockers is not None and blocker_pid in blockers:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("activation/create race did not reach a real PostgreSQL lock wait")


@pytest.mark.database
@pytest.mark.asyncio
async def test_explicit_supported_version_registration_is_exact_and_idempotent() -> None:
    await reset_nonseed_skill_history()
    try:
        first = registration_command(
            "--skill-key",
            "study-destination-compare",
            "--version",
            "1.0.1",
        )
        assert first.returncode == 0, first.stderr
        assert first.stdout.strip() == ("Skill version registered: study-destination-compare@1.0.1")

        replay = registration_command(
            "--skill-key",
            "study-destination-compare",
            "--version",
            "1.0.1",
        )
        assert replay.returncode == 0, replay.stderr
        assert replay.stdout.strip() == (
            "Skill version already registered: study-destination-compare@1.0.1"
        )

        rejected = registration_command(
            "--skill-key",
            "study-destination-compare",
            "--version",
            "9.9.9",
        )
        assert rejected.returncode != 0
        assert rejected.stderr.strip() == "Skill version registration failed closed"

        engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                    {"org": "10000000-0000-0000-0000-000000000001"},
                )
                rows = (
                    (
                        await connection.execute(
                            text(
                                "SELECT v.semantic_version,v.is_seed,"
                                "v.manifest_projection,v.supersedes_version_id=seed.id "
                                "AS supersedes_seed "
                                "FROM app.skill_versions v "
                                "JOIN app.skill_versions seed "
                                "ON seed.organization_id=v.organization_id "
                                "AND seed.definition_id=v.definition_id "
                                "AND seed.semantic_version='1.0.0' "
                                "WHERE v.organization_id=:org "
                                "AND v.skill_key='study-destination-compare' "
                                "ORDER BY v.semantic_version"
                            ),
                            {"org": ("10000000-0000-0000-0000-000000000001")},
                        )
                    )
                    .mappings()
                    .all()
                )
            assert [row["semantic_version"] for row in rows] == ["1.0.0", "1.0.1"]
            assert rows[0]["is_seed"] is True
            assert rows[1]["is_seed"] is False
            assert rows[1]["supersedes_seed"] is True
            assert rows[1]["manifest_projection"]["version"] == "1.0.1"

            async with engine.begin() as connection:
                await connection.execute(
                    text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                    {"org": str(ORG)},
                )
                await connection.execute(
                    text(
                        "ALTER TABLE app.skill_versions "
                        "DISABLE TRIGGER skill_versions_immutable"
                    )
                )
                await connection.execute(
                    text(
                        "UPDATE app.skill_versions "
                        "SET id='8f500000-0000-0000-0000-000000000099' "
                        "WHERE organization_id=:org "
                        "AND skill_key='study-destination-compare' "
                        "AND semantic_version='1.0.1'"
                    ),
                    {"org": ORG},
                )
                await connection.execute(
                    text(
                        "ALTER TABLE app.skill_versions "
                        "ENABLE TRIGGER skill_versions_immutable"
                    )
                )

            mismatch = registration_command(
                "--skill-key",
                "study-destination-compare",
                "--version",
                "1.0.1",
            )
            assert mismatch.returncode != 0
            assert mismatch.stderr.strip() == "Skill version registration failed closed"
        finally:
            await engine.dispose()
    finally:
        await reset_nonseed_skill_history()


@pytest.mark.database
@pytest.mark.asyncio
async def test_lifecycle_writes_are_atomic_and_task_pins_follow_activation_history() -> None:
    await reset_nonseed_skill_history()
    registered = registration_command(
        "--skill-key",
        "study-destination-compare",
        "--version",
        "1.0.1",
    )
    assert registered.returncode == 0, registered.stderr

    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    fixture_case = validate_planning_fixture().planning_input.case
    fail_candidate = UUID("8f100000-0000-0000-0000-000000000099")
    fail_evaluation = UUID("8f200000-0000-0000-0000-000000000099")
    fail_promotion = UUID("8f300000-0000-0000-0000-000000000099")
    fail_rollback = UUID("8f300000-0000-0000-0000-000000000098")
    task_ids = (
        UUID("8f400000-0000-0000-0000-000000000001"),
        UUID("8f400000-0000-0000-0000-000000000002"),
        UUID("8f400000-0000-0000-0000-000000000003"),
    )
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await _set_advisor_context(connection)
                for case_id in LIFECYCLE_CASES:
                    await connection.execute(
                        text(
                            "SELECT app.publish_case_revision("
                            ":org,:case,NULL,1,CAST(:student AS jsonb),"
                            "CAST(:family AS jsonb))"
                        ),
                        {
                            "org": ORG,
                            "case": case_id,
                            "student": _json(fixture_case.student.model_dump(mode="json")),
                            "family": _json(fixture_case.family.model_dump(mode="json")),
                        },
                    )
                    await connection.execute(
                        text("SELECT app.transition_case(:org,:case,'intake','planning')"),
                        {"org": ORG, "case": case_id},
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
                        "CREATE FUNCTION pg_temp.reject_skill_ledger() "
                        "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
                        "IF NEW.operation=current_setting("
                        "'night_voyager.test_skill_ledger_failure',true) THEN "
                        "RAISE EXCEPTION 'injected Skill ledger failure'; END IF; "
                        "RETURN NEW; END; $$"
                    )
                )
                await connection.execute(
                    text(
                        "CREATE TRIGGER test_skill_ledger_failure BEFORE INSERT "
                        "ON app.idempotency_records FOR EACH ROW "
                        "EXECUTE FUNCTION pg_temp.reject_skill_ledger()"
                    )
                )

                savepoint = await connection.begin_nested()
                await connection.execute(
                    text(
                        "SELECT set_config("
                        "'night_voyager.test_skill_ledger_failure',"
                        "'skill_candidate_create',true)"
                    )
                )
                with pytest.raises(DBAPIError):
                    await _create_candidate(
                        connection,
                        candidate_id=fail_candidate,
                        suffix="injected-create",
                    )
                await savepoint.rollback()
                assert not await connection.scalar(
                    text(
                        "SELECT EXISTS(SELECT 1 FROM app.skill_change_candidates "
                        "WHERE organization_id=:org AND id=:candidate)"
                    ),
                    {"org": ORG, "candidate": fail_candidate},
                )

                await _create_candidate(
                    connection,
                    candidate_id=CANDIDATE,
                    suffix="authority",
                )

                savepoint = await connection.begin_nested()
                await connection.execute(
                    text(
                        "SELECT set_config("
                        "'night_voyager.test_skill_ledger_failure',"
                        "'skill_candidate_evaluate',true)"
                    )
                )
                with pytest.raises(DBAPIError):
                    await _record_evaluation(
                        connection,
                        candidate_id=CANDIDATE,
                        evaluation_id=fail_evaluation,
                        suffix="injected-evaluate",
                    )
                await savepoint.rollback()
                assert not await connection.scalar(
                    text(
                        "SELECT EXISTS(SELECT 1 FROM app.skill_evaluation_results "
                        "WHERE organization_id=:org AND id=:evaluation)"
                    ),
                    {"org": ORG, "evaluation": fail_evaluation},
                )

                await _record_evaluation(
                    connection,
                    candidate_id=CANDIDATE,
                    evaluation_id=EVALUATION,
                    suffix="authority",
                )
                await _create_task(
                    connection,
                    case_id=LIFECYCLE_CASES[0],
                    task_id=task_ids[0],
                    manifest_version="1.0.0",
                    suffix="before-promotion",
                )

                savepoint = await connection.begin_nested()
                await connection.execute(
                    text(
                        "SELECT set_config("
                        "'night_voyager.test_skill_ledger_failure',"
                        "'skill_candidate_promote',true)"
                    )
                )
                with pytest.raises(DBAPIError):
                    await _promote(
                        connection,
                        candidate_id=CANDIDATE,
                        event_id=fail_promotion,
                        suffix="injected-promote",
                    )
                await savepoint.rollback()
                assert (
                    await connection.scalar(
                        text(
                            "SELECT max(activation_sequence) "
                            "FROM app.skill_activation_events WHERE organization_id=:org"
                        ),
                        {"org": ORG},
                    )
                    == 1
                )

                await _promote(
                    connection,
                    candidate_id=CANDIDATE,
                    event_id=PROMOTION,
                    suffix="authority",
                )
                await _create_task(
                    connection,
                    case_id=LIFECYCLE_CASES[1],
                    task_id=task_ids[1],
                    manifest_version="1.0.1",
                    suffix="after-promotion",
                )

                savepoint = await connection.begin_nested()
                await connection.execute(
                    text(
                        "SELECT set_config("
                        "'night_voyager.test_skill_ledger_failure',"
                        "'skill_activation_rollback',true)"
                    )
                )
                with pytest.raises(DBAPIError):
                    await _rollback(
                        connection,
                        event_id=fail_rollback,
                        suffix="injected-rollback",
                    )
                await savepoint.rollback()
                assert (
                    await connection.scalar(
                        text(
                            "SELECT max(activation_sequence) "
                            "FROM app.skill_activation_events WHERE organization_id=:org"
                        ),
                        {"org": ORG},
                    )
                    == 2
                )

                await _rollback(
                    connection,
                    event_id=ROLLBACK,
                    suffix="authority",
                )
                await _create_task(
                    connection,
                    case_id=LIFECYCLE_CASES[2],
                    task_id=task_ids[2],
                    manifest_version="1.0.0",
                    suffix="after-rollback",
                )

                pins = (
                    (
                        await connection.execute(
                            text(
                                "SELECT t.id,v.semantic_version,"
                                "t.skill_activation_sequence,"
                                "t.runtime_binding_sha256 "
                                "FROM app.agent_tasks t JOIN app.skill_versions v "
                                "ON v.organization_id=t.organization_id "
                                "AND v.definition_id=t.skill_definition_id "
                                "AND v.id=t.skill_version_id "
                                "WHERE t.organization_id=:org AND t.id=ANY(:tasks) "
                                "ORDER BY t.id"
                            ),
                            {"org": ORG, "tasks": list(task_ids)},
                        )
                    )
                    .mappings()
                    .all()
                )
                assert [
                    (row["semantic_version"], row["skill_activation_sequence"]) for row in pins
                ] == [("1.0.0", 1), ("1.0.1", 2), ("1.0.0", 3)]
                assert len({row["runtime_binding_sha256"] for row in pins}) == 1

                for table, row_id in (
                    ("skill_change_candidates", CANDIDATE),
                    ("skill_evaluation_results", EVALUATION),
                ):
                    savepoint = await connection.begin_nested()
                    with pytest.raises(DBAPIError) as captured:
                        await connection.execute(
                            text(
                                f"UPDATE app.{table} SET request_sha256=repeat('f',64) "
                                "WHERE organization_id=:org AND id=:row_id"
                            ),
                            {"org": ORG, "row_id": row_id},
                        )
                    assert getattr(captured.value.orig, "sqlstate", None) == "NV006"
                    await savepoint.rollback()
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
        await reset_nonseed_skill_history()


@pytest.mark.database
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "activation_first",
    [False, True],
    ids=("create-before-activation", "activation-before-create"),
)
async def test_activation_and_task_creation_linearize_to_one_complete_pin(
    activation_first: bool,
) -> None:
    await reset_nonseed_skill_history()
    registered = registration_command(
        "--skill-key",
        "study-destination-compare",
        "--version",
        "1.0.1",
    )
    assert registered.returncode == 0, registered.stderr

    index = int(activation_first)
    case_id = RACE_CASES[index]
    task_id = RACE_TASKS[index]
    candidate_id = RACE_CANDIDATES[index]
    evaluation_id = RACE_EVALUATIONS[index]
    event_id = RACE_EVENTS[index]
    expected_task_version = "1.0.1" if activation_first else "1.0.0"
    expected_task_sequence = 2 if activation_first else 1
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await _set_advisor_context(connection)
            await _publish_planning_case(connection, case_id)
            await _create_candidate(
                connection,
                candidate_id=candidate_id,
                suffix=f"race-{index}",
            )
            await _record_evaluation(
                connection,
                candidate_id=candidate_id,
                evaluation_id=evaluation_id,
                suffix=f"race-{index}",
            )

        async with (
            engine.connect() as activation_connection,
            engine.connect() as task_connection,
        ):
            activation_transaction = await activation_connection.begin()
            task_transaction = await task_connection.begin()
            pending: asyncio.Task[None] | None = None
            try:
                await _set_advisor_context(activation_connection)
                await _set_advisor_context(task_connection)
                activation_pid = await activation_connection.scalar(
                    text("SELECT pg_backend_pid()")
                )
                task_pid = await task_connection.scalar(text("SELECT pg_backend_pid()"))
                assert isinstance(activation_pid, int)
                assert isinstance(task_pid, int)

                if activation_first:
                    await _promote(
                        activation_connection,
                        candidate_id=candidate_id,
                        event_id=event_id,
                        suffix="race-activation-first",
                    )
                    pending = asyncio.create_task(
                        _create_task(
                            task_connection,
                            case_id=case_id,
                            task_id=task_id,
                            manifest_version="1.0.1",
                            suffix="race-activation-first",
                        )
                    )
                    await _wait_until_blocked(
                        activation_connection,
                        blocked_pid=task_pid,
                        blocker_pid=activation_pid,
                    )
                    assert not pending.done()
                    await activation_transaction.commit()
                    await pending
                    await task_transaction.commit()
                else:
                    await _create_task(
                        task_connection,
                        case_id=case_id,
                        task_id=task_id,
                        manifest_version="1.0.0",
                        suffix="race-create-first",
                    )
                    pending = asyncio.create_task(
                        _promote(
                            activation_connection,
                            candidate_id=candidate_id,
                            event_id=event_id,
                            suffix="race-create-first",
                        )
                    )
                    await _wait_until_blocked(
                        task_connection,
                        blocked_pid=activation_pid,
                        blocker_pid=task_pid,
                    )
                    assert not pending.done()
                    await task_transaction.commit()
                    await pending
                    await activation_transaction.commit()
            finally:
                if pending is not None and not pending.done():
                    pending.cancel()
                if activation_transaction.is_active:
                    await activation_transaction.rollback()
                if task_transaction.is_active:
                    await task_transaction.rollback()

        async with engine.connect() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            pin = (
                (
                    await connection.execute(
                        text(
                            "SELECT v.semantic_version,t.skill_activation_sequence,"
                            "t.runtime_binding_sha256=v.runtime_binding_sha256 AS binding_matches,"
                            "a.activated_version_id=t.skill_version_id AS version_matches,"
                            "a.activation_sequence=t.skill_activation_sequence AS sequence_matches "
                            "FROM app.agent_tasks t "
                            "JOIN app.skill_versions v "
                            "ON v.organization_id=t.organization_id "
                            "AND v.definition_id=t.skill_definition_id "
                            "AND v.id=t.skill_version_id "
                            "JOIN app.skill_activation_events a "
                            "ON a.organization_id=t.organization_id "
                            "AND a.definition_id=t.skill_definition_id "
                            "AND a.id=t.skill_activation_event_id "
                            "WHERE t.organization_id=:org AND t.id=:task"
                        ),
                        {"org": ORG, "task": task_id},
                    )
                )
                .mappings()
                .one()
            )
            active = (
                (
                    await connection.execute(
                        text(
                            "SELECT v.semantic_version,a.activation_sequence "
                            "FROM app.skill_activation_events a "
                            "JOIN app.skill_versions v "
                            "ON v.organization_id=a.organization_id "
                            "AND v.definition_id=a.definition_id "
                            "AND v.id=a.activated_version_id "
                            "WHERE a.organization_id=:org "
                            "ORDER BY a.activation_sequence DESC LIMIT 1"
                        ),
                        {"org": ORG},
                    )
                )
                .mappings()
                .one()
            )
        assert (pin["semantic_version"], pin["skill_activation_sequence"]) == (
            expected_task_version,
            expected_task_sequence,
        )
        assert pin["binding_matches"] is True
        assert pin["version_matches"] is True
        assert pin["sequence_matches"] is True
        assert (active["semantic_version"], active["activation_sequence"]) == ("1.0.1", 2)
    finally:
        await engine.dispose()
        await reset_nonseed_skill_history()


@pytest.mark.database
@pytest.mark.asyncio
async def test_concurrent_activation_has_one_winner_and_one_stale_loser() -> None:
    await reset_nonseed_skill_history()
    registered = registration_command(
        "--skill-key",
        "study-destination-compare",
        "--version",
        "1.0.1",
    )
    assert registered.returncode == 0, registered.stderr

    database_url = os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"]
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await _set_advisor_context(connection)
            await _create_candidate(
                connection,
                candidate_id=CONCURRENT_CANDIDATE,
                suffix="concurrent",
            )
            await _record_evaluation(
                connection,
                candidate_id=CONCURRENT_CANDIDATE,
                evaluation_id=CONCURRENT_EVALUATION,
                suffix="concurrent",
            )

        async def attempt(event_id: UUID, suffix: str) -> tuple[str, UUID]:
            try:
                async with engine.begin() as connection:
                    await _set_advisor_context(connection)
                    await _promote(
                        connection,
                        candidate_id=CONCURRENT_CANDIDATE,
                        event_id=event_id,
                        suffix=suffix,
                    )
                return "promoted", event_id
            except DBAPIError as error:
                return str(getattr(error.orig, "sqlstate", "")), event_id

        outcomes = await asyncio.gather(
            attempt(CONCURRENT_EVENTS[0], "concurrent-a"),
            attempt(CONCURRENT_EVENTS[1], "concurrent-b"),
        )
        assert sorted(outcome for outcome, _event_id in outcomes) == [
            "NV019",
            "promoted",
        ]

        async with engine.connect() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            rows = (
                (
                    await connection.execute(
                        text(
                            "SELECT id,activation_sequence FROM "
                            "app.skill_activation_events "
                            "WHERE organization_id=:org AND event_kind='promote'"
                        ),
                        {"org": ORG},
                    )
                )
                .mappings()
                .all()
            )
        assert len(rows) == 1
        assert rows[0]["activation_sequence"] == 2
        assert rows[0]["id"] in CONCURRENT_EVENTS
    finally:
        await engine.dispose()
        await reset_nonseed_skill_history()
