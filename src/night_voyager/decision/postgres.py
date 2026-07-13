from __future__ import annotations

import hashlib
import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from night_voyager.decision.errors import DecisionAuthorizationError, DecisionConflictError
from night_voyager.decision.hashing import canonical_request_sha256
from night_voyager.decision.models import FamilyDecisionCommand, ReviewCommand, TimelinePlan
from night_voyager.identity.models import ActorContext


class PostgresDecisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def review(
        self, context: ActorContext, command: ReviewCommand, idempotency_key: str
    ) -> dict[str, object]:
        projection: dict[str, object] = {}
        source_date = command.source_snapshot_date
        if command.action.value == "approve_for_consultation":
            route_rows = (
                await self._session.execute(
                    text(
                        "SELECT id,country,outcome,reason_code FROM app.planning_routes "
                        "WHERE organization_id=:org AND planning_run_id=:run ORDER BY country"
                    ),
                    {"org": context.organization_id, "run": command.planning_run_id},
                )
            ).mappings().all()
            intake = await self._session.scalar(
                text(
                    "SELECT student_preferences->>'intake' FROM app.student_case_revisions "
                    "WHERE organization_id=:org AND case_id=:case AND revision=:revision"
                ),
                {
                    "org": context.organization_id,
                    "case": command.case_id,
                    "revision": command.expected_case_revision,
                },
            )
            snapshot = await self._session.scalar(
                text(
                    "SELECT max(e.snapshot_date) FROM app.planning_runs r JOIN "
                    "app.source_pack_entries e ON e.organization_id=r.organization_id AND "
                    "e.source_pack_id=r.source_pack_id AND "
                    "e.source_pack_version=r.source_pack_version "
                    "WHERE r.organization_id=:org AND r.id=:run"
                ),
                {"org": context.organization_id, "run": command.planning_run_id},
            )
            if snapshot is not None:
                source_date = snapshot
            projection = {
                "schema_version": 1,
                "routes": [dict(row) for row in route_rows],
                "eligible_route_ids": [str(item) for item in command.eligible_route_ids],
                "accepted_evidence_risks": [
                    item.model_dump(mode="json") for item in command.risk_acceptances
                ],
                "intake": intake,
                "synthetic_proof": True,
            }
        key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()
        request_payload = command.model_dump(
            mode="json", exclude={"review_id", "brief_id", "family_safe_projection"}
        )
        request_hash = canonical_request_sha256(request_payload)
        try:
            result = await self._session.execute(
                text(
                    "SELECT * FROM app.review_planning_run("
                    ":org,:actor,:case,:run,:revision,:action,:review,CAST(:eligible AS jsonb),"
                    "CAST(:risks AS jsonb),:notes,:brief,CAST(:projection AS jsonb),:source_date,"
                    ":key_hash,:request_hash)"
                ),
                {
                    "org": context.organization_id,
                    "actor": context.actor_id,
                    "case": command.case_id,
                    "run": command.planning_run_id,
                    "revision": command.expected_case_revision,
                    "action": command.action,
                    "review": command.review_id,
                    "eligible": json.dumps([str(item) for item in command.eligible_route_ids]),
                    "risks": json.dumps(
                        [item.model_dump(mode="json") for item in command.risk_acceptances]
                    ),
                    "notes": command.reviewer_notes,
                    "brief": command.brief_id,
                    "projection": json.dumps(projection, default=str),
                    "source_date": source_date,
                    "key_hash": key_hash,
                    "request_hash": request_hash,
                },
            )
        except DBAPIError as error:
            sqlstate = getattr(error.orig, "sqlstate", None)
            if sqlstate in {"NV003", "NV006", "NV008"}:
                raise DecisionConflictError(sqlstate) from error
            if sqlstate == "NV007":
                raise DecisionAuthorizationError from error
            raise
        return dict(result.mappings().one())

    async def get_brief(self, context: ActorContext, brief_id: UUID) -> dict[str, object] | None:
        result = await self._session.execute(
            text(
                "SELECT b.id,b.brief_version,b.family_safe_projection,b.is_current,"
                "d.id AS decision_id,d.receipt_id,t.id AS timeline_id,t.milestones "
                "FROM app.decision_briefs b "
                "JOIN app.student_case_participants p ON p.organization_id=b.organization_id "
                "AND p.case_id=b.case_id AND p.actor_id=:actor AND p.role=:role "
                "LEFT JOIN app.family_decisions d ON d.organization_id=b.organization_id "
                "AND d.decision_brief_id=b.id LEFT JOIN app.timeline_plans t "
                "ON t.organization_id=d.organization_id AND t.family_decision_id=d.id "
                "WHERE b.organization_id=:org AND b.id=:brief"
            ),
            {
                "org": context.organization_id,
                "actor": context.actor_id,
                "role": context.role,
                "brief": brief_id,
            },
        )
        row = result.mappings().one_or_none()
        return dict(row) if row else None

    async def decide(
        self,
        context: ActorContext,
        command: FamilyDecisionCommand,
        *,
        decision_id: UUID,
        receipt_id: UUID,
        timeline_id: UUID,
        timeline: TimelinePlan,
        idempotency_key: str,
    ) -> dict[str, object]:
        key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()
        request_hash = canonical_request_sha256(command.model_dump(mode="json"))
        try:
            result = await self._session.execute(
                text(
                    "SELECT * FROM app.decide_family_brief("
                    ":org,:actor,:role,:brief,:version,:decision,:receipt,:route,:min,:max,"
                    ":currency,CAST(:tradeoffs AS jsonb),:made_by,:source,:timeline,"
                    "CAST(:milestones AS jsonb),:key_hash,:request_hash)"
                ),
                {
                    "org": context.organization_id,
                    "actor": context.actor_id,
                    "role": context.role,
                    "brief": command.brief_id,
                    "version": command.expected_brief_version,
                    "decision": decision_id,
                    "receipt": receipt_id,
                    "route": command.selected_route_id,
                    "min": command.accepted_budget_min_minor,
                    "max": command.accepted_budget_max_minor,
                    "currency": command.currency,
                    "tradeoffs": json.dumps(command.accepted_trade_offs),
                    "made_by": command.decision_made_by_actor_id,
                    "source": command.source,
                    "timeline": timeline_id,
                    "milestones": json.dumps(timeline.model_dump(mode="json")["milestones"]),
                    "key_hash": key_hash,
                    "request_hash": request_hash,
                },
            )
        except DBAPIError as error:
            sqlstate = getattr(error.orig, "sqlstate", None)
            if sqlstate in {"NV003", "NV006", "NV008", "23505"}:
                raise DecisionConflictError(sqlstate) from error
            if sqlstate == "NV007":
                raise DecisionAuthorizationError from error
            raise
        return dict(result.mappings().one())
