from __future__ import annotations

import hashlib
import json
import os
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from night_voyager.collaboration.errors import (
    CollaborationPersistenceError,
    MemoryCandidateTerminalError,
)
from night_voyager.collaboration.hashing import canonical_sha256
from night_voyager.collaboration.models import (
    AppendMessageCommand,
    ConfirmedFactAdvisorV1,
    ConfirmedFactParticipantV1,
    FactKey,
    JapanRiskAcceptedProposal,
    MemoryCandidateAdvisorV1,
    MemoryCandidateParticipantV1,
    MemoryCandidateState,
    ProposeMemoryCandidateCommand,
    RiskToleranceProposal,
    VerificationDecision,
    VerifyMemoryCandidateCommand,
)
from night_voyager.collaboration.postgres import PostgresCollaborationRepository
from night_voyager.identity.demo_seed import (
    COLLABORATION_ACTIVE_CASE_ID,
    COLLABORATION_ACTIVE_TASK_ID,
    COLLABORATION_CASE_ID,
    COLLABORATION_EXPIRED_CANDIDATE_ID,
    COLLABORATION_EXPIRED_CASE_ID,
    COLLABORATION_EXPIRED_MESSAGE_ID,
    COLLABORATION_STALE_CANDIDATE_ID,
    COLLABORATION_STALE_CASE_ID,
    COLLABORATION_STALE_MESSAGE_ID,
    COLLABORATION_THREAD_IDS,
)
from night_voyager.identity.models import ActorContext, ActorRole
from night_voyager.planning.fixtures import validate_planning_fixture

pytestmark = pytest.mark.database

ORG_ID = UUID("10000000-0000-0000-0000-000000000001")
CASE_ID = UUID("40000000-0000-0000-0000-000000000314")
THREAD_ID = UUID("90000000-0000-0000-0000-000000000310")
MESSAGE_ID = UUID("91000000-0000-0000-0000-000000000310")
CANDIDATE_ID = UUID("92000000-0000-0000-0000-000000000310")
VERIFICATION_ID = UUID("93000000-0000-0000-0000-000000000310")
FACT_ID = UUID("94000000-0000-0000-0000-000000000310")
ADVISOR_ID = UUID("20000000-0000-0000-0000-000000000001")
STUDENT_ID = UUID("20000000-0000-0000-0000-000000000002")
PARENT_ID = UUID("20000000-0000-0000-0000-000000000003")
SESSION_ID = UUID("30000000-0000-0000-0000-000000000001")
DEFAULT_DEMO_CASE_ID = UUID("40000000-0000-0000-0000-000000000001")
PLANNING_CASE_ID = UUID("40000000-0000-0000-0000-000000000311")
PLANNING_RUN_ID = UUID("70000000-0000-0000-0000-000000000311")
PLANNING_THREAD_ID = UUID("90000000-0000-0000-0000-000000000311")
PLANNING_MESSAGE_ID = UUID("91000000-0000-0000-0000-000000000311")
PLANNING_CANDIDATE_ID = UUID("92000000-0000-0000-0000-000000000311")
PLANNING_VERIFICATION_ID = UUID("93000000-0000-0000-0000-000000000311")
PLANNING_FACT_ID = UUID("94000000-0000-0000-0000-000000000311")
PLANNING_SOURCE_PACK_ID = UUID("50000000-0000-0000-0000-000000000311")
NULL_SEED_THREAD_ID = UUID("90000000-0000-0000-0000-000000000312")
COLLISION_CASE_ID = UUID("40000000-0000-0000-0000-000000000313")
COLLISION_THREAD_ID = UUID("90000000-0000-0000-0000-000000000313")
COLLISION_TASK_ID = UUID("95000000-0000-0000-0000-000000000313")

OTHER_ORG_ID = UUID("10000000-0000-0000-0000-000000000090")
OTHER_CASE_ID = UUID("40000000-0000-0000-0000-000000000390")
OTHER_THREAD_ID = UUID("90000000-0000-0000-0000-000000000390")
OTHER_MESSAGE_ID = UUID("91000000-0000-0000-0000-000000000390")
OTHER_CANDIDATE_ID = UUID("92000000-0000-0000-0000-000000000390")
OTHER_VERIFICATION_ID = UUID("93000000-0000-0000-0000-000000000390")
OTHER_FACT_ID = UUID("94000000-0000-0000-0000-000000000390")
OTHER_ADVISOR_ID = UUID("20000000-0000-0000-0000-000000000091")
OTHER_STUDENT_ID = UUID("20000000-0000-0000-0000-000000000092")
OTHER_PARENT_ID = UUID("20000000-0000-0000-0000-000000000093")
UNKNOWN_CASE_ID = UUID("40000000-0000-0000-0000-000000000399")

CROSS_CASE_ID = UUID("40000000-0000-0000-0000-000000000320")
CROSS_ONLY_ADVISOR_ID = UUID("20000000-0000-0000-0000-000000000320")
CROSS_THREAD_ID = UUID("90000000-0000-0000-0000-000000000320")
CROSS_MESSAGE_ID = UUID("91000000-0000-0000-0000-000000000320")
CROSS_SOURCE_MESSAGE_ID = UUID("91000000-0000-0000-0000-000000000321")
CROSS_CANDIDATE_ID = UUID("92000000-0000-0000-0000-000000000320")
CROSS_FACT_ID = UUID("94000000-0000-0000-0000-000000000320")
CROSS_CASE_THREAD_ID = UUID("90000000-0000-0000-0000-000000000322")
CROSS_CASE_MESSAGE_ID = UUID("91000000-0000-0000-0000-000000000322")
CROSS_CASE_CANDIDATE_ID = UUID("92000000-0000-0000-0000-000000000322")
CROSS_CASE_FACT_ID = UUID("94000000-0000-0000-0000-000000000322")
CROSS_CASE_ONLY_ADVISOR_ID = UUID("20000000-0000-0000-0000-000000000322")

AUTHOR_THREAD_ID = UUID("90000000-0000-0000-0000-000000000340")
AUTHOR_MESSAGE_ID = UUID("91000000-0000-0000-0000-000000000340")
AUTHOR_CANDIDATE_ID = UUID("92000000-0000-0000-0000-000000000340")

REJECT_CASE_ID = UUID("40000000-0000-0000-0000-000000000350")
REJECT_THREAD_ID = UUID("90000000-0000-0000-0000-000000000350")
REJECT_MESSAGE_ID = UUID("91000000-0000-0000-0000-000000000350")
REJECT_CANDIDATE_ID = UUID("92000000-0000-0000-0000-000000000350")
REJECT_VERIFICATION_ID = UUID("93000000-0000-0000-0000-000000000350")

SUPERSESSION_CASE_ID = UUID("40000000-0000-0000-0000-000000000330")
SUPERSESSION_THREAD_ID = UUID("90000000-0000-0000-0000-000000000330")
SUPERSESSION_MESSAGE_IDS = (
    UUID("91000000-0000-0000-0000-000000000331"),
    UUID("91000000-0000-0000-0000-000000000332"),
    UUID("91000000-0000-0000-0000-000000000333"),
)
SUPERSESSION_CANDIDATE_IDS = (
    UUID("92000000-0000-0000-0000-000000000331"),
    UUID("92000000-0000-0000-0000-000000000332"),
    UUID("92000000-0000-0000-0000-000000000333"),
)
SUPERSESSION_VERIFICATION_IDS = (
    UUID("93000000-0000-0000-0000-000000000331"),
    UUID("93000000-0000-0000-0000-000000000332"),
    UUID("93000000-0000-0000-0000-000000000333"),
)
SUPERSESSION_FACT_IDS = (
    UUID("94000000-0000-0000-0000-000000000331"),
    UUID("94000000-0000-0000-0000-000000000332"),
    UUID("94000000-0000-0000-0000-000000000333"),
)

COLLABORATION_TABLES = (
    "collaboration_threads",
    "message_events",
    "memory_candidates",
    "memory_candidate_verifications",
    "confirmed_facts",
    "case_revision_confirmed_fact_refs",
)
COLLABORATION_API_FUNCTIONS = {
    "create_collaboration_thread": "uuid, uuid, text, uuid, uuid, text, text",
    "append_collaboration_message": (
        "uuid, uuid, text, uuid, uuid, text, text, text, text"
    ),
    "propose_memory_candidate": (
        "uuid, uuid, text, uuid, uuid, integer, text, jsonb, text, text, text"
    ),
    "verify_memory_candidate": (
        "uuid, uuid, uuid, integer, text, text, uuid, uuid, text, text"
    ),
    "read_collaboration_thread": "uuid, uuid, text, uuid",
    "read_collaboration_messages": "uuid, uuid, text, uuid, bigint, integer",
    "read_memory_candidates": "uuid, uuid, text, uuid, integer",
    "read_confirmed_facts": "uuid, uuid, text, uuid, integer",
}
COLLABORATION_INTERNAL_FUNCTIONS = {
    "reject_collaboration_mutation": "",
    "serialize_agent_task_case_revision": "",
    "assert_collaboration_context": "uuid, uuid, text",
    "validate_collaboration_message": "text",
    "validate_collaboration_fact": "text, text, jsonb",
    "seed_demo_collaboration": "uuid, uuid, uuid, uuid, uuid, uuid, uuid, uuid, text",
}

EXPECTED_COLLABORATION_FOREIGN_KEYS = (
    (
        "thread Case",
        "collaboration_threads",
        ("organization_id", "case_id"),
        "student_cases",
        ("organization_id", "id"),
        False,
        False,
    ),
    (
        "thread creator participant",
        "collaboration_threads",
        ("organization_id", "case_id", "created_by_actor_id", "created_by_role"),
        "student_case_participants",
        ("organization_id", "case_id", "actor_id", "role"),
        False,
        False,
    ),
    (
        "message thread",
        "message_events",
        ("organization_id", "case_id", "thread_id"),
        "collaboration_threads",
        ("organization_id", "case_id", "id"),
        False,
        False,
    ),
    (
        "message participant",
        "message_events",
        ("organization_id", "case_id", "actor_id", "actor_role"),
        "student_case_participants",
        ("organization_id", "case_id", "actor_id", "role"),
        False,
        False,
    ),
    (
        "candidate revision",
        "memory_candidates",
        ("organization_id", "case_id", "case_revision"),
        "student_case_revisions",
        ("organization_id", "case_id", "revision"),
        False,
        False,
    ),
    (
        "candidate source message and proposer",
        "memory_candidates",
        (
            "organization_id",
            "case_id",
            "message_event_id",
            "proposing_actor_id",
            "proposing_role",
        ),
        "message_events",
        ("organization_id", "case_id", "id", "actor_id", "actor_role"),
        False,
        False,
    ),
    (
        "candidate subject participant",
        "memory_candidates",
        ("organization_id", "case_id", "subject_actor_id", "subject_role"),
        "student_case_participants",
        ("organization_id", "case_id", "actor_id", "role"),
        False,
        False,
    ),
    (
        "candidate proposer participant",
        "memory_candidates",
        ("organization_id", "case_id", "proposing_actor_id", "proposing_role"),
        "student_case_participants",
        ("organization_id", "case_id", "actor_id", "role"),
        False,
        False,
    ),
    (
        "verification candidate",
        "memory_candidate_verifications",
        ("organization_id", "case_id", "candidate_id"),
        "memory_candidates",
        ("organization_id", "case_id", "id"),
        False,
        False,
    ),
    (
        "verification advisor participant",
        "memory_candidate_verifications",
        ("organization_id", "case_id", "advisor_actor_id", "advisor_role"),
        "student_case_participants",
        ("organization_id", "case_id", "actor_id", "role"),
        False,
        False,
    ),
    (
        "verification result fact",
        "memory_candidate_verifications",
        ("organization_id", "case_id", "result_fact_id"),
        "confirmed_facts",
        ("organization_id", "case_id", "id"),
        True,
        True,
    ),
    (
        "verification result revision",
        "memory_candidate_verifications",
        ("organization_id", "case_id", "result_revision"),
        "student_case_revisions",
        ("organization_id", "case_id", "revision"),
        True,
        True,
    ),
    (
        "fact candidate source",
        "confirmed_facts",
        (
            "organization_id",
            "case_id",
            "source_candidate_id",
            "source_message_event_id",
            "subject_actor_id",
            "subject_role",
        ),
        "memory_candidates",
        (
            "organization_id",
            "case_id",
            "id",
            "message_event_id",
            "subject_actor_id",
            "subject_role",
        ),
        False,
        False,
    ),
    (
        "fact subject participant",
        "confirmed_facts",
        ("organization_id", "case_id", "subject_actor_id", "subject_role"),
        "student_case_participants",
        ("organization_id", "case_id", "actor_id", "role"),
        False,
        False,
    ),
    (
        "fact confirming advisor participant",
        "confirmed_facts",
        (
            "organization_id",
            "case_id",
            "confirming_advisor_actor_id",
            "confirming_advisor_role",
        ),
        "student_case_participants",
        ("organization_id", "case_id", "actor_id", "role"),
        False,
        False,
    ),
    (
        "fact supersession",
        "confirmed_facts",
        ("organization_id", "case_id", "fact_key", "supersedes_fact_id"),
        "confirmed_facts",
        ("organization_id", "case_id", "fact_key", "id"),
        False,
        False,
    ),
    (
        "revision source",
        "case_revision_confirmed_fact_refs",
        ("organization_id", "case_id", "case_revision"),
        "student_case_revisions",
        ("organization_id", "case_id", "revision"),
        False,
        False,
    ),
    (
        "revision fact",
        "case_revision_confirmed_fact_refs",
        ("organization_id", "case_id", "fact_key", "confirmed_fact_id"),
        "confirmed_facts",
        ("organization_id", "case_id", "fact_key", "id"),
        False,
        False,
    ),
)

