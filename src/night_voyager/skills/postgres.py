from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any, NoReturn, TypeVar, cast
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from night_voyager.identity.models import ActorContext
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
from night_voyager.skills.models import (
    SkillActivationKind,
    SkillApprovalPolicy,
    SkillBindingKind,
    SkillEvaluationStatus,
    SkillKey,
    SkillSideEffectLevel,
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

ModelT = TypeVar("ModelT", bound=BaseModel)


class PostgresSkillRepository:
    """Narrow PostgreSQL adapter for governed Skill lifecycle authority."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_catalog(self, context: ActorContext) -> SkillCatalogV1:
        result = await self._execute(
            "SELECT app.list_skill_catalog(:org,:actor) AS projection",
            self._context_parameters(context),
        )
        projection = self._projection(result)
        if not isinstance(projection, list):
            self._raise_persistence(ValueError("unexpected Skill catalog projection"))
        try:
            catalog_rows = cast(list[object], projection)
            items = tuple(
                self._parse_json_model(item, SkillCatalogSummaryV1)
                for item in catalog_rows
            )
            if tuple(item.skill_key.value for item in items) != tuple(
                sorted(item.skill_key.value for item in items)
            ):
                raise ValueError("Skill catalog must be sorted by key")
            return SkillCatalogV1(schema_version=1, items=items)
        except (KeyError, TypeError, ValueError, SQLAlchemyError) as error:
            self._raise_persistence(error)

    async def get_catalog_item(
        self,
        context: ActorContext,
        skill_key: SkillKey,
    ) -> SkillCatalogDetailV1:
        result = await self._execute(
            "SELECT app.get_skill_catalog_item(:org,:actor,:skill_key) AS projection",
            {**self._context_parameters(context), "skill_key": skill_key.value},
        )
        projection = self._mapping_projection(result)
        try:
            raw = dict(projection)
            versions = raw.get("versions")
            events = raw.get("activation_events")
            if not isinstance(versions, list) or not isinstance(events, list):
                raise ValueError("unexpected Skill catalog detail projection")
            version_rows = cast(list[object], versions)
            event_rows = cast(list[object], events)
            raw["versions"] = tuple(
                self._parse_json_model(item, SkillVersionSummaryV1)
                for item in version_rows
            )
            raw["activation_events"] = tuple(
                self._parse_json_model(item, SkillActivationEventSummaryV1)
                for item in event_rows
            )
            return self._parse_json_model(raw, SkillCatalogDetailV1)
        except (KeyError, TypeError, ValueError, SQLAlchemyError) as error:
            self._raise_persistence(error)

    async def create_candidate(
        self,
        context: ActorContext,
        command: CreateSkillCandidateCommand,
        candidate_id: UUID,
        manifest_projection: Mapping[str, object],
        request_sha256: str,
        idempotency_key: str,
    ) -> SkillCandidateCreatedV1:
        result = await self._execute(
            "SELECT * FROM app.create_skill_change_candidate("
            ":org,:actor,:skill_key,:candidate,:proposed_version,:provenance,"
            ":reason,:reference,CAST(:manifest AS jsonb),:request_sha256,:key_sha256)",
            {
                **self._context_parameters(context),
                "skill_key": command.skill_key.value,
                "candidate": candidate_id,
                "proposed_version": command.proposed_version,
                "provenance": command.provenance.value,
                "reason": command.reason,
                "reference": command.reference,
                "manifest": self._json_value(manifest_projection),
                "request_sha256": request_sha256,
                "key_sha256": self._key_sha256(idempotency_key),
            },
        )
        return self._parse_row(result, SkillCandidateCreatedV1)

    async def load_candidate_context(
        self,
        context: ActorContext,
        candidate_id: UUID,
    ) -> SkillCandidateContextV1:
        result = await self._execute(
            "SELECT app.load_skill_candidate_context("
            ":org,:actor,:candidate) AS projection",
            {
                **self._context_parameters(context),
                "candidate": candidate_id,
            },
        )
        return self._parse_json_model(
            self._mapping_projection(result), SkillCandidateContextV1
        )

    async def record_evaluation(
        self,
        context: ActorContext,
        command: EvaluateSkillCandidateCommand,
        evaluation_id: UUID,
        result_projection: Mapping[str, object],
        request_sha256: str,
        idempotency_key: str,
    ) -> SkillEvaluationRecordedV1:
        result = await self._execute(
            "SELECT * FROM app.record_skill_candidate_evaluation("
            ":org,:actor,:candidate,:evaluation,CAST(:result AS jsonb),"
            ":request_sha256,:key_sha256)",
            {
                **self._context_parameters(context),
                "candidate": command.candidate_id,
                "evaluation": evaluation_id,
                "result": self._json_value(result_projection),
                "request_sha256": request_sha256,
                "key_sha256": self._key_sha256(idempotency_key),
            },
        )
        return self._parse_row(result, SkillEvaluationRecordedV1)

    async def activate_candidate(
        self,
        context: ActorContext,
        command: ActivateSkillCandidateCommand,
        activation_event_id: UUID,
        manifest_projection: Mapping[str, object],
        request_sha256: str,
        idempotency_key: str,
    ) -> SkillActivationRecordedV1:
        result = await self._execute(
            "SELECT * FROM app.promote_skill_change_candidate("
            ":org,:actor,:candidate,:event,:expected_active_version,"
            ":expected_sequence,:reason,CAST(:manifest AS jsonb),"
            ":request_sha256,:key_sha256)",
            {
                **self._context_parameters(context),
                "candidate": command.candidate_id,
                "event": activation_event_id,
                "expected_active_version": command.expected_active_version,
                "expected_sequence": command.expected_activation_sequence,
                "reason": command.reason,
                "manifest": self._json_value(manifest_projection),
                "request_sha256": request_sha256,
                "key_sha256": self._key_sha256(idempotency_key),
            },
        )
        return self._parse_row(result, SkillActivationRecordedV1)

    async def rollback_skill(
        self,
        context: ActorContext,
        command: RollbackSkillCommand,
        activation_event_id: UUID,
        manifest_projection: Mapping[str, object],
        request_sha256: str,
        idempotency_key: str,
    ) -> SkillActivationRecordedV1:
        result = await self._execute(
            "SELECT * FROM app.rollback_skill_activation("
            ":org,:actor,:skill_key,:event,:target_version,"
            ":expected_active_version,:expected_sequence,:reason,"
            "CAST(:manifest AS jsonb),:request_sha256,:key_sha256)",
            {
                **self._context_parameters(context),
                "skill_key": command.skill_key.value,
                "event": activation_event_id,
                "target_version": command.target_version,
                "expected_active_version": command.expected_active_version,
                "expected_sequence": command.expected_activation_sequence,
                "reason": command.reason,
                "manifest": self._json_value(manifest_projection),
                "request_sha256": request_sha256,
                "key_sha256": self._key_sha256(idempotency_key),
            },
        )
        return self._parse_row(result, SkillActivationRecordedV1)

    async def inspect_planning_skill(
        self,
        context: ActorContext,
        case_id: UUID,
    ) -> PlanningSkillInspectorV1:
        result = await self._execute(
            "SELECT app.inspect_planning_skill(:org,:actor,:case) AS projection",
            {**self._context_parameters(context), "case": case_id},
        )
        return self._parse_json_model(
            self._mapping_projection(result), PlanningSkillInspectorV1
        )

    async def _execute(
        self,
        statement: str,
        parameters: dict[str, object],
    ) -> Any:
        try:
            return await self._session.execute(text(statement), parameters)
        except DBAPIError as error:
            self._raise_mapped(error)
        except SQLAlchemyError as error:
            self._raise_persistence(error)

    @classmethod
    def _projection(cls, result: Any) -> object:
        row = cls._one(result)
        if set(row) != {"projection"}:
            cls._raise_persistence(ValueError("unexpected Skill projection row"))
        return row["projection"]

    @classmethod
    def _mapping_projection(cls, result: Any) -> Mapping[str, object]:
        projection = cls._projection(result)
        if not isinstance(projection, Mapping):
            cls._raise_persistence(ValueError("unexpected Skill object projection"))
        return cast(Mapping[str, object], projection)

    @classmethod
    def _one(cls, result: Any) -> Mapping[str, object]:
        try:
            row = result.mappings().one()
            if not isinstance(row, Mapping):
                raise ValueError("unexpected Skill result row")
            return cast(Mapping[str, object], row)
        except (KeyError, TypeError, ValueError, SQLAlchemyError) as error:
            cls._raise_persistence(error)

    @classmethod
    def _parse_row(cls, result: Any, model: type[ModelT]) -> ModelT:
        row = cls._one(result)
        return cls._parse_json_model(row, model)

    @classmethod
    def _parse_json_model(
        cls,
        projection: object,
        model: type[ModelT],
    ) -> ModelT:
        try:
            if not isinstance(projection, Mapping):
                raise ValueError("unexpected Skill model projection")
            raw = {"schema_version": 1, **dict(cast(Mapping[str, object], projection))}
            if set(raw) != set(model.model_fields):
                raise ValueError("unexpected Skill result shape")
            normalized = cls._normalize_closed_scalars(raw)
            return model.model_validate(normalized, strict=True)
        except (KeyError, TypeError, ValueError, SQLAlchemyError) as error:
            cls._raise_persistence(error)

    @staticmethod
    def _normalize_closed_scalars(projection: dict[str, object]) -> dict[str, object]:
        enum_fields: dict[str, type[Any]] = {
            "skill_key": SkillKey,
            "active_skill_key": SkillKey,
            "binding_kind": SkillBindingKind,
            "kind": SkillActivationKind,
            "status": SkillEvaluationStatus,
            "evaluation_status": SkillEvaluationStatus,
            "side_effect_level": SkillSideEffectLevel,
            "approval_policy": SkillApprovalPolicy,
        }
        for field, enum_type in enum_fields.items():
            value = projection.get(field)
            if isinstance(value, str):
                projection[field] = enum_type(value)
        for field in (
            "definition_id",
            "owner_actor_id",
            "version_id",
            "event_id",
            "activated_version_id",
            "previous_version_id",
            "candidate_id",
            "base_version_id",
            "proposed_version_id",
            "evaluation_id",
            "activation_event_id",
            "case_id",
        ):
            value = projection.get(field)
            if isinstance(value, str):
                projection[field] = UUID(value)
        created_at = projection.get("created_at")
        if isinstance(created_at, str):
            parsed = datetime.fromisoformat(created_at)
            if parsed.tzinfo is None:
                raise ValueError("Skill timestamp must include timezone")
            projection["created_at"] = parsed
        return projection

    @staticmethod
    def _context_parameters(context: ActorContext) -> dict[str, object]:
        return {"org": context.organization_id, "actor": context.actor_id}

    @staticmethod
    def _key_sha256(idempotency_key: str) -> str:
        return hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()

    @staticmethod
    def _json_value(value: Mapping[str, object]) -> str:
        return json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @staticmethod
    def _raise_mapped(error: DBAPIError) -> NoReturn:
        sqlstate = str(getattr(error.orig, "sqlstate", ""))
        mapped: dict[str, tuple[type[Exception], str]] = {
            "NV007": (SkillAuthorizationError, "resource_unavailable"),
            "NV008": (SkillIdempotencyConflictError, "idempotency_conflict"),
            "NV015": (SkillVersionUnavailableError, "skill_version_unavailable"),
            "NV016": (SkillCandidateStaleError, "skill_candidate_stale"),
            "NV017": (SkillCandidateTerminalError, "skill_candidate_terminal"),
            "NV018": (SkillEvaluationFailedError, "skill_evaluation_failed"),
            "NV019": (SkillActivationStaleError, "skill_activation_stale"),
            "NV020": (SkillScopeExpansionError, "skill_scope_expansion"),
            "NV021": (SkillRollbackUnsupportedError, "skill_rollback_unsupported"),
            "NV022": (SkillPinInvalidError, "skill_pin_invalid"),
        }
        mapping = mapped.get(sqlstate)
        if mapping is None:
            PostgresSkillRepository._raise_persistence(error)
        error_type, code = mapping
        raise error_type(code) from error

    @staticmethod
    def _raise_persistence(error: BaseException) -> NoReturn:
        raise SkillPersistenceError("persistence_unavailable") from error


__all__ = ["PostgresSkillRepository"]
