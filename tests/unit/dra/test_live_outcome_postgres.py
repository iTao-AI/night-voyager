from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from night_voyager.dra.fixtures import load_strict_live_closure_scenario
from night_voyager.dra.live_models import derive_identity_hash
from night_voyager.dra.live_outcome import DraLiveOutcomeIntentV1
from night_voyager.dra.live_outcome_postgres import PostgresLiveOutcomeInspector
from night_voyager.identity.models import ActorContext, ActorRole

ORG = UUID("10000000-0000-0000-0000-000000000001")
ACTOR = UUID("20000000-0000-0000-0000-000000000001")
SESSION = UUID("30000000-0000-0000-0000-000000000001")
CANDIDATE = UUID("40000000-0000-0000-0000-000000000001")


class EmptyProjection:
    def mappings(self) -> EmptyProjection:
        return self

    def one_or_none(self) -> None:
        return None


class RowProjection:
    def __init__(self, row: dict[str, object]) -> None:
        self._row = row

    def mappings(self) -> RowProjection:
        return self

    def one_or_none(self) -> dict[str, object]:
        return self._row


@pytest.mark.asyncio
async def test_outcome_inspector_sets_exact_actor_context_before_projection() -> None:
    session = AsyncMock()
    session.execute.return_value = EmptyProjection()
    context = ActorContext(
        organization_id=ORG,
        actor_id=ACTOR,
        role=ActorRole.ADVISOR,
        session_id=SESSION,
    )
    intent = DraLiveOutcomeIntentV1(
        intent_sha256="0" * 64,
        organization_id=ORG,
        candidate_id=CANDIDATE,
        advisor_actor_identity_sha256=derive_identity_hash("actor", str(ACTOR)),
        tenant_identity_sha256=derive_identity_hash("tenant", str(ORG)),
    )

    await PostgresLiveOutcomeInspector(session).inspect(context, intent)

    assert session.execute.await_count == 5
    for index, expected in enumerate(
        (
            ("night_voyager.organization_id", str(ORG)),
            ("night_voyager.actor_id", str(ACTOR)),
            ("night_voyager.role", "advisor"),
            ("night_voyager.session_id", str(SESSION)),
        )
    ):
        parameters = session.execute.await_args_list[index].args[1]
        assert (parameters["key"], parameters["value"]) == expected
    projection_parameters = session.execute.await_args_list[4].args[1]
    assert projection_parameters == {
        "org": ORG,
        "actor": ACTOR,
        "candidate": CANDIDATE,
    }


@pytest.mark.asyncio
async def test_strict_outcome_identity_is_projected_only_from_database_row() -> None:
    scenario = load_strict_live_closure_scenario()
    row: dict[str, object] = {
        "candidate_id": CANDIDATE,
        "producer_repository": scenario.producer.repository,
        "producer_ref_kind": scenario.producer.ref_kind,
        "producer_ref": scenario.producer.ref,
        "producer_release": None,
        "producer_commit": scenario.producer.commit,
        "contract_schema": scenario.producer.consumer_contract_schema,
        "fixture_sha256": scenario.producer.consumer_fixture_sha256,
        "profile_id": scenario.producer.profile_id,
        "profile_version": scenario.producer.profile_version,
        "proof_schema": scenario.producer.proof_schema,
        "request_identity_sha256": scenario.request_identity.request_sha256,
        "verification_count": 0,
        "approved_verification_count": 0,
        "verification_id": None,
        "promoted_source_pack_id": None,
        "promoted_source_pack_version": None,
        "promoted_source_entry_id": None,
        "promoted_evidence_id": None,
        "external_claim": None,
        "evidence_role": None,
        "external_authority": None,
        "governed_task_count": 0,
        "task_id": None,
        "task_state": None,
        "planning_run_id": None,
        "planning_run_state": None,
        "execution_count": 0,
        "execution_id": None,
        "execution_planning_run_id": None,
        "terminal_event_count": 0,
        "terminal_event_id": None,
        "terminal_event_planning_run_id": None,
        "sse_cursor": None,
        "skill_definition_id": None,
        "skill_version_id": None,
        "skill_activation_event_id": None,
        "skill_activation_sequence": None,
        "runtime_binding_sha256": None,
        "advisor_review_count": 0,
        "review_id": None,
        "brief_id": None,
        "family_decision_count": 0,
        "decision_id": None,
        "decision_receipt_count": 0,
        "decision_receipt_id": None,
        "timeline_plan_count": 0,
        "timeline_plan_id": None,
    }
    session = AsyncMock()
    session.execute.return_value = RowProjection(row)
    context = ActorContext(
        organization_id=ORG,
        actor_id=ACTOR,
        role=ActorRole.ADVISOR,
        session_id=SESSION,
    )
    intent = DraLiveOutcomeIntentV1(
        intent_sha256="0" * 64,
        organization_id=ORG,
        candidate_id=CANDIDATE,
        advisor_actor_identity_sha256=derive_identity_hash("actor", str(ACTOR)),
        tenant_identity_sha256=derive_identity_hash("tenant", str(ORG)),
    )

    projection = await PostgresLiveOutcomeInspector(session).inspect(
        context, intent
    )

    assert projection.durable_candidate is not None
    assert projection.durable_candidate.producer == scenario.producer
    assert (
        projection.durable_candidate.request_identity
        == scenario.request_identity
    )
    assert (
        projection.durable_candidate.observed_profile
        == scenario.profile_manifest
    )
