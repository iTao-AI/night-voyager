from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from night_voyager.collaboration.hashing import canonical_sha256
from night_voyager.collaboration.models import (
    AppendMessageCommand,
    FactKey,
    JapanRiskAcceptedProposal,
    ProposeMemoryCandidateCommand,
    RiskToleranceProposal,
    VerificationDecision,
    VerifyMemoryCandidateCommand,
)
from night_voyager.planning.fixtures import validate_planning_fixture

pytestmark = pytest.mark.database

ORG_ID = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR_ID = UUID("20000000-0000-0000-0000-000000000001")
STUDENT_ID = UUID("20000000-0000-0000-0000-000000000002")
PARENT_ID = UUID("20000000-0000-0000-0000-000000000003")
PACK_ID = UUID("50000000-0000-0000-0000-000000000521")
RUN_ID = UUID("70000000-0000-0000-0000-000000000522")
VERIFY_SIGNATURE = (
    "app.verify_memory_candidate(uuid,uuid,uuid,integer,text,text,uuid,uuid,text,text)"
)

CASE_TABLE_PREDICATES = (
    ("student_cases", "id"),
    ("student_case_revisions", "case_id"),
    ("planning_runs", "case_id"),
    ("collaboration_threads", "case_id"),
    ("message_events", "case_id"),
    ("memory_candidates", "case_id"),
    ("memory_candidate_verifications", "case_id"),
    ("confirmed_facts", "case_id"),
    ("case_revision_confirmed_fact_refs", "case_id"),
    ("audit_events", "case_id"),
)
IDEMPOTENCY_WRITE_PATTERN = (
    r"VALUES\(p_org,p_actor,'memory_candidate_verify',p_key_sha256,"
    r"p_request_sha256,'memory_candidate_verification',p_verification,"
    r"clock_timestamp\(\)\);"
)


@dataclass(frozen=True)
class RuntimeFixture:
    case_id: UUID
    thread_id: UUID
    initial_message_id: UUID
    initial_candidate_id: UUID
    initial_verification_id: UUID
    initial_fact_id: UUID
    target_message_id: UUID
    target_candidate_id: UUID
    planning: bool


INTAKE_FIXTURE = RuntimeFixture(
    case_id=UUID("40000000-0000-0000-0000-000000000521"),
    thread_id=UUID("42000000-0000-0000-0000-000000000521"),
    initial_message_id=UUID("43000000-0000-0000-0000-000000000521"),
    initial_candidate_id=UUID("45000000-0000-0000-0000-000000000521"),
    initial_verification_id=UUID("46000000-0000-0000-0000-000000000521"),
    initial_fact_id=UUID("47000000-0000-0000-0000-000000000521"),
    target_message_id=UUID("43000000-0000-0000-0000-000000000523"),
    target_candidate_id=UUID("45000000-0000-0000-0000-000000000523"),
    planning=False,
)
PLANNING_FIXTURE = RuntimeFixture(
    case_id=UUID("40000000-0000-0000-0000-000000000522"),
    thread_id=UUID("42000000-0000-0000-0000-000000000522"),
    initial_message_id=UUID("43000000-0000-0000-0000-000000000522"),
    initial_candidate_id=UUID("45000000-0000-0000-0000-000000000522"),
    initial_verification_id=UUID("46000000-0000-0000-0000-000000000522"),
    initial_fact_id=UUID("47000000-0000-0000-0000-000000000522"),
    target_message_id=UUID("43000000-0000-0000-0000-000000000524"),
    target_candidate_id=UUID("45000000-0000-0000-0000-000000000524"),
    planning=True,
)


@dataclass(frozen=True)
class RollbackBoundary:
    name: str
    decision: VerificationDecision
    pattern: str
    fixture: RuntimeFixture = INTAKE_FIXTURE
    occurrence: int = 0
    expected_matches: int = 1


