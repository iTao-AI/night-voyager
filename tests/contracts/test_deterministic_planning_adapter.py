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
from night_voyager.planning.models import PlanningInput, PlanningResult
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


@pytest.mark.asyncio
async def test_deterministic_adapter_returns_untrusted_bytes_not_planning_authority() -> None:
    request = adapter_request()
    outcome = await DeterministicPlanningAdapter().generate(request)
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


@pytest.mark.asyncio
async def test_typed_failure_is_constructor_injected_and_has_no_request_selector() -> None:
    failure = AdapterFailure(code=AdapterFailureCode.TRANSIENT_UNAVAILABLE)
    outcome = await DeterministicPlanningAdapter(injected_failure=failure).generate(
        adapter_request()
    )
    assert outcome == failure
    assert "failure" not in PlanningAdapterRequest.model_fields
    assert "adapter" not in PlanningAdapterRequest.model_fields


@pytest.mark.asyncio
async def test_adapter_rejects_unapproved_source_pack_pin() -> None:
    request = adapter_request().model_copy(
        update={"source_pack_id": UUID("50000000-0000-0000-0000-000000000099")}
    )
    outcome = await DeterministicPlanningAdapter().generate(request)
    assert outcome == AdapterFailure(code=AdapterFailureCode.PIN_MISMATCH)