PARTICIPANT_CANDIDATE_KEYS = {
    "schema_version",
    "fact_key",
    "value",
    "state",
    "created_at",
    "expires_at",
}
ADVISOR_CANDIDATE_KEYS = PARTICIPANT_CANDIDATE_KEYS | {
    "candidate_id",
    "message_event_id",
    "source_message_sequence_no",
    "subject_actor_id",
    "subject_role",
    "case_revision",
    "verification_id",
    "decision",
    "reason",
    "request_sha256",
    "value_sha256",
}
PARTICIPANT_FACT_KEYS = {
    "schema_version",
    "fact_key",
    "value",
    "fact_version",
    "confirmed_at",
    "subject_role",
    "confirming_advisor_role",
}
ADVISOR_FACT_KEYS = PARTICIPANT_FACT_KEYS | {
    "confirmed_fact_id",
    "candidate_id",
    "verification_id",
    "source_message_event_id",
    "source_message_sequence_no",
    "source_message_sha256_prefix",
    "confirming_advisor_actor_id",
    "reason",
    "supersedes_fact_id",
}


def actor_context(role: ActorRole) -> ActorContext:
    return ActorContext(
        organization_id=ORG_ID,
        actor_id={
            ActorRole.ADVISOR: ADVISOR_ID,
            ActorRole.STUDENT: STUDENT_ID,
            ActorRole.PARENT: PARENT_ID,
        }[role],
        role=role,
        session_id=SESSION_ID,
    )


async def set_actor_context(session: AsyncSession, context: ActorContext) -> None:
    for key, value in (
        ("organization_id", context.organization_id),
        ("actor_id", context.actor_id),
        ("role", context.role.value),
    ):
        await session.execute(
            text("SELECT set_config(:key,:value,true)"),
            {"key": f"night_voyager.{key}", "value": str(value)},
        )


async def ensure_intake_case() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    fixture_case = validate_planning_fixture().planning_input.case
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG_ID)},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.organizations(id,name,is_synthetic) "
                    "VALUES(:org,'Synthetic collaboration repository test',true) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {"org": ORG_ID},
            )
            for index, (actor_id, role) in enumerate(
                (
                    (ADVISOR_ID, ActorRole.ADVISOR),
                    (STUDENT_ID, ActorRole.STUDENT),
                    (PARENT_ID, ActorRole.PARENT),
                ),
                start=1,
            ):
                await connection.execute(
                    text(
                        "INSERT INTO app.actors("
                        "id,organization_id,display_name,is_synthetic) "
                        "VALUES(:actor,:org,:name,true) ON CONFLICT (id) DO NOTHING"
                    ),
                    {
                        "actor": actor_id,
                        "org": ORG_ID,
                        "name": f"Synthetic collaboration {role.value}",
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
                        "membership": UUID(f"35000000-0000-0000-0000-{index:012d}"),
                        "org": ORG_ID,
                        "actor": actor_id,
                        "role": role.value,
                    },
                )
            exists = await connection.scalar(
                text(
                    "SELECT EXISTS(SELECT 1 FROM app.student_cases "
                    "WHERE organization_id=:org AND id=:case)"
                ),
                {"org": ORG_ID, "case": CASE_ID},
            )
            if not exists:
                await connection.execute(
                    text(
                        "SELECT app.publish_case_revision("
                        ":org,:case,NULL,1,CAST(:student AS jsonb),CAST(:family AS jsonb))"
                    ),
                    {
                        "org": ORG_ID,
                        "case": CASE_ID,
                        "student": json.dumps(fixture_case.student.model_dump(mode="json")),
                        "family": json.dumps(fixture_case.family.model_dump(mode="json")),
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


async def ensure_planning_case() -> None:
    await ensure_intake_case()
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    fixture_case = validate_planning_fixture().planning_input.case
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG_ID)},
            )
            exists = await connection.scalar(
                text(
                    "SELECT EXISTS(SELECT 1 FROM app.student_cases "
                    "WHERE organization_id=:org AND id=:case)"
                ),
                {"org": ORG_ID, "case": PLANNING_CASE_ID},
            )
            if not exists:
                await connection.execute(
                    text(
                        "SELECT app.publish_case_revision("
                        ":org,:case,NULL,1,CAST(:student AS jsonb),CAST(:family AS jsonb))"
                    ),
                    {
                        "org": ORG_ID,
                        "case": PLANNING_CASE_ID,
                        "student": json.dumps(fixture_case.student.model_dump(mode="json")),
                        "family": json.dumps(fixture_case.family.model_dump(mode="json")),
                    },
                )
                await connection.execute(
                    text(
                        "UPDATE app.student_cases SET state='planning' "
                        "WHERE organization_id=:org AND id=:case"
                    ),
                    {"org": ORG_ID, "case": PLANNING_CASE_ID},
                )
            await connection.execute(
                text("SELECT app.seed_case_participants(:org,:case,:advisor,:student,:parent)"),
                {
                    "org": ORG_ID,
                    "case": PLANNING_CASE_ID,
                    "advisor": ADVISOR_ID,
                    "student": STUDENT_ID,
                    "parent": PARENT_ID,
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO app.source_packs("
                    "organization_id,id,version,schema_version,manifest_sha256) "
                    "VALUES(:org,:pack,1,1,repeat('7',64)) ON CONFLICT DO NOTHING"
                ),
                {"org": ORG_ID, "pack": PLANNING_SOURCE_PACK_ID},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.planning_runs("
                    "organization_id,id,case_id,case_revision,source_pack_id,"
                    "source_pack_version,policy_version,evidence_projection_sha256,"
                    "state,is_current) "
                    "VALUES(:org,:run,:case,1,:pack,1,'collaboration-test-v1',"
                    "repeat('8',64),'synthesizing',true) ON CONFLICT DO NOTHING"
                ),
                {
                    "org": ORG_ID,
                    "run": PLANNING_RUN_ID,
                    "case": PLANNING_CASE_ID,
                    "pack": PLANNING_SOURCE_PACK_ID,
                },
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_only_the_source_message_author_can_propose_its_memory_candidate() -> None:
    await ensure_intake_case()
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    advisor = actor_context(ActorRole.ADVISOR)
    student = actor_context(ActorRole.STUDENT)
    parent = actor_context(ActorRole.PARENT)
    try:
        async with sessions() as session:
            transaction = await session.begin()
            try:
                adapter = PostgresCollaborationRepository(session)
                await set_actor_context(session, advisor)
                await adapter.create_thread(
                    advisor,
                    CASE_ID,
                    AUTHOR_THREAD_ID,
                    sha256("author-thread-request"),
                    "author-thread",
                )
                body = "Our family accepts a bounded high-risk option."
                await set_actor_context(session, parent)
                await adapter.append_message(
                    parent,
                    AppendMessageCommand(thread_id=AUTHOR_THREAD_ID, body=body),
                    AUTHOR_MESSAGE_ID,
                    sha256(body),
                    sha256("author-message-request"),
                    "author-message",
                )

                await set_actor_context(session, student)
                await expect_session_sqlstate(
                    session,
                    "SELECT * FROM app.propose_memory_candidate("
                    ":org,:actor,:role,:message,:candidate,1,:fact_key,"
                    "CAST(:value AS jsonb),:value_sha256,:request_sha256,"
                    ":key_sha256)",
                    {
                        "org": ORG_ID,
                        "actor": STUDENT_ID,
                        "role": "student",
                        "message": AUTHOR_MESSAGE_ID,
                        "candidate": UUID(
                            "92000000-0000-0000-0000-000000000341"
                        ),
                        "fact_key": "student.intended_field",
                        "value": json.dumps("computer science"),
                        "value_sha256": canonical_sha256("computer science"),
                        "request_sha256": sha256(
                            "wrong-source-author-request"
                        ),
                        "key_sha256": sha256("wrong-source-author-key"),
                    },
                    "NV007",
                )

                await set_actor_context(session, parent)
                proposed = await adapter.propose_candidate(
                    parent,
                    ProposeMemoryCandidateCommand(
                        message_event_id=AUTHOR_MESSAGE_ID,
                        case_revision=1,
                        proposal=RiskToleranceProposal(
                            schema_version=1,
                            fact_key=FactKey.FAMILY_RISK_TOLERANCE,
                            value="high",
                        ),
                    ),
                    AUTHOR_CANDIDATE_ID,
                    canonical_sha256("high"),
                    sha256("source-author-request"),
                    "source-author-candidate",
                )
                assert proposed.state is MemoryCandidateState.PENDING

                await set_actor_context(session, advisor)
                candidates = await adapter.list_candidates(advisor, CASE_ID, 50)
                assert len(candidates) == 1
                candidate = candidates[0]
                assert isinstance(candidate, MemoryCandidateAdvisorV1)
                assert candidate.candidate_id == AUTHOR_CANDIDATE_ID
                assert candidate.message_event_id == AUTHOR_MESSAGE_ID
                assert candidate.subject_actor_id == PARENT_ID
                assert candidate.subject_role is ActorRole.PARENT
            finally:
                if transaction.is_active:
                    await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_cross_tenant_reads_and_writes_are_non_enumerating_and_side_effect_free() -> None:
    await ensure_intake_case()
    await ensure_other_tenant_case()
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    advisor = actor_context(ActorRole.ADVISOR)
    try:
        async with sessions() as session:
            transaction = await session.begin()
            try:
                await set_actor_context(session, advisor)
                read_statement = (
                    "SELECT * FROM app.read_collaboration_thread("
                    ":org,:actor,:role,:case)"
                )
                write_statement = (
                    "SELECT * FROM app.create_collaboration_thread("
                    ":org,:actor,:role,:case,:thread,:request_sha256,:key_sha256)"
                )
                await expect_session_sqlstate(
                    session,
                    read_statement,
                    {
                        "org": ORG_ID,
                        "actor": ADVISOR_ID,
                        "role": "advisor",
                        "case": OTHER_CASE_ID,
                    },
                    "NV007",
                )
                await expect_session_sqlstate(
                    session,
                    read_statement,
                    {
                        "org": ORG_ID,
                        "actor": ADVISOR_ID,
                        "role": "advisor",
                        "case": UNKNOWN_CASE_ID,
                    },
                    "NV007",
                )
                await expect_session_sqlstate(
                    session,
                    write_statement,
                    {
                        "org": ORG_ID,
                        "actor": ADVISOR_ID,
                        "role": "advisor",
                        "case": OTHER_CASE_ID,
                        "thread": UUID(
                            "90000000-0000-0000-0000-000000000391"
                        ),
                        "request_sha256": "a" * 64,
                        "key_sha256": "b" * 64,
                    },
                    "NV007",
                )
                await expect_session_sqlstate(
                    session,
                    write_statement,
                    {
                        "org": ORG_ID,
                        "actor": ADVISOR_ID,
                        "role": "advisor",
                        "case": UNKNOWN_CASE_ID,
                        "thread": UUID(
                            "90000000-0000-0000-0000-000000000399"
                        ),
                        "request_sha256": "c" * 64,
                        "key_sha256": "d" * 64,
                    },
                    "NV007",
                )
            finally:
                if transaction.is_active:
                    await transaction.rollback()
    finally:
        await engine.dispose()

    migrator = create_async_engine(
        os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"]
    )
    try:
        async with migrator.begin() as connection:
            await connection.execute(
                text(
                    "SELECT set_config("
                    "'night_voyager.organization_id',:org,true)"
                ),
                {"org": str(OTHER_ORG_ID)},
            )
            role_row = (
                (
                    await connection.execute(
                        text(
                            "SELECT current_user AS role_name,rolsuper,rolbypassrls "
                            "FROM pg_roles WHERE rolname=current_user"
                        )
                    )
                )
                .mappings()
                .one()
            )
            assert dict(role_row) == {
                "role_name": "night_voyager_migrator",
                "rolsuper": False,
                "rolbypassrls": False,
            }
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.collaboration_threads "
                        "WHERE organization_id=:org AND case_id=:case"
                    ),
                    {"org": OTHER_ORG_ID, "case": OTHER_CASE_ID},
                )
                == 1
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.idempotency_records "
                        "WHERE operation='collaboration_thread_create' "
                        "AND organization_id=:org AND key_sha256=:cross_key"
                    ),
                    {"org": OTHER_ORG_ID, "cross_key": "b" * 64},
                )
                == 0
            )
            for table in COLLABORATION_TABLES:
                assert (
                    await connection.scalar(
                        text(
                            f"SELECT count(*) FROM app.{table} "
                            "WHERE organization_id=:org"
                        ),
                        {"org": OTHER_ORG_ID},
                    )
                    == 1
                )
                await connection.execute(
                    text(
                        f"CREATE TEMP TABLE rls_snapshot_{table} "
                        f"ON COMMIT DROP AS SELECT * FROM app.{table}"
                    )
                )
            await connection.execute(
                text(
                    "SELECT set_config("
                    "'night_voyager.organization_id',:org,true)"
                ),
                {"org": str(ORG_ID)},
            )
            forced_rls_visible: set[str] = set()
            wrong_tenant_insert: set[str] = set()
            for table in COLLABORATION_TABLES:
                assert (
                    await connection.scalar(
                        text(
                            f"SELECT count(*) FROM app.{table} "
                            "WHERE organization_id=:org"
                        ),
                        {"org": OTHER_ORG_ID},
                    )
                    == 0
                )
                forced_rls_visible.add(table)
                with pytest.raises(DBAPIError) as raised:
                    async with connection.begin_nested():
                        await connection.execute(
                            text(
                                f"INSERT INTO app.{table} "
                                f"SELECT * FROM pg_temp.rls_snapshot_{table}"
                            )
                        )
                assert getattr(raised.value.orig, "sqlstate", None) == "42501"
                wrong_tenant_insert.add(table)
            assert forced_rls_visible == set(COLLABORATION_TABLES)
            assert wrong_tenant_insert == set(COLLABORATION_TABLES)
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.idempotency_records "
                        "WHERE operation='collaboration_thread_create' "
                        "AND organization_id=:org "
                        "AND key_sha256 IN (:cross_key,:missing_key)"
                    ),
                    {
                        "org": ORG_ID,
                        "cross_key": "b" * 64,
                        "missing_key": "d" * 64,
                    },
                )
                == 0
            )
    finally:
        await migrator.dispose()


