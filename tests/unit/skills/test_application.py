from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from night_voyager.identity.models import ActorContext, ActorRole
from night_voyager.skills.application import SkillService
from night_voyager.skills.errors import (
    SkillActivationStaleError,
    SkillAuthorizationError,
    SkillCandidateStaleError,
    SkillCandidateTerminalError,
    SkillEvaluationFailedError,
    SkillIdempotencyConflictError,
    SkillPersistenceError,
    SkillPinInvalidError,
    SkillRollbackUnsupportedError,
    SkillScopeExpansionError,
    SkillVersionUnavailableError,
)
from night_voyager.skills.evaluation import SkillEvaluator
from night_voyager.skills.models import (
    SkillActivationKind,
    SkillBindingKind,
    SkillChangeProvenance,
    SkillEvaluationStatus,
    SkillKey,
    canonical_sha256,
)
from night_voyager.skills.ports import (
    ActivateSkillCandidateCommand,
    CreateSkillCandidateCommand,
    EvaluateSkillCandidateCommand,
    PlanningSkillInspectorV1,
    RollbackSkillCommand,
    SkillActivationEventSummaryV1,
    SkillActivationRecordedV1,
    SkillCandidateContextV1,
    SkillCandidateCreatedV1,
    SkillCatalogDetailV1,
    SkillCatalogSummaryV1,
    SkillCatalogV1,
    SkillEvaluationRecordedV1,
    SkillVersionSummaryV1,
)
from night_voyager.skills.postgres import PostgresSkillRepository
from night_voyager.skills.registry import SkillRuntimeRegistry

ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
STUDENT = UUID("20000000-0000-0000-0000-000000000002")
SESSION = UUID("30000000-0000-0000-0000-000000000001")
CASE = UUID("40000000-0000-0000-0000-000000000001")
DEFINITION = UUID("70000000-0000-0000-0000-000000000001")
BASE_VERSION = UUID("71000000-0000-0000-0000-000000000001")
PROPOSED_VERSION = UUID("71000000-0000-0000-0000-000000000002")
CANDIDATE = UUID("72000000-0000-0000-0000-000000000001")
EVALUATION = UUID("73000000-0000-0000-0000-000000000001")
ACTIVATION = UUID("74000000-0000-0000-0000-000000000001")
IDEMPOTENCY_KEY = "skill-lifecycle-idempotency-key"


def actor(role: ActorRole = ActorRole.ADVISOR) -> ActorContext:
    return ActorContext(
        organization_id=ORG,
        actor_id=ADVISOR if role is ActorRole.ADVISOR else STUDENT,
        role=role,
        session_id=SESSION,
    )


def runtime_registry() -> SkillRuntimeRegistry:
    return SkillRuntimeRegistry.from_json(
        Path("fixtures/skills/runtime-manifest-v1.json").read_bytes()
    )


def evaluator(registry: SkillRuntimeRegistry) -> SkillEvaluator:
    return SkillEvaluator.from_json(
        Path("fixtures/skills/eval-manifest-v1.json").read_bytes(), registry
    )


def create_command(
    *,
    skill_key: SkillKey = SkillKey.STUDY_DESTINATION_COMPARE,
    proposed_version: str = "1.0.1",
) -> CreateSkillCandidateCommand:
    return CreateSkillCandidateCommand(
        skill_key=skill_key,
        proposed_version=proposed_version,
        provenance=SkillChangeProvenance.MAINTAINER_PROPOSAL,
        reason="Add deterministic negative compatibility coverage.",
        reference="public-safe-test-reference",
    )


