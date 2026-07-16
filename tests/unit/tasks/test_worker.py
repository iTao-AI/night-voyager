from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import UUID

import pytest

from night_voyager.adapters.protocols import (
    AdapterFailure,
    AdapterFailureCode,
    AdapterPayload,
    PlanningAdapterRequest,
)
from night_voyager.planning.hashing import canonical_sha256
from night_voyager.tasks.errors import TaskLeaseLostError, TaskTransientError
from night_voyager.tasks.worker import AgentTaskClaim, TaskWorker, WorkerTaskInput
from tests.unit.planning.test_mixed import governed_mixed_input

ORG = UUID("10000000-0000-0000-0000-000000000001")
TASK = UUID("80000000-0000-0000-0000-000000000401")
CASE = UUID("40000000-0000-0000-0000-000000000401")
PACK = UUID("50000000-0000-0000-0000-000000000001")
CLAIM = AgentTaskClaim(task_id=TASK, organization_id=ORG, lease_generation=1)
INPUT = WorkerTaskInput(
    request=PlanningAdapterRequest(
        schema_version=1,
        operation="generate_planning_run_v1",
        organization_id=ORG,
        case_id=CASE,
        case_revision=1,
        source_pack_id=PACK,
        source_pack_version=1,
        policy_version="m3a-policy-v1",
    ),
    supersedes_run_id=None,
)
INPUT_SHA256 = canonical_sha256(INPUT.request.model_dump(mode="json"))


def test_worker_request_contract_accepts_only_the_two_planning_operations() -> None:
    mixed = INPUT.request.model_copy(
        update={"operation": "generate_governed_mixed_planning_run_v1"}
    )
    assert mixed.operation == "generate_governed_mixed_planning_run_v1"
    with pytest.raises(ValueError):
        PlanningAdapterRequest.model_validate(
            INPUT.request.model_dump() | {"operation": "unapproved_operation"}
        )


class FakeState:
    def __init__(
        self,
        *,
        heartbeat_loses_lease: bool = False,
        task_input: WorkerTaskInput = INPUT,
    ) -> None:
        self.active_sessions = 0
        self.calls: list[str] = []
        self.claimed = False
        self.heartbeat_loses_lease = heartbeat_loses_lease
        self.heartbeat_seen = asyncio.Event()
        self.task_input = task_input


class FakeRepository:
    def __init__(self, state: FakeState) -> None:
        self.state = state

    async def claim(self, worker_id: str) -> AgentTaskClaim | None:
        self.state.calls.append(f"claim:{worker_id}")
        if self.state.claimed:
            return None
        self.state.claimed = True
        return CLAIM

    async def load(self, claim: AgentTaskClaim) -> WorkerTaskInput:
        assert claim == CLAIM
        self.state.calls.append("load")
        return self.state.task_input

    async def start(
        self, claim: AgentTaskClaim, worker_id: str, input_sha256: str
    ) -> None:
        assert claim == CLAIM
        assert input_sha256 == canonical_sha256(
            self.state.task_input.request.model_dump(mode="json")
        )
        self.state.calls.append(f"start:{input_sha256}")

    async def heartbeat(self, claim: AgentTaskClaim, worker_id: str) -> None:
        assert claim == CLAIM
        self.state.calls.append("heartbeat")
        self.state.heartbeat_seen.set()
        if self.state.heartbeat_loses_lease:
            raise TaskLeaseLostError

    async def fail(
        self,
        claim: AgentTaskClaim,
        worker_id: str,
        code: str,
        *,
        retryable: bool,
        fallback_used: bool,
    ) -> str:
        assert claim == CLAIM
        self.state.calls.append(f"fail:{code}:{retryable}:{fallback_used}")
        return "failed"

    async def finalize(self, *args: object, **kwargs: object) -> str:
        self.state.calls.append("finalize")
        return "waiting_review"


class FailureAdapter:
    def __init__(self, state: FakeState, *, wait_for_heartbeat: bool = False) -> None:
        self.state = state
        self.wait_for_heartbeat = wait_for_heartbeat

    async def generate(self, request: PlanningAdapterRequest) -> AdapterFailure:
        assert request == self.state.task_input.request
        assert self.state.active_sessions == 0
        self.state.calls.append("adapter")
        if self.wait_for_heartbeat:
            await self.state.heartbeat_seen.wait()
        return AdapterFailure(code=AdapterFailureCode.UNKNOWN)