@pytest.mark.asyncio
async def test_same_tenant_cross_case_lineage_rejects_each_isolatable_fk_edge() -> None:
    await ensure_intake_case()
    await ensure_additional_intake_case(CROSS_CASE_ID)
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.execute(
                    text(
                        "SELECT set_config("
                        "'night_voyager.organization_id',:org,true)"
                    ),
                    {"org": str(ORG_ID)},
                )
                await connection.execute(
                    text(
                        "INSERT INTO app.actors("
                        "id,organization_id,display_name,is_synthetic) "
                        "VALUES(:actor,:org,'Synthetic Case A advisor',true)"
                    ),
                    {"actor": CROSS_ONLY_ADVISOR_ID, "org": ORG_ID},
                )
                await connection.execute(
                    text(
                        "INSERT INTO app.memberships("
                        "id,organization_id,actor_id,role) "
                        "VALUES(:membership,:org,:actor,'advisor')"
                    ),
                    {
                        "membership": UUID(
                            "36000000-0000-0000-0000-000000000320"
                        ),
                        "org": ORG_ID,
                        "actor": CROSS_ONLY_ADVISOR_ID,
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO app.student_case_participants("
                        "organization_id,case_id,actor_id,role) "
                        "VALUES(:org,:case,:actor,'advisor')"
                    ),
                    {
                        "org": ORG_ID,
                        "case": CASE_ID,
                        "actor": CROSS_ONLY_ADVISOR_ID,
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO app.collaboration_threads("
                        "organization_id,id,case_id,created_by_actor_id,"
                        "created_by_role) "
                        "VALUES(:org,:thread,:case,:advisor,'advisor')"
                    ),
                    {
                        "org": ORG_ID,
                        "thread": CROSS_THREAD_ID,
                        "case": CASE_ID,
                        "advisor": ADVISOR_ID,
                    },
                )
                for sequence_no, message_id in enumerate(
                    (CROSS_MESSAGE_ID, CROSS_SOURCE_MESSAGE_ID), start=1
                ):
                    await connection.execute(
                        text(
                            "INSERT INTO app.message_events("
                            "organization_id,id,thread_id,case_id,sequence_no,"
                            "actor_id,actor_role,body,content_sha256,"
                            "request_sha256) "
                            "VALUES(:org,:message,:thread,:case,:sequence,"
                            ":actor,'parent',:body,:content_sha256,"
                            ":request_sha256)"
                        ),
                        {
                            "org": ORG_ID,
                            "message": message_id,
                            "thread": CROSS_THREAD_ID,
                            "case": CASE_ID,
                            "sequence": sequence_no,
                            "actor": PARENT_ID,
                            "body": f"Synthetic cross-Case source {sequence_no}.",
                            "content_sha256": sha256(
                                f"cross-case-message-{sequence_no}"
                            ),
                            "request_sha256": sha256(
                                f"cross-case-message-request-{sequence_no}"
                            ),
                        },
                    )
                await connection.execute(
                    text(
                        "WITH seeded AS (SELECT clock_timestamp() AS created) "
                        "INSERT INTO app.memory_candidates("
                        "organization_id,id,case_id,case_revision,"
                        "message_event_id,subject_actor_id,subject_role,"
                        "proposing_actor_id,proposing_role,fact_key,"
                        "proposed_value,value_sha256,request_sha256,created_at,"
                        "expires_at) "
                        "SELECT :org,:candidate,:case,1,:message,:actor,'parent',"
                        ":actor,'parent','family.risk_tolerance',"
                        "CAST(:value AS jsonb),:value_sha256,:request_sha256,"
                        "seeded.created,seeded.created+interval '7 days' "
                        "FROM seeded"
                    ),
                    {
                        "org": ORG_ID,
                        "candidate": CROSS_CANDIDATE_ID,
                        "case": CASE_ID,
                        "message": CROSS_MESSAGE_ID,
                        "actor": PARENT_ID,
                        "value": json.dumps("medium"),
                        "value_sha256": canonical_sha256("medium"),
                        "request_sha256": sha256("cross-case-candidate"),
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO app.confirmed_facts("
                        "organization_id,id,case_id,fact_key,value,value_sha256,"
                        "source_candidate_id,source_message_event_id,"
                        "subject_actor_id,subject_role,"
                        "confirming_advisor_actor_id,confirming_advisor_role,"
                        "supersedes_fact_id,fact_version) "
                        "VALUES(:org,:fact,:case,'family.risk_tolerance',"
                        "CAST(:value AS jsonb),:value_sha256,:candidate,:message,"
                        ":parent,'parent',:advisor,'advisor',NULL,1)"
                    ),
                    {
                        "org": ORG_ID,
                        "fact": CROSS_FACT_ID,
                        "case": CASE_ID,
                        "value": json.dumps("medium"),
                        "value_sha256": canonical_sha256("medium"),
                        "candidate": CROSS_CANDIDATE_ID,
                        "message": CROSS_MESSAGE_ID,
                        "parent": PARENT_ID,
                        "advisor": ADVISOR_ID,
                    },
                )
                with pytest.raises(DBAPIError) as raised:
                    async with connection.begin_nested():
                        await connection.execute(
                            text(
                                "INSERT INTO app.collaboration_threads("
                                "organization_id,id,case_id,created_by_actor_id,"
                                "created_by_role) "
                                "VALUES(:org,:id,:case,:actor,'advisor')"
                            ),
                            {
                                "org": ORG_ID,
                                "id": UUID(
                                    "90000000-0000-0000-0000-000000000325"
                                ),
                                "case": CROSS_CASE_ID,
                                "actor": CROSS_ONLY_ADVISOR_ID,
                            },
                        )
                assert getattr(raised.value.orig, "sqlstate", None) == "23503"
                observed: set[str] = {"thread participant"}
                await connection.execute(
                    text(
                        "SELECT app.publish_case_revision("
                        ":org,:case,1,2,revision.student_preferences,"
                        "revision.family_preferences) "
                        "FROM app.student_case_revisions revision "
                        "WHERE revision.organization_id=:org "
                        "AND revision.case_id=:case AND revision.revision=1"
                    ),
                    {"org": ORG_ID, "case": CROSS_CASE_ID},
                )
                await connection.execute(
                    text(
                        "INSERT INTO app.actors("
                        "id,organization_id,display_name,is_synthetic) "
                        "VALUES(:actor,:org,'Synthetic Case B advisor',true)"
                    ),
                    {"actor": CROSS_CASE_ONLY_ADVISOR_ID, "org": ORG_ID},
                )
                await connection.execute(
                    text(
                        "INSERT INTO app.memberships("
                        "id,organization_id,actor_id,role) "
                        "VALUES(:membership,:org,:actor,'advisor')"
                    ),
                    {
                        "membership": UUID(
                            "36000000-0000-0000-0000-000000000322"
                        ),
                        "org": ORG_ID,
                        "actor": CROSS_CASE_ONLY_ADVISOR_ID,
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO app.student_case_participants("
                        "organization_id,case_id,actor_id,role) "
                        "VALUES(:org,:case,:actor,'advisor')"
                    ),
                    {
                        "org": ORG_ID,
                        "case": CROSS_CASE_ID,
                        "actor": CROSS_CASE_ONLY_ADVISOR_ID,
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO app.collaboration_threads("
                        "organization_id,id,case_id,created_by_actor_id,"
                        "created_by_role) "
                        "VALUES(:org,:thread,:case,:advisor,'advisor')"
                    ),
                    {
                        "org": ORG_ID,
                        "thread": CROSS_CASE_THREAD_ID,
                        "case": CROSS_CASE_ID,
                        "advisor": ADVISOR_ID,
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO app.message_events("
                        "organization_id,id,thread_id,case_id,sequence_no,"
                        "actor_id,actor_role,body,content_sha256,"
                        "request_sha256) "
                        "VALUES(:org,:message,:thread,:case,1,:actor,'parent',"
                        ":body,:content_sha256,:request_sha256)"
                    ),
                    {
                        "org": ORG_ID,
                        "message": CROSS_CASE_MESSAGE_ID,
                        "thread": CROSS_CASE_THREAD_ID,
                        "case": CROSS_CASE_ID,
                        "actor": PARENT_ID,
                        "body": "Synthetic Case B source.",
                        "content_sha256": sha256("cross-case-b-message"),
                        "request_sha256": sha256(
                            "cross-case-b-message-request"
                        ),
                    },
                )
                await connection.execute(
                    text(
                        "WITH seeded AS (SELECT clock_timestamp() AS created) "
                        "INSERT INTO app.memory_candidates("
                        "organization_id,id,case_id,case_revision,"
                        "message_event_id,subject_actor_id,subject_role,"
                        "proposing_actor_id,proposing_role,fact_key,"
                        "proposed_value,value_sha256,request_sha256,created_at,"
                        "expires_at) SELECT :org,:candidate,:case,2,:message,"
                        ":actor,'parent',:actor,'parent',"
                        "'family.risk_tolerance',CAST(:value AS jsonb),"
                        ":value_sha256,:request_sha256,seeded.created,"
                        "seeded.created+interval '7 days' FROM seeded"
                    ),
                    {
                        "org": ORG_ID,
                        "candidate": CROSS_CASE_CANDIDATE_ID,
                        "case": CROSS_CASE_ID,
                        "message": CROSS_CASE_MESSAGE_ID,
                        "actor": PARENT_ID,
                        "value": json.dumps("low"),
                        "value_sha256": canonical_sha256("low"),
                        "request_sha256": sha256("cross-case-b-candidate"),
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO app.confirmed_facts("
                        "organization_id,id,case_id,fact_key,value,value_sha256,"
                        "source_candidate_id,source_message_event_id,"
                        "subject_actor_id,subject_role,"
                        "confirming_advisor_actor_id,confirming_advisor_role,"
                        "supersedes_fact_id,fact_version) "
                        "VALUES(:org,:fact,:case,'family.risk_tolerance',"
                        "CAST(:value AS jsonb),:value_sha256,:candidate,:message,"
                        ":parent,'parent',:advisor,'advisor',NULL,1)"
                    ),
                    {
                        "org": ORG_ID,
                        "fact": CROSS_CASE_FACT_ID,
                        "case": CROSS_CASE_ID,
                        "value": json.dumps("low"),
                        "value_sha256": canonical_sha256("low"),
                        "candidate": CROSS_CASE_CANDIDATE_ID,
                        "message": CROSS_CASE_MESSAGE_ID,
                        "parent": PARENT_ID,
                        "advisor": ADVISOR_ID,
                    },
                )

                invalid_rows = (
                    (
                        "message thread",
                        "INSERT INTO app.message_events("
                        "organization_id,id,thread_id,case_id,sequence_no,"
                        "actor_id,actor_role,body,content_sha256,request_sha256) "
                        "VALUES(:org,:id,:thread,:case,3,:actor,'parent',"
                        "'Cross Case message',:content,:request)",
                        {
                            "org": ORG_ID,
                            "id": UUID(
                                "91000000-0000-0000-0000-000000000325"
                            ),
                            "thread": CROSS_THREAD_ID,
                            "case": CROSS_CASE_ID,
                            "actor": PARENT_ID,
                            "content": sha256("cross-case-invalid-message"),
                            "request": sha256(
                                "cross-case-invalid-message-request"
                            ),
                        },
                    ),
                    (
                        "message participant",
                        "INSERT INTO app.message_events("
                        "organization_id,id,thread_id,case_id,sequence_no,"
                        "actor_id,actor_role,body,content_sha256,request_sha256) "
                        "VALUES(:org,:id,:thread,:case,2,:actor,'advisor',"
                        "'Cross Case participant',:content,:request)",
                        {
                            "org": ORG_ID,
                            "id": UUID(
                                "91000000-0000-0000-0000-000000000326"
                            ),
                            "thread": CROSS_CASE_THREAD_ID,
                            "case": CROSS_CASE_ID,
                            "actor": CROSS_ONLY_ADVISOR_ID,
                            "content": sha256(
                                "cross-case-invalid-message-participant"
                            ),
                            "request": sha256(
                                "cross-case-invalid-message-participant-request"
                            ),
                        },
                    ),
                    (
                        "candidate revision",
                        "WITH seeded AS (SELECT clock_timestamp() AS created) "
                        "INSERT INTO app.memory_candidates("
                        "organization_id,id,case_id,case_revision,"
                        "message_event_id,subject_actor_id,subject_role,"
                        "proposing_actor_id,proposing_role,fact_key,"
                        "proposed_value,value_sha256,request_sha256,created_at,"
                        "expires_at) SELECT :org,:id,:case,2,:message,:actor,"
                        "'parent',:actor,'parent','family.risk_tolerance',"
                        "CAST(:value AS jsonb),:value_sha256,:request_sha256,"
                        "seeded.created,seeded.created+interval '7 days' "
                        "FROM seeded",
                        {
                            "org": ORG_ID,
                            "id": UUID(
                                "92000000-0000-0000-0000-000000000326"
                            ),
                            "case": CASE_ID,
                            "message": CROSS_SOURCE_MESSAGE_ID,
                            "actor": PARENT_ID,
                            "value": json.dumps("high"),
                            "value_sha256": canonical_sha256("high"),
                            "request_sha256": sha256(
                                "cross-case-invalid-candidate-revision"
                            ),
                        },
                    ),
                    (
                        "candidate source message",
                        "WITH seeded AS (SELECT clock_timestamp() AS created) "
                        "INSERT INTO app.memory_candidates("
                        "organization_id,id,case_id,case_revision,"
                        "message_event_id,subject_actor_id,subject_role,"
                        "proposing_actor_id,proposing_role,fact_key,"
                        "proposed_value,value_sha256,request_sha256,created_at,"
                        "expires_at) SELECT :org,:id,:case,1,:message,:actor,"
                        "'parent',:actor,'parent','family.risk_tolerance',"
                        "CAST(:value AS jsonb),:value_sha256,:request_sha256,"
                        "seeded.created,seeded.created+interval '7 days' "
                        "FROM seeded",
                        {
                            "org": ORG_ID,
                            "id": UUID(
                                "92000000-0000-0000-0000-000000000325"
                            ),
                            "case": CROSS_CASE_ID,
                            "message": CROSS_SOURCE_MESSAGE_ID,
                            "actor": PARENT_ID,
                            "value": json.dumps("high"),
                            "value_sha256": canonical_sha256("high"),
                            "request_sha256": sha256(
                                "cross-case-invalid-candidate"
                            ),
                        },
                    ),
                    (
                        "verification candidate",
                        "INSERT INTO app.memory_candidate_verifications("
                        "organization_id,id,candidate_id,case_id,"
                        "advisor_actor_id,advisor_role,decision,reason,"
                        "request_sha256,result_fact_id,result_revision) "
                        "VALUES(:org,:id,:candidate,:case,:advisor,'advisor',"
                        "'reject','Synthetic rejection',:request,NULL,NULL)",
                        {
                            "org": ORG_ID,
                            "id": UUID(
                                "93000000-0000-0000-0000-000000000325"
                            ),
                            "candidate": CROSS_CANDIDATE_ID,
                            "case": CROSS_CASE_ID,
                            "advisor": ADVISOR_ID,
                            "request": sha256(
                                "cross-case-invalid-verification"
                            ),
                        },
                    ),
                    (
                        "verification advisor participant",
                        "INSERT INTO app.memory_candidate_verifications("
                        "organization_id,id,candidate_id,case_id,"
                        "advisor_actor_id,advisor_role,decision,reason,"
                        "request_sha256,result_fact_id,result_revision) "
                        "VALUES(:org,:id,:candidate,:case,:advisor,'advisor',"
                        "'reject','Synthetic rejection',:request,NULL,NULL)",
                        {
                            "org": ORG_ID,
                            "id": UUID(
                                "93000000-0000-0000-0000-000000000326"
                            ),
                            "candidate": CROSS_CANDIDATE_ID,
                            "case": CASE_ID,
                            "advisor": CROSS_CASE_ONLY_ADVISOR_ID,
                            "request": sha256(
                                "cross-case-invalid-verification-advisor"
                            ),
                        },
                    ),
                    (
                        "verification result fact",
                        "INSERT INTO app.memory_candidate_verifications("
                        "organization_id,id,candidate_id,case_id,"
                        "advisor_actor_id,advisor_role,decision,reason,"
                        "request_sha256,result_fact_id,result_revision) "
                        "VALUES(:org,:id,:candidate,:case,:advisor,'advisor',"
                        "'confirm','Synthetic confirmation',:request,:fact,1)",
                        {
                            "org": ORG_ID,
                            "id": UUID(
                                "93000000-0000-0000-0000-000000000327"
                            ),
                            "candidate": CROSS_CANDIDATE_ID,
                            "case": CASE_ID,
                            "advisor": ADVISOR_ID,
                            "request": sha256(
                                "cross-case-invalid-verification-fact"
                            ),
                            "fact": CROSS_CASE_FACT_ID,
                        },
                    ),
                    (
                        "verification result revision",
                        "INSERT INTO app.memory_candidate_verifications("
                        "organization_id,id,candidate_id,case_id,"
                        "advisor_actor_id,advisor_role,decision,reason,"
                        "request_sha256,result_fact_id,result_revision) "
                        "VALUES(:org,:id,:candidate,:case,:advisor,'advisor',"
                        "'confirm','Synthetic confirmation',:request,:fact,2)",
                        {
                            "org": ORG_ID,
                            "id": UUID(
                                "93000000-0000-0000-0000-000000000328"
                            ),
                            "candidate": CROSS_CANDIDATE_ID,
                            "case": CASE_ID,
                            "advisor": ADVISOR_ID,
                            "request": sha256(
                                "cross-case-invalid-verification-revision"
                            ),
                            "fact": CROSS_FACT_ID,
                        },
                    ),
                    (
                        "fact source candidate",
                        "INSERT INTO app.confirmed_facts("
                        "organization_id,id,case_id,fact_key,value,"
                        "value_sha256,source_candidate_id,"
                        "source_message_event_id,subject_actor_id,subject_role,"
                        "confirming_advisor_actor_id,confirming_advisor_role,"
                        "supersedes_fact_id,fact_version) "
                        "VALUES(:org,:id,:case,'family.risk_tolerance',"
                        "CAST(:value AS jsonb),:value_sha256,:candidate,"
                        ":message,:parent,'parent',:advisor,'advisor',NULL,2)",
                        {
                            "org": ORG_ID,
                            "id": UUID(
                                "94000000-0000-0000-0000-000000000325"
                            ),
                            "case": CROSS_CASE_ID,
                            "value": json.dumps("medium"),
                            "value_sha256": canonical_sha256("medium"),
                            "candidate": CROSS_CANDIDATE_ID,
                            "message": CROSS_MESSAGE_ID,
                            "parent": PARENT_ID,
                            "advisor": ADVISOR_ID,
                        },
                    ),
                    (
                        "fact confirming advisor participant",
                        "INSERT INTO app.confirmed_facts("
                        "organization_id,id,case_id,fact_key,value,"
                        "value_sha256,source_candidate_id,"
                        "source_message_event_id,subject_actor_id,subject_role,"
                        "confirming_advisor_actor_id,confirming_advisor_role,"
                        "supersedes_fact_id,fact_version) "
                        "VALUES(:org,:id,:case,'family.risk_tolerance',"
                        "CAST(:value AS jsonb),:value_sha256,:candidate,"
                        ":message,:parent,'parent',:advisor,'advisor',NULL,2)",
                        {
                            "org": ORG_ID,
                            "id": UUID(
                                "94000000-0000-0000-0000-000000000326"
                            ),
                            "case": CASE_ID,
                            "value": json.dumps("high"),
                            "value_sha256": canonical_sha256("high"),
                            "candidate": CROSS_CANDIDATE_ID,
                            "message": CROSS_MESSAGE_ID,
                            "parent": PARENT_ID,
                            "advisor": CROSS_CASE_ONLY_ADVISOR_ID,
                        },
                    ),
                    (
                        "fact supersession",
                        "INSERT INTO app.confirmed_facts("
                        "organization_id,id,case_id,fact_key,value,"
                        "value_sha256,source_candidate_id,"
                        "source_message_event_id,subject_actor_id,subject_role,"
                        "confirming_advisor_actor_id,confirming_advisor_role,"
                        "supersedes_fact_id,fact_version) "
                        "VALUES(:org,:id,:case,'family.risk_tolerance',"
                        "CAST(:value AS jsonb),:value_sha256,:candidate,"
                        ":message,:parent,'parent',:advisor,'advisor',"
                        ":supersedes,2)",
                        {
                            "org": ORG_ID,
                            "id": UUID(
                                "94000000-0000-0000-0000-000000000327"
                            ),
                            "case": CASE_ID,
                            "value": json.dumps("high"),
                            "value_sha256": canonical_sha256("high"),
                            "candidate": CROSS_CANDIDATE_ID,
                            "message": CROSS_MESSAGE_ID,
                            "parent": PARENT_ID,
                            "advisor": ADVISOR_ID,
                            "supersedes": CROSS_CASE_FACT_ID,
                        },
                    ),
                    (
                        "revision source",
                        "INSERT INTO app.case_revision_confirmed_fact_refs("
                        "organization_id,case_id,case_revision,fact_key,"
                        "confirmed_fact_id) VALUES(:org,:case,2,"
                        "'family.risk_tolerance',:fact)",
                        {
                            "org": ORG_ID,
                            "case": CASE_ID,
                            "fact": CROSS_FACT_ID,
                        },
                    ),
                    (
                        "revision fact reference",
                        "INSERT INTO app.case_revision_confirmed_fact_refs("
                        "organization_id,case_id,case_revision,fact_key,"
                        "confirmed_fact_id) VALUES(:org,:case,1,"
                        "'family.risk_tolerance',:fact)",
                        {
                            "org": ORG_ID,
                            "case": CROSS_CASE_ID,
                            "fact": CROSS_FACT_ID,
                        },
                    ),
                )
                for label, statement, parameters in invalid_rows:
                    with pytest.raises(DBAPIError) as raised:
                        async with connection.begin_nested():
                            await connection.execute(text(statement), parameters)
                            await connection.execute(
                                text("SET CONSTRAINTS ALL IMMEDIATE")
                            )
                    assert getattr(raised.value.orig, "sqlstate", None) == "23503"
                    observed.add(label)
                assert observed == {
                    "thread participant",
                    "message thread",
                    "message participant",
                    "candidate revision",
                    "candidate source message",
                    "verification candidate",
                    "verification advisor participant",
                    "verification result fact",
                    "verification result revision",
                    "fact source candidate",
                    "fact confirming advisor participant",
                    "fact supersession",
                    "revision source",
                    "revision fact reference",
                }
            finally:
                if transaction.is_active:
                    await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_api_and_worker_have_no_direct_authority_on_any_collaboration_table() -> None:
    operations = {
        "SELECT": "SELECT * FROM app.{table} LIMIT 1",
        "INSERT": (
            "INSERT INTO app.{table}(organization_id) "
            f"VALUES('{ORG_ID}')"
        ),
        "UPDATE": "UPDATE app.{table} SET organization_id=organization_id",
        "DELETE": "DELETE FROM app.{table}",
        "TRUNCATE": "TRUNCATE app.{table}",
    }
    for database_url in (
        os.environ["NIGHT_VOYAGER_API_DATABASE_URL"],
        os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"],
    ):
        engine = create_async_engine(database_url)
        try:
            async with engine.connect() as connection:
                observed: set[tuple[str, str]] = set()
                for table in COLLABORATION_TABLES:
                    for privilege, template in operations.items():
                        await expect_connection_sqlstate(
                            connection,
                            template.format(table=table),
                            "42501",
                        )
                        observed.add((table, privilege))
                assert observed == {
                    (table, privilege)
                    for table in COLLABORATION_TABLES
                    for privilege in operations
                }
        finally:
            await engine.dispose()


@pytest.mark.asyncio
async def test_collaboration_catalog_closes_table_and_function_grants_exactly() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            table_rows = (
                (
                    await connection.execute(
                        text(
                            "SELECT c.relname,c.relrowsecurity,"
                            "c.relforcerowsecurity,owner.rolname AS owner_name,"
                            "(has_table_privilege('night_voyager_api',c.oid,'SELECT') "
                            "OR has_table_privilege('night_voyager_api',c.oid,'INSERT') "
                            "OR has_table_privilege('night_voyager_api',c.oid,'UPDATE') "
                            "OR has_table_privilege('night_voyager_api',c.oid,'DELETE') "
                            "OR has_table_privilege('night_voyager_api',c.oid,'TRUNCATE')) "
                            "AS api_any,"
                            "(has_table_privilege('night_voyager_worker',c.oid,'SELECT') "
                            "OR has_table_privilege('night_voyager_worker',c.oid,'INSERT') "
                            "OR has_table_privilege('night_voyager_worker',c.oid,'UPDATE') "
                            "OR has_table_privilege('night_voyager_worker',c.oid,'DELETE') "
                            "OR has_table_privilege('night_voyager_worker',c.oid,'TRUNCATE')) "
                            "AS worker_any,"
                            "(has_table_privilege('public',c.oid,'SELECT') "
                            "OR has_table_privilege('public',c.oid,'INSERT') "
                            "OR has_table_privilege('public',c.oid,'UPDATE') "
                            "OR has_table_privilege('public',c.oid,'DELETE') "
                            "OR has_table_privilege('public',c.oid,'TRUNCATE')) "
                            "AS public_any "
                            "FROM pg_class c "
                            "JOIN pg_namespace n ON n.oid=c.relnamespace "
                            "JOIN pg_roles owner ON owner.oid=c.relowner "
                            "WHERE n.nspname='app' AND c.relname IN ("
                            "'collaboration_threads','message_events',"
                            "'memory_candidates','memory_candidate_verifications',"
                            "'confirmed_facts','case_revision_confirmed_fact_refs')"
                        )
                    )
                )
                .mappings()
                .all()
            )
            assert {row["relname"] for row in table_rows} == set(
                COLLABORATION_TABLES
            )
            for row in table_rows:
                assert row["relrowsecurity"] is True
                assert row["relforcerowsecurity"] is True
                assert row["owner_name"] == "night_voyager_migrator"
                assert row["api_any"] is False
                assert row["worker_any"] is False
                assert row["public_any"] is False

            policy_rows = (
                (
                    await connection.execute(
                        text(
                            "SELECT child.relname,p.polname,p.polcmd::text AS polcmd,"
                            "p.polpermissive,"
                            "p.polroles,pg_get_expr(p.polqual,p.polrelid) AS qual,"
                            "pg_get_expr(p.polwithcheck,p.polrelid) AS with_check "
                            "FROM pg_policy p "
                            "JOIN pg_class child ON child.oid=p.polrelid "
                            "JOIN pg_namespace n ON n.oid=child.relnamespace "
                            "WHERE n.nspname='app' AND child.relname IN ("
                            "'collaboration_threads','message_events',"
                            "'memory_candidates','memory_candidate_verifications',"
                            "'confirmed_facts','case_revision_confirmed_fact_refs')"
                        )
                    )
                )
                .mappings()
                .all()
            )
            assert {row["relname"] for row in policy_rows} == set(
                COLLABORATION_TABLES
            )
            assert len(policy_rows) == len(COLLABORATION_TABLES)
            for row in policy_rows:
                assert row["polname"] == f"{row['relname']}_tenant_isolation"
                assert row["polcmd"] == "*"
                assert row["polpermissive"] is True
                assert tuple(row["polroles"]) == (0,)
                assert row["qual"] == row["with_check"]
                assert row["qual"] is not None
                for fragment in (
                    "organization_id",
                    "NULLIF",
                    "current_setting",
                    "night_voyager.organization_id",
                ):
                    assert fragment in row["qual"]

            foreign_key_rows = (
                (
                    await connection.execute(
                        text(
                            "SELECT child.relname AS child_table,"
                            "ARRAY(SELECT child_att.attname "
                            "FROM unnest(con.conkey) WITH ORDINALITY "
                            "AS cols(attnum,ord) "
                            "JOIN pg_attribute child_att "
                            "ON child_att.attrelid=con.conrelid "
                            "AND child_att.attnum=cols.attnum "
                            "ORDER BY cols.ord) AS child_columns,"
                            "parent.relname AS parent_table,"
                            "ARRAY(SELECT parent_att.attname "
                            "FROM unnest(con.confkey) WITH ORDINALITY "
                            "AS cols(attnum,ord) "
                            "JOIN pg_attribute parent_att "
                            "ON parent_att.attrelid=con.confrelid "
                            "AND parent_att.attnum=cols.attnum "
                            "ORDER BY cols.ord) AS parent_columns,"
                            "con.condeferrable,con.condeferred,"
                            "pg_get_constraintdef(con.oid,true) AS definition "
                            "FROM pg_constraint con "
                            "JOIN pg_class child ON child.oid=con.conrelid "
                            "JOIN pg_class parent ON parent.oid=con.confrelid "
                            "JOIN pg_namespace n ON n.oid=child.relnamespace "
                            "WHERE con.contype='f' AND n.nspname='app' "
                            "AND child.relname IN ("
                            "'collaboration_threads','message_events',"
                            "'memory_candidates','memory_candidate_verifications',"
                            "'confirmed_facts','case_revision_confirmed_fact_refs')"
                        )
                    )
                )
                .mappings()
                .all()
            )
            observed_foreign_keys = {
                (
                    row["child_table"],
                    tuple(row["child_columns"]),
                    row["parent_table"],
                    tuple(row["parent_columns"]),
                    row["condeferrable"],
                    row["condeferred"],
                )
                for row in foreign_key_rows
            }
            assert observed_foreign_keys == {
                expected[1:] for expected in EXPECTED_COLLABORATION_FOREIGN_KEYS
            }
            assert all(
                row["definition"].startswith("FOREIGN KEY (")
                for row in foreign_key_rows
            )

            function_rows = (
                (
                    await connection.execute(
                        text(
                            "SELECT p.proname,oidvectortypes(p.proargtypes) "
                            "AS identity_arguments,p.prosecdef,p.proconfig,"
                            "owner.rolname AS owner_name,"
                            "has_function_privilege("
                            "'night_voyager_api',p.oid,'EXECUTE') AS api_execute,"
                            "has_function_privilege("
                            "'night_voyager_worker',p.oid,'EXECUTE') "
                            "AS worker_execute,"
                            "has_function_privilege("
                            "'public',p.oid,'EXECUTE') AS public_execute "
                            "FROM pg_proc p "
                            "JOIN pg_namespace n ON n.oid=p.pronamespace "
                            "JOIN pg_roles owner ON owner.oid=p.proowner "
                            "WHERE n.nspname='app' AND p.proname IN ("
                            "'reject_collaboration_mutation',"
                            "'serialize_agent_task_case_revision',"
                            "'assert_collaboration_context',"
                            "'validate_collaboration_message',"
                            "'validate_collaboration_fact',"
                            "'create_collaboration_thread',"
                            "'append_collaboration_message',"
                            "'propose_memory_candidate',"
                            "'verify_memory_candidate',"
                            "'read_collaboration_thread',"
                            "'read_collaboration_messages',"
                            "'read_memory_candidates',"
                            "'read_confirmed_facts','seed_demo_collaboration')"
                        )
                    )
                )
                .mappings()
                .all()
            )
            expected_functions = {
                **COLLABORATION_API_FUNCTIONS,
                **COLLABORATION_INTERNAL_FUNCTIONS,
            }
            assert {row["proname"] for row in function_rows} == set(
                expected_functions
            )
            for row in function_rows:
                name = row["proname"]
                assert row["identity_arguments"] == expected_functions[name]
                assert row["owner_name"] == "night_voyager_migrator"
                assert row["proconfig"] == [
                    "search_path=pg_catalog, pg_temp"
                ]
                assert row["prosecdef"] is (
                    name != "reject_collaboration_mutation"
                )
                assert row["api_execute"] is (
                    name in COLLABORATION_API_FUNCTIONS
                )
                assert row["worker_execute"] is False
                assert row["public_execute"] is False

            legacy_writer = (
                (
                    await connection.execute(
                        text(
                            "SELECT has_function_privilege("
                            "'night_voyager_api',p.oid,'EXECUTE') AS api_execute "
                            "FROM pg_proc p JOIN pg_namespace n "
                            "ON n.oid=p.pronamespace "
                            "WHERE n.nspname='app' "
                            "AND p.proname='publish_case_revision' "
                            "AND oidvectortypes(p.proargtypes)="
                            "'uuid, uuid, integer, integer, jsonb, jsonb'"
                        )
                    )
                )
                .mappings()
                .one()
            )
            assert legacy_writer["api_execute"] is False
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_successful_reject_is_terminal_replayable_and_revision_neutral() -> None:
    await ensure_additional_intake_case(REJECT_CASE_ID)
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    advisor = actor_context(ActorRole.ADVISOR)
    parent = actor_context(ActorRole.PARENT)
    try:
        async with sessions() as session, session.begin():
            adapter = PostgresCollaborationRepository(session)
            await set_actor_context(session, advisor)
            await adapter.create_thread(
                advisor,
                REJECT_CASE_ID,
                REJECT_THREAD_ID,
                sha256("reject-thread-request"),
                "reject-thread",
            )
            before_revision = await session.scalar(
                text(
                    "SELECT current_revision FROM app.student_cases "
                    "WHERE organization_id=:org AND id=:case"
                ),
                {"org": ORG_ID, "case": REJECT_CASE_ID},
            )
            assert before_revision == 1

            body = "Our family is not ready to accept the Japan risk."
            await set_actor_context(session, parent)
            await adapter.append_message(
                parent,
                AppendMessageCommand(thread_id=REJECT_THREAD_ID, body=body),
                REJECT_MESSAGE_ID,
                sha256(body),
                sha256("reject-message-request"),
                "reject-message",
            )
            await adapter.propose_candidate(
                parent,
                ProposeMemoryCandidateCommand(
                    message_event_id=REJECT_MESSAGE_ID,
                    case_revision=1,
                    proposal=RiskToleranceProposal(
                        schema_version=1,
                        fact_key=FactKey.FAMILY_RISK_TOLERANCE,
                        value="low",
                    ),
                ),
                REJECT_CANDIDATE_ID,
                canonical_sha256("low"),
                sha256("reject-candidate-request"),
                "reject-candidate",
            )

            reason = "The family explicitly declined this proposed memory."
            request_sha256 = sha256("reject-verification-request")
            await set_actor_context(session, advisor)
            rejected = await adapter.verify_candidate(
                advisor,
                VerifyMemoryCandidateCommand(
                    candidate_id=REJECT_CANDIDATE_ID,
                    expected_case_revision=1,
                    decision=VerificationDecision.REJECT,
                    reason=reason,
                ),
                REJECT_VERIFICATION_ID,
                None,
                request_sha256,
                "reject-verification",
            )
            replay = await adapter.verify_candidate(
                advisor,
                VerifyMemoryCandidateCommand(
                    candidate_id=REJECT_CANDIDATE_ID,
                    expected_case_revision=1,
                    decision=VerificationDecision.REJECT,
                    reason=reason,
                ),
                UUID("93000000-0000-0000-0000-000000000351"),
                None,
                request_sha256,
                "reject-verification",
            )
            assert rejected.verification_id == REJECT_VERIFICATION_ID
            assert rejected.decision is VerificationDecision.REJECT
            assert rejected.result_fact_id is None
            assert rejected.result_revision is None
            assert rejected.replayed is False
            assert replay.verification_id == REJECT_VERIFICATION_ID
            assert replay.replayed is True

            with pytest.raises(MemoryCandidateTerminalError):
                async with session.begin_nested():
                    await adapter.verify_candidate(
                        advisor,
                        VerifyMemoryCandidateCommand(
                            candidate_id=REJECT_CANDIDATE_ID,
                            expected_case_revision=1,
                            decision=VerificationDecision.REJECT,
                            reason=reason,
                        ),
                        UUID("93000000-0000-0000-0000-000000000352"),
                        None,
                        request_sha256,
                        "reject-verification-second-key",
                    )

            candidates = await adapter.list_candidates(advisor, REJECT_CASE_ID, 50)
            assert len(candidates) == 1
            candidate = candidates[0]
            assert isinstance(candidate, MemoryCandidateAdvisorV1)
            assert candidate.state is MemoryCandidateState.REJECTED
            assert candidate.verification_id == REJECT_VERIFICATION_ID
            assert candidate.decision is VerificationDecision.REJECT
            assert candidate.reason == reason
            assert await adapter.list_confirmed_facts(advisor, REJECT_CASE_ID, 50) == ()
            assert (
                await session.scalar(
                    text(
                        "SELECT current_revision FROM app.student_cases "
                        "WHERE organization_id=:org AND id=:case"
                    ),
                    {"org": ORG_ID, "case": REJECT_CASE_ID},
                )
                == before_revision
            )
    finally:
        await engine.dispose()

    migrator = create_async_engine(
        os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"]
    )
    try:
        async with migrator.begin() as connection:
            await connection.execute(
                text(
                    "SELECT set_config("
                    "'night_voyager.organization_id',:org,true)"
                ),
                {"org": str(ORG_ID)},
            )
            verification_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM app.memory_candidate_verifications "
                    "WHERE organization_id=:org AND case_id=:case "
                    "AND id=:verification AND candidate_id=:candidate "
                    "AND advisor_actor_id=:advisor AND decision='reject' "
                    "AND reason=:reason AND request_sha256=:request_sha256 "
                    "AND result_fact_id IS NULL AND result_revision IS NULL"
                ),
                {
                    "org": ORG_ID,
                    "case": REJECT_CASE_ID,
                    "verification": REJECT_VERIFICATION_ID,
                    "candidate": REJECT_CANDIDATE_ID,
                    "advisor": ADVISOR_ID,
                    "reason": reason,
                    "request_sha256": request_sha256,
                },
            )
            audit_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM app.audit_events "
                    "WHERE organization_id=:org AND case_id=:case "
                    "AND actor_id=:advisor "
                    "AND event_type='memory_candidate_rejected' "
                    "AND subject_id=:verification "
                    "AND payload->>'candidate_id'=:candidate"
                ),
                {
                    "org": ORG_ID,
                    "case": REJECT_CASE_ID,
                    "advisor": ADVISOR_ID,
                    "verification": REJECT_VERIFICATION_ID,
                    "candidate": str(REJECT_CANDIDATE_ID),
                },
            )
            idempotency_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM app.idempotency_records "
                    "WHERE organization_id=:org AND actor_id=:advisor "
                    "AND operation='memory_candidate_verify' "
                    "AND key_sha256=:key_sha256 "
                    "AND request_sha256=:request_sha256 "
                    "AND response_kind='memory_candidate_verification' "
                    "AND response_id=:verification"
                ),
                {
                    "org": ORG_ID,
                    "advisor": ADVISOR_ID,
                    "key_sha256": sha256("reject-verification"),
                    "request_sha256": request_sha256,
                    "verification": REJECT_VERIFICATION_ID,
                },
            )
            fact_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM app.confirmed_facts "
                    "WHERE organization_id=:org AND case_id=:case"
                ),
                {"org": ORG_ID, "case": REJECT_CASE_ID},
            )
            revision_ref_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM app.case_revision_confirmed_fact_refs "
                    "WHERE organization_id=:org AND case_id=:case"
                ),
                {"org": ORG_ID, "case": REJECT_CASE_ID},
            )
            assert (
                verification_count,
                audit_count,
                idempotency_count,
                fact_count,
                revision_ref_count,
            ) == (1, 1, 1, 0, 0)
            assert (
                await connection.scalar(
                    text(
                        "SELECT current_revision FROM app.student_cases "
                        "WHERE organization_id=:org AND id=:case"
                    ),
                    {"org": ORG_ID, "case": REJECT_CASE_ID},
                )
                == 1
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.student_case_revisions "
                        "WHERE organization_id=:org AND case_id=:case"
                    ),
                    {"org": ORG_ID, "case": REJECT_CASE_ID},
                )
                == 1
            )
    finally:
        await migrator.dispose()


