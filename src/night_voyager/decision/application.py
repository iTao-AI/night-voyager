from __future__ import annotations

from night_voyager.decision.models import ReviewCommand
from night_voyager.decision.ports import DecisionRepository
from night_voyager.identity.models import ActorContext


class DecisionService:
    def __init__(self, repository: DecisionRepository) -> None:
        self._repository = repository

    async def review(
        self, context: ActorContext, command: ReviewCommand, idempotency_key: str
    ) -> dict[str, object]:
        return await self._repository.review(context, command, idempotency_key)
