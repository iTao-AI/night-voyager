from __future__ import annotations

from collections.abc import Callable, Mapping
from uuid import UUID, uuid4

from night_voyager.identity.models import ActorContext, ActorRole
from night_voyager.tasks.errors import TaskAuthorizationError
from night_voyager.tasks.models import (
    AgentTaskState,
    CancelTaskCommand,
    CreateTaskCommand,
)
from night_voyager.tasks.policy import project_task_status
from night_voyager.tasks.ports import TaskRepository

__all__ = ["CancelTaskCommand", "CreateTaskCommand", "TaskService"]


class TaskService:
    def __init__(
        self,
        repository: TaskRepository,
        *,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._id_factory = id_factory

    async def create(
        self,
        context: ActorContext,
        command: CreateTaskCommand,
        idempotency_key: str,
    ) -> dict[str, object]:
        self._require_advisor(context)
        row = await self._repository.create(
            context, command, self._id_factory(), idempotency_key
        )
        return self._project(row)

    async def get(
        self, context: ActorContext, task_id: UUID
    ) -> dict[str, object] | None:
        self._require_advisor(context)
        row = await self._repository.get(context, task_id)
        return None if row is None else self._project(row)

    async def cancel(
        self,
        context: ActorContext,
        command: CancelTaskCommand,
        idempotency_key: str,
    ) -> dict[str, object]:
        self._require_advisor(context)
        return self._project(
            await self._repository.cancel(context, command, idempotency_key)
        )

    @staticmethod
    def _require_advisor(context: ActorContext) -> None:
        if context.role is not ActorRole.ADVISOR:
            raise TaskAuthorizationError

    @staticmethod
    def _project(row: Mapping[str, object]) -> dict[str, object]:
        state = AgentTaskState(str(row["state"]))
        projected = {
            "task_id": row["task_id"],
            "row_version": row["row_version"],
            "status": project_task_status(
                state,
                result_is_current=bool(row.get("result_is_current", True)),
            ).value,
            "public_code": row.get("terminal_code"),
            "attempt_count": row["attempt_count"],
            "planning_run_id": row.get("result_planning_run_id"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        if "replayed" in row:
            projected["replayed"] = row["replayed"]
        return projected