ROLLBACK_BOUNDARIES = (
    RollbackBoundary(
        name="confirm_verification",
        decision=VerificationDecision.CONFIRM,
        pattern=(
            r"VALUES\(p_org,p_verification,p_candidate,resolved_case,p_actor,"
            r"'advisor','confirm',p_reason,p_request_sha256,p_fact,next_revision\);"
        ),
    ),
    RollbackBoundary(
        name="confirm_fact",
        decision=VerificationDecision.CONFIRM,
        pattern=r"p_actor,'advisor',prior_fact\.id,next_fact_version\s*\);",
    ),
    RollbackBoundary(
        name="confirm_revision",
        decision=VerificationDecision.CONFIRM,
        pattern=(r"VALUES\(p_org,resolved_case,next_revision,1,next_student,next_family\);"),
    ),
    RollbackBoundary(
        name="confirm_existing_fact_refs",
        decision=VerificationDecision.CONFIRM,
        pattern=(
            r"INSERT INTO app\.case_revision_confirmed_fact_refs\(\s*"
            r"organization_id,case_id,case_revision,fact_key,confirmed_fact_id\s*"
            r"\)\s*SELECT.*?successor\.supersedes_fact_id=fact\.id\s*\);"
        ),
    ),
    RollbackBoundary(
        name="confirm_new_fact_ref",
        decision=VerificationDecision.CONFIRM,
        pattern=(r"VALUES\(p_org,resolved_case,next_revision,candidate\.fact_key,p_fact\);"),
    ),
    RollbackBoundary(
        name="confirm_case_cas",
        decision=VerificationDecision.CONFIRM,
        pattern=(
            r"IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV003', "
            r"MESSAGE='Case revision compare-and-swap failed'; END IF;"
        ),
    ),
    RollbackBoundary(
        name="confirm_planning_run_currentness",
        decision=VerificationDecision.CONFIRM,
        pattern=(
            r"IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV003', "
            r"MESSAGE='PlanningRun currentness changed'; END IF;"
        ),
        fixture=PLANNING_FIXTURE,
    ),
    RollbackBoundary(
        name="confirm_audit",
        decision=VerificationDecision.CONFIRM,
        pattern=(
            r"VALUES\(p_org,gen_random_uuid\(\),resolved_case,p_actor,"
            r"'memory_candidate_confirmed',p_verification,"
            r"jsonb_build_object\('fact_id',p_fact,'revision',next_revision\),"
            r"clock_timestamp\(\)\);"
        ),
    ),
    RollbackBoundary(
        name="confirm_idempotency",
        decision=VerificationDecision.CONFIRM,
        pattern=IDEMPOTENCY_WRITE_PATTERN,
        occurrence=1,
        expected_matches=2,
    ),
    RollbackBoundary(
        name="reject_verification",
        decision=VerificationDecision.REJECT,
        pattern=(
            r"VALUES\(p_org,p_verification,p_candidate,resolved_case,p_actor,"
            r"'advisor','reject',p_reason,p_request_sha256,NULL,NULL\);"
        ),
    ),
    RollbackBoundary(
        name="reject_audit",
        decision=VerificationDecision.REJECT,
        pattern=(
            r"VALUES\(p_org,gen_random_uuid\(\),resolved_case,p_actor,"
            r"'memory_candidate_rejected',p_verification,"
            r"jsonb_build_object\('candidate_id',p_candidate\),clock_timestamp\(\)\);"
        ),
    ),
    RollbackBoundary(
        name="reject_idempotency",
        decision=VerificationDecision.REJECT,
        pattern=IDEMPOTENCY_WRITE_PATTERN,
        occurrence=0,
        expected_matches=2,
    ),
)


def _key_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def _set_context(
    connection: AsyncConnection,
    actor_id: UUID,
    role: str,
) -> None:
    for name, value in (
        ("organization_id", ORG_ID),
        ("actor_id", actor_id),
        ("role", role),
    ):
        await connection.execute(
            text("SELECT set_config(:name,:value,true)"),
            {"name": f"night_voyager.{name}", "value": str(value)},
        )