def candidate_context(
    registry: SkillRuntimeRegistry,
    *,
    skill_key: SkillKey = SkillKey.STUDY_DESTINATION_COMPARE,
    version: str = "1.0.1",
    evaluation_status: SkillEvaluationStatus | None = None,
) -> SkillCandidateContextV1:
    entry = registry.get(skill_key, version)
    return SkillCandidateContextV1(
        schema_version=1,
        candidate_id=CANDIDATE,
        skill_key=skill_key,
        binding_kind=entry.binding_kind,
        base_version_id=BASE_VERSION,
        proposed_version_id=PROPOSED_VERSION,
        proposed_version=version,
        manifest_projection=entry.model_dump(mode="json", exclude_none=True),
        evaluation_id=EVALUATION if evaluation_status is not None else None,
        evaluation_status=evaluation_status,
    )


def catalog_summary() -> SkillCatalogSummaryV1:
    return SkillCatalogSummaryV1(
        schema_version=1,
        skill_key=SkillKey.STUDY_DESTINATION_COMPARE,
        definition_id=DEFINITION,
        owner_actor_id=ADVISOR,
        binding_kind=SkillBindingKind.PLANNING_RUNTIME,
        latest_version="1.0.1",
        active_version="1.0.0",
        activation_sequence=1,
    )


class RecordingRepository:
    def __init__(self, registry: SkillRuntimeRegistry) -> None:
        self.registry = registry
        self.calls: list[tuple[object, ...]] = []
        self.context = candidate_context(registry)
        self.failure: Exception | None = None

    def _fail(self) -> None:
        if self.failure is not None:
            raise self.failure

    async def list_catalog(self, context: ActorContext) -> SkillCatalogV1:
        self.calls.append(("list_catalog", context))
        self._fail()
        return SkillCatalogV1(schema_version=1, items=(catalog_summary(),))

    async def get_catalog_item(
        self, context: ActorContext, skill_key: SkillKey
    ) -> SkillCatalogDetailV1:
        self.calls.append(("get_catalog_item", context, skill_key))
        self._fail()
        entry = self.registry.get(skill_key, "1.0.0")
        return SkillCatalogDetailV1(
            schema_version=1,
            skill_key=skill_key,
            definition_id=DEFINITION,
            owner_actor_id=ADVISOR,
            binding_kind=entry.binding_kind,
            versions=(
                SkillVersionSummaryV1.from_manifest(
                    version_id=BASE_VERSION,
                    entry=entry,
                    runtime_manifest_id=self.registry.manifest.manifest_id,
                    runtime_manifest_version=self.registry.manifest.manifest_version,
                    runtime_manifest_sha256=self.registry.manifest.manifest_sha256,
                ),
            ),
            activation_events=(
                SkillActivationEventSummaryV1(
                    schema_version=1,
                    event_id=ACTIVATION,
                    kind=SkillActivationKind.SEED,
                    activated_version_id=BASE_VERSION,
                    previous_version_id=None,
                    activation_sequence=1,
                    created_at=datetime(2026, 7, 18, tzinfo=UTC),
                ),
            ),
        )

    async def create_candidate(
        self,
        context: ActorContext,
        command: CreateSkillCandidateCommand,
        candidate_id: UUID,
        manifest_projection: Mapping[str, object],
        request_sha256: str,
        idempotency_key: str,
    ) -> SkillCandidateCreatedV1:
        self.calls.append(
            (
                "create_candidate",
                context,
                command,
                candidate_id,
                manifest_projection,
                request_sha256,
                idempotency_key,
            )
        )
        self._fail()
        return SkillCandidateCreatedV1(
            schema_version=1, candidate_id=candidate_id, replayed=False
        )

    async def load_candidate_context(
        self, context: ActorContext, candidate_id: UUID
    ) -> SkillCandidateContextV1:
        self.calls.append(("load_candidate_context", context, candidate_id))
        self._fail()
        return self.context

    async def record_evaluation(
        self,
        context: ActorContext,
        command: EvaluateSkillCandidateCommand,
        evaluation_id: UUID,
        result_projection: Mapping[str, object],
        request_sha256: str,
        idempotency_key: str,
    ) -> SkillEvaluationRecordedV1:
        self.calls.append(
            (
                "record_evaluation",
                context,
                command,
                evaluation_id,
                result_projection,
                request_sha256,
                idempotency_key,
            )
        )
        self._fail()
        return SkillEvaluationRecordedV1(
            schema_version=1,
            evaluation_id=evaluation_id,
            status=SkillEvaluationStatus(result_projection["status"]),
            replayed=False,
        )

    async def activate_candidate(
        self,
        context: ActorContext,
        command: ActivateSkillCandidateCommand,
        activation_event_id: UUID,
        manifest_projection: Mapping[str, object],
        request_sha256: str,
        idempotency_key: str,
    ) -> SkillActivationRecordedV1:
        self.calls.append(
            (
                "activate_candidate",
                context,
                command,
                activation_event_id,
                manifest_projection,
                request_sha256,
                idempotency_key,
            )
        )
        self._fail()
        return SkillActivationRecordedV1(
            schema_version=1,
            activation_event_id=activation_event_id,
            activation_sequence=command.expected_activation_sequence + 1,
            replayed=False,
        )

    async def rollback_skill(
        self,
        context: ActorContext,
        command: RollbackSkillCommand,
        activation_event_id: UUID,
        manifest_projection: Mapping[str, object],
        request_sha256: str,
        idempotency_key: str,
    ) -> SkillActivationRecordedV1:
        self.calls.append(
            (
                "rollback_skill",
                context,
                command,
                activation_event_id,
                manifest_projection,
                request_sha256,
                idempotency_key,
            )
        )
        self._fail()
        return SkillActivationRecordedV1(
            schema_version=1,
            activation_event_id=activation_event_id,
            activation_sequence=command.expected_activation_sequence + 1,
            replayed=False,
        )

    async def inspect_planning_skill(
        self, context: ActorContext, case_id: UUID
    ) -> PlanningSkillInspectorV1:
        self.calls.append(("inspect_planning_skill", context, case_id))
        self._fail()
        return PlanningSkillInspectorV1(
            schema_version=1,
            case_id=case_id,
            operation=None,
            active_skill_key=SkillKey.STUDY_DESTINATION_COMPARE,
            active_version="1.0.0",
            activation_sequence=1,
            evaluator_id="night-voyager.deterministic-skill-evaluator",
            evaluator_version="v1",
            evaluation_dataset_id="night-voyager.study-destination-compare.eval",
            evaluation_dataset_version="1.0.0",
            task_request_sha256_prefix=None,
            version_content_sha256_prefix="111111111111",
            runtime_binding_sha256_prefix="cd897b22d034",
            adapter_id=None,
            adapter_version=None,
            pin_status="not_created",
        )


