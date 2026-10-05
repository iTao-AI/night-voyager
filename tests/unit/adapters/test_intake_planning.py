from __future__ import annotations

import pytest

from night_voyager.adapters.deterministic_planning import DeterministicPlanningAdapter
from night_voyager.adapters.protocols import (
    AdapterFailure,
    AdapterFailureCode,
    AdapterPayload,
    PlanningAdapterRequest,
)
from night_voyager.planning.models import PlanningInput
from night_voyager.planning.synthetic import PersistedSyntheticSnapshotV1
from tests.unit.planning.test_intake_revision_fixture import intake_snapshot


class SnapshotRepository:
    async def load(self, request: PlanningAdapterRequest) -> PersistedSyntheticSnapshotV1:
        return intake_snapshot()


@pytest.mark.asyncio
@pytest.mark.parametrize("wrong_request", (False, True))
async def test_adapter_binds_request_identity_to_independent_intake_evidence(
    wrong_request: bool,
) -> None:
    snapshot = intake_snapshot()
    request = PlanningAdapterRequest(
        schema_version=1,
        operation="generate_planning_run_v1",
        organization_id=snapshot.organization_id,
        case_id=snapshot.case.case_id,
        case_revision=1 if wrong_request else 2,
        source_pack_id=snapshot.source_pack_id,
        source_pack_version=1,
        policy_version="m3a-policy-v1",
    )
    outcome = await DeterministicPlanningAdapter(SnapshotRepository()).generate(request)
    if wrong_request:
        assert isinstance(outcome, AdapterFailure)
        assert outcome.code is AdapterFailureCode.PIN_MISMATCH
    else:
        assert isinstance(outcome, AdapterPayload)
        value = PlanningInput.model_validate_json(outcome.payload)
        assert value.case == snapshot.case
        assert value.costs[0].intake == "2028-02"
        assert value.costs[0].tuition_minor == 4200000