@pytest.mark.asyncio
async def test_terminal_projection_precedes_stale_and_expired() -> None:
    if os.environ.get("NIGHT_VOYAGER_DEMO_SEED_READY") != "1":
        pytest.skip("full demo seed is exercised by the authority and db-check suites")
    verification_id = UUID("93000000-0000-0000-0000-000000000399")
    reason = "Synthetic historical rejection for terminal precedence."
    engine = create_async_engine(
        os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"]
    )
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await set_connection_context(connection)
                stale_and_expired = (
                    (
                        await connection.execute(
                            text(
                                "SELECT "
                                "candidate.case_revision<>selected_case.current_revision "
                                "AS stale,candidate.expires_at<=clock_timestamp() "
                                "AS expired "
                                "FROM app.memory_candidates candidate "
                                "JOIN app.student_cases selected_case "
                                "ON selected_case.organization_id="
                                "candidate.organization_id "
                                "AND selected_case.id=candidate.case_id "
                                "WHERE candidate.organization_id=:org "
                                "AND candidate.id=:candidate"
                            ),
                            {
                                "org": ORG_ID,
                                "candidate": COLLABORATION_STALE_CANDIDATE_ID,
                            },
                        )
                    )
                    .mappings()
                    .one()
                )
                assert dict(stale_and_expired) == {
                    "stale": True,
                    "expired": True,
                }
                await connection.execute(
                    text(
                        "INSERT INTO app.memory_candidate_verifications("
                        "organization_id,id,candidate_id,case_id,"
                        "advisor_actor_id,advisor_role,decision,reason,"
                        "request_sha256,result_fact_id,result_revision,created_at) "
                        "VALUES(:org,:verification,:candidate,:case,:advisor,"
                        "'advisor','reject',:reason,:request_sha256,NULL,NULL,"
                        "'2026-01-02T00:00:00Z'::timestamptz)"
                    ),
                    {
                        "org": ORG_ID,
                        "verification": verification_id,
                        "candidate": COLLABORATION_STALE_CANDIDATE_ID,
                        "case": COLLABORATION_STALE_CASE_ID,
                        "advisor": ADVISOR_ID,
                        "reason": reason,
                        "request_sha256": sha256(
                            "terminal-precedence-verification"
                        ),
                    },
                )
                advisor_terminal_projection = (
                    await connection.execute(
                        text(
                            "SELECT projection FROM app.read_memory_candidates("
                            ":org,:actor,'advisor',:case,50)"
                        ),
                        {
                            "org": ORG_ID,
                            "actor": ADVISOR_ID,
                            "case": COLLABORATION_STALE_CASE_ID,
                        },
                    )
                ).scalar_one()
                assert advisor_terminal_projection["state"] == "rejected"
                assert advisor_terminal_projection["verification_id"] == str(
                    verification_id
                )
                assert advisor_terminal_projection["decision"] == "reject"
                assert advisor_terminal_projection["reason"] == reason

                await set_connection_context(
                    connection,
                    actor_id=PARENT_ID,
                    role=ActorRole.PARENT,
                )
                participant_terminal_projection = (
                    await connection.execute(
                        text(
                            "SELECT projection FROM app.read_memory_candidates("
                            ":org,:actor,'parent',:case,50)"
                        ),
                        {
                            "org": ORG_ID,
                            "actor": PARENT_ID,
                            "case": COLLABORATION_STALE_CASE_ID,
                        },
                    )
                ).scalar_one()
                assert participant_terminal_projection["state"] == "rejected"
                assert "verification_id" not in participant_terminal_projection
                assert "reason" not in participant_terminal_projection
            finally:
                if transaction.is_active:
                    await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_three_confirmations_supersede_one_head_and_clone_complete_fact_refs() -> None:
    await ensure_additional_intake_case(SUPERSESSION_CASE_ID)
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    advisor = actor_context(ActorRole.ADVISOR)
    parent = actor_context(ActorRole.PARENT)
    scenarios = (
        (
            "Our family initially prefers a low-risk route.",
            RiskToleranceProposal(
                schema_version=1,
                fact_key=FactKey.FAMILY_RISK_TOLERANCE,
                value="low",
            ),
        ),
        (
            "Our family accepts the explicitly documented Japan risk.",
            JapanRiskAcceptedProposal(
                schema_version=1,
                fact_key=FactKey.FAMILY_JAPAN_RISK_ACCEPTED,
                value=True,
            ),
        ),
        (
            "Our family now accepts a bounded high-risk route.",
            RiskToleranceProposal(
                schema_version=1,
                fact_key=FactKey.FAMILY_RISK_TOLERANCE,
                value="high",
            ),
        ),
    )
    try:
        async with sessions() as session, session.begin():
            adapter = PostgresCollaborationRepository(session)
            await set_actor_context(session, advisor)
            await adapter.create_thread(
                advisor,
                SUPERSESSION_CASE_ID,
                SUPERSESSION_THREAD_ID,
                sha256("supersession-thread-request"),
                "supersession-thread",
            )
            for index, (body, proposal) in enumerate(scenarios):
                expected_revision = index + 1
                await set_actor_context(session, parent)
                await adapter.append_message(
                    parent,
                    AppendMessageCommand(
                        thread_id=SUPERSESSION_THREAD_ID,
                        body=body,
                    ),
                    SUPERSESSION_MESSAGE_IDS[index],
                    sha256(body),
                    sha256(f"supersession-message-request-{index}"),
                    f"supersession-message-{index}",
                )
                value = proposal.model_dump(mode="json")["value"]
                await adapter.propose_candidate(
                    parent,
                    ProposeMemoryCandidateCommand(
                        message_event_id=SUPERSESSION_MESSAGE_IDS[index],
                        case_revision=expected_revision,
                        proposal=proposal,
                    ),
                    SUPERSESSION_CANDIDATE_IDS[index],
                    canonical_sha256(value),
                    sha256(f"supersession-candidate-request-{index}"),
                    f"supersession-candidate-{index}",
                )
                await set_actor_context(session, advisor)
                verified = await adapter.verify_candidate(
                    advisor,
                    VerifyMemoryCandidateCommand(
                        candidate_id=SUPERSESSION_CANDIDATE_IDS[index],
                        expected_case_revision=expected_revision,
                        decision=VerificationDecision.CONFIRM,
                        reason="The participant explicitly confirmed this fact.",
                    ),
                    SUPERSESSION_VERIFICATION_IDS[index],
                    SUPERSESSION_FACT_IDS[index],
                    sha256(f"supersession-verification-request-{index}"),
                    f"supersession-verification-{index}",
                )
                assert verified.verification_id == (
                    SUPERSESSION_VERIFICATION_IDS[index]
                )
                assert verified.result_fact_id == SUPERSESSION_FACT_IDS[index]
                assert verified.result_revision == expected_revision + 1
    finally:
        await engine.dispose()

    migrator = create_async_engine(
        os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"]
    )
    try:
        async with migrator.begin() as connection:
            await connection.execute(
                text(
                    "SELECT set_config("
                    "'night_voyager.organization_id',:org,true)"
                ),
                {"org": str(ORG_ID)},
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT current_revision FROM app.student_cases "
                        "WHERE organization_id=:org AND id=:case"
                    ),
                    {"org": ORG_ID, "case": SUPERSESSION_CASE_ID},
                )
                == 4
            )
            fact_rows = (
                (
                    await connection.execute(
                        text(
                            "SELECT id,fact_key,value,fact_version,"
                            "supersedes_fact_id FROM app.confirmed_facts "
                            "WHERE organization_id=:org AND case_id=:case"
                        ),
                        {"org": ORG_ID, "case": SUPERSESSION_CASE_ID},
                    )
                )
                .mappings()
                .all()
            )
            facts = {row["id"]: row for row in fact_rows}
            assert set(facts) == set(SUPERSESSION_FACT_IDS)
            assert dict(facts[SUPERSESSION_FACT_IDS[0]]) == {
                "id": SUPERSESSION_FACT_IDS[0],
                "fact_key": "family.risk_tolerance",
                "value": "low",
                "fact_version": 1,
                "supersedes_fact_id": None,
            }
            assert dict(facts[SUPERSESSION_FACT_IDS[1]]) == {
                "id": SUPERSESSION_FACT_IDS[1],
                "fact_key": "family.japan_risk_accepted",
                "value": True,
                "fact_version": 1,
                "supersedes_fact_id": None,
            }
            assert dict(facts[SUPERSESSION_FACT_IDS[2]]) == {
                "id": SUPERSESSION_FACT_IDS[2],
                "fact_key": "family.risk_tolerance",
                "value": "high",
                "fact_version": 2,
                "supersedes_fact_id": SUPERSESSION_FACT_IDS[0],
            }

            reference_rows = (
                (
                    await connection.execute(
                        text(
                            "SELECT case_revision,fact_key,confirmed_fact_id "
                            "FROM app.case_revision_confirmed_fact_refs "
                            "WHERE organization_id=:org AND case_id=:case "
                            "ORDER BY case_revision,fact_key"
                        ),
                        {"org": ORG_ID, "case": SUPERSESSION_CASE_ID},
                    )
                )
                .mappings()
                .all()
            )
            assert {
                (
                    row["case_revision"],
                    row["fact_key"],
                    row["confirmed_fact_id"],
                )
                for row in reference_rows
            } == {
                (2, "family.risk_tolerance", SUPERSESSION_FACT_IDS[0]),
                (3, "family.risk_tolerance", SUPERSESSION_FACT_IDS[0]),
                (3, "family.japan_risk_accepted", SUPERSESSION_FACT_IDS[1]),
                (4, "family.risk_tolerance", SUPERSESSION_FACT_IDS[2]),
                (4, "family.japan_risk_accepted", SUPERSESSION_FACT_IDS[1]),
            }
            revisions = (
                (
                    await connection.execute(
                        text(
                            "SELECT revision,family_preferences "
                            "FROM app.student_case_revisions "
                            "WHERE organization_id=:org AND case_id=:case "
                            "AND revision BETWEEN 2 AND 4 ORDER BY revision"
                        ),
                        {"org": ORG_ID, "case": SUPERSESSION_CASE_ID},
                    )
                )
                .mappings()
                .all()
            )
            assert [row["revision"] for row in revisions] == [2, 3, 4]
            assert revisions[0]["family_preferences"]["risk_tolerance"] == "low"
            assert revisions[1]["family_preferences"]["risk_tolerance"] == "low"
            assert revisions[1]["family_preferences"][
                "japan_risk_accepted"
            ] is True
            assert revisions[2]["family_preferences"]["risk_tolerance"] == "high"
            assert revisions[2]["family_preferences"][
                "japan_risk_accepted"
            ] is True
    finally:
        await migrator.dispose()


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def ensure_additional_intake_case(case_id: UUID) -> None:
    await ensure_intake_case()
    fixture_case = validate_planning_fixture().planning_input.case
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG_ID)},
            )
            exists = await connection.scalar(
                text(
                    "SELECT EXISTS(SELECT 1 FROM app.student_cases "
                    "WHERE organization_id=:org AND id=:case)"
                ),
                {"org": ORG_ID, "case": case_id},
            )
            if not exists:
                await connection.execute(
                    text(
                        "SELECT app.publish_case_revision("
                        ":org,:case,NULL,1,CAST(:student AS jsonb),"
                        "CAST(:family AS jsonb))"
                    ),
                    {
                        "org": ORG_ID,
                        "case": case_id,
                        "student": json.dumps(
                            fixture_case.student.model_dump(mode="json")
                        ),
                        "family": json.dumps(
                            fixture_case.family.model_dump(mode="json")
                        ),
                    },
                )
            await connection.execute(
                text(
                    "SELECT app.seed_case_participants("
                    ":org,:case,:advisor,:student,:parent)"
                ),
                {
                    "org": ORG_ID,
                    "case": case_id,
                    "advisor": ADVISOR_ID,
                    "student": STUDENT_ID,
                    "parent": PARENT_ID,
                },
            )
    finally:
        await engine.dispose()


