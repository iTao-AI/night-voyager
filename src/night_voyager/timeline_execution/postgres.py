from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Literal, TypeVar, cast
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from night_voyager.identity.models import ActorContext
from night_voyager.timeline_execution.errors import (
    TimelineExecutionConflictError,
    TimelineExecutionProjectionError,
    TimelineExecutionUnavailableError,
)
from night_voyager.timeline_execution.hashing import canonical_sha256
from night_voyager.timeline_execution.models import (
    PlanExecutionContextV1,
    TimelineExecutionViewV1,
    TimelineMutationReceiptV1,
)
from night_voyager.timeline_execution.policy import derive_current_action
from night_voyager.timeline_execution.ports import (
    AttestTimelineCheckpointCommand,
    RequestTimelineReassessmentCommand,
    StartTimelineExecutionCommand,
    VerifyTimelineCheckpointCommand,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


class PostgresTimelineExecutionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def context(
        self,
        actor: ActorContext,
        scenario: Literal["governed-plan-execution-v1"],
    ) -> PlanExecutionContextV1 | None:
        raw = await self._call(
            "SELECT app.read_plan_execution_context(:org,:actor,:role,:scenario)",
            {
                "org": actor.organization_id,
                "actor": actor.actor_id,
                "role": actor.role,
                "scenario": scenario,
            },
        )
        return self._decode_optional(PlanExecutionContextV1, raw)

    async def read(
        self, actor: ActorContext, case_id: UUID
    ) -> TimelineExecutionViewV1 | None:
        raw = await self._call(
            "SELECT app.read_timeline_execution(:org,:actor,:role,:case)",
            {
                "org": actor.organization_id,
                "actor": actor.actor_id,
                "role": actor.role,
                "case": case_id,
            },
        )
        view = self._decode_optional(TimelineExecutionViewV1, raw)
        if view is not None and derive_current_action(view) != view.current_action:
            raise TimelineExecutionProjectionError(
                "timeline execution current action is contradictory"
            )
        return view

    async def start(
        self,
        actor: ActorContext,
        command: StartTimelineExecutionCommand,
        idempotency_key: str,
    ) -> TimelineMutationReceiptV1:
        raw = await self._call(
            "SELECT app.start_timeline_execution("
            ":org,:actor,:role,:timeline,:case,:case_revision,"
            ":execution,:receipt,:key_hash,:request_hash)",
            {
                "org": actor.organization_id,
                "actor": actor.actor_id,
                "role": actor.role,
                "timeline": command.timeline_plan_id,
                "case": command.case_id,
                "case_revision": command.expected_case_revision,
                "execution": command.execution_id,
                "receipt": command.receipt_id,
                "key_hash": self._key_hash(idempotency_key),
                "request_hash": canonical_sha256(
                    command.model_dump(
                        mode="json", exclude={"execution_id", "receipt_id"}
                    )
                ),
            },
        )
        return self._decode_required(TimelineMutationReceiptV1, raw)

    async def attest(
        self,
        actor: ActorContext,
        command: AttestTimelineCheckpointCommand,
        idempotency_key: str,
    ) -> TimelineMutationReceiptV1:
        raw = await self._call(
            "SELECT app.attest_timeline_checkpoint("
            ":org,:actor,:role,:execution,:checkpoint,:execution_version,"
            ":checkpoint_version,:kind,:status,:attestation_code,:reason_code,"
            ":attestation,:receipt,:key_hash,:request_hash)",
            {
                "org": actor.organization_id,
                "actor": actor.actor_id,
                "role": actor.role,
                "execution": command.execution_id,
                "checkpoint": command.checkpoint_id,
                "execution_version": command.expected_execution_version,
                "checkpoint_version": command.expected_checkpoint_version,
                "kind": command.attestation_kind,
                "status": command.status_code,
                "attestation_code": command.attestation_code,
                "reason_code": command.reason_code,
                "attestation": command.attestation_id,
                "receipt": command.receipt_id,
                "key_hash": self._key_hash(idempotency_key),
                "request_hash": canonical_sha256(
                    command.model_dump(
                        mode="json", exclude={"attestation_id", "receipt_id"}
                    )
                ),
            },
        )
        return self._decode_required(TimelineMutationReceiptV1, raw)

    async def verify(
        self,
        actor: ActorContext,
        command: VerifyTimelineCheckpointCommand,
        idempotency_key: str,
    ) -> TimelineMutationReceiptV1:
        raw = await self._call(
            "SELECT app.verify_timeline_checkpoint("
            ":org,:actor,:role,:case,:execution,:checkpoint,:attestation,"
            ":execution_version,:checkpoint_version,:action,:reason_code,"
            ":verification,:receipt,:key_hash,:request_hash)",
            {
                "org": actor.organization_id,
                "actor": actor.actor_id,
                "role": actor.role,
                "case": command.case_id,
                "execution": command.execution_id,
                "checkpoint": command.checkpoint_id,
                "attestation": command.attestation_id,
                "execution_version": command.expected_execution_version,
                "checkpoint_version": command.expected_checkpoint_version,
                "action": command.action,
                "reason_code": command.reason_code,
                "verification": command.verification_id,
                "receipt": command.receipt_id,
                "key_hash": self._key_hash(idempotency_key),
                "request_hash": canonical_sha256(
                    command.model_dump(
                        mode="json", exclude={"verification_id", "receipt_id"}
                    )
                ),
            },
        )
        return self._decode_required(TimelineMutationReceiptV1, raw)

    async def reassess(
        self,
        actor: ActorContext,
        command: RequestTimelineReassessmentCommand,
        idempotency_key: str,
    ) -> TimelineMutationReceiptV1:
        raw = await self._call(
            "SELECT app.request_timeline_reassessment("
            ":org,:actor,:role,:case,:execution,:checkpoint,:trigger_reference,"
            ":execution_version,:checkpoint_version,:trigger,:reassessment,"
            ":receipt,:key_hash,:request_hash)",
            {
                "org": actor.organization_id,
                "actor": actor.actor_id,
                "role": actor.role,
                "case": command.case_id,
                "execution": command.execution_id,
                "checkpoint": command.checkpoint_id,
                "trigger_reference": command.trigger_reference_id,
                "execution_version": command.expected_execution_version,
                "checkpoint_version": command.expected_checkpoint_version,
                "trigger": command.trigger,
                "reassessment": command.reassessment_id,
                "receipt": command.receipt_id,
                "key_hash": self._key_hash(idempotency_key),
                "request_hash": canonical_sha256(
                    command.model_dump(
                        mode="json", exclude={"reassessment_id", "receipt_id"}
                    )
                ),
            },
        )
        return self._decode_required(TimelineMutationReceiptV1, raw)

    async def _call(self, statement: str, parameters: dict[str, object]) -> object:
        try:
            return await self._session.scalar(text(statement), parameters)
        except DBAPIError as error:
            sqlstate = getattr(error.orig, "sqlstate", None)
            if sqlstate in {"NV003", "NV007"}:
                raise TimelineExecutionUnavailableError(
                    "execution authority unavailable"
                ) from error
            conflict_codes = {
                "NV006": "checkpoint_not_current",
                "NV008": "idempotency_conflict",
                "NV020": "stale_execution_version",
                "NV021": "stale_checkpoint_version",
                "NV022": "execution_completed",
                "NV023": "checkpoint_not_current",
                "NV024": "checkpoint_attestation_conflict",
                "NV025": "advisor_verification_required",
                "NV026": "reassessment_required",
                "23505": "checkpoint_not_current",
                "40001": "stale_execution_version",
            }
            if sqlstate in conflict_codes:
                raise TimelineExecutionConflictError(conflict_codes[str(sqlstate)]) from error
            raise

    @staticmethod
    def _key_hash(idempotency_key: str) -> str:
        return hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()

    @classmethod
    def _decode_optional(cls, model: type[ModelT], raw: object) -> ModelT | None:
        if raw is None:
            return None
        return cls._decode_required(model, raw)

    @staticmethod
    def _decode_required(model: type[ModelT], raw: object) -> ModelT:
        try:
            payload: object
            if isinstance(raw, str):
                payload = json.loads(raw)
            elif isinstance(raw, Mapping):
                payload = dict(cast(Mapping[str, object], raw))
            else:
                payload = raw
            return model.model_validate(payload)
        except (ValidationError, ValueError, TypeError, json.JSONDecodeError) as error:
            raise TimelineExecutionProjectionError(
                "timeline execution projection is malformed"
            ) from error
