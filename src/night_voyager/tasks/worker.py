from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager, suppress
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from night_voyager.adapters.protocols import (
    AdapterFailure,
    AdapterFailureCode,
    PlanningAdapterRequest,
)
from night_voyager.planning.hashing import canonical_sha256
from night_voyager.planning.policy import evaluate_planning_run
from night_voyager.tasks.errors import TaskLeaseLostError, TaskTransientError
from night_voyager.tasks.policy import (
    AdapterPayloadError,
    classify_adapter_outcome,
    validate_adapter_payload,
)
from night_voyager.tasks.ports import PlanningAdapterPort

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AgentTaskClaim:
    task_id: UUID
    organization_id: UUID
    lease_generation: int


@dataclass(frozen=True, slots=True)
class WorkerTaskInput:
    request: PlanningAdapterRequest
    supersedes_run_id: UUID | None
    attempt_no: int = 1


class WorkerTaskRepository(Protocol):
    async def claim(self, worker_id: str) -> AgentTaskClaim | None: ...

    async def load(self, claim: AgentTaskClaim) -> WorkerTaskInput: ...

    async def start(
        self, claim: AgentTaskClaim, worker_id: str, input_sha256: str
    ) -> None: ...

    async def heartbeat(self, claim: AgentTaskClaim, worker_id: str) -> None: ...

    async def fail(
        self,
        claim: AgentTaskClaim,
        worker_id: str,
        code: str,
        *,
        retryable: bool,
        fallback_used: bool,
    ) -> str: ...

    async def finalize(
        self,
        claim: AgentTaskClaim,
        worker_id: str,
        *,
        run_id: UUID,
        evidence_hash: str,
        state: str,
        reason_code: str,
        output_hash: str,
        output: dict[str, object],
        supersedes_run_id: UUID | None,
    ) -> str: ...


type RepositoryFactory = Callable[
    [], AbstractAsyncContextManager[WorkerTaskRepository]
]


class TaskWorker:
    def __init__(
        self,
        repository_factory: RepositoryFactory,
        adapter: PlanningAdapterPort,
        *,
        worker_id: str,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        run_id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository_factory = repository_factory
        self._adapter = adapter
        self._worker_id = worker_id
        self._sleep = sleep
        self._run_id_factory = run_id_factory

    async def run_once(self) -> bool:
        async with self._repository_factory() as repository:
            claim = await repository.claim(self._worker_id)
        if claim is None:
            return False
        try:
            async with self._repository_factory() as repository:
                task_input = await repository.load(claim)
            async with self._repository_factory() as repository:
                await repository.start(
                    claim,
                    self._worker_id,
                    canonical_sha256(task_input.request.model_dump(mode="json")),
                )
        except TaskLeaseLostError:
            return True

        stop_heartbeat = asyncio.Event()
        lease_lost = asyncio.Event()
        heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(claim, stop_heartbeat, lease_lost)
        )
        try:
            outcome = await self._adapter.generate(task_input.request)
        finally:
            stop_heartbeat.set()
            if not heartbeat_task.done():
                heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task
        if lease_lost.is_set():
            return True

        try:
            if isinstance(outcome, AdapterFailure):
                decision = classify_adapter_outcome(
                    outcome, attempt_no=task_input.attempt_no
                )
                async with self._repository_factory() as repository:
                    await repository.fail(
                        claim,
                        self._worker_id,
                        decision.public_code,
                        retryable=decision.retryable,
                        fallback_used=(
                            outcome.code is AdapterFailureCode.FALLBACK_AUTHORITY
                        ),
                    )
                return True
            try:
                planning_input = validate_adapter_payload(outcome, task_input.request)
            except AdapterPayloadError as error:
                async with self._repository_factory() as repository:
                    await repository.fail(
                        claim,
                        self._worker_id,
                        error.code,
                        retryable=False,
                        fallback_used=error.code == "fallback_authority",
                    )
                return True
            result = evaluate_planning_run(planning_input)
            output: dict[str, object] = {
                **result.model_dump(mode="json"),
                "costs": [item.model_dump(mode="json") for item in planning_input.costs],
                "rankings": [
                    item.model_dump(mode="json") for item in planning_input.rankings
                ],
            }
            async with self._repository_factory() as repository:
                await repository.finalize(
                    claim,
                    self._worker_id,
                    run_id=self._run_id_factory(),
                    evidence_hash=canonical_sha256(
                        [item.model_dump(mode="json") for item in planning_input.evidence]
                    ),
                    state=result.state.value,
                    reason_code=result.reason_code,
                    output_hash=canonical_sha256(result.model_dump(mode="json")),
                    output=output,
                    supersedes_run_id=task_input.supersedes_run_id,
                )
        except TaskLeaseLostError:
            return True
        return True

    async def run_forever(self, stop: asyncio.Event | None = None) -> None:
        stop_event = stop or asyncio.Event()
        while not stop_event.is_set():
            try:
                worked = await self.run_once()
            except TaskTransientError:
                LOGGER.warning("task_worker_transient")
                worked = False
            if not worked and not stop_event.is_set():
                await self._sleep(1)

    async def _heartbeat_loop(
        self,
        claim: AgentTaskClaim,
        stop: asyncio.Event,
        lease_lost: asyncio.Event,
    ) -> None:
        while not stop.is_set():
            await self._sleep(15)
            if stop.is_set():
                return
            try:
                async with self._repository_factory() as repository:
                    await repository.heartbeat(claim, self._worker_id)
            except TaskLeaseLostError:
                lease_lost.set()
                return
