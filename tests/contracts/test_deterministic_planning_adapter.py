from __future__ import annotations

from uuid import UUID

import pytest

from night_voyager.adapters.deterministic_planning import DeterministicPlanningAdapter
from night_voyager.adapters.protocols import (
    AdapterFailure,
    AdapterFailureCode,
    AdapterPayload,
    PlanningAdapterRequest,
)
from night_voyager.planning.fixtures import validate_planning_fixture
from night_voyager.planning.models import Country, PlanningInput, PlanningResult
from night_voyager.planning.synthetic import PersistedSyntheticSnapshotV1
from night_voyager.tasks.policy import validate_adapter_payload


def adapter_request() -> PlanningAdapterRequest:
    return PlanningAdapterRequest(
        schema_version=1,
        operation="generate_planning_run_v1",
        organization_id=UUID("10000000-0000-0000-0000-000000000001"),
        case_id=UUID("40000000-0000-0000-0000-000000000010"),
        case_revision=1,
        source_pack_id=UUID("50000000-0000-0000-0000-000000000001"),
        source_pack_version=1,
        policy_version="m3a-policy-v1",
    )


def persisted_snapshot(
    request: PlanningAdapterRequest,
    *,
    countries: tuple[Country, ...] = (
        Country.AUSTRALIA,
        Country.JAPAN,
        Country.MALAYSIA,
    ),
) -> PersistedSyntheticSnapshotV1:
    baseline = validate_planning_fixture().planning_input
    case = baseline.case.model_copy(
        update={
            "organization_id": request.organization_id,
            "case_id": request.case_id,
            "revision": request.case_revision,
            "student": baseline.case.student.model_copy(
                update={"preferred_countries": countries}
            ),
        }
    )
    return PersistedSyntheticSnapshotV1(
        schema_version=1,
        organization_id=request.organization_id,
        case=case,
        source_pack_id=request.source_pack_id,
        source_pack_version=request.source_pack_version,
        policy_version=request.policy_version,
    )


class StaticSnapshotRepository:
    def __init__(self, snapshot: PersistedSyntheticSnapshotV1) -> None:
        self._snapshot = snapshot

    async def load(
        self, request: PlanningAdapterRequest
    ) -> PersistedSyntheticSnapshotV1:
        return self._snapshot


@pytest.mark.asyncio
async def test_deterministic_adapter_returns_untrusted_bytes_not_planning_authority() -> None:
    request = adapter_request()
    outcome = await DeterministicPlanningAdapter(
        StaticSnapshotRepository(persisted_snapshot(request))
    ).generate(request)
    assert isinstance(outcome, AdapterPayload)
    assert isinstance(outcome.payload, bytes)
    assert not isinstance(outcome, PlanningResult)
    planning_input = validate_adapter_payload(outcome, request)
    assert isinstance(planning_input, PlanningInput)
    assert planning_input.organization_id == request.organization_id
    assert planning_input.case.case_id == request.case_id
    assert planning_input.case.revision == request.case_revision
    assert all(
        item.authority.value == "accepted_synthetic_demo" for item in planning_input.evidence
    )
    assert "generate_governed_mixed_planning_run_v1" not in planning_input.model_dump_json()


@pytest.mark.asyncio
async def test_typed_failure_is_constructor_injected_and_has_no_request_selector() -> None:
    failure = AdapterFailure(code=AdapterFailureCode.TRANSIENT_UNAVAILABLE)
    request = adapter_request()
    outcome = await DeterministicPlanningAdapter(
        StaticSnapshotRepository(persisted_snapshot(request)),
        injected_failure=failure,
    ).generate(request)
    assert outcome == failure
    assert "failure" not in PlanningAdapterRequest.model_fields
    assert "adapter" not in PlanningAdapterRequest.model_fields


@pytest.mark.asyncio
async def test_adapter_rejects_unapproved_source_pack_pin() -> None:
    approved_request = adapter_request()
    request = approved_request.model_copy(
        update={"source_pack_id": UUID("50000000-0000-0000-0000-000000000099")}
    )
    outcome = await DeterministicPlanningAdapter(
        StaticSnapshotRepository(persisted_snapshot(approved_request))
    ).generate(request)
    assert outcome == AdapterFailure(code=AdapterFailureCode.PIN_MISMATCH)


@pytest.mark.asyncio
async def test_adapter_preserves_persisted_case_facts_over_fixture_values() -> None:
    request = adapter_request()
    snapshot = persisted_snapshot(request, countries=(Country.JAPAN,))
    baseline = validate_planning_fixture().planning_input
    persisted_budget = baseline.case.family.budget.model_copy(
        update={
            "preferred_minor": 18000000,
            "hard_ceiling_minor": 22000000,
            "elasticity_bps": 500,
        }
    )
    persisted_case = snapshot.case.model_copy(
        update={
            "student": snapshot.case.student.model_copy(update={"intake": "2028-09"}),
            "family": snapshot.case.family.model_copy(
                update={
                    "risk_tolerance": "low",
                    "japan_risk_accepted": False,
                    "budget": persisted_budget,
                }
            ),
        }
    )
    snapshot = snapshot.model_copy(update={"case": persisted_case})

    outcome = await DeterministicPlanningAdapter(
        StaticSnapshotRepository(snapshot)
    ).generate(request)

    assert isinstance(outcome, AdapterPayload)
    planning_input = PlanningInput.model_validate_json(outcome.payload)
    assert planning_input.case == persisted_case
    assert planning_input.case.student.intake == "2028-09"
    assert planning_input.case.student.preferred_countries == (Country.JAPAN,)
    assert planning_input.case.family.japan_risk_accepted is False
    assert planning_input.case.family.budget == persisted_budget
    assert planning_input.costs == ()
    assert planning_input.rankings == ()
