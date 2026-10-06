# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
import os
from typing import Literal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from night_voyager.collaboration.hashing import canonical_sha256
from night_voyager.skills.models import SkillKey
from night_voyager.skills.registry import SkillRuntimeRegistry
from tests.integration.planning.test_revision_authority import (
    ADVISOR,
    ORG,
    PARENT,
    STUDENT,
    RevisionFixture,
    confirm_candidate,
    digest,
    fixture,
    prepare_preferred_countries_candidate,
    request_revision,
    seed_reviewable_case,
    set_context,
)

pytestmark = pytest.mark.database


async def append_candidate(
    c: AsyncConnection,
    target: RevisionFixture,
    *,
    fact_key: str,
    value: object,
    role: Literal["student", "parent"] = "student",
) -> UUID:
    actor = STUDENT if role == "student" else PARENT
    message, candidate = uuid4(), uuid4()
    body = "Synthetic participant proposal for the current Case revision."
    await set_context(c, actor, role)
    await c.execute(
        text(
            "SELECT * FROM app.append_collaboration_message(:org,:actor,:role,:thread,:message,:body,:content,:request,:key)"
        ),
        {
            "org": ORG,
            "actor": actor,
            "role": role,
            "thread": target.identifier("9a000000"),
            "message": message,
            "body": body,
            "content": hashlib.sha256(body.encode()).hexdigest(),
            "request": digest(str(message)),
            "key": digest(f"message-key-{message}"),
        },
    )
    await c.execute(
        text(
            "SELECT * FROM app.propose_memory_candidate(:org,:actor,:role,:message,:candidate,1,:fact,CAST(:value AS jsonb),:hash,:request,:key)"
        ),
        {
            "org": ORG,
            "actor": actor,
            "role": role,
            "message": message,
            "candidate": candidate,
            "fact": fact_key,
            "value": json.dumps(value),
            "hash": canonical_sha256(value),
            "request": digest(str(candidate)),
            "key": digest(f"candidate-key-{candidate}"),
        },
    )
    return candidate


@pytest.mark.asyncio
async def test_parent_cannot_author_intake_and_pending_intake_becomes_stale_after_another_fact() -> (
    None
):
    target = fixture(uuid4().int % 1000000000000)
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        await seed_reviewable_case(migrator, target, policy_version="m3a-policy-v1")
        async with api.begin() as c:
            await request_revision(
                c,
                target,
                review_id=target.identifier("8a000000"),
                key_hash=digest(str(uuid4())),
                request_hash=digest(str(uuid4())),
            )
            candidate = await prepare_preferred_countries_candidate(
                c, target, fact_key="student.intake", value="2028-02"
            )
            with pytest.raises(DBAPIError) as parent:
                async with c.begin_nested():
                    await append_candidate(
                        c, target, fact_key="student.intake", value="2028-02", role="parent"
                    )
            assert getattr(parent.value.orig, "sqlstate", None) == "NV006"
            other = await append_candidate(
                c, target, fact_key="student.preferred_countries", value=["australia", "japan"]
            )
            await confirm_candidate(c, target, other, verification_offset=1, key_label="other")
        async with api.begin() as c:
            with pytest.raises(DBAPIError) as stale:
                async with c.begin_nested():
                    await confirm_candidate(c, target, candidate)
            assert getattr(stale.value.orig, "sqlstate", None) == "NV003"
        async with migrator.begin() as c:
            await set_context(c, ADVISOR, "advisor")
            assert (
                await c.scalar(
                    text(
                        "SELECT current_revision FROM app.student_cases WHERE organization_id=:org AND id=:case"
                    ),
                    {"org": ORG, "case": target.case_id},
                )
                == 2
            )
            assert (
                await c.scalar(
                    text(
                        "SELECT count(*) FROM app.memory_candidate_verifications WHERE organization_id=:org AND candidate_id=:candidate"
                    ),
                    {"org": ORG, "candidate": candidate},
                )
                == 0
            )
    finally:
        await migrator.dispose()
        await api.dispose()