def service(
    repository: RecordingRepository,
    registry: SkillRuntimeRegistry,
) -> SkillService:
    ids = iter((CANDIDATE, EVALUATION, ACTIVATION))
    return SkillService(
        repository,
        registry=registry,
        evaluator=evaluator(registry),
        id_factory=lambda: next(ids),
    )


@pytest.mark.asyncio
async def test_catalog_and_inspector_require_advisor_before_repository() -> None:
    registry = runtime_registry()
    repository = RecordingRepository(registry)
    skill_service = service(repository, registry)

    catalog = await skill_service.list_catalog(actor())
    detail = await skill_service.get_catalog_item(
        actor(), SkillKey.STUDY_DESTINATION_COMPARE
    )
    inspector = await skill_service.inspect_planning_skill(actor(), CASE)
    assert catalog.items[0].binding_kind is SkillBindingKind.PLANNING_RUNTIME
    assert detail.versions[0].input_contract_id == "night-voyager.planning-input.v1"
    assert inspector.pin_status == "not_created"

    for operation in (
        lambda: skill_service.list_catalog(actor(ActorRole.STUDENT)),
        lambda: skill_service.get_catalog_item(
            actor(ActorRole.STUDENT), SkillKey.STUDY_DESTINATION_COMPARE
        ),
        lambda: skill_service.inspect_planning_skill(actor(ActorRole.STUDENT), CASE),
    ):
        with pytest.raises(SkillAuthorizationError):
            await operation()
    assert len(repository.calls) == 3