async def ensure_other_tenant_case() -> None:
    fixture_case = validate_planning_fixture().planning_input.case
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(OTHER_ORG_ID)},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.organizations(id,name,is_synthetic) "
                    "VALUES(:org,'Synthetic collaboration authority tenant',true) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {"org": OTHER_ORG_ID},
            )
            actors = (
                (
                    OTHER_ADVISOR_ID,
                    ActorRole.ADVISOR,
                    UUID("36000000-0000-0000-0000-000000000091"),
                ),
                (
                    OTHER_STUDENT_ID,
                    ActorRole.STUDENT,
                    UUID("36000000-0000-0000-0000-000000000092"),
                ),
                (
                    OTHER_PARENT_ID,
                    ActorRole.PARENT,
                    UUID("36000000-0000-0000-0000-000000000093"),
                ),
            )
            for actor_id, role, membership_id in actors:
                await connection.execute(
                    text(
                        "INSERT INTO app.actors("
                        "id,organization_id,display_name,is_synthetic) "
                        "VALUES(:actor,:org,:name,true) ON CONFLICT (id) DO NOTHING"
                    ),
                    {
                        "actor": actor_id,
                        "org": OTHER_ORG_ID,
                        "name": f"Synthetic other {role.value}",
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
                        "membership": membership_id,
                        "org": OTHER_ORG_ID,
                        "actor": actor_id,
                        "role": role.value,
                    },
                )
            exists = await connection.scalar(
                text(
                    "SELECT EXISTS(SELECT 1 FROM app.student_cases "
                    "WHERE organization_id=:org AND id=:case)"
                ),
                {"org": OTHER_ORG_ID, "case": OTHER_CASE_ID},
            )
            if not exists:
                await connection.execute(
                    text(
                        "SELECT app.publish_case_revision("
                        ":org,:case,NULL,1,CAST(:student AS jsonb),"
                        "CAST(:family AS jsonb))"
                    ),
                    {
                        "org": OTHER_ORG_ID,
                        "case": OTHER_CASE_ID,
                        "student": json.dumps(
                            fixture_case.student.model_dump(mode="json")
                        ),
                        "family": json.dumps(
                            fixture_case.family.model_dump(mode="json")
                        ),
                    },
                )
            await connection.execute(
                text(
                    "SELECT app.seed_case_participants("
                    ":org,:case,:advisor,:student,:parent)"
                ),
                {
                    "org": OTHER_ORG_ID,
                    "case": OTHER_CASE_ID,
                    "advisor": OTHER_ADVISOR_ID,
                    "student": OTHER_STUDENT_ID,
                    "parent": OTHER_PARENT_ID,
                },
            )
            await set_connection_context(
                connection,
                organization_id=OTHER_ORG_ID,
                actor_id=OTHER_ADVISOR_ID,
            )
            await connection.execute(
                text(
                    "SELECT * FROM app.create_collaboration_thread("
                    ":org,:actor,'advisor',:case,:thread,"
                    ":request_sha256,:key_sha256)"
                ),
                {
                    "org": OTHER_ORG_ID,
                    "actor": OTHER_ADVISOR_ID,
                    "case": OTHER_CASE_ID,
                    "thread": OTHER_THREAD_ID,
                    "request_sha256": sha256("other-tenant-thread-request"),
                    "key_sha256": sha256("other-tenant-thread-key"),
                },
            )
            await set_connection_context(
                connection,
                organization_id=OTHER_ORG_ID,
                actor_id=OTHER_PARENT_ID,
                role=ActorRole.PARENT,
            )
            other_body = "Synthetic cross-tenant RLS fixture."
            await connection.execute(
                text(
                    "SELECT * FROM app.append_collaboration_message("
                    ":org,:actor,'parent',:thread,:message,:body,"
                    ":content_sha256,:request_sha256,:key_sha256)"
                ),
                {
                    "org": OTHER_ORG_ID,
                    "actor": OTHER_PARENT_ID,
                    "thread": OTHER_THREAD_ID,
                    "message": OTHER_MESSAGE_ID,
                    "body": other_body,
                    "content_sha256": sha256(other_body),
                    "request_sha256": sha256("other-tenant-message-request"),
                    "key_sha256": sha256("other-tenant-message-key"),
                },
            )
            await connection.execute(
                text(
                    "SELECT * FROM app.propose_memory_candidate("
                    ":org,:actor,'parent',:message,:candidate,1,"
                    "'family.risk_tolerance',CAST(:value AS jsonb),"
                    ":value_sha256,:request_sha256,:key_sha256)"
                ),
                {
                    "org": OTHER_ORG_ID,
                    "actor": OTHER_PARENT_ID,
                    "message": OTHER_MESSAGE_ID,
                    "candidate": OTHER_CANDIDATE_ID,
                    "value": json.dumps("medium"),
                    "value_sha256": canonical_sha256("medium"),
                    "request_sha256": sha256("other-tenant-candidate-request"),
                    "key_sha256": sha256("other-tenant-candidate-key"),
                },
            )
            await set_connection_context(
                connection,
                organization_id=OTHER_ORG_ID,
                actor_id=OTHER_ADVISOR_ID,
            )
            await connection.execute(
                text(
                    "SELECT * FROM app.verify_memory_candidate("
                    ":org,:actor,:candidate,1,'confirm',:reason,"
                    ":verification,:fact,:request_sha256,:key_sha256)"
                ),
                {
                    "org": OTHER_ORG_ID,
                    "actor": OTHER_ADVISOR_ID,
                    "candidate": OTHER_CANDIDATE_ID,
                    "reason": "Synthetic RLS graph confirmation.",
                    "verification": OTHER_VERIFICATION_ID,
                    "fact": OTHER_FACT_ID,
                    "request_sha256": sha256("other-tenant-verify-request"),
                    "key_sha256": sha256("other-tenant-verify-key"),
                },
            )
    finally:
        await engine.dispose()


