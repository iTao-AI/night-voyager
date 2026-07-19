from __future__ import annotations

from night_voyager.adapters.protocols import (
    AdapterFailure,
    AdapterFailureCode,
    AdapterOutcome,
    PlanningAdapter,
    PlanningAdapterRequest,
    PlanningAdapterResolution,
)
from night_voyager.skills.models import SkillLeafBindingV1


class PlanningAdapterRouter:
    def __init__(self, *, synthetic: PlanningAdapter, mixed: PlanningAdapter) -> None:
        self._synthetic = synthetic
        self._mixed = mixed

    def resolve(self, operation: str) -> PlanningAdapterResolution:
        if operation == "generate_planning_run_v1":
            return PlanningAdapterResolution(
                leaf_binding=SkillLeafBindingV1(
                    operation="generate_planning_run_v1",
                    adapter_id="deterministic_planning",
                    adapter_version="m4a-v1",
                ),
                adapter=self._synthetic,
            )
        if operation == "generate_governed_mixed_planning_run_v1":
            return PlanningAdapterResolution(
                leaf_binding=SkillLeafBindingV1(
                    operation="generate_governed_mixed_planning_run_v1",
                    adapter_id="governed_mixed_planning",
                    adapter_version="dra-mixed-v1",
                ),
                adapter=self._mixed,
            )
        raise ValueError("unsupported planning operation")

    async def generate(self, request: PlanningAdapterRequest) -> AdapterOutcome:
        try:
            resolution = self.resolve(request.operation)
        except ValueError:
            return AdapterFailure(code=AdapterFailureCode.PIN_MISMATCH)
        return await resolution.adapter.generate(request)
