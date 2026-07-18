from __future__ import annotations

import pytest

from night_voyager.adapters.protocols import PlanningAdapterRequest
from night_voyager.adapters.router import PlanningAdapterRouter


class StubAdapter:
    async def generate(self, request: PlanningAdapterRequest):  # type: ignore[no-untyped-def]
        raise AssertionError(request)


def test_router_resolves_the_actual_closed_operation_leaf_and_object() -> None:
    synthetic = StubAdapter()
    mixed = StubAdapter()
    router = PlanningAdapterRouter(synthetic=synthetic, mixed=mixed)

    synthetic_resolution = router.resolve("generate_planning_run_v1")
    mixed_resolution = router.resolve("generate_governed_mixed_planning_run_v1")

    assert synthetic_resolution.adapter is synthetic
    assert synthetic_resolution.leaf_binding.model_dump() == {
        "operation": "generate_planning_run_v1",
        "adapter_id": "deterministic_planning",
        "adapter_version": "m4a-v1",
    }
    assert mixed_resolution.adapter is mixed
    assert mixed_resolution.leaf_binding.model_dump() == {
        "operation": "generate_governed_mixed_planning_run_v1",
        "adapter_id": "governed_mixed_planning",
        "adapter_version": "dra-mixed-v1",
    }


def test_router_rejects_an_operation_outside_the_closed_map() -> None:
    router = PlanningAdapterRouter(synthetic=StubAdapter(), mixed=StubAdapter())

    with pytest.raises(ValueError, match="unsupported planning operation"):
        router.resolve("unknown")