@pytest.mark.asyncio
async def test_candidate_uses_only_packaged_manifest_and_canonical_request_hash() -> None:
    registry = runtime_registry()
    repository = RecordingRepository(registry)
    result = await service(repository, registry).create_candidate(
        actor(), create_command(), IDEMPOTENCY_KEY
    )

    assert result.candidate_id == CANDIDATE
    call = repository.calls[-1]
    assert call[0] == "create_candidate"
    assert call[4] == registry.get(
        SkillKey.STUDY_DESTINATION_COMPARE, "1.0.1"
    ).model_dump(mode="json", exclude_none=True)
    assert call[5] == canonical_sha256(create_command().model_dump(mode="json"))
    assert call[6] == IDEMPOTENCY_KEY
    assert "executor_id" not in create_command().model_dump(mode="json")


@pytest.mark.asyncio
async def test_unknown_registered_version_fails_before_repository() -> None:
    registry = runtime_registry()
    repository = RecordingRepository(registry)

    with pytest.raises(SkillVersionUnavailableError):
        await service(repository, registry).create_candidate(
            actor(), create_command(proposed_version="9.9.9"), IDEMPOTENCY_KEY
        )
    assert repository.calls == []


@pytest.mark.asyncio
async def test_evaluation_is_computed_server_side_from_owned_candidate_context() -> None:
    registry = runtime_registry()
    repository = RecordingRepository(registry)
    result = await service(repository, registry).evaluate_candidate(
        actor(), EvaluateSkillCandidateCommand(candidate_id=CANDIDATE), IDEMPOTENCY_KEY
    )

    assert result.status is SkillEvaluationStatus.PASSED
    assert repository.calls[0] == ("load_candidate_context", actor(), CANDIDATE)
    record_call = repository.calls[1]
    assert record_call[0] == "record_evaluation"
    projection = cast(Mapping[str, object], record_call[4])
    assert projection["skill_key"] == SkillKey.STUDY_DESTINATION_COMPARE.value
    assert projection["version"] == "1.0.1"
    assert projection["status"] == "passed"
    assert projection["failed_assertion_ids"] == []
    assert record_call[5] == canonical_sha256(
        EvaluateSkillCandidateCommand(candidate_id=CANDIDATE).model_dump(mode="json")
    )


@pytest.mark.asyncio
async def test_manifest_drift_fails_closed_before_evaluation_or_mutation() -> None:
    registry = runtime_registry()
    repository = RecordingRepository(registry)
    drifted = dict(repository.context.manifest_projection)
    drifted["content_sha256"] = "f" * 64
    repository.context = repository.context.model_copy(
        update={"manifest_projection": drifted}
    )

    with pytest.raises(SkillVersionUnavailableError):
        await service(repository, registry).evaluate_candidate(
            actor(), EvaluateSkillCandidateCommand(candidate_id=CANDIDATE), IDEMPOTENCY_KEY
        )
    assert [call[0] for call in repository.calls] == ["load_candidate_context"]


@pytest.mark.asyncio
async def test_activation_and_rollback_bind_exact_registered_manifests_and_cas() -> None:
    registry = runtime_registry()
    repository = RecordingRepository(registry)
    skill_service = service(repository, registry)
    activation_command = ActivateSkillCandidateCommand(
        candidate_id=CANDIDATE,
        expected_active_version="1.0.0",
        expected_activation_sequence=1,
        reason="Promote the evaluated compatibility revision.",
    )
    activation = await skill_service.activate_candidate(
        actor(), activation_command, IDEMPOTENCY_KEY
    )
    assert activation.activation_sequence == 2
    activation_call = repository.calls[-1]
    assert activation_call[0] == "activate_candidate"
    assert activation_call[4] == registry.get(
        SkillKey.STUDY_DESTINATION_COMPARE, "1.0.1"
    ).model_dump(mode="json", exclude_none=True)

    rollback_command = RollbackSkillCommand(
        skill_key=SkillKey.STUDY_DESTINATION_COMPARE,
        target_version="1.0.0",
        expected_active_version="1.0.1",
        expected_activation_sequence=2,
        reason="Restore the prior supported version.",
    )
    rollback = await skill_service.rollback_skill(
        actor(), rollback_command, "rollback-key"
    )
    assert rollback.activation_sequence == 3
    rollback_call = repository.calls[-1]
    assert rollback_call[0] == "rollback_skill"
    assert rollback_call[4] == registry.get(
        SkillKey.STUDY_DESTINATION_COMPARE, "1.0.0"
    ).model_dump(mode="json", exclude_none=True)