@pytest.mark.asyncio
async def test_confirmed_intake_requires_explicit_task_with_frozen_new_source_and_replay() -> None:
    target = fixture(uuid4().int % 1000000000000)
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    worker = create_async_engine(os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"])
    new_pack = "50000000-0000-0000-0000-000000000017"
    try:
        await seed_reviewable_case(migrator, target, policy_version="m3a-policy-v1")
        async with api.begin() as c:
            await request_revision(
                c,
                target,
                review_id=target.identifier("8a000000"),
                key_hash=digest(f"review-key-{target.suffix}"),
                request_hash=digest(f"review-request-{target.suffix}"),
            )
            candidate = await prepare_preferred_countries_candidate(
                c, target, fact_key="student.intake", value="2028-02"
            )
        async with api.begin() as c:
            await set_context(c, ADVISOR, "advisor")
            assert (
                await c.scalar(
                    text(
                        "SELECT app.read_connected_journey_fact_pending(:org,:ac"
                        "tor,'advisor',:case)"
                    ),
                    {"org": ORG, "actor": ADVISOR, "case": target.case_id},
                )
                is True
            )
            result = await confirm_candidate(c, target, candidate)
            assert result["result_revision"] == 2
            assert result["replayed"] is False
            replay = await confirm_candidate(c, target, candidate)
            assert replay["replayed"] is True
            with pytest.raises(DBAPIError) as conflict:
                async with c.begin_nested():
                    await c.execute(
                        text(
                            "SELECT * FROM app.verify_memory_candidate(:org,:actor,:candidate,1,'confirm','bounded intake review',:verification,:fact,:request,:key)"
                        ),
                        {
                            "org": ORG,
                            "actor": ADVISOR,
                            "candidate": candidate,
                            "verification": uuid4(),
                            "fact": uuid4(),
                            "request": digest("different request"),
                            "key": digest(f"confirm-key-{target.suffix}-0"),
                        },
                    )
            assert getattr(conflict.value.orig, "sqlstate", None) == "NV008"
        async with migrator.begin() as c:
            await set_context(c, ADVISOR, "advisor")
            assert (
                await c.scalar(
                    text(
                        "SELECT count(*) FROM app.agent_tasks WHERE organization"
                        "_id=:org AND case_id=:case"
                    ),
                    {"org": ORG, "case": target.case_id},
                )
                == 0
            )
            lineage = (
                (
                    await c.execute(
                        text(
                            "SELECT student_preferences->>'intake' AS intake,superseded_planning_run_id FROM app.student_case_revisions WHERE organization_id=:org AND case_id=:case AND revision=2"
                        ),
                        {"org": ORG, "case": target.case_id},
                    )
                )
                .mappings()
                .one()
            )
            assert lineage["intake"] == "2028-02"
            assert lineage["superseded_planning_run_id"] == target.run_id
        manifest = (
            SkillRuntimeRegistry.load_packaged()
            .get(SkillKey.STUDY_DESTINATION_COMPARE, "1.0.0")
            .model_dump_json(exclude_none=True)
        )
        async with api.begin() as c:
            await set_context(c, ADVISOR, "advisor")
            command = text(
                "SELECT * FROM app.create_agent_task(:org,:actor,:case,:task,'generate_planning_run_v1',2,CAST(:pack AS uuid),1,'m3a-policy-v1',CAST(:manifest AS jsonb),:request,:key)"
            )
            parameters = {
                "org": ORG,
                "actor": ADVISOR,
                "case": target.case_id,
                "task": target.identifier("89000000"),
                "pack": "50000000-0000-0000-0000-000000000001",
                "manifest": manifest,
                "request": digest(f"task-request-{target.suffix}"),
                "key": digest(f"task-key-{target.suffix}"),
            }
            with pytest.raises(DBAPIError) as wrong:
                async with c.begin_nested():
                    await c.execute(command, parameters)
            assert getattr(wrong.value.orig, "sqlstate", None) == "NV027"
            parameters["pack"] = new_pack
            result = (await c.execute(command, parameters)).mappings().one()
            assert result["state"] == "queued"
        async with worker.begin() as c:
            await c.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            value = await c.scalar(
                text(
                    "SELECT app.load_persisted_synthetic_planning_snapshot(:org,:case,2,CAST(:pack AS uuid),1,'m3a-policy-v1')"
                ),
                {"org": ORG, "case": target.case_id, "pack": new_pack},
            )
            assert value["case"]["student"]["intake"] == "2028-02"
            assert value["source_pack_id"] == new_pack
        # Leave no dispatch for another test's worker to claim. This uses the
        # real assigned-advisor cancellation authority after durable assertions.
        async with api.begin() as c:
            await set_context(c, ADVISOR, "advisor")
            cancelled = (
                (
                    await c.execute(
                        text(
                            "SELECT * FROM app.cancel_agent_task(:org,:actor,:task,1,:request,:key)"
                        ),
                        {
                            "org": ORG,
                            "actor": ADVISOR,
                            "task": target.identifier("89000000"),
                            "request": digest(f"cancel-request-{target.suffix}"),
                            "key": digest(f"cancel-key-{target.suffix}"),
                        },
                    )
                )
                .mappings()
                .one()
            )
            assert cancelled["state"] == "cancelled"
    finally:
        await migrator.dispose()
        await api.dispose()
        await worker.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "expected"),
    (
        ("unchanged", "NV006"),
        ("no_review", "NV003"),
        ("expired", "NV013"),
        ("active", "NV014"),
        ("unassigned", "NV007"),
        ("source_drift", "NV027"),
    ),
)
async def test_intake_authority_refuses_ineligible_confirmation_without_partial_publication(
    mode: str, expected: str
) -> None:
    from tests.integration.planning.test_revision_authority import insert_blocking_task

    target = fixture(uuid4().int % 1000000000000)
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        await seed_reviewable_case(migrator, target, policy_version="m3a-policy-v1")
        async with api.begin() as c:
            if mode != "no_review":
                await request_revision(
                    c,
                    target,
                    review_id=target.identifier("8a000000"),
                    key_hash=digest(f"review-key-{target.suffix}"),
                    request_hash=digest(f"review-request-{target.suffix}"),
                )
            candidate = await prepare_preferred_countries_candidate(
                c,
                target,
                fact_key="student.intake",
                value="2027-02" if mode == "unchanged" else "2028-02",
            )
        async with migrator.begin() as c:
            await set_context(c, ADVISOR, "advisor")
            if mode == "expired":
                old_candidate = candidate
                candidate = uuid4()
                new_message = uuid4()
                await c.execute(
                    text(
                        "INSERT INTO app.message_events(organization_id,id,thread_id,case_id,sequence_no,actor_id,actor_role,body,content_sha256,request_sha256,created_at) SELECT organization_id,:message,thread_id,case_id,sequence_no+1,actor_id,actor_role,body,content_sha256,request_sha256,now()-interval '9 days' FROM app.message_events WHERE organization_id=:org AND id=(SELECT message_event_id FROM app.memory_candidates WHERE organization_id=:org AND id=:old)"
                    ),
                    {"org": ORG, "message": new_message, "old": old_candidate},
                )
                await c.execute(
                    text(
                        "INSERT INTO app.memory_candidates(organization_id,id,case_id,case_revision,message_event_id,subject_actor_id,subject_role,proposing_actor_id,proposing_role,fact_key,proposed_value,value_sha256,request_sha256,provenance_kind,created_at,expires_at) SELECT organization_id,:candidate,case_id,case_revision,:message,subject_actor_id,subject_role,proposing_actor_id,proposing_role,fact_key,proposed_value,value_sha256,request_sha256,provenance_kind,now()-interval '8 days',now()-interval '1 day' FROM app.memory_candidates WHERE organization_id=:org AND id=:old"
                    ),
                    {
                        "org": ORG,
                        "candidate": candidate,
                        "message": new_message,
                        "old": old_candidate,
                    },
                )
            if mode == "active":
                await insert_blocking_task(c, target, state="queued")
            if mode == "source_drift":
                await c.execute(
                    text(
                        "UPDATE app.source_packs SET manifest_sha256=repeat('0',64) WHERE organization_id=:org AND id='50000000-0000-0000-0000-000000000017'"
                    ),
                    {"org": ORG},
                )
        async with api.begin() as c:
            with pytest.raises(DBAPIError) as denied:
                async with c.begin_nested():
                    if mode == "unassigned":
                        actor = uuid4()
                        await set_context(c, actor, "advisor")
                        await c.execute(
                            text(
                                "SELECT * FROM app.verify_memory_candidate(:org,:actor,:candidate,1,'confirm','bounded intake review',:verification,:fact,:request,:key)"
                            ),
                            {
                                "org": ORG,
                                "actor": actor,
                                "candidate": candidate,
                                "verification": uuid4(),
                                "fact": uuid4(),
                                "request": digest(str(uuid4())),
                                "key": digest(str(uuid4())),
                            },
                        )
                    else:
                        await confirm_candidate(c, target, candidate)
            assert getattr(denied.value.orig, "sqlstate", None) == expected
        async with migrator.begin() as c:
            await set_context(c, ADVISOR, "advisor")
            assert (
                await c.scalar(
                    text(
                        "SELECT current_revision FROM app.student_cases WHERE or"
                        "ganization_id=:org AND id=:case"
                    ),
                    {"org": ORG, "case": target.case_id},
                )
                == 1
            )
            assert (
                await c.scalar(
                    text(
                        "SELECT is_current FROM app.planning_runs WHERE organiza"
                        "tion_id=:org AND id=:run"
                    ),
                    {"org": ORG, "run": target.run_id},
                )
                is True
            )
            assert (
                await c.scalar(
                    text(
                        "SELECT count(*) FROM app.memory_candidate_verifications WHERE organization_id=:org AND candidate_id=:id"
                    ),
                    {"org": ORG, "id": candidate},
                )
                == 0
            )
    finally:
        if mode == "source_drift":
            async with migrator.begin() as c:
                await set_context(c, ADVISOR, "advisor")
                await c.execute(
                    text(
                        "UPDATE app.source_packs SET manifest_sha256='832aab1715564dee0e3a4530a181ccd4581bb7e5199144cb34dc55b20077add1' WHERE organization_id=:org AND id='50000000-0000-0000-0000-000000000017'"
                    ),
                    {"org": ORG},
                )
        await migrator.dispose()
        await api.dispose()


