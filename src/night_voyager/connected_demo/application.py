from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from night_voyager.connected_demo.fixtures import (
    CanonicalDemoSourceContract,
    resolve_canonical_demo_source_contract,
)
from night_voyager.connected_demo.models import (
    AdvisorLedgerV1,
    AdvisorLedgerV2,
    ConnectedJourneyStatusV1,
    CurrentDecisionBriefV1,
    CurrentDecisionBriefV2,
)
from night_voyager.connected_demo.ports import ConnectedDemoRepository
from night_voyager.identity.models import ActorContext


class ConnectedDemoService:
    def __init__(
        self,
        repository: ConnectedDemoRepository,
        *,
        source_resolver: Callable[[], CanonicalDemoSourceContract] = (
            resolve_canonical_demo_source_contract
        ),
    ) -> None:
        self._repository = repository
        self._source_resolver = source_resolver

    async def advisor_ledger(
        self, context: ActorContext, case_id: UUID, *, contract_version: int = 1
    ) -> AdvisorLedgerV1 | AdvisorLedgerV2 | None:
        if contract_version == 2:
            return await self._repository.advisor_ledger_v2(
                context, case_id, self._source_resolver()
            )
        if contract_version != 1:
            raise ValueError("connected_demo_contract_version_invalid")
        return await self._repository.advisor_ledger(
            context, case_id, self._source_resolver()
        )

    async def current_decision_brief(
        self, context: ActorContext, case_id: UUID, *, contract_version: int = 1
    ) -> CurrentDecisionBriefV1 | CurrentDecisionBriefV2 | None:
        if contract_version == 2:
            return await self._repository.current_decision_brief_v2(context, case_id)
        if contract_version != 1:
            raise ValueError("connected_demo_contract_version_invalid")
        return await self._repository.current_decision_brief(context, case_id)

    async def journey_status(
        self, context: ActorContext, case_id: UUID
    ) -> ConnectedJourneyStatusV1 | None:
        return await self._repository.journey_status(context, case_id)
