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
    PlanningAdapterResolution,
    PlanningAdapterResolver,
)
from night_voyager.planning.hashing import canonical_sha256
from night_voyager.planning.policy import evaluate_planning_run
from night_voyager.skills.models import (
    SkillKey,
    SkillLeafBindingV1,
    SkillRuntimeManifestEntryV1,
    SkillRuntimePin,
)
from night_voyager.skills.registry import (
    SkillRuntimeIncompatibility,
    SkillRuntimeRegistry,
)
from night_voyager.tasks.errors import (
    TaskLeaseLostError,
    TaskTransientError,
)
from night_voyager.tasks.policy import (
    AdapterPayloadError,
    classify_adapter_outcome,
    validate_adapter_payload,
)

LOGGER = logging.getLogger(__name__)


class TaskPinInvalidError(Exception):
    """Trusted database projection cannot prove the claimed runtime pin."""


@dataclass(frozen=True, slots=True)
class AgentTaskClaim:
    task_id: UUID
    organization_id: UUID
    lease_generation: int


@dataclass(frozen=True, slots=True)
class WorkerTaskInput:
    request: PlanningAdapterRequest
    skill_pin: SkillRuntimePin
    skill_key: SkillKey
    semantic_version: str
    leaf_binding: SkillLeafBindingV1
    registered_manifest: SkillRuntimeManifestEntryV1
    runtime_manifest_id: str
    runtime_manifest_version: str
    runtime_manifest_sha256: str
    supersedes_run_id: UUID | None
    attempt_no: int = 1


class WorkerTaskRepository(Protocol):
    async def claim(self, worker_id: str) -> AgentTaskClaim | None: ...

    async def load(self, claim: AgentTaskClaim) -> WorkerTaskInput: ...

    async def start(self, claim: AgentTaskClaim, worker_id: str, input_sha256: str) -> None: ...

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


type RepositoryFactory = Callable[[], AbstractAsyncContextManager[WorkerTaskRepository]]


class TaskWorker:
    def __init__(
        self,
        repository_factory: RepositoryFactory,
        router: PlanningAdapterResolver,
        registry: SkillRuntimeRegistry,
        *,
        worker_id: str,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        run_id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository_factory = repository_factory
        self._router = router
        self._registry = registry
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
            resolution = self._resolve_runtime(task_input)
            async with self._repository_factory() as repository:
                await repository.start(
                    claim,
                    self._worker_id,
                    canonical_sha256(
                        {
                            "request": task_input.request.model_dump(mode="json"),
                            "five_field_pin": task_input.skill_pin.model_dump(mode="json"),
                        }
                    ),
                )
        except (TaskPinInvalidError, SkillRuntimeIncompatibility):
            await self._fail_invalid_pin(claim)
            return True
        except TaskLeaseLostError:
            return True

        stop_heartbeat = asyncio.Event()
        lease_lost = asyncio.Event()
        heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(claim, stop_heartbeat, lease_lost)
        )
        try:
            outcome = await resolution.adapter.generate(task_input.request)
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
                decision = classify_adapter_outcome(outcome, attempt_no=task_input.attempt_no)
                async with self._repository_factory() as repository:
                    await repository.fail(
                        claim,
                        self._worker_id,
                        decision.public_code,
                        retryable=decision.retryable,
                        fallback_used=(outcome.code is AdapterFailureCode.FALLBACK_AUTHORITY),
                    )
                return True
            try:
                planning_input = validate_adapter_payload(
                    outcome,
                    task_input.request,
                    resolution.leaf_binding,
                )
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
                "rankings": [item.model_dump(mode="json") for item in planning_input.rankings],
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

    def _resolve_runtime(self, task_input: WorkerTaskInput) -> PlanningAdapterResolution:
        try:
            resolution = self._router.resolve(task_input.request.operation)
        except ValueError as error:
            raise SkillRuntimeIncompatibility("task operation is not configured") from error
        if resolution.leaf_binding != task_input.leaf_binding:
            raise SkillRuntimeIncompatibility(
                "claimed execution leaf does not match resolved router leaf"
            )
        packaged = self._registry.validate_pin(
            task_input.skill_pin,
            task_input.skill_key,
            task_input.semantic_version,
            task_input.request.operation,
            resolution.leaf_binding,
        )
        if packaged != task_input.registered_manifest:
            raise SkillRuntimeIncompatibility(
                "registered Skill manifest does not match packaged runtime"
            )
        manifest = self._registry.manifest
        if (
            task_input.runtime_manifest_id != manifest.manifest_id
            or task_input.runtime_manifest_version != manifest.manifest_version
            or task_input.runtime_manifest_sha256 != manifest.manifest_sha256
        ):
            raise SkillRuntimeIncompatibility(
                "registered runtime manifest identity does not match package"
            )
        return resolution

    async def _fail_invalid_pin(self, claim: AgentTaskClaim) -> None:
        try:
            async with self._repository_factory() as repository:
                await repository.fail(
                    claim,
                    self._worker_id,
                    "skill_pin_invalid",
                    retryable=False,
                    fallback_used=False,
                )
        except TaskLeaseLostError:
            return

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