@pytest.mark.asyncio
async def test_unavailable_intake_confirmation_preserves_current_predecessor_and_business_writes() -> (
    None
):
    target = fixture(uuid4().int % 1000000000000)
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        await seed_reviewable_case(migrator, target, policy_version="m3a-policy-v1")
        async with api.begin() as c:
            await request_revision(
                c,
                target,
                review_id=target.identifier("8a000000"),
                key_hash=digest(f"intake-review-key-{target.suffix}"),
                request_hash=digest(f"intake-review-request-{target.suffix}"),
            )
            candidate = await prepare_preferred_countries_candidate(
                c, target, fact_key="student.intake", value="2028-09"
            )
        async with api.begin() as c:
            with pytest.raises(DBAPIError) as unavailable:
                async with c.begin_nested():
                    await confirm_candidate(c, target, candidate)
            assert getattr(unavailable.value.orig, "sqlstate", None) == "NV027"
        async with migrator.begin() as c:
            await set_context(c, ADVISOR, "advisor")
            row = (
                (
                    await c.execute(
                        text(
                            "SELECT current_revision,(SELECT is_current FROM app.planning_runs WHERE id=:run AND organization_id=:org) AS current,(SELECT count(*) FROM app.confirmed_facts WHERE case_id=:case AND organization_id=:org) AS facts,(SELECT count(*) FROM app.memory_candidate_verifications WHERE candidate_id=:candidate AND organization_id=:org) AS verifications,(SELECT count(*) FROM app.agent_tasks WHERE case_id=:case AND organization_id=:org) AS tasks FROM app.student_cases WHERE id=:case AND organization_id=:org"
                        ),
                        {
                            "org": ORG,
                            "case": target.case_id,
                            "run": target.run_id,
                            "candidate": candidate,
                        },
                    )
                )
                .mappings()
                .one()
            )
            assert dict(row) == {
                "current_revision": 1,
                "current": True,
                "facts": 0,
                "verifications": 0,
                "tasks": 0,
            }
    finally:
        await migrator.dispose()
        await api.dispose()