async def _ensure_case_graph(connection: AsyncConnection, fixture: RuntimeFixture) -> None:
    await _set_context(connection, ADVISOR_ID, "advisor")
    await connection.execute(
        text(
            "INSERT INTO app.organizations(id,name,is_synthetic) "
            "VALUES(:org,'Synthetic collaboration rollback proof',true) "
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
                "INSERT INTO app.actors(id,organization_id,display_name,is_synthetic) "
                "VALUES(:actor,:org,:display_name,true) ON CONFLICT (id) DO NOTHING"
            ),
            {
                "actor": actor_id,
                "org": ORG_ID,
                "display_name": f"Synthetic rollback {role}",
            },
        )
        await connection.execute(
            text(
                "INSERT INTO app.memberships(id,organization_id,actor_id,role) "
                "VALUES(:membership,:org,:actor,:role) "
                "ON CONFLICT (organization_id,actor_id,role) DO NOTHING"
            ),
            {
                "membership": UUID(f"35000000-0000-0000-0000-{5210 + offset:012d}"),
                "org": ORG_ID,
                "actor": actor_id,
                "role": role,
            },
        )

    case_exists = await connection.scalar(
        text(
            "SELECT EXISTS(SELECT 1 FROM app.student_cases WHERE organization_id=:org AND id=:case)"
        ),
        {"org": ORG_ID, "case": fixture.case_id},
    )
    if not case_exists:
        planning_case = validate_planning_fixture().planning_input.case
        await connection.execute(
            text(
                "SELECT app.publish_case_revision("
                ":org,:case,NULL,1,CAST(:student AS jsonb),CAST(:family AS jsonb))"
            ),
            {
                "org": ORG_ID,
                "case": fixture.case_id,
                "student": json.dumps(planning_case.student.model_dump(mode="json")),
                "family": json.dumps(planning_case.family.model_dump(mode="json")),
            },
        )
    await connection.execute(
        text("SELECT app.seed_case_participants(:org,:case,:advisor,:student,:parent)"),
        {
            "org": ORG_ID,
            "case": fixture.case_id,
            "advisor": ADVISOR_ID,
            "student": STUDENT_ID,
            "parent": PARENT_ID,
        },
    )


