from __future__ import annotations

from typing import Protocol

from night_voyager.decision.models import ReviewCommand
from night_voyager.identity.models import ActorContext


class DecisionRepository(Protocol):
    async def review(
        self, context: ActorContext, command: ReviewCommand, idempotency_key: str
    ) -> dict[str, object]: ...
