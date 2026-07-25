from __future__ import annotations

from typing import Protocol
from uuid import UUID

from night_voyager.dra.live_evaluation import DraLiveOutcomeProjectionV1
from night_voyager.dra.live_models import derive_identity_hash
from night_voyager.dra.models import FrozenModel, Sha256
from night_voyager.identity.models import ActorContext, ActorRole


class DraLiveOutcomeIntentV1(FrozenModel):
    intent_sha256: Sha256
    organization_id: UUID
    candidate_id: UUID
    advisor_actor_identity_sha256: Sha256
    tenant_identity_sha256: Sha256

    def validate_context(self, context: ActorContext) -> None:
        if (
            context.role is not ActorRole.ADVISOR
            or context.organization_id != self.organization_id
            or derive_identity_hash("actor", str(context.actor_id))
            != self.advisor_actor_identity_sha256
            or derive_identity_hash("tenant", str(context.organization_id))
            != self.tenant_identity_sha256
        ):
            raise ValueError("dra_live_outcome_actor_invalid")


class LiveOutcomeInspector(Protocol):
    async def inspect(
        self,
        context: ActorContext,
        intent: DraLiveOutcomeIntentV1,
    ) -> DraLiveOutcomeProjectionV1: ...
