# ruff: noqa: E501
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import dataclass
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from night_voyager.collaboration.hashing import canonical_sha256
from night_voyager.planning.fixtures import validate_planning_fixture

pytestmark = pytest.mark.database

ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
STUDENT = UUID("20000000-0000-0000-0000-000000000002")
PARENT = UUID("20000000-0000-0000-0000-000000000003")
PACK = UUID("50000000-0000-0000-0000-000000000001")


@dataclass(frozen=True)
class RevisionFixture:
    suffix: int
    case_id: UUID
    run_id: UUID

    def identifier(self, prefix: str, offset: int = 0) -> UUID:
        return UUID(f"{prefix}-0000-0000-0000-{self.suffix + offset:012d}")


def fixture(suffix: int) -> RevisionFixture:
    return RevisionFixture(
        suffix=suffix,
        case_id=UUID(f"4a000000-0000-0000-0000-{suffix:012d}"),
        run_id=UUID(f"7a000000-0000-0000-0000-{suffix:012d}"),
    )


def digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


async def set_context(
    connection: AsyncConnection,
    actor: UUID,
    role: str,
) -> None:
    for key, value in (
        ("organization_id", ORG),
        ("actor_id", actor),
        ("role", role),
    ):
        await connection.execute(
            text("SELECT set_config(:key,:value,true)"),
            {"key": f"night_voyager.{key}", "value": str(value)},
        )


async def seed_reviewable_case(
    migrator: AsyncEngine,
    revision_fixture: RevisionFixture,
) -> None:
    planning_input = validate_planning_fixture().planning_input
    async with migrator.begin() as connection:
        await set_context(connection, ADVISOR, "advisor")
        await connection.execute(
            text(
                "SELECT app.publish_case_revision("
                ":org,:case,NULL,1,CAST(:student AS jsonb),CAST(:family AS jsonb))"
            ),
            {
                "org": ORG,
                "case": revision_fixture.case_id,
                "student": json.dumps(planning_input.case.student.model_dump(mode="json")),
                "family": json.dumps(planning_input.case.family.model_dump(mode="json")),
            },
        )
        await connection.execute(
            text("SELECT app.seed_case_participants(:org,:case,:advisor,:student,:parent)"),
            {
                "org": ORG,
                "case": revision_fixture.case_id,
                "advisor": ADVISOR,
                "student": STUDENT,
                "parent": PARENT,
            },
        )
        await connection.execute(
            text("SELECT app.transition_case(:org,:case,'intake','planning')"),
            {"org": ORG, "case": revision_fixture.case_id},
        )
        await connection.execute(
            text(
                "INSERT INTO app.planning_runs("
                "organization_id,id,case_id,case_revision,source_pack_id,"
                "source_pack_version,policy_version,evidence_projection_sha256,"
                "state,is_current) VALUES("
                ":org,:run,:case,1,:pack,1,'revision-authority-v1',repeat('a',64),"
                "'synthesizing',true)"
            ),
            {
                "org": ORG,
                "run": revision_fixture.run_id,
                "case": revision_fixture.case_id,
                "pack": PACK,
            },
        )
        await connection.execute(
            text(
                "UPDATE app.planning_runs SET state='review_required',"
                "reason_code='revision_requested',output_sha256=repeat('b',64) "
                "WHERE organization_id=:org AND id=:run"
            ),
            {"org": ORG, "run": revision_fixture.run_id},
        )


async def request_revision(
    connection: AsyncConnection,
    revision_fixture: RevisionFixture,
    *,
    review_id: UUID,
    key_hash: str,
    request_hash: str,
    run_id: UUID | None = None,
    action: str = "request_revision",
) -> dict[str, object]:
    await set_context(connection, ADVISOR, "advisor")
    result = await connection.execute(
        text(
            "SELECT * FROM app.review_planning_run("
            ":org,:actor,:case,:run,1,:action,:review,'[]'::jsonb,'[]'::jsonb,"
            "'bounded revision request',NULL,'{}'::jsonb,current_date,:key,:request)"
        ),
        {
            "org": ORG,
            "actor": ADVISOR,
            "case": revision_fixture.case_id,
            "run": run_id or revision_fixture.run_id,
            "action": action,
            "review": review_id,
            "key": key_hash,
            "request": request_hash,
        },
    )
    return dict(result.mappings().one())