class PayloadAdapter:
    def __init__(self, payload: AdapterPayload) -> None:
        self.payload = payload

    async def generate(self, request: PlanningAdapterRequest) -> AdapterPayload:
        return self.payload


def repository_factory(state: FakeState):
    @asynccontextmanager
    async def factory() -> AsyncGenerator[FakeRepository]:
        state.active_sessions += 1
        try:
            yield FakeRepository(state)
        finally:
            state.active_sessions -= 1

    return factory


@pytest.mark.asyncio
async def test_run_once_uses_short_sessions_and_runs_adapter_outside_them() -> None:
    state = FakeState()
    worker = TaskWorker(
        repository_factory(state),
        FailureAdapter(state),
        worker_id="worker-unit",
    )

    assert await worker.run_once() is True

    assert state.active_sessions == 0
    assert state.calls == [
        "claim:worker-unit",
        "load",
        f"start:{INPUT_SHA256}",
        "adapter",
        "fail:unknown:False:False",
    ]


@pytest.mark.asyncio
async def test_worker_rejects_mixed_payload_baseline_drift_before_policy() -> None:
    planning_input = governed_mixed_input()
    payload = planning_input.model_dump(mode="json")
    payload["costs"][0]["fx_rate"] = "0.000001"  # type: ignore[index]
    task_input = WorkerTaskInput(
        request=PlanningAdapterRequest(
            schema_version=1,
            operation="generate_governed_mixed_planning_run_v1",
            organization_id=planning_input.organization_id,
            case_id=planning_input.case.case_id,
            case_revision=planning_input.case.revision,
            source_pack_id=planning_input.source_pack.pack_id,
            source_pack_version=planning_input.source_pack.version,
            policy_version="m3a-policy-v1",
        ),
        supersedes_run_id=None,
    )
    state = FakeState(task_input=task_input)
    worker = TaskWorker(
        repository_factory(state),
        PayloadAdapter(
            AdapterPayload(
                payload=json.dumps(payload).encode(),
                adapter_id="governed_mixed_planning",
                adapter_version="dra-mixed-v1",
            )
        ),
        worker_id="worker-mixed-drift",
    )

    assert await worker.run_once() is True
    assert "fail:baseline_drift:False:False" in state.calls
    assert "finalize" not in state.calls


@pytest.mark.asyncio
async def test_heartbeat_uses_independent_session_and_lease_loss_discards_output() -> None:
    state = FakeState(heartbeat_loses_lease=True)
    sleep_calls = 0

    async def pulse_sleep(_: float) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls > 1:
            await asyncio.Event().wait()

    worker = TaskWorker(
        repository_factory(state),
        FailureAdapter(state, wait_for_heartbeat=True),
        worker_id="worker-unit",
        sleep=pulse_sleep,
    )

    assert await worker.run_once() is True

    assert "heartbeat" in state.calls
    assert not any(call.startswith("fail:") for call in state.calls)
    assert "finalize" not in state.calls
    assert state.active_sessions == 0


@pytest.mark.asyncio
async def test_supervisor_retries_transient_database_errors_with_bounded_idle_sleep() -> None:
    state = FakeState()
    stop = asyncio.Event()

    class TransientRepository(FakeRepository):
        async def claim(self, worker_id: str) -> AgentTaskClaim | None:
            self.state.calls.append(f"claim:{worker_id}")
            raise TaskTransientError

    @asynccontextmanager
    async def factory() -> AsyncGenerator[TransientRepository]:
        yield TransientRepository(state)

    async def stop_after_one_sleep(seconds: float) -> None:
        assert seconds == 1
        state.calls.append("sleep:1")
        stop.set()

    worker = TaskWorker(
        factory,
        FailureAdapter(state),
        worker_id="worker-supervisor",
        sleep=stop_after_one_sleep,
    )

    await worker.run_forever(stop)

    assert state.calls == ["claim:worker-supervisor", "sleep:1"]


@pytest.mark.asyncio
async def test_supervisor_does_not_hide_programming_errors() -> None:
    state = FakeState()

    class BrokenRepository(FakeRepository):
        async def claim(self, worker_id: str) -> AgentTaskClaim | None:
            raise RuntimeError("programming defect")

    @asynccontextmanager
    async def factory() -> AsyncGenerator[BrokenRepository]:
        yield BrokenRepository(state)

    worker = TaskWorker(
        factory,
        FailureAdapter(state),
        worker_id="worker-broken",
    )

    with pytest.raises(RuntimeError, match="programming defect"):
        await worker.run_forever()
