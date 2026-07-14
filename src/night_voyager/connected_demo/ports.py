from __future__ import annotations

from typing import Protocol
from uuid import UUID

from night_voyager.connected_demo.fixtures import CanonicalDemoSourceContract
from night_voyager.connected_demo.models import AdvisorLedgerV1, CurrentDecisionBriefV1
from night_voyager.identity.models import ActorContext


class ConnectedDemoRepository(Protocol):
    async def advisor_ledger(
        self,
        context: ActorContext,
        case_id: UUID,
        source: CanonicalDemoSourceContract,
    ) -> AdvisorLedgerV1 | None: ...

    async def current_decision_brief(
        self, context: ActorContext, case_id: UUID
    ) -> CurrentDecisionBriefV1 | None: ...