async def prepare_preferred_countries_candidate(
    connection: AsyncConnection,
    revision_fixture: RevisionFixture,
) -> UUID:
    thread_id = revision_fixture.identifier("9a000000")
    message_id = revision_fixture.identifier("9b000000")
    candidate_id = revision_fixture.identifier("9c000000")
    await set_context(connection, ADVISOR, "advisor")
    await connection.execute(
        text(
            "SELECT * FROM app.create_collaboration_thread("
            ":org,:actor,'advisor',:case,:thread,:request,:key)"
        ),
        {
            "org": ORG,
            "actor": ADVISOR,
            "case": revision_fixture.case_id,
            "thread": thread_id,
            "request": digest(f"thread-request-{revision_fixture.suffix}"),
            "key": digest(f"thread-key-{revision_fixture.suffix}"),
        },
    )
    body = "I prefer Australia and Japan for this bounded revision."
    await set_context(connection, STUDENT, "student")
    await connection.execute(
        text(
            "SELECT * FROM app.append_collaboration_message("
            ":org,:actor,'student',:thread,:message,:body,:content,:request,:key)"
        ),
        {
            "org": ORG,
            "actor": STUDENT,
            "thread": thread_id,
            "message": message_id,
            "body": body,
            "content": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "request": digest(f"message-request-{revision_fixture.suffix}"),
            "key": digest(f"message-key-{revision_fixture.suffix}"),
        },
    )
    value = ["australia", "japan"]
    await connection.execute(
        text(
            "SELECT * FROM app.propose_memory_candidate("
            ":org,:actor,'student',:message,:candidate,1,"
            "'student.preferred_countries',CAST(:value AS jsonb),"
            ":value_hash,:request,:key)"
        ),
        {
            "org": ORG,
            "actor": STUDENT,
            "message": message_id,
            "candidate": candidate_id,
            "value": json.dumps(value),
            "value_hash": canonical_sha256(value),
            "request": digest(f"candidate-request-{revision_fixture.suffix}"),
            "key": digest(f"candidate-key-{revision_fixture.suffix}"),
        },
    )
    return candidate_id


async def confirm_candidate(
    connection: AsyncConnection,
    revision_fixture: RevisionFixture,
    candidate_id: UUID,
    *,
    verification_offset: int = 0,
    key_label: str = "confirm",
) -> dict[str, object]:
    await set_context(connection, ADVISOR, "advisor")
    result = await connection.execute(
        text(
            "SELECT * FROM app.verify_memory_candidate("
            ":org,:actor,:candidate,1,'confirm',:reason,:verification,:fact,"
            ":request,:key)"
        ),
        {
            "org": ORG,
            "actor": ADVISOR,
            "candidate": candidate_id,
            "reason": "The student confirmed the bounded country set.",
            "verification": revision_fixture.identifier(
                "9d000000", verification_offset
            ),
            "fact": revision_fixture.identifier("9e000000", verification_offset),
            "request": digest(
                f"{key_label}-request-{revision_fixture.suffix}-{verification_offset}"
            ),
            "key": digest(
                f"{key_label}-key-{revision_fixture.suffix}-{verification_offset}"
            ),
        },
    )
    return dict(result.mappings().one())


