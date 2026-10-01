from __future__ import annotations

from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest

from night_voyager.collaboration.policy import role_allows_fact
from night_voyager.connected_demo.models import DemoPhaseV2
from night_voyager.connected_demo.postgres import PostgresConnectedDemoRepository
from night_voyager.identity.models import ActorContext, ActorRole


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "expected"),
    ((ActorRole.PARENT, "parent"), (ActorRole.STUDENT, "student"), (ActorRole.ADVISOR, "student")),
)
async def test_requested_revision_projects_verified_participant_role(role, expected):
    context = ActorContext(
        organization_id=UUID("10000000-0000-0000-0000-000000000001"),
        actor_id=UUID("20000000-0000-0000-0000-000000000003"),
        role=role,
        session_id=UUID("30000000-0000-0000-0000-000000000003"),
    )
    row = {
        "role": role.value,
        "state": "review_required",
        "current_revision": 1,
        "brief_id": None,
        "decision_id": None,
        "revision_requested": True,
        "revision_fact_pending": False,
        "revision_predecessor_run_id": None,
        "task_id": None,
        "result_planning_run_id": None,
        "task_predecessor_run_id": None,
        "run_supersedes_run_id": None,
        "run_is_current": True,
        "run_state": "review_required",
    }
    result = Mock()
    result.mappings.return_value.one_or_none.return_value = row
    session = Mock(execute=AsyncMock(return_value=result))
    projection = await PostgresConnectedDemoRepository(session).journey_status(
        context, UUID("40000000-0000-0000-0000-000000000002")
    )
    assert projection is not None
    assert projection.phase is DemoPhaseV2.REVISION_REQUESTED
    assert projection.active_role == expected


@pytest.mark.parametrize(
    "phase", tuple(phase for phase in DemoPhaseV2 if phase is not DemoPhaseV2.REVISION_REQUESTED)
)
def test_parent_projection_does_not_change_other_phase_authority(phase):
    expected = (
        "parent" if phase in {DemoPhaseV2.FAMILY_REVIEW, DemoPhaseV2.PLAN_READY} else "advisor"
    )
    assert PostgresConnectedDemoRepository._journey_active_role(phase, "parent") == expected


def test_budget_and_country_proposal_permissions_remain_separate():
    assert role_allows_fact(ActorRole.PARENT, "family.budget")
    assert not role_allows_fact(ActorRole.STUDENT, "family.budget")
    assert role_allows_fact(ActorRole.STUDENT, "student.preferred_countries")
    assert not role_allows_fact(ActorRole.PARENT, "student.preferred_countries")