@pytest.mark.asyncio
async def test_catalog_only_candidate_cannot_be_activated() -> None:
    registry = runtime_registry()
    repository = RecordingRepository(registry)
    repository.context = candidate_context(
        registry,
        skill_key=SkillKey.STUDENT_PROFILE_INTAKE,
        version="1.0.0",
    )
    command = ActivateSkillCandidateCommand(
        candidate_id=CANDIDATE,
        expected_active_version="1.0.0",
        expected_activation_sequence=1,
        reason="This must remain catalog only.",
    )

    with pytest.raises(SkillVersionUnavailableError):
        await service(repository, registry).activate_candidate(
            actor(), command, IDEMPOTENCY_KEY
        )
    assert [call[0] for call in repository.calls] == ["load_candidate_context"]


def test_commands_are_strict_and_bound_public_text() -> None:
    with pytest.raises(ValidationError):
        CreateSkillCandidateCommand.model_validate_json(
            json.dumps(
                {
                **create_command().model_dump(mode="json"),
                "executor_id": "browser-controlled",
                }
            )
        )
    with pytest.raises(ValidationError):
        CreateSkillCandidateCommand.model_validate_json(
            json.dumps(
                {
                    **create_command().model_dump(mode="json"),
                    "reason": "x" * 513,
                }
            )
        )


class SqlStateOrigin(Exception):
    def __init__(self, sqlstate: str | None) -> None:
        super().__init__("raw database detail must not escape")
        self.sqlstate = sqlstate


def db_error(sqlstate: str | None) -> DBAPIError:
    return DBAPIError(
        "SELECT internal_detail()",
        {},
        SqlStateOrigin(sqlstate),
        connection_invalidated=sqlstate is None,
    )


@pytest.mark.parametrize(
    ("sqlstate", "error_type"),
    [
        ("NV007", SkillAuthorizationError),
        ("NV008", SkillIdempotencyConflictError),
        ("NV015", SkillVersionUnavailableError),
        ("NV016", SkillCandidateStaleError),
        ("NV017", SkillCandidateTerminalError),
        ("NV018", SkillEvaluationFailedError),
        ("NV019", SkillActivationStaleError),
        ("NV020", SkillScopeExpansionError),
        ("NV021", SkillRollbackUnsupportedError),
        ("NV022", SkillPinInvalidError),
        ("23505", SkillPersistenceError),
        (None, SkillPersistenceError),
    ],
)
@pytest.mark.asyncio
async def test_postgres_maps_only_frozen_sqlstates(
    sqlstate: str | None, error_type: type[Exception]
) -> None:
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = db_error(sqlstate)
    repository = PostgresSkillRepository(cast(AsyncSession, session))

    with pytest.raises(error_type) as captured:
        await repository.list_catalog(actor())
    assert str(captured.value) in {
        "resource_unavailable",
        "idempotency_conflict",
        "skill_version_unavailable",
        "skill_candidate_stale",
        "skill_candidate_terminal",
        "skill_evaluation_failed",
        "skill_activation_stale",
        "skill_scope_expansion",
        "skill_rollback_unsupported",
        "skill_pin_invalid",
        "persistence_unavailable",
    }
    assert "raw database detail" not in str(captured.value)