@pytest.mark.asyncio
async def test_request_revision_then_confirmation_creates_exact_atomic_lineage() -> None:
    target = fixture(1201)
    review_id = target.identifier("8a000000")
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        await seed_reviewable_case(migrator, target)
        async with api.begin() as connection:
            review = await request_revision(
                connection,
                target,
                review_id=review_id,
                key_hash=digest("revision-success-key"),
                request_hash=digest("revision-success-request"),
            )
        assert review == {
            "review_id": review_id,
            "brief_id": None,
            "case_state": "planning",
            "replayed": False,
        }
        async with migrator.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            before = (
                await connection.execute(
                    text(
                        "SELECT current_revision,state,"
                        "(SELECT is_current FROM app.planning_runs "
                        " WHERE organization_id=:org AND id=:run) AS predecessor_current,"
                        "(SELECT count(*) FROM app.agent_tasks "
                        " WHERE organization_id=:org AND case_id=:case) AS task_count "
                        "FROM app.student_cases WHERE organization_id=:org AND id=:case"
                    ),
                    {"org": ORG, "case": target.case_id, "run": target.run_id},
                )
            ).mappings().one()
        assert dict(before) == {
            "current_revision": 1,
            "state": "planning",
            "predecessor_current": True,
            "task_count": 0,
        }
        async with api.begin() as connection:
            candidate_id = await prepare_preferred_countries_candidate(connection, target)
            confirmation = await confirm_candidate(connection, target, candidate_id)
        assert confirmation["result_revision"] == 2
        async with migrator.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            lineage = (
                await connection.execute(
                    text(
                        "SELECT revision_requested_by_review_id,"
                        "superseded_planning_run_id "
                        "FROM app.student_case_revisions "
                        "WHERE organization_id=:org AND case_id=:case AND revision=2"
                    ),
                    {"org": ORG, "case": target.case_id},
                )
            ).mappings().one()
            current = await connection.scalar(
                text(
                    "SELECT is_current FROM app.planning_runs "
                    "WHERE organization_id=:org AND id=:run"
                ),
                {"org": ORG, "run": target.run_id},
            )
            refs = await connection.scalar(
                text(
                    "SELECT count(*) FROM app.case_revision_confirmed_fact_refs "
                    "WHERE organization_id=:org AND case_id=:case AND case_revision=2"
                ),
                {"org": ORG, "case": target.case_id},
            )
        assert dict(lineage) == {
            "revision_requested_by_review_id": review_id,
            "superseded_planning_run_id": target.run_id,
        }
        assert current is False
        assert refs == 1
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_confirmation_without_request_revision_is_rejected_without_writes() -> None:
    target = fixture(1202)
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        await seed_reviewable_case(migrator, target)
        async with api.begin() as connection:
            await request_revision(
                connection,
                target,
                review_id=target.identifier("8a000000"),
                key_hash=digest("reject-review-key"),
                request_hash=digest("reject-review-request"),
                action="reject",
            )
            candidate_id = await prepare_preferred_countries_candidate(connection, target)
            with pytest.raises(DBAPIError) as rejected:
                await confirm_candidate(connection, target, candidate_id)
            assert getattr(rejected.value.orig, "sqlstate", None) == "NV003"
        async with migrator.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            revision_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM app.student_case_revisions "
                    "WHERE organization_id=:org AND case_id=:case"
                ),
                {"org": ORG, "case": target.case_id},
            )
            assert revision_count == 1
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_request_revision_rejects_noncurrent_old_run() -> None:
    target = fixture(1203)
    new_run = target.identifier("7b000000")
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        await seed_reviewable_case(migrator, target)
        async with migrator.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            await connection.execute(
                text(
                    "UPDATE app.planning_runs SET is_current=false "
                    "WHERE organization_id=:org AND id=:run"
                ),
                {"org": ORG, "run": target.run_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.planning_runs("
                    "organization_id,id,case_id,case_revision,source_pack_id,"
                    "source_pack_version,policy_version,evidence_projection_sha256,"
                    "state,reason_code,output_sha256,is_current) VALUES("
                    ":org,:run,:case,1,:pack,1,'revision-authority-v1',repeat('c',64),"
                    "'review_required','replacement',repeat('d',64),true)"
                ),
                {
                    "org": ORG,
                    "run": new_run,
                    "case": target.case_id,
                    "pack": PACK,
                },
            )
        async with api.begin() as connection:
            with pytest.raises(DBAPIError) as rejected:
                await request_revision(
                    connection,
                    target,
                    review_id=target.identifier("8a000000"),
                    key_hash=digest("old-run-key"),
                    request_hash=digest("old-run-request"),
                )
            assert getattr(rejected.value.orig, "sqlstate", None) == "NV003"
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_composite_lineage_constraints_reject_cross_case_predecessor() -> None:
    first = fixture(1204)
    second = fixture(1205)
    review_id = first.identifier("8a000000")
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        await seed_reviewable_case(migrator, first)
        await seed_reviewable_case(migrator, second)
        async with api.begin() as connection:
            await request_revision(
                connection,
                first,
                review_id=review_id,
                key_hash=digest("cross-case-key"),
                request_hash=digest("cross-case-request"),
            )
        planning_input = validate_planning_fixture().planning_input
        async with migrator.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            with pytest.raises(DBAPIError) as rejected:
                await connection.execute(
                    text(
                        "INSERT INTO app.student_case_revisions("
                        "organization_id,case_id,revision,schema_version,"
                        "student_preferences,family_preferences,"
                        "revision_requested_by_review_id,superseded_planning_run_id) "
                        "VALUES(:org,:case,2,1,CAST(:student AS jsonb),"
                        "CAST(:family AS jsonb),:review,:run)"
                    ),
                    {
                        "org": ORG,
                        "case": second.case_id,
                        "student": json.dumps(
                            planning_input.case.student.model_dump(mode="json")
                        ),
                        "family": json.dumps(
                            planning_input.case.family.model_dump(mode="json")
                        ),
                        "review": review_id,
                        "run": first.run_id,
                    },
                )
            assert getattr(rejected.value.orig, "sqlstate", None) == "23503"
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_revision_request_replay_conflict_and_different_key_race_are_closed() -> None:
    target = fixture(1206)
    review_id = target.identifier("8a000000")
    key_hash = digest("replay-key")
    request_hash = digest("replay-request")
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        await seed_reviewable_case(migrator, target)
        async with api.begin() as connection:
            first = await request_revision(
                connection,
                target,
                review_id=review_id,
                key_hash=key_hash,
                request_hash=request_hash,
            )
        async with api.begin() as connection:
            replay = await request_revision(
                connection,
                target,
                review_id=target.identifier("8a000000", 1),
                key_hash=key_hash,
                request_hash=request_hash,
            )
        assert first["replayed"] is False
        assert replay["replayed"] is True
        assert replay["review_id"] == review_id
        async with api.begin() as connection:
            with pytest.raises(DBAPIError) as conflict:
                await request_revision(
                    connection,
                    target,
                    review_id=target.identifier("8a000000", 2),
                    key_hash=key_hash,
                    request_hash=digest("different-payload"),
                )
            assert getattr(conflict.value.orig, "sqlstate", None) == "NV008"

        raced = fixture(1207)
        await seed_reviewable_case(migrator, raced)
        async with api.connect() as first_connection, api.connect() as second_connection:
            first_transaction = await first_connection.begin()
            second_transaction = await second_connection.begin()
            first_result = await request_revision(
                first_connection,
                raced,
                review_id=raced.identifier("8a000000"),
                key_hash=digest("race-key-a"),
                request_hash=digest("race-request"),
            )
            pending = asyncio.create_task(
                request_revision(
                    second_connection,
                    raced,
                    review_id=raced.identifier("8a000000", 1),
                    key_hash=digest("race-key-b"),
                    request_hash=digest("race-request"),
                )
            )
            await first_transaction.commit()
            with pytest.raises(DBAPIError) as loser:
                await asyncio.wait_for(pending, timeout=10)
            assert getattr(loser.value.orig, "sqlstate", None) == "NV008"
            await second_transaction.rollback()
        assert first_result["replayed"] is False
        async with migrator.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            counts = (
                await connection.execute(
                    text(
                        "SELECT "
                        "(SELECT count(*) FROM app.advisor_reviews "
                        " WHERE organization_id=:org AND planning_run_id=:run "
                        " AND action='request_revision') AS reviews,"
                        "(SELECT count(*) FROM app.audit_events "
                        " WHERE organization_id=:org AND case_id=:case "
                        " AND event_type='advisor_review') AS audits"
                    ),
                    {"org": ORG, "run": raced.run_id, "case": raced.case_id},
                )
            ).mappings().one()
        assert dict(counts) == {"reviews": 1, "audits": 1}
    finally:
        await api.dispose()
        await migrator.dispose()


@pytest.mark.asyncio
async def test_concurrent_confirmations_and_duplicate_successors_have_one_winner() -> None:
    target = fixture(1208)
    review_id = target.identifier("8a000000")
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        await seed_reviewable_case(migrator, target)
        async with api.begin() as connection:
            await request_revision(
                connection,
                target,
                review_id=review_id,
                key_hash=digest("confirm-race-review-key"),
                request_hash=digest("confirm-race-review-request"),
            )
            candidate_id = await prepare_preferred_countries_candidate(connection, target)
        async with api.connect() as first_connection, api.connect() as second_connection:
            first_transaction = await first_connection.begin()
            second_transaction = await second_connection.begin()
            winner = await confirm_candidate(first_connection, target, candidate_id)
            pending = asyncio.create_task(
                confirm_candidate(
                    second_connection,
                    target,
                    candidate_id,
                    verification_offset=1,
                    key_label="confirm-race",
                )
            )
            await first_transaction.commit()
            with pytest.raises(DBAPIError):
                await asyncio.wait_for(pending, timeout=10)
            await second_transaction.rollback()
        assert winner["result_revision"] == 2
        async with migrator.begin() as connection:
            await set_context(connection, ADVISOR, "advisor")
            revision_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM app.student_case_revisions "
                    "WHERE organization_id=:org AND case_id=:case "
                    "AND superseded_planning_run_id=:run"
                ),
                {"org": ORG, "case": target.case_id, "run": target.run_id},
            )
            with pytest.raises(DBAPIError) as duplicate_revision:
                await connection.execute(
                    text(
                        "INSERT INTO app.student_case_revisions("
                        "organization_id,case_id,revision,schema_version,"
                        "student_preferences,family_preferences,"
                        "revision_requested_by_review_id,superseded_planning_run_id) "
                        "SELECT organization_id,case_id,3,schema_version,"
                        "student_preferences,family_preferences,"
                        "revision_requested_by_review_id,superseded_planning_run_id "
                        "FROM app.student_case_revisions "
                        "WHERE organization_id=:org AND case_id=:case AND revision=2"
                    ),
                    {"org": ORG, "case": target.case_id},
                )
            assert getattr(duplicate_revision.value.orig, "sqlstate", None) == "23505"
        assert revision_count == 1
    finally:
        await api.dispose()
        await migrator.dispose()
