from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID

import pytest

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
