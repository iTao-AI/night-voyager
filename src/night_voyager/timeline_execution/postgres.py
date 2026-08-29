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
    ConnectedPlanExecutionContextV1,
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

    async def connected_context(
        self, actor: ActorContext, case_id: UUID
    ) -> ConnectedPlanExecutionContextV1 | None:
        rows = await self._select_rows(
            """
            SELECT
              1 AS schema_version,
              'connected-advisor-family' AS journey,
              c.id AS case_id,
              c.current_revision AS case_revision,
              d.id AS decision_id,
              d.receipt_id AS decision_receipt_id,
              tp.id AS timeline_plan_id,
              te.id AS execution_id,
              p.role AS active_role,
              'assigned' AS assignment_status,
              te.case_id AS execution_case_id,
              te.case_revision AS execution_case_revision,
              te.family_decision_id AS execution_decision_id,
              te.decision_receipt_id AS execution_decision_receipt_id,
              te.timeline_plan_id AS execution_timeline_plan_id
            FROM app.student_cases AS c
            JOIN app.student_case_participants AS p
              ON p.organization_id = c.organization_id
             AND p.case_id = c.id
             AND p.actor_id = :actor
             AND p.role = :role
            JOIN app.student_case_revisions AS r
              ON r.organization_id = c.organization_id
             AND r.case_id = c.id
             AND r.revision = c.current_revision
            JOIN app.decision_briefs AS b
             ON b.organization_id = c.organization_id
             AND b.case_id = c.id
             AND b.case_revision = c.current_revision
            JOIN app.family_decisions AS d
              ON d.organization_id = b.organization_id
             AND d.case_id = b.case_id
             AND d.decision_brief_id = b.id
             AND d.brief_version = b.brief_version
             AND d.planning_run_id = b.planning_run_id
            JOIN app.timeline_plans AS tp
              ON tp.organization_id = d.organization_id
             AND tp.family_decision_id = d.id
            LEFT JOIN app.timeline_executions AS te
              ON te.organization_id = tp.organization_id
             AND te.timeline_plan_id = tp.id
            WHERE c.organization_id = :org
              AND c.id = :case
              AND c.state = 'plan_ready'
            """,
            {
                "org": actor.organization_id,
                "actor": actor.actor_id,
                "role": actor.role,
                "case": case_id,
            },
        )
        if not rows:
            return None
        if len(rows) != 1:
            raise TimelineExecutionProjectionError(
                "connected plan execution projection is contradictory"
            )
        row = rows[0]
        if row.get("case_id") != case_id or row.get("active_role") != actor.role:
            raise TimelineExecutionProjectionError(
                "connected plan execution projection is contradictory"
            )
        execution_id = row.get("execution_id")
        execution_fields = (
            "execution_case_id",
            "execution_case_revision",
            "execution_decision_id",
            "execution_decision_receipt_id",
            "execution_timeline_plan_id",
        )
        if execution_id is None:
            if any(row.get(field) is not None for field in execution_fields):
                raise TimelineExecutionProjectionError(
                    "connected plan execution projection is contradictory"
                )
        elif (
            row.get("execution_case_id") != row.get("case_id")
            or row.get("execution_case_revision") != row.get("case_revision")
            or row.get("execution_decision_id") != row.get("decision_id")
            or row.get("execution_decision_receipt_id")
            != row.get("decision_receipt_id")
            or row.get("execution_timeline_plan_id") != row.get("timeline_plan_id")
        ):
            raise TimelineExecutionProjectionError(
                "connected plan execution projection is contradictory"
            )
        payload = {field: row[field] for field in (
            "schema_version",
            "journey",
            "case_id",
            "case_revision",
            "decision_id",
            "decision_receipt_id",
            "timeline_plan_id",
            "execution_id",
            "active_role",
            "assignment_status",
        )}
        try:
            return ConnectedPlanExecutionContextV1.model_validate(payload)
        except ValidationError as error:
            raise TimelineExecutionProjectionError(
                "connected plan execution projection is malformed"
            ) from error

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
            ":org,:actor,:role,:case,:execution,:checkpoint,:execution_version,"
            ":checkpoint_version,:kind,:status,:attestation_code,:reason_code,"
            ":attestation,:receipt,:key_hash,:request_hash)",
            {
                "org": actor.organization_id,
                "actor": actor.actor_id,
                "role": actor.role,
                "case": command.case_id,
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

    async def _select_rows(
        self, statement: str, parameters: dict[str, object]
    ) -> list[Mapping[str, object]]:
        try:
            result = await self._session.execute(text(statement), parameters)
            return cast(list[Mapping[str, object]], result.mappings().all())
        except DBAPIError as error:
            sqlstate = getattr(error.orig, "sqlstate", None)
            if sqlstate in {"NV003", "NV007"}:
                raise TimelineExecutionUnavailableError(
                    "execution authority unavailable"
                ) from error
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