async def _seed_runtime_authority(
    connection: AsyncConnection,
    fixture: RuntimeFixture,
) -> None:
    create_request = canonical_sha256({"schema_version": 1, "case_id": str(fixture.case_id)})
    await _set_context(connection, ADVISOR_ID, "advisor")
    await connection.execute(
        text(
            "SELECT * FROM app.create_collaboration_thread("
            ":org,:actor,'advisor',:case,:thread,:request_hash,:key_hash)"
        ),
        {
            "org": ORG_ID,
            "actor": ADVISOR_ID,
            "case": fixture.case_id,
            "thread": fixture.thread_id,
            "request_hash": create_request,
            "key_hash": _key_sha256(f"rollback-thread:{fixture.case_id}"),
        },
    )

    initial_message = AppendMessageCommand(
        thread_id=fixture.thread_id,
        body="Our family accepts the bounded Japan-risk condition.",
    )
    await _set_context(connection, PARENT_ID, "parent")
    await connection.execute(
        text(
            "SELECT * FROM app.append_collaboration_message("
            ":org,:actor,'parent',:thread,:message,:body,:content_hash,"
            ":request_hash,:key_hash)"
        ),
        {
            "org": ORG_ID,
            "actor": PARENT_ID,
            "thread": fixture.thread_id,
            "message": fixture.initial_message_id,
            "body": initial_message.body,
            "content_hash": hashlib.sha256(initial_message.body.encode("utf-8")).hexdigest(),
            "request_hash": canonical_sha256(initial_message.model_dump(mode="json")),
            "key_hash": _key_sha256(f"rollback-initial-message:{fixture.case_id}"),
        },
    )
    initial_proposal = ProposeMemoryCandidateCommand(
        message_event_id=fixture.initial_message_id,
        case_revision=1,
        proposal=JapanRiskAcceptedProposal(
            schema_version=1,
            fact_key=FactKey.FAMILY_JAPAN_RISK_ACCEPTED,
            value=True,
        ),
    )
    initial_value = initial_proposal.proposal.model_dump(mode="json")["value"]
    await connection.execute(
        text(
            "SELECT * FROM app.propose_memory_candidate("
            ":org,:actor,'parent',:message,:candidate,1,"
            "'family.japan_risk_accepted',CAST(:value AS jsonb),"
            ":value_hash,:request_hash,:key_hash)"
        ),
        {
            "org": ORG_ID,
            "actor": PARENT_ID,
            "message": fixture.initial_message_id,
            "candidate": fixture.initial_candidate_id,
            "value": json.dumps(initial_value),
            "value_hash": canonical_sha256(initial_value),
            "request_hash": canonical_sha256(initial_proposal.model_dump(mode="json")),
            "key_hash": _key_sha256(f"rollback-initial-proposal:{fixture.case_id}"),
        },
    )

    initial_verification = VerifyMemoryCandidateCommand(
        candidate_id=fixture.initial_candidate_id,
        expected_case_revision=1,
        decision=VerificationDecision.CONFIRM,
        reason="The participant explicitly confirmed this bounded preference.",
    )
    await _set_context(connection, ADVISOR_ID, "advisor")
    result = (
        (
            await connection.execute(
                text(
                    "SELECT * FROM app.verify_memory_candidate("
                    ":org,:actor,:candidate,1,'confirm',:reason,:verification,:fact,"
                    ":request_hash,:key_hash)"
                ),
                {
                    "org": ORG_ID,
                    "actor": ADVISOR_ID,
                    "candidate": fixture.initial_candidate_id,
                    "reason": initial_verification.reason,
                    "verification": fixture.initial_verification_id,
                    "fact": fixture.initial_fact_id,
                    "request_hash": canonical_sha256(initial_verification.model_dump(mode="json")),
                    "key_hash": _key_sha256(f"rollback-initial-verification:{fixture.case_id}"),
                },
            )
        )
        .mappings()
        .one()
    )
    assert result["result_revision"] == 2
    assert result["result_fact_id"] == fixture.initial_fact_id

    target_message = AppendMessageCommand(
        thread_id=fixture.thread_id,
        body="Our family now proposes a high but bounded risk tolerance.",
    )
    await _set_context(connection, PARENT_ID, "parent")
    await connection.execute(
        text(
            "SELECT * FROM app.append_collaboration_message("
            ":org,:actor,'parent',:thread,:message,:body,:content_hash,"
            ":request_hash,:key_hash)"
        ),
        {
            "org": ORG_ID,
            "actor": PARENT_ID,
            "thread": fixture.thread_id,
            "message": fixture.target_message_id,
            "body": target_message.body,
            "content_hash": hashlib.sha256(target_message.body.encode("utf-8")).hexdigest(),
            "request_hash": canonical_sha256(target_message.model_dump(mode="json")),
            "key_hash": _key_sha256(f"rollback-target-message:{fixture.case_id}"),
        },
    )
    target_proposal = ProposeMemoryCandidateCommand(
        message_event_id=fixture.target_message_id,
        case_revision=2,
        proposal=RiskToleranceProposal(
            schema_version=1,
            fact_key=FactKey.FAMILY_RISK_TOLERANCE,
            value="high",
        ),
    )
    target_value = target_proposal.proposal.model_dump(mode="json")["value"]
    await connection.execute(
        text(
            "SELECT * FROM app.propose_memory_candidate("
            ":org,:actor,'parent',:message,:candidate,2,"
            "'family.risk_tolerance',CAST(:value AS jsonb),"
            ":value_hash,:request_hash,:key_hash)"
        ),
        {
            "org": ORG_ID,
            "actor": PARENT_ID,
            "message": fixture.target_message_id,
            "candidate": fixture.target_candidate_id,
            "value": json.dumps(target_value),
            "value_hash": canonical_sha256(target_value),
            "request_hash": canonical_sha256(target_proposal.model_dump(mode="json")),
            "key_hash": _key_sha256(f"rollback-target-proposal:{fixture.case_id}"),
        },
    )


