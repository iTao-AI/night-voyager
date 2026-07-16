from __future__ import annotations

import json
import os
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from night_voyager.collaboration.models import (
    AppendMessageCommand,
    ConfirmedFactAdvisorV1,
    ConfirmedFactParticipantV1,
    FactKey,
    MemoryCandidateAdvisorV1,
    MemoryCandidateParticipantV1,
    ProposeMemoryCandidateCommand,
    RiskToleranceProposal,
    VerificationDecision,
    VerifyMemoryCandidateCommand,
)
from night_voyager.collaboration.postgres import PostgresCollaborationRepository
from night_voyager.identity.models import ActorContext, ActorRole
from night_voyager.planning.fixtures import validate_planning_fixture

pytestmark = pytest.mark.database

ORG_ID = UUID("10000000-0000-0000-0000-000000000001")
CASE_ID = UUID("40000000-0000-0000-0000-000000000310")
THREAD_ID = UUID("90000000-0000-0000-0000-000000000310")
MESSAGE_ID = UUID("91000000-0000-0000-0000-000000000310")
CANDIDATE_ID = UUID("92000000-0000-0000-0000-000000000310")
VERIFICATION_ID = UUID("93000000-0000-0000-0000-000000000310")
FACT_ID = UUID("94000000-0000-0000-0000-000000000310")
ADVISOR_ID = UUID("20000000-0000-0000-0000-000000000001")
STUDENT_ID = UUID("20000000-0000-0000-0000-000000000002")
PARENT_ID = UUID("20000000-0000-0000-0000-000000000003")
SESSION_ID = UUID("30000000-0000-0000-0000-000000000001")

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
                        "membership": UUID(
                            f"35000000-0000-0000-0000-{index:012d}"
                        ),
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
                    "case": CASE_ID,
                    "advisor": ADVISOR_ID,
                    "student": STUDENT_ID,
                    "parent": PARENT_ID,
                },
            )
    finally:
        await engine.dispose()


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
                participant_candidates = await adapter.list_candidates(
                    parent, CASE_ID, 50
                )
                assert all(
                    type(item) is MemoryCandidateParticipantV1
                    for item in participant_candidates
                )

                advisor_candidate_rows = await raw_projections(
                    session, "read_memory_candidates", advisor
                )
                assert set(advisor_candidate_rows[0]) == ADVISOR_CANDIDATE_KEYS
                advisor_candidates = await adapter.list_candidates(advisor, CASE_ID, 50)
                assert all(
                    type(item) is MemoryCandidateAdvisorV1
                    for item in advisor_candidates
                )
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

                advisor_fact_rows = await raw_projections(
                    session, "read_confirmed_facts", advisor
                )
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
                participant_facts = await adapter.list_confirmed_facts(
                    parent, CASE_ID, 50
                )
                assert all(
                    type(item) is ConfirmedFactParticipantV1
                    for item in participant_facts
                )
            finally:
                if transaction.is_active:
                    await transaction.rollback()
    finally:
        await engine.dispose()
