from datetime import date
from uuid import UUID

import pytest

from night_voyager.decision.application import DecisionService
from night_voyager.decision.models import ReviewAction, ReviewCommand
from night_voyager.identity.models import ActorContext, ActorRole

ORG = UUID("10000000-0000-0000-0000-000000000001")
ACTOR = UUID("20000000-0000-0000-0000-000000000001")
CASE = UUID("40000000-0000-0000-0000-000000000001")
RUN = UUID("70000000-0000-0000-0000-000000000001")


class Repository:
    received: object | None = None

    async def review(
        self, context: ActorContext, command: ReviewCommand, idempotency_key: str
    ) -> dict[str, object]:
        self.received = (context, command, idempotency_key)
        return {"review_id": str(command.review_id), "case_state": "planning", "replayed": False}


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
        family_safe_projection=None,
        source_snapshot_date=date(2026, 7, 1),
    )

    result = await DecisionService(repository).review(context, command, "opaque-key")

    assert result["case_state"] == "planning"
    assert repository.received == (context, command, "opaque-key")
