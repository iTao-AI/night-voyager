from __future__ import annotations

import hashlib
from typing import NoReturn
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from night_voyager.decision.hashing import canonical_request_sha256
from night_voyager.identity.models import ActorContext
from night_voyager.tasks.errors import TaskAuthorizationError, TaskConflictError
from night_voyager.tasks.models import CancelTaskCommand, CreateTaskCommand


class PostgresTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        context: ActorContext,
        command: CreateTaskCommand,
        task_id: UUID,
        idempotency_key: str,
    ) -> dict[str, object]:
        try:
            result = await self._session.execute(
                text(
                    "SELECT * FROM app.create_agent_task("
                    ":org,:actor,:case,:task,:revision,:pack,:pack_version,:policy,"
                    ":request_hash,:key_hash)"
                ),
                {
                    "org": context.organization_id,
                    "actor": context.actor_id,
                    "case": command.case_id,
                    "task": task_id,
                    "revision": command.expected_case_revision,
                    "pack": command.source_pack_id,
                    "pack_version": command.source_pack_version,
                    "policy": command.policy_version,
                    "request_hash": canonical_request_sha256(
                        command.model_dump(mode="json")
                    ),
                    "key_hash": self._key_hash(idempotency_key),
                },
            )
        except DBAPIError as error:
            self._raise_mapped(error)
        created = result.mappings().one()
        row = await self.get(context, created.task_id)
        if row is None:
            raise RuntimeError("created task is not readable")
        return {**row, "replayed": created.replayed}

    async def get(
        self, context: ActorContext, task_id: UUID
    ) -> dict[str, object] | None:
        result = await self._session.execute(
            text(
                "SELECT t.id AS task_id,t.row_version,t.state,t.attempt_count,t.terminal_code,"
                "t.result_planning_run_id,t.created_at,t.updated_at,"
                "CASE WHEN t.result_planning_run_id IS NULL THEN true "
                "ELSE COALESCE(r.is_current,false) END AS result_is_current "
                "FROM app.agent_tasks t JOIN app.student_case_participants p "
                "ON p.organization_id=t.organization_id AND p.case_id=t.case_id "
                "AND p.actor_id=:actor AND p.role='advisor' "
                "LEFT JOIN app.planning_runs r ON r.organization_id=t.organization_id "
                "AND r.id=t.result_planning_run_id "
                "WHERE t.organization_id=:org AND t.id=:task"
            ),
            {
                "org": context.organization_id,
                "actor": context.actor_id,
                "task": task_id,
            },
        )
        row = result.mappings().one_or_none()
        return None if row is None else dict(row)

    async def cancel(
        self,
        context: ActorContext,
        command: CancelTaskCommand,
        idempotency_key: str,
    ) -> dict[str, object]:
        request_hash = canonical_request_sha256(command.model_dump(mode="json"))
        try:
            result = await self._session.execute(
                text(
                    "SELECT * FROM app.cancel_agent_task("
                    ":org,:actor,:task,:version,:request_hash,:key_hash)"
                ),
                {
                    "org": context.organization_id,
                    "actor": context.actor_id,
                    "task": command.task_id,
                    "version": command.expected_row_version,
                    "request_hash": request_hash,
                    "key_hash": self._key_hash(idempotency_key),
                },
            )
        except DBAPIError as error:
            self._raise_mapped(error)
        cancelled = result.mappings().one()
        row = await self.get(context, cancelled.task_id)
        if row is None:
            raise RuntimeError("cancelled task is not readable")
        return {**row, "replayed": cancelled.replayed}

    @staticmethod
    def _key_hash(idempotency_key: str) -> str:
        return hashlib.sha256(idempotency_key.encode()).hexdigest()

    @staticmethod
    def _raise_mapped(error: DBAPIError) -> NoReturn:
        sqlstate = getattr(error.orig, "sqlstate", None)
        if sqlstate in {"NV003", "NV006", "NV008", "NV009", "23505"}:
            raise TaskConflictError(str(sqlstate)) from error
        if sqlstate == "NV007":
            raise TaskAuthorizationError from error
        raise error
