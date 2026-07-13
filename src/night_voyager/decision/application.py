from __future__ import annotations

from datetime import date
from typing import cast
from uuid import UUID, uuid4

from night_voyager.decision.models import (
    DecisionBriefProjection,
    DecisionSource,
    FamilyDecisionCommand,
    ReviewCommand,
)
from night_voyager.decision.policy import build_timeline_plan, validate_family_decision
from night_voyager.decision.ports import DecisionRepository
from night_voyager.identity.models import ActorContext, ActorRole


class DecisionService:
    def __init__(self, repository: DecisionRepository) -> None:
        self._repository = repository

    async def review(
        self, context: ActorContext, command: ReviewCommand, idempotency_key: str
    ) -> dict[str, object]:
        return await self._repository.review(context, command, idempotency_key)

    async def get_brief(self, context: ActorContext, brief_id: UUID) -> dict[str, object] | None:
        result = await self._repository.get_brief(context, brief_id)
        if result is None:
            return None
        return {key: value for key, value in result.items() if not key.startswith("_")}

    async def decide_direct(
        self,
        context: ActorContext,
        command: FamilyDecisionCommand,
        idempotency_key: str,
    ) -> dict[str, object]:
        if context.role not in {ActorRole.STUDENT, ActorRole.PARENT}:
            raise ValueError("direct decision requires assigned family role")
        if (
            command.source is not DecisionSource.DIRECT
            or command.decision_made_by_actor_id != context.actor_id
        ):
            raise ValueError("direct decision actor mismatch")
        return await self._decide(context, command, idempotency_key)

    async def decide_as_advisor(
        self,
        context: ActorContext,
        command: FamilyDecisionCommand,
        idempotency_key: str,
    ) -> dict[str, object]:
        if (
            context.role is not ActorRole.ADVISOR
            or command.source is not DecisionSource.FAMILY_CONSULTATION
        ):
            raise ValueError("advisor-recorded decision requires family consultation")
        return await self._decide(context, command, idempotency_key)

    async def _decide(
        self,
        context: ActorContext,
        command: FamilyDecisionCommand,
        idempotency_key: str,
    ) -> dict[str, object]:
        record = await self._repository.get_brief(context, command.brief_id)
        if record is None:
            raise LookupError("decision brief unavailable")
        projection = DecisionBriefProjection.model_validate(record["family_safe_projection"])
        validate_family_decision(
            command,
            projection,
            brief_id=cast(UUID, record["id"]),
            brief_version=cast(int, record["brief_version"]),
            pinned_budget_hard_ceiling_minor=cast(int, record["_hard_ceiling"]),
            pinned_australia_cost_minor=cast(int, record["_australia_cost"]),
        )
        route = next(
            item for item in projection.routes if item.route_id == command.selected_route_id
        )
        snapshot = cast(date, record["source_snapshot_date"])
        timeline = build_timeline_plan(route.country, projection.intake, snapshot)
        return await self._repository.decide(
            context,
            command,
            decision_id=uuid4(),
            receipt_id=uuid4(),
            timeline_id=uuid4(),
            timeline=timeline,
            idempotency_key=idempotency_key,
        )
