from __future__ import annotations

from night_voyager.adapters.protocols import (
    AdapterFailure,
    AdapterFailureCode,
    AdapterOutcome,
    AdapterPayload,
    PlanningAdapterRequest,
)
from night_voyager.planning.fixtures import validate_planning_fixture


class DeterministicPlanningAdapter:
    def __init__(self, *, injected_failure: AdapterFailure | None = None) -> None:
        self._injected_failure = injected_failure

    async def generate(self, request: PlanningAdapterRequest) -> AdapterOutcome:
        if self._injected_failure is not None:
            return self._injected_failure
        fixture = validate_planning_fixture()
        source = fixture.planning_input
        if (
            request.source_pack_id != source.source_pack.pack_id
            or request.source_pack_version != source.source_pack.version
            or request.policy_version != "m3a-policy-v1"
        ):
            return AdapterFailure(code=AdapterFailureCode.PIN_MISMATCH)
        planning_input = source.model_copy(
            update={
                "organization_id": request.organization_id,
                "case": source.case.model_copy(
                    update={
                        "organization_id": request.organization_id,
                        "case_id": request.case_id,
                        "revision": request.case_revision,
                    }
                ),
                "source_pack": source.source_pack.model_copy(
                    update={"organization_id": request.organization_id}
                ),
                "evidence": tuple(
                    item.model_copy(update={"organization_id": request.organization_id})
                    for item in source.evidence
                ),
                "costs": tuple(
                    item.model_copy(update={"organization_id": request.organization_id})
                    for item in source.costs
                ),
                "rankings": tuple(
                    item.model_copy(update={"organization_id": request.organization_id})
                    for item in source.rankings
                ),
            }
        )
        return AdapterPayload(payload=planning_input.model_dump_json().encode("utf-8"))
