from __future__ import annotations

from night_voyager.adapters.protocols import (
    AdapterFailure,
    AdapterFailureCode,
    AdapterOutcome,
    PlanningAdapter,
    PlanningAdapterRequest,
)


class PlanningAdapterRouter:
    def __init__(self, *, synthetic: PlanningAdapter, mixed: PlanningAdapter) -> None:
        self._synthetic = synthetic
        self._mixed = mixed

    async def generate(self, request: PlanningAdapterRequest) -> AdapterOutcome:
        if request.operation == "generate_planning_run_v1":
            return await self._synthetic.generate(request)
        if request.operation == "generate_governed_mixed_planning_run_v1":
            return await self._mixed.generate(request)
        return AdapterFailure(code=AdapterFailureCode.PIN_MISMATCH)
