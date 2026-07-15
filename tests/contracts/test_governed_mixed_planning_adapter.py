from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

import pytest

from night_voyager.adapters.governed_mixed_planning import GovernedMixedPlanningAdapter
from night_voyager.adapters.protocols import (
    AdapterFailure,
    AdapterFailureCode,
    AdapterPayload,
    PlanningAdapterRequest,
)
from night_voyager.adapters.router import PlanningAdapterRouter
from night_voyager.planning.trusted import (
    GovernedMixedPlanningInput,
    GovernedMixedSnapshotV1,
)
from night_voyager.tasks.policy import AdapterPayloadError, validate_adapter_payload
from tests.unit.planning.test_mixed import governed_snapshot

ORG = UUID("10000000-0000-0000-0000-000000000001")
CASE = UUID("40000000-0000-0000-0000-000000000001")
PACK = UUID("50000000-0000-0000-0000-000000000001")


def mixed_request() -> PlanningAdapterRequest:
    return PlanningAdapterRequest(
        schema_version=1,
        operation="generate_governed_mixed_planning_run_v1",
        organization_id=ORG,
        case_id=CASE,
        case_revision=1,
        source_pack_id=PACK,
        source_pack_version=2,
        policy_version="m3a-policy-v1",
    )


class FakeSnapshotRepository:
    def __init__(self, snapshot: GovernedMixedSnapshotV1) -> None:
        self.snapshot = snapshot
        self.requests: list[PlanningAdapterRequest] = []

    async def load(self, request: PlanningAdapterRequest) -> GovernedMixedSnapshotV1:
        self.requests.append(request)
        return self.snapshot


@dataclass
class SpyAdapter:
    outcome: AdapterPayload | AdapterFailure
    calls: list[PlanningAdapterRequest] = field(default_factory=lambda: [])

    async def generate(
        self, request: PlanningAdapterRequest
    ) -> AdapterPayload | AdapterFailure:
        self.calls.append(request)
        return self.outcome


@pytest.mark.asyncio
async def test_router_selects_only_the_mixed_adapter_for_mixed_operation() -> None:
    synthetic = SpyAdapter(AdapterFailure(code=AdapterFailureCode.UNKNOWN))
    mixed = SpyAdapter(AdapterFailure(code=AdapterFailureCode.PIN_MISMATCH))
    router = PlanningAdapterRouter(synthetic=synthetic, mixed=mixed)
    request = mixed_request()
    assert await router.generate(request) == AdapterFailure(
        code=AdapterFailureCode.PIN_MISMATCH
    )
    assert mixed.calls == [request]
    assert synthetic.calls == []


@pytest.mark.asyncio
async def test_mixed_adapter_materializes_only_the_worker_snapshot() -> None:
    snapshot = governed_snapshot()
    repository = FakeSnapshotRepository(snapshot)
    request = mixed_request()
    outcome = await GovernedMixedPlanningAdapter(repository).generate(request)
    assert isinstance(outcome, AdapterPayload)
    assert (outcome.adapter_id, outcome.adapter_version) == (
        "governed_mixed_planning",
        "dra-mixed-v1",
    )
    planning_input = validate_adapter_payload(outcome, request)
    assert isinstance(planning_input, GovernedMixedPlanningInput)
    assert planning_input.operation == "generate_governed_mixed_planning_run_v1"
    assert repository.requests == [request]


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ("request", "external_hash", "case"))
async def test_mixed_adapter_rejects_pin_or_snapshot_mutation(mutation: str) -> None:
    snapshot = governed_snapshot()
    request = mixed_request()
    if mutation == "request":
        request = request.model_copy(update={"source_pack_version": 3})
    elif mutation == "external_hash":
        snapshot = snapshot.model_copy(
            update={
                "evidence": (
                    snapshot.evidence[0].model_copy(update={"source_sha256": "f" * 64}),
                    *snapshot.evidence[1:],
                )
            }
        )
    else:
        snapshot = snapshot.model_copy(
            update={
                "case": snapshot.case.model_copy(
                    update={"case_id": UUID("40000000-0000-0000-0000-000000000099")}
                )
            }
        )
    outcome = await GovernedMixedPlanningAdapter(FakeSnapshotRepository(snapshot)).generate(
        request
    )
    assert outcome == AdapterFailure(code=AdapterFailureCode.PIN_MISMATCH)


def test_adapter_payload_identity_is_an_exact_pair() -> None:
    with pytest.raises(ValueError):
        AdapterPayload(
            payload=b"{}",
            adapter_id="governed_mixed_planning",
            adapter_version="m4a-v1",
        )


def test_cross_operation_payload_fails_closed() -> None:
    synthetic_payload = AdapterPayload(payload=b'{"schema_version":1,"evidence":[]}')
    with pytest.raises(AdapterPayloadError, match="invalid_schema"):
        validate_adapter_payload(synthetic_payload, mixed_request())
