from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from night_voyager.identity.models import ActorContext, ActorRole
from night_voyager.skills.models import (
    SkillKey,
    SkillRuntimeManifestEntryV1,
    SkillRuntimePin,
)
from night_voyager.skills.registry import SkillRuntimeRegistry
from night_voyager.tasks.application import (
    CancelTaskCommand,
    CreateTaskCommand,
    TaskService,
)
from night_voyager.tasks.errors import TaskAuthorizationError

ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
TASK = UUID("80000000-0000-0000-0000-000000000301")
CASE = UUID("40000000-0000-0000-0000-000000000301")
PACK = UUID("50000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[3]
REGISTRY = SkillRuntimeRegistry.from_json(
    (ROOT / "fixtures/skills/runtime-manifest-v1.json").read_bytes()
)
ENTRY = REGISTRY.get(SkillKey.STUDY_DESTINATION_COMPARE, "1.0.0")
assert ENTRY.operation_bindings is not None
PIN = SkillRuntimePin(
    skill_definition_id=UUID("81000000-0000-0000-0000-000000000002"),
    skill_version_id=UUID("82000000-0000-0000-0000-000000000002"),
    skill_activation_event_id=UUID("84000000-0000-0000-0000-000000000001"),
    skill_activation_sequence=1,
    runtime_binding_sha256=ENTRY.runtime_binding_sha256 or "",
)
LEAF = ENTRY.operation_bindings[0]


def actor(role: ActorRole = ActorRole.ADVISOR) -> ActorContext:
    return ActorContext(ORG, ADVISOR, role, UUID(int=1))


def record(*, state: str = "queued", current: bool = True) -> dict[str, object]:
    return {
        "task_id": TASK,
        "row_version": 2,
        "state": state,
        "attempt_count": 1,
        "terminal_code": None,
        "result_planning_run_id": UUID(int=7) if state == "waiting_review" else None,
        "result_is_current": current,
        "created_at": NOW,
        "updated_at": NOW,
        "operation": "generate_planning_run_v1",
        "skill_key": SkillKey.STUDY_DESTINATION_COMPARE.value,
        "semantic_version": "1.0.0",
        **PIN.model_dump(),
        "lease_owner": "must-not-leak",
        "lease_generation": 9,
    }


class FakeRepository:
    def __init__(self) -> None:
        self.row: dict[str, object] | None = record()
        self.calls: list[tuple[object, ...]] = []

    async def resolve_active_skill_version(self, context: ActorContext) -> tuple[str, str]:
        self.calls.append(("resolve_active_skill_version", context))
        return SkillKey.STUDY_DESTINATION_COMPARE.value, "1.0.0"

    async def create(
        self,
        context: ActorContext,
        command: CreateTaskCommand,
        task_id: UUID,
        idempotency_key: str,
        skill_manifest: SkillRuntimeManifestEntryV1,
    ) -> dict[str, object]:
        self.calls.append(("create", context, command, task_id, idempotency_key, skill_manifest))
        assert self.row is not None
        return {**self.row, "task_id": task_id, "replayed": False}

    async def get(self, context: ActorContext, task_id: UUID) -> dict[str, object] | None:
        self.calls.append(("get", context, task_id))
        return self.row

    async def cancel(
        self,
        context: ActorContext,
        command: CancelTaskCommand,
        idempotency_key: str,
    ) -> dict[str, object]:
        self.calls.append(("cancel", context, command, idempotency_key))
        assert self.row is not None
        return {**self.row, "state": "cancelled", "replayed": False}


def create_command() -> CreateTaskCommand:
    return CreateTaskCommand(
        case_id=CASE,
        expected_case_revision=1,
        source_pack_id=PACK,
        source_pack_version=1,
    )


def test_create_command_accepts_only_the_two_planning_operations() -> None:
    mixed = CreateTaskCommand.model_validate(
        {
            **create_command().model_dump(),
            "operation": "generate_governed_mixed_planning_run_v1",
        }
    )
    assert mixed.operation == "generate_governed_mixed_planning_run_v1"

    with pytest.raises(ValidationError):
        CreateTaskCommand.model_validate(
            {**create_command().model_dump(), "operation": "unknown_operation"}
        )


@pytest.mark.asyncio
async def test_create_projects_only_public_fields_and_injects_task_id() -> None:
    repository = FakeRepository()
    service = TaskService(repository, registry=REGISTRY, id_factory=lambda: TASK)

    result = await service.create(actor(), create_command(), "create-key")

    assert result == {
        "task_id": TASK,
        "row_version": 2,
        "status": "preparing",
        "public_code": None,
        "attempt_count": 1,
        "planning_run_id": None,
        "created_at": NOW,
        "updated_at": NOW,
        "skill_pin": PIN,
        "leaf_binding": LEAF,
        "replayed": False,
    }
    assert repository.calls[0][0] == "resolve_active_skill_version"
    assert repository.calls[1][3] == TASK
    assert repository.calls[1][-1] == ENTRY
    assert "state" not in result
    assert "lease_owner" not in result
    assert "lease_generation" not in result


@pytest.mark.asyncio
async def test_get_applies_currentness_override_and_non_enumeration() -> None:
    repository = FakeRepository()
    repository.row = record(state="waiting_review", current=False)
    service = TaskService(repository, registry=REGISTRY)

    result = await service.get(actor(), TASK)
    assert result is not None
    assert result["status"] == "outdated"
    assert result["planning_run_id"] == UUID(int=7)

    repository.row = None
    assert await service.get(actor(), UUID(int=999)) is None


@pytest.mark.asyncio
async def test_create_get_and_cancel_require_advisor_role() -> None:
    service = TaskService(FakeRepository(), registry=REGISTRY)
    parent = actor(ActorRole.PARENT)

    with pytest.raises(TaskAuthorizationError):
        await service.create(parent, create_command(), "key")
    with pytest.raises(TaskAuthorizationError):
        await service.get(parent, TASK)
    with pytest.raises(TaskAuthorizationError):
        await service.cancel(
            parent,
            CancelTaskCommand(task_id=TASK, expected_row_version=2),
            "cancel-key",
        )


@pytest.mark.asyncio
async def test_cancel_projects_cancelled_status_and_replay_marker() -> None:
    repository = FakeRepository()
    service = TaskService(repository, registry=REGISTRY)

    result = await service.cancel(
        actor(),
        CancelTaskCommand(task_id=TASK, expected_row_version=2),
        "cancel-key",
    )

    assert result["status"] == "cancelled"
    assert result["replayed"] is False
    assert repository.calls[-1][0] == "cancel"