async def _ensure_runtime_fixture(fixture: RuntimeFixture) -> None:
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with migrator.begin() as connection:
            await _ensure_case_graph(connection, fixture)
        async with api.begin() as connection:
            await _seed_runtime_authority(connection, fixture)
        if fixture.planning:
            async with migrator.begin() as connection:
                await _set_context(connection, ADVISOR_ID, "advisor")
                state = await connection.scalar(
                    text(
                        "SELECT state FROM app.student_cases "
                        "WHERE organization_id=:org AND id=:case"
                    ),
                    {"org": ORG_ID, "case": fixture.case_id},
                )
                if state == "intake":
                    await connection.execute(
                        text("SELECT app.transition_case(:org,:case,'intake','planning')"),
                        {"org": ORG_ID, "case": fixture.case_id},
                    )
                await connection.execute(
                    text(
                        "INSERT INTO app.source_packs("
                        "organization_id,id,version,schema_version,manifest_sha256) "
                        "VALUES(:org,:pack,1,1,repeat('5',64)) "
                        "ON CONFLICT (organization_id,id,version) DO NOTHING"
                    ),
                    {"org": ORG_ID, "pack": PACK_ID},
                )
                await connection.execute(
                    text(
                        "INSERT INTO app.planning_runs("
                        "organization_id,id,case_id,case_revision,source_pack_id,"
                        "source_pack_version,policy_version,evidence_projection_sha256,"
                        "state,is_current) VALUES("
                        ":org,:run,:case,2,:pack,1,'m3a-policy-v1',repeat('6',64),"
                        "'synthesizing',true) ON CONFLICT (organization_id,id) DO NOTHING"
                    ),
                    {
                        "org": ORG_ID,
                        "run": RUN_ID,
                        "case": fixture.case_id,
                        "pack": PACK_ID,
                    },
                )
    finally:
        await api.dispose()
        await migrator.dispose()


async def _function_definition(engine: AsyncEngine) -> str:
    async with engine.begin() as connection:
        definition = await connection.scalar(
            text("SELECT pg_get_functiondef(to_regprocedure(:signature))"),
            {"signature": VERIFY_SIGNATURE},
        )
    assert isinstance(definition, str)
    return definition


async def _install_function(engine: AsyncEngine, definition: str) -> None:
    async with engine.begin() as connection:
        await connection.exec_driver_sql(definition)


def _inject_failure(definition: str, boundary: RollbackBoundary) -> str:
    matches = tuple(re.finditer(boundary.pattern, definition, flags=re.DOTALL))
    assert len(matches) == boundary.expected_matches
    assert 0 <= boundary.occurrence < len(matches)
    selected = matches[boundary.occurrence]
    injected = (
        "\n  RAISE EXCEPTION USING ERRCODE='NV099', "
        f"MESSAGE='injected collaboration rollback boundary {boundary.name}';"
    )
    return definition[: selected.end()] + injected + definition[selected.end() :]


async def _authority_snapshot(
    engine: AsyncEngine,
    fixture: RuntimeFixture,
) -> dict[str, tuple[object, ...]]:
    snapshot: dict[str, tuple[object, ...]] = {}
    async with engine.begin() as connection:
        await _set_context(connection, ADVISOR_ID, "advisor")
        for table, case_column in CASE_TABLE_PREDICATES:
            rows = (
                (
                    await connection.execute(
                        text(
                            f"SELECT to_jsonb(authority_row) AS row_data FROM app.{table} "
                            "AS authority_row WHERE organization_id=:org "
                            f"AND {case_column}=:case "
                            "ORDER BY to_jsonb(authority_row)::text"
                        ),
                        {"org": ORG_ID, "case": fixture.case_id},
                    )
                )
                .scalars()
                .all()
            )
            snapshot[table] = tuple(rows)
        ledgers = (
            (
                await connection.execute(
                    text(
                        "SELECT to_jsonb(ledger) AS row_data FROM app.idempotency_records "
                        "AS ledger WHERE organization_id=:org "
                        "AND actor_id IN (:advisor,:parent) AND operation IN ("
                        "'collaboration_thread_create','collaboration_message_append',"
                        "'memory_candidate_propose','memory_candidate_verify') "
                        "ORDER BY to_jsonb(ledger)::text"
                    ),
                    {"org": ORG_ID, "advisor": ADVISOR_ID, "parent": PARENT_ID},
                )
            )
            .scalars()
            .all()
        )
        snapshot["idempotency_records"] = tuple(ledgers)
    assert set(snapshot) == {
        *(table for table, _ in CASE_TABLE_PREDICATES),
        "idempotency_records",
    }
    return snapshot