async def set_connection_context(
    connection: AsyncConnection,
    *,
    organization_id: UUID = ORG_ID,
    actor_id: UUID = ADVISOR_ID,
    role: ActorRole = ActorRole.ADVISOR,
) -> None:
    for key, value in (
        ("organization_id", organization_id),
        ("actor_id", actor_id),
        ("role", role.value),
    ):
        await connection.execute(
            text("SELECT set_config(:key,:value,true)"),
            {"key": f"night_voyager.{key}", "value": str(value)},
        )


async def expect_session_sqlstate(
    session: AsyncSession,
    statement: str,
    parameters: dict[str, object],
    expected: str,
) -> None:
    with pytest.raises(DBAPIError) as raised:
        async with session.begin_nested():
            await session.execute(text(statement), parameters)
    assert getattr(raised.value.orig, "sqlstate", None) == expected


async def expect_connection_sqlstate(
    connection: AsyncConnection,
    statement: str,
    expected: str,
) -> None:
    with pytest.raises(DBAPIError) as raised:
        async with connection.begin():
            await set_connection_context(connection)
            await connection.execute(text(statement))
    assert getattr(raised.value.orig, "sqlstate", None) == expected


async def raw_projections(
    session: AsyncSession,
    function: str,
    context: ActorContext,
) -> tuple[dict[str, object], ...]:
    await set_actor_context(session, context)
    result = await session.execute(
        text(f"SELECT projection FROM app.{function}(:org,:actor,:role,:case,50)"),
        {
            "org": ORG_ID,
            "actor": context.actor_id,
            "role": context.role.value,
            "case": CASE_ID,
        },
    )
    return tuple(row["projection"] for row in result.mappings().all())


