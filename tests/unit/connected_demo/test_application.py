from __future__ import annotations

from uuid import UUID

import pytest

from night_voyager.connected_demo.application import ConnectedDemoService
from night_voyager.connected_demo.fixtures import CanonicalDemoSourceContract
from night_voyager.connected_demo.models import AdvisorLedgerV1, CurrentDecisionBriefV1
from night_voyager.identity.models import ActorContext, ActorRole


class FakeRepository:
    def __init__(self) -> None:
        self.ledger_call: tuple[ActorContext, UUID, CanonicalDemoSourceContract] | None = None
        self.brief_call: tuple[ActorContext, UUID] | None = None

    async def advisor_ledger(
        self,
        context: ActorContext,
        case_id: UUID,
        source: CanonicalDemoSourceContract,
    ) -> AdvisorLedgerV1 | None:
        self.ledger_call = (context, case_id, source)
        return None

    async def current_decision_brief(
        self, context: ActorContext, case_id: UUID
    ) -> CurrentDecisionBriefV1 | None:
        self.brief_call = (context, case_id)
        return None


@pytest.mark.asyncio
async def test_service_resolves_server_owned_source_for_advisor_ledger() -> None:
    repository = FakeRepository()
    source = CanonicalDemoSourceContract(
        source_pack_id=UUID("50000000-0000-0000-0000-000000000001"),
        source_pack_version=1,
        manifest_sha256="a" * 64,
        policy_version="m3a-policy-v1",
    )
    context = ActorContext(
        organization_id=UUID("10000000-0000-0000-0000-000000000001"),
        actor_id=UUID("20000000-0000-0000-0000-000000000001"),
        role=ActorRole.ADVISOR,
        session_id=UUID("30000000-0000-0000-0000-000000000001"),
    )
    case_id = UUID("40000000-0000-0000-0000-000000000002")
    service = ConnectedDemoService(repository, source_resolver=lambda: source)

    assert await service.advisor_ledger(context, case_id) is None
    assert repository.ledger_call == (context, case_id, source)


@pytest.mark.asyncio
async def test_service_delegates_current_brief_without_client_authority() -> None:
    repository = FakeRepository()
    context = ActorContext(
        organization_id=UUID("10000000-0000-0000-0000-000000000001"),
        actor_id=UUID("20000000-0000-0000-0000-000000000003"),
        role=ActorRole.PARENT,
        session_id=UUID("30000000-0000-0000-0000-000000000003"),
    )
    case_id = UUID("40000000-0000-0000-0000-000000000001")
    service = ConnectedDemoService(repository)

    assert await service.current_decision_brief(context, case_id) is None
    assert repository.brief_call == (context, case_id)
