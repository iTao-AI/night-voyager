from __future__ import annotations

from typing import Protocol
from uuid import UUID

from night_voyager.decision.models import FamilyDecisionCommand, ReviewCommand, TimelinePlan
from night_voyager.identity.models import ActorContext


class DecisionRepository(Protocol):
    async def review(
        self, context: ActorContext, command: ReviewCommand, idempotency_key: str
    ) -> dict[str, object]: ...

    async def get_brief(
        self, context: ActorContext, brief_id: UUID
    ) -> dict[str, object] | None: ...

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
    ) -> dict[str, object]: ...
