from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import NoReturn
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from night_voyager.adapters.protocols import PlanningAdapterRequest
from night_voyager.decision.hashing import canonical_request_sha256
from night_voyager.identity.models import ActorContext
from night_voyager.tasks.errors import (
    TaskAuthorizationError,
    TaskConflictError,
    TaskLeaseLostError,
    TaskTransientError,
)
from night_voyager.tasks.models import CancelTaskCommand, CreateTaskCommand
from night_voyager.tasks.worker import AgentTaskClaim, WorkerTaskInput, WorkerTaskRepository


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
                    ":org,:actor,:case,:task,:operation,:revision,:pack,:pack_version,:policy,"
                    ":request_hash,:key_hash)"
                ),
                {
                    "org": context.organization_id,
                    "actor": context.actor_id,
                    "case": command.case_id,
                    "task": task_id,
                    "operation": command.operation,
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
        if sqlstate in {"NV003", "NV006", "NV008", "NV009", "NV011", "23505"}:
            raise TaskConflictError(str(sqlstate)) from error
        if sqlstate == "NV007":
            raise TaskAuthorizationError from error
        raise error


class PostgresWorkerTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def claim(self, worker_id: str) -> AgentTaskClaim | None:
        try:
            row = (
                await self._session.execute(
                    text("SELECT * FROM app.claim_agent_task(:worker)"),
                    {"worker": worker_id},
                )
            ).mappings().one_or_none()
        except DBAPIError as error:
            self._raise_worker_mapped(error)
        if row is None:
            return None
        return AgentTaskClaim(
            task_id=row.task_id,
            organization_id=row.organization_id,
            lease_generation=row.lease_generation,
        )

    async def load(self, claim: AgentTaskClaim) -> WorkerTaskInput:
        await self._set_organization(claim.organization_id)
        row = (
            await self._session.execute(
                text(
                    "SELECT t.operation,t.case_id,t.case_revision,t.source_pack_id,"
                    "t.source_pack_version,t.policy_version,t.attempt_count,"
                    "(SELECT r.id FROM app.planning_runs r "
                    "WHERE r.organization_id=t.organization_id AND r.case_id=t.case_id "
                    "AND r.is_current ORDER BY r.created_at DESC LIMIT 1) AS supersedes_run_id "
                    "FROM app.agent_tasks t WHERE t.organization_id=:org AND t.id=:task "
                    "AND t.lease_generation=:generation AND t.state IN ('leased','running') "
                    "AND t.lease_expires_at>clock_timestamp()"
                ),
                {
                    "org": claim.organization_id,
                    "task": claim.task_id,
                    "generation": claim.lease_generation,
                },
            )
        ).mappings().one_or_none()
        if row is None:
            raise TaskLeaseLostError
        return WorkerTaskInput(
            request=PlanningAdapterRequest(
                schema_version=1,
                operation=row.operation,
                organization_id=claim.organization_id,
                case_id=row.case_id,
                case_revision=row.case_revision,
                source_pack_id=row.source_pack_id,
                source_pack_version=row.source_pack_version,
                policy_version=row.policy_version,
            ),
            supersedes_run_id=row.supersedes_run_id,
            attempt_no=row.attempt_count,
        )

    async def start(
        self, claim: AgentTaskClaim, worker_id: str, input_sha256: str
    ) -> None:
        await self._set_organization(claim.organization_id)
        try:
            await self._session.execute(
                text(
                    "SELECT app.start_agent_task("
                    ":org,:task,:worker,:generation,:input_sha256)"
                ),
                {
                    **self._transition_parameters(claim, worker_id),
                    "input_sha256": input_sha256,
                },
            )
        except DBAPIError as error:
            self._raise_worker_mapped(error)

    async def heartbeat(self, claim: AgentTaskClaim, worker_id: str) -> None:
        await self._execute_transition(
            claim,
            "SELECT app.heartbeat_agent_task(:org,:task,:worker,:generation)",
            worker_id,
        )

    async def fail(
        self,
        claim: AgentTaskClaim,
        worker_id: str,
        code: str,
        *,
        retryable: bool,
        fallback_used: bool,
    ) -> str:
        await self._set_organization(claim.organization_id)
        try:
            value = await self._session.scalar(
                text(
                    "SELECT app.fail_agent_task("
                    ":org,:task,:worker,:generation,:code,:retryable,:fallback_used)"
                ),
                {
                    **self._transition_parameters(claim, worker_id),
                    "code": code,
                    "retryable": retryable,
                    "fallback_used": fallback_used,
                },
            )
        except DBAPIError as error:
            self._raise_worker_mapped(error)
        return str(value)

    async def finalize(
        self,
        claim: AgentTaskClaim,
        worker_id: str,
        *,
        run_id: UUID,
        evidence_hash: str,
        state: str,
        reason_code: str,
        output_hash: str,
        output: dict[str, object],
        supersedes_run_id: UUID | None,
    ) -> str:
        await self._set_organization(claim.organization_id)
        try:
            value = await self._session.scalar(
                text(
                    "SELECT app.finalize_agent_task_result("
                    ":org,:task,:worker,:generation,:run,:evidence_hash,:state,:reason,"
                    ":output_hash,CAST(:output AS jsonb),:supersedes)"
                ),
                {
                    **self._transition_parameters(claim, worker_id),
                    "run": run_id,
                    "evidence_hash": evidence_hash,
                    "state": state,
                    "reason": reason_code,
                    "output_hash": output_hash,
                    "output": json.dumps(output),
                    "supersedes": supersedes_run_id,
                },
            )
        except DBAPIError as error:
            self._raise_worker_mapped(error)
        return str(value)

    async def _execute_transition(
        self, claim: AgentTaskClaim, statement: str, worker_id: str
    ) -> None:
        await self._set_organization(claim.organization_id)
        try:
            await self._session.execute(
                text(statement), self._transition_parameters(claim, worker_id)
            )
        except DBAPIError as error:
            self._raise_worker_mapped(error)

    async def _set_organization(self, organization_id: UUID) -> None:
        await self._session.execute(
            text("SELECT set_config('night_voyager.organization_id',:org,true)"),
            {"org": str(organization_id)},
        )

    @staticmethod
    def _transition_parameters(
        claim: AgentTaskClaim, worker_id: str
    ) -> dict[str, object]:
        return {
            "org": claim.organization_id,
            "task": claim.task_id,
            "worker": worker_id,
            "generation": claim.lease_generation,
        }

    @staticmethod
    def _raise_worker_mapped(error: DBAPIError) -> NoReturn:
        sqlstate = getattr(error.orig, "sqlstate", None)
        if sqlstate == "NV010":
            raise TaskLeaseLostError from error
        if (
            isinstance(error, OperationalError)
            or error.connection_invalidated
            or (isinstance(sqlstate, str) and sqlstate.startswith("08"))
            or sqlstate in {"40001", "40P01"}
        ):
            raise TaskTransientError from error
        raise error


def postgres_worker_repository_factory(
    session_factory: async_sessionmaker[AsyncSession],
):
    @asynccontextmanager
    async def factory() -> AsyncGenerator[WorkerTaskRepository]:
        async with session_factory() as session, session.begin():
            yield PostgresWorkerTaskRepository(session)

    return factory
