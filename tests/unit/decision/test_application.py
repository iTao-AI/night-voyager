from datetime import date
from typing import cast
from uuid import UUID

import pytest

from night_voyager.decision.application import DecisionService
from night_voyager.decision.models import (
    BriefRoute,
    DecisionBriefProjection,
    DecisionSource,
    FamilyDecisionCommand,
    ReviewAction,
    ReviewCommand,
    TimelinePlan,
)
from night_voyager.identity.models import ActorContext, ActorRole
from night_voyager.planning.models import Country, RouteOutcome

ORG = UUID("10000000-0000-0000-0000-000000000001")
ACTOR = UUID("20000000-0000-0000-0000-000000000001")
CASE = UUID("40000000-0000-0000-0000-000000000001")
RUN = UUID("70000000-0000-0000-0000-000000000001")


class Repository:
    received: object | None = None
    brief_record: dict[str, object] | None = None

    async def review(
        self, context: ActorContext, command: ReviewCommand, idempotency_key: str
    ) -> dict[str, object]:
        self.received = (context, command, idempotency_key)
        return {"review_id": str(command.review_id), "case_state": "planning", "replayed": False}

    async def get_brief(self, context: ActorContext, brief_id: UUID) -> dict[str, object] | None:
        self.received = (context, brief_id)
        return self.brief_record or {"brief_id": str(brief_id)}

    async def decide(
        self,
        context: ActorContext,
        command: FamilyDecisionCommand,
        *,
        decision_id: UUID,
        receipt_id: UUID,
        timeline_id: UUID,
        timeline: TimelinePlan,
        idempotency_key: str,
    ) -> dict[str, object]:
        self.received = (context, command, timeline, idempotency_key)
        return {"decision_id": decision_id, "receipt_id": receipt_id, "timeline_id": timeline_id}


@pytest.mark.asyncio
async def test_service_passes_trusted_actor_context_to_repository() -> None:
    repository = Repository()
    context = ActorContext(ORG, ACTOR, ActorRole.ADVISOR, UUID(int=9))
    command = ReviewCommand(
        schema_version=1,
        case_id=CASE,
        planning_run_id=RUN,
        expected_case_revision=1,
        action=ReviewAction.REQUEST_REVISION,
        review_id=UUID(int=10),
        eligible_route_ids=(),
        risk_acceptances=(),
        reviewer_notes="refresh optional evidence",
        brief_id=None,
    )

    result = await DecisionService(repository).review(context, command, "opaque-key")

    assert result["case_state"] == "planning"
    assert repository.received == (context, command, "opaque-key")


@pytest.mark.asyncio
async def test_service_owns_brief_read_runtime_seam() -> None:
    repository = Repository()
    context = ActorContext(ORG, ACTOR, ActorRole.ADVISOR, UUID(int=9))
    result = await DecisionService(repository).get_brief(context, UUID(int=20))
    assert result == {"brief_id": str(UUID(int=20))}


@pytest.mark.asyncio
async def test_service_owns_typed_direct_decision_and_timeline_seam() -> None:
    repository = Repository()
    brief = UUID(int=20)
    route = UUID(int=21)

    repository.brief_record = {
        "id": brief,
        "brief_version": 1,
        "source_snapshot_date": date(2026, 7, 1),
        "family_safe_projection": DecisionBriefProjection(
            schema_version=1,
            intake="2027-02",
            routes=(
                BriefRoute(
                    route_id=route,
                    country=Country.AUSTRALIA,
                    outcome=RouteOutcome.RECOMMENDED_WITH_CONDITION,
                    reason_code="complete_cost_and_fx_within_boundary",
                ),
            ),
            eligible_route_ids=(route,),
            accepted_evidence_risks=(),
            synthetic_proof=True,
        ).model_dump(mode="json"),
        "_hard_ceiling": 40_000_000,
        "_australia_cost": 30_550_000,
    }
    context = ActorContext(ORG, ACTOR, ActorRole.PARENT, UUID(int=9))
    command = FamilyDecisionCommand(
        schema_version=1,
        brief_id=brief,
        expected_brief_version=1,
        selected_route_id=route,
        accepted_budget_min_minor=30_000_000,
        accepted_budget_max_minor=40_000_000,
        currency="CNY",
        accepted_trade_offs=("budget_elasticity",),
        decision_made_by_actor_id=ACTOR,
        source=DecisionSource.DIRECT,
    )
    result = await DecisionService(repository).decide_direct(context, command, "decision-key")
    assert result["receipt_id"] is not None
    received = repository.received
    assert isinstance(received, tuple)
    timeline = cast(TimelinePlan, received[2])
    assert isinstance(timeline, TimelinePlan)
    assert timeline.milestones[0].due_date == date(2026, 9, 1)
