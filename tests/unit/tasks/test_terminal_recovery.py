from uuid import UUID

import pytest
from pydantic import ValidationError

from night_voyager.identity.models import ActorContext, ActorRole
from night_voyager.skills.models import SkillRuntimeManifestEntryV1
from night_voyager.tasks import models, policy
from night_voyager.tasks.application import TaskService
from night_voyager.tasks.errors import TaskAuthorizationError
from tests.unit.tasks.test_application import ENTRY, REGISTRY, TASK, FakeRepository, actor, record


@pytest.mark.parametrize(
    "state,code,allowed",
    [
        ("failed", "transient_unavailable", True),
        ("failed", "transport_interrupted", True),
        ("failed", "lease_expired", True),
        ("timed_out", "deadline_exceeded", True),
        ("failed", "deadline_exceeded", False),
        ("failed", "invalid_schema", False),
        ("failed", "unknown", False),
        ("cancelled", "transport_interrupted", False),
        ("blocked", "transient_unavailable", False),
        ("succeeded", "transport_interrupted", False),
    ],
)
def test_terminal_recovery_allowlist_matches_real_producer_states(
    state: str, code: str, allowed: bool
) -> None:
    assert hasattr(policy, "terminal_recovery_allowed")
    assert policy.terminal_recovery_allowed(state, code, has_result=False) is allowed
    assert policy.terminal_recovery_allowed(state, code, has_result=True) is False


def test_retry_command_contains_only_source_and_expected_versions() -> None:
    assert hasattr(models, "RetryTaskCommand")
    command = models.RetryTaskCommand(
        task_id=TASK, expected_row_version=5, expected_case_revision=1
    )
    assert set(command.model_dump()) == {
        "task_id",
        "expected_row_version",
        "expected_case_revision",
    }
    for extra in ("operation", "source_pack_id", "policy_version", "skill_version_id"):
        with pytest.raises(ValidationError):
            models.RetryTaskCommand.model_validate(
                {**command.model_dump(), extra: str(UUID(int=7))}
            )


class RetryRepository(FakeRepository):
    async def retry(
        self,
        context: ActorContext,
        command: models.RetryTaskCommand,
        task_id: UUID,
        idempotency_key: str,
        skill_manifest: SkillRuntimeManifestEntryV1,
    ) -> dict[str, object]:
        self.calls.append(("retry", context, command, task_id, idempotency_key, skill_manifest))
        return {**record(), "task_id": task_id, "replayed": True}


@pytest.mark.asyncio
async def test_retry_reuses_packaged_runtime_validation_and_atomic_repository_operation() -> None:
    assert hasattr(models, "RetryTaskCommand")
    assert hasattr(TaskService, "retry")
    repo = RetryRepository()
    service = TaskService(repo, registry=REGISTRY, id_factory=lambda: UUID(int=99))
    command = models.RetryTaskCommand(
        task_id=TASK, expected_row_version=5, expected_case_revision=1
    )
    result = await service.retry(actor(), command, "retry-key")
    assert result["task_id"] == UUID(int=99)
    assert result["replayed"] is True
    assert [call[0] for call in repo.calls] == ["resolve_active_skill_version", "retry"]
    assert repo.calls[-1][-1] == ENTRY
    with pytest.raises(TaskAuthorizationError):
        await service.retry(actor(ActorRole.PARENT), command, "retry-key")
