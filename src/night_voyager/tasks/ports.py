from __future__ import annotations

from typing import Protocol
from uuid import UUID

from night_voyager.adapters.protocols import PlanningAdapter
from night_voyager.identity.models import ActorContext
from night_voyager.skills.models import SkillRuntimeManifestEntryV1
from night_voyager.tasks.models import CancelTaskCommand, CreateTaskCommand


class PlanningAdapterPort(PlanningAdapter, Protocol):
    """Task-layer alias for the product-owned adapter boundary."""


class TaskRepository(Protocol):
    async def resolve_active_skill_version(
        self, context: ActorContext
    ) -> tuple[str, str]: ...

    async def create(
        self,
        context: ActorContext,
        command: CreateTaskCommand,
        task_id: UUID,
        idempotency_key: str,
        skill_manifest: SkillRuntimeManifestEntryV1,
    ) -> dict[str, object]: ...

    async def get(
        self, context: ActorContext, task_id: UUID
    ) -> dict[str, object] | None: ...

    async def cancel(
        self,
        context: ActorContext,
        command: CancelTaskCommand,
        idempotency_key: str,
    ) -> dict[str, object]: ...