def _assert_pre_failure_authority(
    snapshot: dict[str, tuple[object, ...]],
    fixture: RuntimeFixture,
) -> None:
    assert len(snapshot["student_cases"]) == 1
    assert len(snapshot["student_case_revisions"]) == 2
    assert len(snapshot["collaboration_threads"]) == 1
    assert len(snapshot["message_events"]) == 2
    assert len(snapshot["memory_candidates"]) == 2
    assert len(snapshot["memory_candidate_verifications"]) == 1
    assert len(snapshot["confirmed_facts"]) == 1
    assert len(snapshot["case_revision_confirmed_fact_refs"]) == 1
    assert len(snapshot["audit_events"]) == 1
    assert len(snapshot["planning_runs"]) == (1 if fixture.planning else 0)


async def _invoke_injected_boundary(
    engine: AsyncEngine,
    boundary: RollbackBoundary,
) -> None:
    command = VerifyMemoryCandidateCommand(
        candidate_id=boundary.fixture.target_candidate_id,
        expected_case_revision=2,
        decision=boundary.decision,
        reason="The rollback proof keeps every authority write atomic.",
    )
    verification_id = UUID(
        f"46000000-0000-0000-0000-{5900 + ROLLBACK_BOUNDARIES.index(boundary):012d}"
    )
    fact_id = (
        UUID(f"47000000-0000-0000-0000-{5900 + ROLLBACK_BOUNDARIES.index(boundary):012d}")
        if boundary.decision is VerificationDecision.CONFIRM
        else None
    )
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await _set_context(connection, ADVISOR_ID, "advisor")
            savepoint = await connection.begin_nested()
            try:
                with pytest.raises(DBAPIError) as rejected:
                    await connection.execute(
                        text(
                            "SELECT * FROM app.verify_memory_candidate("
                            ":org,:actor,:candidate,2,:decision,:reason,"
                            ":verification,:fact,:request_hash,:key_hash)"
                        ),
                        {
                            "org": ORG_ID,
                            "actor": ADVISOR_ID,
                            "candidate": boundary.fixture.target_candidate_id,
                            "decision": boundary.decision.value,
                            "reason": command.reason,
                            "verification": verification_id,
                            "fact": fact_id,
                            "request_hash": canonical_sha256(command.model_dump(mode="json")),
                            "key_hash": _key_sha256(f"rollback-boundary:{boundary.name}"),
                        },
                    )
                assert getattr(rejected.value.orig, "sqlstate", None) == "NV099"
            finally:
                if savepoint.is_active:
                    await savepoint.rollback()
        finally:
            if transaction.is_active:
                await transaction.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "boundary",
    ROLLBACK_BOUNDARIES,
    ids=[boundary.name for boundary in ROLLBACK_BOUNDARIES],
)
async def test_verification_rolls_back_the_full_authority_snapshot_after_each_write(
    boundary: RollbackBoundary,
) -> None:
    await _ensure_runtime_fixture(boundary.fixture)
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        original_definition = await _function_definition(migrator)
        baseline = await _authority_snapshot(migrator, boundary.fixture)
        _assert_pre_failure_authority(baseline, boundary.fixture)
        injected_definition = _inject_failure(original_definition, boundary)
        try:
            await _install_function(migrator, injected_definition)
            await _invoke_injected_boundary(api, boundary)
        finally:
            await _install_function(migrator, original_definition)
        assert await _function_definition(migrator) == original_definition
        assert await _authority_snapshot(migrator, boundary.fixture) == baseline
    finally:
        await api.dispose()
        await migrator.dispose()
