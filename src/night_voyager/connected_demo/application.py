from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from night_voyager.connected_demo.fixtures import (
    CanonicalDemoSourceContract,
    resolve_canonical_demo_source_contract,
)
from night_voyager.connected_demo.models import AdvisorLedgerV1, CurrentDecisionBriefV1
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
        self, context: ActorContext, case_id: UUID
    ) -> AdvisorLedgerV1 | None:
        return await self._repository.advisor_ledger(
            context, case_id, self._source_resolver()
        )

    async def current_decision_brief(
        self, context: ActorContext, case_id: UUID
    ) -> CurrentDecisionBriefV1 | None:
        return await self._repository.current_decision_brief(context, case_id)
