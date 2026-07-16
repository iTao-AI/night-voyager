from __future__ import annotations

from typing import Protocol

from night_voyager.adapters.protocols import (
    AdapterFailure,
    AdapterFailureCode,
    AdapterOutcome,
    AdapterPayload,
    PlanningAdapterRequest,
)
from night_voyager.planning.mixed import materialize_governed_mixed_input
from night_voyager.planning.mixed_postgres import MixedSnapshotLoadError
from night_voyager.planning.trusted import GovernedMixedSnapshotV1


class MixedSnapshotRepository(Protocol):
    async def load(
        self, request: PlanningAdapterRequest
    ) -> GovernedMixedSnapshotV1: ...


class GovernedMixedPlanningAdapter:
    def __init__(self, repository: MixedSnapshotRepository) -> None:
        self._repository = repository

    async def generate(self, request: PlanningAdapterRequest) -> AdapterOutcome:
        if request.operation != "generate_governed_mixed_planning_run_v1":
            return AdapterFailure(code=AdapterFailureCode.PIN_MISMATCH)
        try:
            snapshot = await self._repository.load(request)
            if (
                snapshot.organization_id != request.organization_id
                or snapshot.case.case_id != request.case_id
                or snapshot.case.revision != request.case_revision
                or snapshot.source_pack.pack_id != request.source_pack_id
                or snapshot.source_pack.version != request.source_pack_version
            ):
                return AdapterFailure(code=AdapterFailureCode.PIN_MISMATCH)
            planning_input = materialize_governed_mixed_input(snapshot)
        except MixedSnapshotLoadError as error:
            return AdapterFailure(
                code=(
                    AdapterFailureCode.TRANSIENT_UNAVAILABLE
                    if error.retryable
                    else AdapterFailureCode.PIN_MISMATCH
                )
            )
        except ValueError:
            return AdapterFailure(code=AdapterFailureCode.PIN_MISMATCH)
        return AdapterPayload(
            payload=planning_input.model_dump_json().encode("utf-8"),
            adapter_id="governed_mixed_planning",
            adapter_version="dra-mixed-v1",
        )