def result_with_row(row: Mapping[str, object]) -> MagicMock:
    result = MagicMock()
    result.mappings.return_value.one.return_value = row
    return result


@pytest.mark.asyncio
async def test_postgres_uses_frozen_function_signatures_and_server_parameters() -> None:
    registry = runtime_registry()
    command = create_command()
    entry = registry.get(command.skill_key, command.proposed_version)
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = result_with_row(
        {"candidate_id": CANDIDATE, "replayed": False}
    )
    repository = PostgresSkillRepository(cast(AsyncSession, session))

    created = await repository.create_candidate(
        actor(),
        command,
        CANDIDATE,
        entry.model_dump(mode="json", exclude_none=True),
        "a" * 64,
        IDEMPOTENCY_KEY,
    )
    assert created.candidate_id == CANDIDATE
    statement, params = session.execute.await_args.args
    assert "app.create_skill_change_candidate" in str(statement)
    assert set(params) == {
        "org",
        "actor",
        "skill_key",
        "candidate",
        "proposed_version",
        "provenance",
        "reason",
        "reference",
        "manifest",
        "request_sha256",
        "key_sha256",
    }
    assert params["manifest"] == json.dumps(
        entry.model_dump(mode="json", exclude_none=True),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    assert "executor_id" not in command.model_dump(mode="json")


@pytest.mark.asyncio
async def test_postgres_rejects_unknown_result_shapes_as_persistence_failure() -> None:
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = result_with_row(
        {
            "candidate_id": CANDIDATE,
            "replayed": False,
            "raw_database_detail": "must not escape",
        }
    )
    repository = PostgresSkillRepository(cast(AsyncSession, session))

    with pytest.raises(SkillPersistenceError, match="persistence_unavailable"):
        await repository.create_candidate(
            actor(),
            create_command(),
            CANDIDATE,
            runtime_registry()
            .get(SkillKey.STUDY_DESTINATION_COMPARE, "1.0.1")
            .model_dump(mode="json", exclude_none=True),
            "a" * 64,
            IDEMPOTENCY_KEY,
        )


@pytest.mark.asyncio
async def test_postgres_parses_strict_catalog_and_audit_safe_inspector_projections() -> None:
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = (
        result_with_row(
            {
                "projection": [
                    {
                        "skill_key": "study-destination-compare",
                        "definition_id": str(DEFINITION),
                        "owner_actor_id": str(ADVISOR),
                        "binding_kind": "planning_runtime",
                        "latest_version": "1.0.1",
                        "active_version": "1.0.0",
                        "activation_sequence": 1,
                    }
                ]
            }
        ),
        result_with_row(
            {
                "projection": {
                    "case_id": str(CASE),
                    "operation": "generate_planning_run_v1",
                    "active_skill_key": "study-destination-compare",
                    "active_version": "1.0.0",
                    "activation_sequence": 1,
                    "evaluator_id": "night-voyager.deterministic-skill-evaluator",
                    "evaluator_version": "v1",
                    "evaluation_dataset_id": (
                        "night-voyager.study-destination-compare.eval"
                    ),
                    "evaluation_dataset_version": "1.0.0",
                    "task_request_sha256_prefix": "aaaaaaaaaaaa",
                    "version_content_sha256_prefix": "bbbbbbbbbbbb",
                    "runtime_binding_sha256_prefix": "cd897b22d034",
                    "adapter_id": "deterministic_planning",
                    "adapter_version": "m4a-v1",
                    "pin_status": "matched",
                }
            }
        ),
    )
    repository = PostgresSkillRepository(cast(AsyncSession, session))

    catalog = await repository.list_catalog(actor())
    inspector = await repository.inspect_planning_skill(actor(), CASE)
    assert catalog.items[0].skill_key is SkillKey.STUDY_DESTINATION_COMPARE
    assert inspector.pin_status == "matched"
    assert inspector.task_request_sha256_prefix == "aaaaaaaaaaaa"
    assert "skill_definition_id" not in inspector.model_dump(mode="json")
