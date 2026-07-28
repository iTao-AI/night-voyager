from __future__ import annotations

from typing import Protocol
from uuid import UUID

from night_voyager.connected_demo.fixtures import CanonicalDemoSourceContract
from night_voyager.connected_demo.models import (
    AdvisorLedgerV1,
    AdvisorLedgerV2,
    ConnectedJourneyStatusV1,
    CurrentDecisionBriefV1,
    CurrentDecisionBriefV2,
)
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

    async def advisor_ledger_v2(
        self,
        context: ActorContext,
        case_id: UUID,
        source: CanonicalDemoSourceContract,
    ) -> AdvisorLedgerV2 | None: ...

    async def current_decision_brief_v2(
        self, context: ActorContext, case_id: UUID
    ) -> CurrentDecisionBriefV2 | None: ...

    async def journey_status(
        self, context: ActorContext, case_id: UUID
    ) -> ConnectedJourneyStatusV1 | None: ...