@pytest.mark.asyncio
async def test_adapter_round_trip_is_typed_idempotent_and_database_role_safe() -> None:
    """The API adapter consumes only closed functions; PostgreSQL removes private fields."""
    await ensure_intake_case()
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    advisor = actor_context(ActorRole.ADVISOR)
    parent = actor_context(ActorRole.PARENT)
    try:
        async with sessions() as session:
            transaction = await session.begin()
            try:
                adapter = PostgresCollaborationRepository(session)

                await set_actor_context(session, advisor)
                thread = await adapter.create_thread(
                    advisor,
                    CASE_ID,
                    THREAD_ID,
                    "1" * 64,
                    "integration-thread-create",
                )

                await set_actor_context(session, parent)
                message = await adapter.append_message(
                    parent,
                    AppendMessageCommand(
                        thread_id=thread.thread_id,
                        body="Our family can accept a bounded high-risk option.",
                    ),
                    MESSAGE_ID,
                    "2" * 64,
                    "3" * 64,
                    "integration-message-append",
                )
                proposed = await adapter.propose_candidate(
                    parent,
                    ProposeMemoryCandidateCommand(
                        message_event_id=message.message_event_id,
                        case_revision=1,
                        proposal=RiskToleranceProposal(
                            schema_version=1,
                            fact_key=FactKey.FAMILY_RISK_TOLERANCE,
                            value="high",
                        ),
                    ),
                    CANDIDATE_ID,
                    "4" * 64,
                    "5" * 64,
                    "integration-candidate-propose",
                )
                assert type(proposed) is MemoryCandidateParticipantV1

                participant_candidate_rows = await raw_projections(
                    session, "read_memory_candidates", parent
                )
                assert len(participant_candidate_rows) == 1
                assert set(participant_candidate_rows[0]) == PARTICIPANT_CANDIDATE_KEYS
                assert not (
                    {
                        "candidate_id",
                        "message_event_id",
                        "subject_actor_id",
                        "request_sha256",
                        "reason",
                    }
                    & participant_candidate_rows[0].keys()
                )
                participant_candidates = await adapter.list_candidates(parent, CASE_ID, 50)
                assert all(
                    type(item) is MemoryCandidateParticipantV1 for item in participant_candidates
                )

                advisor_candidate_rows = await raw_projections(
                    session, "read_memory_candidates", advisor
                )
                assert set(advisor_candidate_rows[0]) == ADVISOR_CANDIDATE_KEYS
                advisor_candidates = await adapter.list_candidates(advisor, CASE_ID, 50)
                assert all(type(item) is MemoryCandidateAdvisorV1 for item in advisor_candidates)
                advisor_candidate = advisor_candidates[0]
                assert isinstance(advisor_candidate, MemoryCandidateAdvisorV1)
                assert advisor_candidate.candidate_id == CANDIDATE_ID

                await set_actor_context(session, advisor)
                verified = await adapter.verify_candidate(
                    advisor,
                    VerifyMemoryCandidateCommand(
                        candidate_id=CANDIDATE_ID,
                        expected_case_revision=1,
                        decision=VerificationDecision.CONFIRM,
                        reason="The participant confirmed this bounded preference.",
                    ),
                    VERIFICATION_ID,
                    FACT_ID,
                    "6" * 64,
                    "integration-candidate-verify",
                )
                replay = await adapter.verify_candidate(
                    advisor,
                    VerifyMemoryCandidateCommand(
                        candidate_id=CANDIDATE_ID,
                        expected_case_revision=1,
                        decision=VerificationDecision.CONFIRM,
                        reason="The participant confirmed this bounded preference.",
                    ),
                    UUID("93000000-0000-0000-0000-000000000399"),
                    UUID("94000000-0000-0000-0000-000000000399"),
                    "6" * 64,
                    "integration-candidate-verify",
                )
                assert verified.result_fact_id == FACT_ID
                assert verified.result_revision == 2
                assert verified.replayed is False
                assert replay.verification_id == VERIFICATION_ID
                assert replay.result_fact_id == FACT_ID
                assert replay.replayed is True

                advisor_fact_rows = await raw_projections(session, "read_confirmed_facts", advisor)
                assert set(advisor_fact_rows[0]) == ADVISOR_FACT_KEYS
                advisor_facts = await adapter.list_confirmed_facts(advisor, CASE_ID, 50)
                assert all(type(item) is ConfirmedFactAdvisorV1 for item in advisor_facts)
                advisor_fact = advisor_facts[0]
                assert isinstance(advisor_fact, ConfirmedFactAdvisorV1)
                assert advisor_fact.confirmed_fact_id == FACT_ID

                participant_fact_rows = await raw_projections(
                    session, "read_confirmed_facts", parent
                )
                assert set(participant_fact_rows[0]) == PARTICIPANT_FACT_KEYS
                assert not (
                    {
                        "confirmed_fact_id",
                        "candidate_id",
                        "verification_id",
                        "source_message_event_id",
                        "source_message_sha256_prefix",
                        "confirming_advisor_actor_id",
                        "reason",
                        "supersedes_fact_id",
                    }
                    & participant_fact_rows[0].keys()
                )
                participant_facts = await adapter.list_confirmed_facts(parent, CASE_ID, 50)
                assert all(type(item) is ConfirmedFactParticipantV1 for item in participant_facts)
            finally:
                if transaction.is_active:
                    await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_planning_confirmation_retires_only_the_locked_current_run() -> None:
    """A synthesizing run may become non-current only after atomic confirmation."""
    await ensure_planning_case()
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    advisor = actor_context(ActorRole.ADVISOR)
    parent = actor_context(ActorRole.PARENT)
    try:
        async with sessions() as session:
            transaction = await session.begin()
            try:
                adapter = PostgresCollaborationRepository(session)
                await set_actor_context(session, advisor)
                await adapter.create_thread(
                    advisor,
                    PLANNING_CASE_ID,
                    PLANNING_THREAD_ID,
                    "7" * 64,
                    "planning-thread-create",
                )
                await set_actor_context(session, parent)
                await adapter.append_message(
                    parent,
                    AppendMessageCommand(
                        thread_id=PLANNING_THREAD_ID,
                        body="Our family accepts a bounded high-risk option.",
                    ),
                    PLANNING_MESSAGE_ID,
                    "8" * 64,
                    "9" * 64,
                    "planning-message-append",
                )
                await adapter.propose_candidate(
                    parent,
                    ProposeMemoryCandidateCommand(
                        message_event_id=PLANNING_MESSAGE_ID,
                        case_revision=1,
                        proposal=RiskToleranceProposal(
                            schema_version=1,
                            fact_key=FactKey.FAMILY_RISK_TOLERANCE,
                            value="high",
                        ),
                    ),
                    PLANNING_CANDIDATE_ID,
                    "a" * 64,
                    "b" * 64,
                    "planning-candidate-propose",
                )
                await set_actor_context(session, advisor)
                verified = await adapter.verify_candidate(
                    advisor,
                    VerifyMemoryCandidateCommand(
                        candidate_id=PLANNING_CANDIDATE_ID,
                        expected_case_revision=1,
                        decision=VerificationDecision.CONFIRM,
                        reason="The participant confirmed this bounded preference.",
                    ),
                    PLANNING_VERIFICATION_ID,
                    PLANNING_FACT_ID,
                    "c" * 64,
                    "planning-candidate-verify",
                )
                run = (
                    (
                        await session.execute(
                            text(
                                "SELECT state,is_current FROM app.planning_runs "
                                "WHERE organization_id=:org AND id=:run"
                            ),
                            {"org": ORG_ID, "run": PLANNING_RUN_ID},
                        )
                    )
                    .mappings()
                    .one()
                )
                assert verified.result_revision == 2
                assert dict(run) == {"state": "synthesizing", "is_current": False}
            finally:
                if transaction.is_active:
                    await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_missing_idempotency_response_is_persistence_not_terminal() -> None:
    """Ledger corruption cannot be presented as a genuine terminal candidate."""
    await ensure_intake_case()
    request_sha256 = "d" * 64
    idempotency_key = "missing-verification-response"
    key_sha256 = hashlib.sha256(idempotency_key.encode()).hexdigest()
    missing_response = UUID("93000000-0000-0000-0000-000000000399")
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with migrator.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG_ID)},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.idempotency_records("
                    "organization_id,actor_id,operation,key_sha256,request_sha256,"
                    "response_kind,response_id) "
                    "VALUES(:org,:actor,'memory_candidate_verify',:key,:request,"
                    "'memory_candidate_verification',:response) "
                    "ON CONFLICT DO NOTHING"
                ),
                {
                    "org": ORG_ID,
                    "actor": ADVISOR_ID,
                    "key": key_sha256,
                    "request": request_sha256,
                    "response": missing_response,
                },
            )
    finally:
        await migrator.dispose()

    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    advisor = actor_context(ActorRole.ADVISOR)
    try:
        async with sessions() as session, session.begin():
            adapter = PostgresCollaborationRepository(session)
            await set_actor_context(session, advisor)
            with pytest.raises(CollaborationPersistenceError, match="persistence_unavailable"):
                await adapter.verify_candidate(
                    advisor,
                    VerifyMemoryCandidateCommand(
                        candidate_id=CANDIDATE_ID,
                        expected_case_revision=1,
                        decision=VerificationDecision.REJECT,
                        reason="The candidate does not match the current preference.",
                    ),
                    missing_response,
                    None,
                    request_sha256,
                    idempotency_key,
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_database_fact_validation_maps_large_numeric_values_to_nv006() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    invalid_budget = {
        "schema_version": 1,
        "currency": "CNY",
        "period": "program_total",
        "preferred_minor": 100,
        "hard_ceiling_minor": 200,
        "elasticity_bps": 10**100,
        "refused": False,
    }
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                savepoint = await connection.begin_nested()
                try:
                    with pytest.raises(DBAPIError) as rejected:
                        await connection.execute(
                            text(
                                "SELECT app.validate_collaboration_fact("
                                "'parent','family.budget',CAST(:value AS jsonb))"
                            ),
                            {"value": json.dumps(invalid_budget)},
                        )
                    assert getattr(rejected.value.orig, "sqlstate", None) == "NV006"
                finally:
                    if savepoint.is_active:
                        await savepoint.rollback()
            finally:
                if transaction.is_active:
                    await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_demo_collaboration_seed_rejects_null_fixture_without_partial_thread() -> None:
    await ensure_intake_case()
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.execute(
                    text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                    {"org": str(ORG_ID)},
                )
                savepoint = await connection.begin_nested()
                try:
                    with pytest.raises(DBAPIError) as rejected:
                        await connection.execute(
                            text(
                                "SELECT app.seed_demo_collaboration("
                                ":org,:case,:thread,:advisor,NULL,NULL,NULL,NULL,NULL)"
                            ),
                            {
                                "org": ORG_ID,
                                "case": CASE_ID,
                                "thread": NULL_SEED_THREAD_ID,
                                "advisor": ADVISOR_ID,
                            },
                        )
                    assert getattr(rejected.value.orig, "sqlstate", None) == "NV006"
                finally:
                    if savepoint.is_active:
                        await savepoint.rollback()
                assert (
                    await connection.scalar(
                        text(
                            "SELECT count(*) FROM app.collaboration_threads "
                            "WHERE organization_id=:org AND id=:thread"
                        ),
                        {"org": ORG_ID, "thread": NULL_SEED_THREAD_ID},
                    )
                    == 0
                )
            finally:
                if transaction.is_active:
                    await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_demo_collaboration_seed_rejects_task_id_collision_atomically() -> None:
    await ensure_planning_case()
    fixture_case = validate_planning_fixture().planning_input.case
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.execute(
                    text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                    {"org": str(ORG_ID)},
                )
                await connection.execute(
                    text(
                        "SELECT app.publish_case_revision("
                        ":org,:case,NULL,1,CAST(:student AS jsonb),CAST(:family AS jsonb))"
                    ),
                    {
                        "org": ORG_ID,
                        "case": COLLISION_CASE_ID,
                        "student": json.dumps(fixture_case.student.model_dump(mode="json")),
                        "family": json.dumps(fixture_case.family.model_dump(mode="json")),
                    },
                )
                await connection.execute(
                    text(
                        "UPDATE app.student_cases SET state='planning' "
                        "WHERE organization_id=:org AND id=:case"
                    ),
                    {"org": ORG_ID, "case": COLLISION_CASE_ID},
                )
                await connection.execute(
                    text("SELECT app.seed_case_participants(:org,:case,:advisor,:student,:parent)"),
                    {
                        "org": ORG_ID,
                        "case": COLLISION_CASE_ID,
                        "advisor": ADVISOR_ID,
                        "student": STUDENT_ID,
                        "parent": PARENT_ID,
                    },
                )
                source_pack = (
                    (
                        await connection.execute(
                            text(
                                "SELECT id,version FROM app.source_packs "
                                "WHERE organization_id=:org ORDER BY id,version LIMIT 1"
                            ),
                            {"org": ORG_ID},
                        )
                    )
                    .mappings()
                    .one()
                )
                await connection.execute(
                    text(
                        "INSERT INTO app.agent_tasks("
                        "organization_id,id,case_id,operation,case_revision,source_pack_id,"
                        "source_pack_version,policy_version,request_sha256,created_by_actor_id,"
                        "row_version,state,attempt_count,lease_generation,created_at,updated_at) "
                        "VALUES(:org,:task,:case,'generate_planning_run_v1',1,:pack,:version,"
                        "'m3a-policy-v1',repeat('f',64),:advisor,1,'waiting_review',0,0,"
                        "timestamptz '2026-01-02 00:00:00+00',"
                        "timestamptz '2026-01-02 00:00:00+00')"
                    ),
                    {
                        "org": ORG_ID,
                        "task": COLLISION_TASK_ID,
                        "case": PLANNING_CASE_ID,
                        "pack": source_pack["id"],
                        "version": source_pack["version"],
                        "advisor": ADVISOR_ID,
                    },
                )

                savepoint = await connection.begin_nested()
                try:
                    with pytest.raises(DBAPIError) as rejected:
                        await connection.execute(
                            text(
                                "SELECT app.seed_demo_collaboration("
                                ":org,:case,:thread,:advisor,NULL,NULL,NULL,:task,'active_task')"
                            ),
                            {
                                "org": ORG_ID,
                                "case": COLLISION_CASE_ID,
                                "thread": COLLISION_THREAD_ID,
                                "advisor": ADVISOR_ID,
                                "task": COLLISION_TASK_ID,
                            },
                        )
                    assert getattr(rejected.value.orig, "sqlstate", None) == "NV008"
                finally:
                    if savepoint.is_active:
                        await savepoint.rollback()

                assert (
                    await connection.scalar(
                        text(
                            "SELECT count(*) FROM app.collaboration_threads "
                            "WHERE organization_id=:org AND case_id=:case"
                        ),
                        {"org": ORG_ID, "case": COLLISION_CASE_ID},
                    )
                    == 0
                )
                assert (
                    await connection.scalar(
                        text(
                            "SELECT count(*) FROM app.agent_task_events "
                            "WHERE organization_id=:org AND task_id=:task"
                        ),
                        {"org": ORG_ID, "task": COLLISION_TASK_ID},
                    )
                    == 0
                )
            finally:
                if transaction.is_active:
                    await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_demo_collaboration_seed_is_exact_idempotent_and_isolated() -> None:
    if os.environ.get("NIGHT_VOYAGER_DEMO_SEED_READY") != "1":
        pytest.skip("full demo seed is exercised by the authority and db-check suites")
    fixture_case = validate_planning_fixture().planning_input.case
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG_ID)},
            )
            cases = (
                (
                    await connection.execute(
                        text(
                            "SELECT id,state,current_revision FROM app.student_cases "
                            "WHERE organization_id=:org AND id IN "
                            "(:primary,:active,:stale,:expired) ORDER BY id"
                        ),
                        {
                            "org": ORG_ID,
                            "primary": COLLABORATION_CASE_ID,
                            "active": COLLABORATION_ACTIVE_CASE_ID,
                            "stale": COLLABORATION_STALE_CASE_ID,
                            "expired": COLLABORATION_EXPIRED_CASE_ID,
                        },
                    )
                )
                .mappings()
                .all()
            )
            assert [(row["id"], row["state"], row["current_revision"]) for row in cases] == [
                (COLLABORATION_CASE_ID, "intake", 1),
                (COLLABORATION_ACTIVE_CASE_ID, "planning", 1),
                (COLLABORATION_STALE_CASE_ID, "intake", 2),
                (COLLABORATION_EXPIRED_CASE_ID, "intake", 1),
            ]

            threads = (
                (
                    await connection.execute(
                        text(
                            "SELECT case_id,id,created_by_actor_id,created_at "
                            "FROM app.collaboration_threads WHERE organization_id=:org "
                            "AND case_id IN (:primary,:active,:stale,:expired) "
                            "ORDER BY case_id"
                        ),
                        {
                            "org": ORG_ID,
                            "primary": COLLABORATION_CASE_ID,
                            "active": COLLABORATION_ACTIVE_CASE_ID,
                            "stale": COLLABORATION_STALE_CASE_ID,
                            "expired": COLLABORATION_EXPIRED_CASE_ID,
                        },
                    )
                )
                .mappings()
                .all()
            )
            assert [(row["case_id"], row["id"]) for row in threads] == [
                (COLLABORATION_CASE_ID, COLLABORATION_THREAD_IDS["primary"]),
                (
                    COLLABORATION_ACTIVE_CASE_ID,
                    COLLABORATION_THREAD_IDS["active_task"],
                ),
                (
                    COLLABORATION_STALE_CASE_ID,
                    COLLABORATION_THREAD_IDS["stale"],
                ),
                (
                    COLLABORATION_EXPIRED_CASE_ID,
                    COLLABORATION_THREAD_IDS["expired"],
                ),
            ]
            assert all(row["created_by_actor_id"] == ADVISOR_ID for row in threads)
            assert {row["created_at"].isoformat() for row in threads} == {
                "2026-01-01T00:00:00+00:00"
            }

            candidate_states = (
                (
                    await connection.execute(
                        text(
                            "SELECT candidate.id,CASE "
                            "WHEN candidate.case_revision<>selected_case.current_revision "
                            "THEN 'stale' "
                            "WHEN candidate.expires_at<=clock_timestamp() THEN 'expired' "
                            "ELSE 'pending' END AS state "
                            "FROM app.memory_candidates candidate "
                            "JOIN app.student_cases selected_case "
                            "ON selected_case.organization_id=candidate.organization_id "
                            "AND selected_case.id=candidate.case_id "
                            "WHERE candidate.organization_id=:org "
                            "AND candidate.id IN (:stale,:expired) ORDER BY candidate.id"
                        ),
                        {
                            "org": ORG_ID,
                            "stale": COLLABORATION_STALE_CANDIDATE_ID,
                            "expired": COLLABORATION_EXPIRED_CANDIDATE_ID,
                        },
                    )
                )
                .mappings()
                .all()
            )
            assert [(row["id"], row["state"]) for row in candidate_states] == [
                (COLLABORATION_STALE_CANDIDATE_ID, "stale"),
                (COLLABORATION_EXPIRED_CANDIDATE_ID, "expired"),
            ]

            seeded_proposals = (
                (
                    await connection.execute(
                        text(
                            "SELECT event.id AS message_id,event.thread_id,event.body,"
                            "event.content_sha256,"
                            "event.request_sha256 AS message_request_sha256,"
                            "candidate.id AS candidate_id,candidate.case_revision,"
                            "candidate.fact_key,candidate.proposed_value,"
                            "candidate.value_sha256,"
                            "candidate.request_sha256 AS candidate_request_sha256 "
                            "FROM app.message_events event "
                            "JOIN app.memory_candidates candidate "
                            "ON candidate.organization_id=event.organization_id "
                            "AND candidate.message_event_id=event.id "
                            "WHERE event.organization_id=:org "
                            "AND event.id IN (:stale,:expired) ORDER BY event.id"
                        ),
                        {
                            "org": ORG_ID,
                            "stale": COLLABORATION_STALE_MESSAGE_ID,
                            "expired": COLLABORATION_EXPIRED_MESSAGE_ID,
                        },
                    )
                )
                .mappings()
                .all()
            )
            assert [row["message_id"] for row in seeded_proposals] == [
                COLLABORATION_STALE_MESSAGE_ID,
                COLLABORATION_EXPIRED_MESSAGE_ID,
            ]
            assert [row["candidate_id"] for row in seeded_proposals] == [
                COLLABORATION_STALE_CANDIDATE_ID,
                COLLABORATION_EXPIRED_CANDIDATE_ID,
            ]
            for row in seeded_proposals:
                assert row["content_sha256"] == hashlib.sha256(
                    row["body"].encode("utf-8")
                ).hexdigest()
                assert row["message_request_sha256"] == canonical_sha256(
                    {"body": row["body"], "thread_id": str(row["thread_id"])}
                )
                assert row["value_sha256"] == canonical_sha256(row["proposed_value"])
                assert row["candidate_request_sha256"] == canonical_sha256(
                    {
                        "case_revision": row["case_revision"],
                        "message_event_id": str(row["message_id"]),
                        "proposal": {
                            "fact_key": row["fact_key"],
                            "schema_version": 1,
                            "value": row["proposed_value"],
                        },
                    }
                )

            active_task = (
                (
                    await connection.execute(
                        text(
                            "SELECT state,operation,result_planning_run_id "
                            "FROM app.agent_tasks WHERE organization_id=:org AND id=:task"
                        ),
                        {"org": ORG_ID, "task": COLLABORATION_ACTIVE_TASK_ID},
                    )
                )
                .mappings()
                .one()
            )
            assert dict(active_task) == {
                "state": "waiting_review",
                "operation": "generate_planning_run_v1",
                "result_planning_run_id": None,
            }
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.message_events "
                        "WHERE organization_id=:org AND thread_id=:thread"
                    ),
                    {
                        "org": ORG_ID,
                        "thread": COLLABORATION_THREAD_IDS["primary"],
                    },
                )
                == 0
            )

            default_case = (
                (
                    await connection.execute(
                        text(
                            "SELECT selected_case.state,selected_case.current_revision,"
                            "revision.student_preferences,revision.family_preferences "
                            "FROM app.student_cases selected_case "
                            "JOIN app.student_case_revisions revision "
                            "ON revision.organization_id=selected_case.organization_id "
                            "AND revision.case_id=selected_case.id "
                            "AND revision.revision=selected_case.current_revision "
                            "WHERE selected_case.organization_id=:org "
                            "AND selected_case.id=:case"
                        ),
                        {"org": ORG_ID, "case": DEFAULT_DEMO_CASE_ID},
                    )
                )
                .mappings()
                .one()
            )
            assert default_case["state"] == "advisor_review"
            assert default_case["current_revision"] == 1
            assert default_case["student_preferences"] == fixture_case.student.model_dump(
                mode="json"
            )
            assert default_case["family_preferences"] == fixture_case.family.model_dump(mode="json")
    finally:
        await engine.dispose()
