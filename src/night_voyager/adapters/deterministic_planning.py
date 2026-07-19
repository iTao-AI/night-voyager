from __future__ import annotations

from typing import Protocol

from night_voyager.adapters.protocols import (
    AdapterFailure,
    AdapterFailureCode,
    AdapterOutcome,
    AdapterPayload,
    PlanningAdapterRequest,
)
from night_voyager.planning.synthetic import (
    PersistedSyntheticSnapshotV1,
    materialize_persisted_synthetic_input,
)
from night_voyager.planning.synthetic_postgres import SyntheticSnapshotLoadError


class SyntheticSnapshotRepository(Protocol):
    async def load(
        self, request: PlanningAdapterRequest
    ) -> PersistedSyntheticSnapshotV1: ...


class DeterministicPlanningAdapter:
    def __init__(
        self,
        repository: SyntheticSnapshotRepository,
        *,
        injected_failure: AdapterFailure | None = None,
    ) -> None:
        self._repository = repository
        self._injected_failure = injected_failure

    async def generate(self, request: PlanningAdapterRequest) -> AdapterOutcome:
        if self._injected_failure is not None:
            return self._injected_failure
        if request.operation != "generate_planning_run_v1":
            return AdapterFailure(code=AdapterFailureCode.PIN_MISMATCH)
        try:
            snapshot = await self._repository.load(request)
            if (
                snapshot.organization_id != request.organization_id
                or snapshot.case.case_id != request.case_id
                or snapshot.case.revision != request.case_revision
                or snapshot.source_pack_id != request.source_pack_id
                or snapshot.source_pack_version != request.source_pack_version
                or snapshot.policy_version != request.policy_version
            ):
                return AdapterFailure(code=AdapterFailureCode.PIN_MISMATCH)
            planning_input = materialize_persisted_synthetic_input(snapshot)
        except SyntheticSnapshotLoadError as error:
            return AdapterFailure(
                code=(
                    AdapterFailureCode.TRANSIENT_UNAVAILABLE
                    if error.retryable
                    else AdapterFailureCode.PIN_MISMATCH
                )
            )
        except ValueError:
            return AdapterFailure(code=AdapterFailureCode.PIN_MISMATCH)
        return AdapterPayload(payload=planning_input.model_dump_json().encode("utf-8"))
