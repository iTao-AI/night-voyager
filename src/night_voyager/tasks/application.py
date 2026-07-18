from __future__ import annotations

from collections.abc import Callable, Mapping
from uuid import UUID, uuid4

from night_voyager.identity.models import ActorContext, ActorRole
from night_voyager.skills.models import SkillLeafBindingV1, SkillRuntimePin
from night_voyager.skills.registry import (
    SkillRuntimeIncompatibility,
    SkillRuntimeRegistry,
)
from night_voyager.tasks.errors import TaskAuthorizationError, TaskConflictError
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
        registry: SkillRuntimeRegistry,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._registry = registry
        self._id_factory = id_factory

    async def create(
        self,
        context: ActorContext,
        command: CreateTaskCommand,
        idempotency_key: str,
    ) -> dict[str, object]:
        self._require_advisor(context)
        skill_key, semantic_version = await self._repository.resolve_active_skill_version(
            context
        )
        try:
            skill_manifest = self._registry.get(skill_key, semantic_version)
        except SkillRuntimeIncompatibility as error:
            raise TaskConflictError("skill_version_unavailable") from error
        row = await self._repository.create(
            context,
            command,
            self._id_factory(),
            idempotency_key,
            skill_manifest,
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

    def _project(self, row: Mapping[str, object]) -> dict[str, object]:
        state = AgentTaskState(str(row["state"]))
        skill_pin = self._project_skill_pin(row)
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
            "skill_pin": skill_pin,
            "leaf_binding": self._project_leaf_binding(row, skill_pin),
        }
        if "replayed" in row:
            projected["replayed"] = row["replayed"]
        return projected

    @staticmethod
    def _project_skill_pin(row: Mapping[str, object]) -> SkillRuntimePin | None:
        if row.get("skill_definition_id") is None:
            return None
        return SkillRuntimePin.model_validate(
            {
                field: row[field]
                for field in (
                    "skill_definition_id",
                    "skill_version_id",
                    "skill_activation_event_id",
                    "skill_activation_sequence",
                    "runtime_binding_sha256",
                )
            }
        )

    def _project_leaf_binding(
        self,
        row: Mapping[str, object],
        skill_pin: SkillRuntimePin | None,
    ) -> SkillLeafBindingV1 | None:
        if skill_pin is None:
            return None
        skill_key = row.get("skill_key")
        semantic_version = row.get("semantic_version")
        operation = row.get("operation")
        if not all(isinstance(value, str) for value in (skill_key, semantic_version, operation)):
            raise RuntimeError("pinned task runtime identity is unavailable")
        entry = self._registry.get(str(skill_key), str(semantic_version))
        leaf = next(
            (
                item
                for item in entry.operation_bindings or ()
                if item.operation == operation
            ),
            None,
        )
        if leaf is None:
            raise RuntimeError("pinned task operation leaf is unavailable")
        self._registry.validate_pin(
            skill_pin,
            str(skill_key),
            str(semantic_version),
            str(operation),
            leaf,
        )
        return leaf
