from __future__ import annotations

from collections.abc import Callable, Mapping
from uuid import UUID, uuid4

from night_voyager.identity.models import ActorContext, ActorRole
from night_voyager.skills.errors import (
    SkillAuthorizationError,
    SkillRollbackUnsupportedError,
    SkillVersionUnavailableError,
)
from night_voyager.skills.evaluation import (
    SkillEvaluationIncompatibility,
    SkillEvaluator,
)
from night_voyager.skills.models import (
    SkillBindingKind,
    SkillKey,
    SkillRuntimeManifestEntryV1,
    canonical_sha256,
)
from night_voyager.skills.ports import (
    ActivateSkillCandidateCommand,
    CreateSkillCandidateCommand,
    EvaluateSkillCandidateCommand,
    PlanningSkillInspectorV1,
    RollbackSkillCommand,
    SkillActivationRecordedV1,
    SkillCandidateContextV1,
    SkillCandidateCreatedV1,
    SkillCatalogDetailV1,
    SkillCatalogV1,
    SkillEvaluationRecordedV1,
    SkillRepository,
)
from night_voyager.skills.registry import (
    SkillRuntimeIncompatibility,
    SkillRuntimeRegistry,
)


class SkillService:
    def __init__(
        self,
        repository: SkillRepository,
        *,
        registry: SkillRuntimeRegistry,
        evaluator: SkillEvaluator,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._registry = registry
        self._evaluator = evaluator
        self._id_factory = id_factory

    async def list_catalog(self, context: ActorContext) -> SkillCatalogV1:
        self._require_advisor(context)
        return await self._repository.list_catalog(context)

    async def get_catalog_item(
        self,
        context: ActorContext,
        skill_key: SkillKey,
    ) -> SkillCatalogDetailV1:
        self._require_advisor(context)
        return await self._repository.get_catalog_item(context, skill_key)

    async def create_candidate(
        self,
        context: ActorContext,
        command: CreateSkillCandidateCommand,
        idempotency_key: str,
    ) -> SkillCandidateCreatedV1:
        self._require_advisor(context)
        entry = self._supported_entry(
            command.skill_key,
            command.proposed_version,
            unavailable=SkillVersionUnavailableError,
        )
        return await self._repository.create_candidate(
            context,
            command,
            self._id_factory(),
            self._manifest_projection(entry),
            canonical_sha256(command.model_dump(mode="json")),
            idempotency_key,
        )

    async def evaluate_candidate(
        self,
        context: ActorContext,
        command: EvaluateSkillCandidateCommand,
        idempotency_key: str,
    ) -> SkillEvaluationRecordedV1:
        self._require_advisor(context)
        candidate = await self._repository.load_candidate_context(
            context, command.candidate_id
        )
        self._candidate_entry(candidate)
        try:
            evaluation = self._evaluator.evaluate(
                candidate.skill_key,
                candidate.proposed_version,
            )
        except SkillEvaluationIncompatibility as error:
            raise SkillVersionUnavailableError("skill_version_unavailable") from error
        return await self._repository.record_evaluation(
            context,
            command,
            self._id_factory(),
            evaluation.model_dump(mode="json"),
            canonical_sha256(command.model_dump(mode="json")),
            idempotency_key,
        )

    async def activate_candidate(
        self,
        context: ActorContext,
        command: ActivateSkillCandidateCommand,
        idempotency_key: str,
    ) -> SkillActivationRecordedV1:
        self._require_advisor(context)
        candidate = await self._repository.load_candidate_context(
            context, command.candidate_id
        )
        entry = self._candidate_entry(candidate)
        if entry.binding_kind is not SkillBindingKind.PLANNING_RUNTIME:
            raise SkillVersionUnavailableError("skill_version_unavailable")
        return await self._repository.activate_candidate(
            context,
            command,
            self._id_factory(),
            self._manifest_projection(entry),
            canonical_sha256(command.model_dump(mode="json")),
            idempotency_key,
        )

    async def rollback_skill(
        self,
        context: ActorContext,
        command: RollbackSkillCommand,
        idempotency_key: str,
    ) -> SkillActivationRecordedV1:
        self._require_advisor(context)
        entry = self._supported_entry(
            command.skill_key,
            command.target_version,
            unavailable=SkillRollbackUnsupportedError,
        )
        return await self._repository.rollback_skill(
            context,
            command,
            self._id_factory(),
            self._manifest_projection(entry),
            canonical_sha256(command.model_dump(mode="json")),
            idempotency_key,
        )

    async def inspect_planning_skill(
        self,
        context: ActorContext,
        case_id: UUID,
    ) -> PlanningSkillInspectorV1:
        self._require_advisor(context)
        return await self._repository.inspect_planning_skill(context, case_id)

    def _candidate_entry(
        self,
        candidate: SkillCandidateContextV1,
    ) -> SkillRuntimeManifestEntryV1:
        entry = self._supported_entry(
            candidate.skill_key,
            candidate.proposed_version,
            unavailable=SkillVersionUnavailableError,
        )
        if self._manifest_projection(entry) != candidate.manifest_projection:
            raise SkillVersionUnavailableError("skill_version_unavailable")
        return entry

    def _supported_entry(
        self,
        skill_key: SkillKey,
        version: str,
        *,
        unavailable: type[SkillVersionUnavailableError | SkillRollbackUnsupportedError],
    ) -> SkillRuntimeManifestEntryV1:
        try:
            return self._registry.get(skill_key, version)
        except SkillRuntimeIncompatibility as error:
            code = (
                "skill_rollback_unsupported"
                if unavailable is SkillRollbackUnsupportedError
                else "skill_version_unavailable"
            )
            raise unavailable(code) from error

    @staticmethod
    def _manifest_projection(
        entry: SkillRuntimeManifestEntryV1,
    ) -> Mapping[str, object]:
        return entry.model_dump(mode="json", exclude_none=True)

    @staticmethod
    def _require_advisor(context: ActorContext) -> None:
        if context.role is not ActorRole.ADVISOR:
            raise SkillAuthorizationError("resource_unavailable")


__all__ = ["SkillService"]
