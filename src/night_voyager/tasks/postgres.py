from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import NoReturn, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from night_voyager.adapters.protocols import PlanningAdapterRequest
from night_voyager.decision.hashing import canonical_request_sha256
from night_voyager.identity.models import ActorContext
from night_voyager.skills.models import (
    SkillKey,
    SkillLeafBindingV1,
    SkillRuntimeManifestEntryV1,
    SkillRuntimePin,
)
from night_voyager.tasks.errors import (
    TaskAuthorizationError,
    TaskConflictError,
    TaskLeaseLostError,
    TaskTransientError,
)
from night_voyager.tasks.models import CancelTaskCommand, CreateTaskCommand
from night_voyager.tasks.worker import (
    AgentTaskClaim,
    TaskPinInvalidError,
    WorkerTaskInput,
    WorkerTaskRepository,
)


class PostgresTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve_active_skill_version(self, context: ActorContext) -> tuple[str, str]:
        try:
            projection = await self._session.scalar(
                text("SELECT app.get_skill_catalog_item(:org,:actor,:skill_key)"),
                {
                    "org": context.organization_id,
                    "actor": context.actor_id,
                    "skill_key": "study-destination-compare",
                },
            )
        except DBAPIError as error:
            self._raise_mapped(error)
        if not isinstance(projection, dict):
            raise TaskConflictError("skill_version_unavailable")
        projection_data = cast(dict[str, object], projection)
        events = projection_data.get("activation_events")
        versions = projection_data.get("versions")
        skill_key = projection_data.get("skill_key")
        if (
            not isinstance(skill_key, str)
            or not isinstance(events, list)
            or not events
            or not isinstance(versions, list)
        ):
            raise TaskConflictError("skill_version_unavailable")
        event_items = cast(list[object], events)
        version_items = cast(list[object], versions)
        latest = event_items[-1]
        if not isinstance(latest, dict):
            raise TaskConflictError("skill_version_unavailable")
        latest_data = cast(dict[str, object], latest)
        active_version_id = latest_data.get("activated_version_id")
        for version in version_items:
            if not isinstance(version, dict):
                continue
            version_data = cast(dict[str, object], version)
            semantic_version = version_data.get("semantic_version")
            if str(version_data.get("version_id")) == str(active_version_id) and isinstance(
                semantic_version, str
            ):
                return skill_key, semantic_version
        raise TaskConflictError("skill_version_unavailable")

    async def create(
        self,
        context: ActorContext,
        command: CreateTaskCommand,
        task_id: UUID,
        idempotency_key: str,
        skill_manifest: SkillRuntimeManifestEntryV1,
    ) -> dict[str, object]:
        try:
            result = await self._session.execute(
                text(
                    "SELECT * FROM app.create_agent_task("
                    ":org,:actor,:case,:task,:operation,:revision,:pack,:pack_version,:policy,"
                    "CAST(:skill_manifest AS jsonb),:request_hash,:key_hash)"
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
                    "skill_manifest": skill_manifest.model_dump_json(exclude_none=True),
                    "request_hash": canonical_request_sha256(command.model_dump(mode="json")),
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

    async def get(self, context: ActorContext, task_id: UUID) -> dict[str, object] | None:
        result = await self._session.execute(
            text(
                "SELECT t.id AS task_id,t.operation,t.row_version,t.state,"
                "t.attempt_count,t.terminal_code,"
                "t.result_planning_run_id,t.created_at,t.updated_at,"
                "t.skill_definition_id,t.skill_version_id,t.skill_activation_event_id,"
                "t.skill_activation_sequence,t.runtime_binding_sha256,"
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
        if row is None:
            return None
        task = dict(row)
        if task["skill_definition_id"] is None:
            task["skill_key"] = None
            task["semantic_version"] = None
            return task
        projection = await self._session.scalar(
            text("SELECT app.get_skill_catalog_item(:org,:actor,:skill_key)"),
            {
                "org": context.organization_id,
                "actor": context.actor_id,
                "skill_key": "study-destination-compare",
            },
        )
        if not isinstance(projection, dict):
            raise RuntimeError("pinned task Skill projection is invalid")
        projection_data = cast(dict[str, object], projection)
        versions = projection_data.get("versions")
        if not isinstance(versions, list):
            raise RuntimeError("pinned task Skill projection is invalid")
        for version in cast(list[object], versions):
            if not isinstance(version, dict):
                continue
            version_data = cast(dict[str, object], version)
            if str(version_data.get("version_id")) == str(task["skill_version_id"]):
                task["skill_key"] = projection_data.get("skill_key")
                task["semantic_version"] = version_data.get("semantic_version")
                return task
        raise RuntimeError("pinned task Skill version is unavailable")

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
        if sqlstate == "NV008":
            raise TaskConflictError("idempotency_conflict") from error
        if sqlstate in {"NV003", "NV006", "NV009", "NV011", "23505"}:
            raise TaskConflictError(str(sqlstate)) from error
        if sqlstate == "NV015":
            raise TaskConflictError("skill_version_unavailable") from error
        if sqlstate == "NV022":
            raise TaskConflictError("skill_pin_invalid") from error
        if sqlstate == "NV007":
            raise TaskAuthorizationError from error
        raise error


class PostgresWorkerTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def claim(self, worker_id: str) -> AgentTaskClaim | None:
        try:
            row = (
                (
                    await self._session.execute(
                        text("SELECT * FROM app.claim_agent_task(:worker)"),
                        {"worker": worker_id},
                    )
                )
                .mappings()
                .one_or_none()
            )
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
        try:
            result = await self._session.execute(
                text(
                    "SELECT t.operation,t.case_id,t.case_revision,t.source_pack_id,"
                    "t.source_pack_version,t.policy_version,t.attempt_count,"
                    "app.load_agent_task_skill_pin(:org,:task,:generation) "
                    "AS skill_runtime,"
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
        except DBAPIError as error:
            self._raise_worker_mapped(error)
        row = result.mappings().one_or_none()
        if row is None:
            raise TaskLeaseLostError
        runtime = row.skill_runtime
        if not isinstance(runtime, dict):
            raise TaskPinInvalidError
        runtime_data = cast(dict[str, object], runtime)
        try:
            if (
                str(runtime_data["task_id"]) != str(claim.task_id)
                or runtime_data["operation"] != row.operation
                or runtime_data["binding_kind"] != "planning_runtime"
            ):
                raise ValueError("worker runtime identity mismatch")
            skill_pin = SkillRuntimePin.model_validate_json(
                json.dumps(
                    {
                        field: runtime_data[field]
                        for field in (
                            "skill_definition_id",
                            "skill_version_id",
                            "skill_activation_event_id",
                            "skill_activation_sequence",
                            "runtime_binding_sha256",
                        )
                    }
                )
            )
            registered_manifest = SkillRuntimeManifestEntryV1.model_validate_json(
                json.dumps(runtime_data["manifest_projection"])
            )
            leaf_binding = SkillLeafBindingV1.model_validate_json(
                json.dumps(
                    {
                        "operation": row.operation,
                        "adapter_id": runtime_data["claimed_adapter_id"],
                        "adapter_version": runtime_data["claimed_adapter_version"],
                    }
                )
            )
            skill_key = SkillKey(str(runtime_data["skill_key"]))
            semantic_version = str(runtime_data["semantic_version"])
            if (
                registered_manifest.skill_key is not skill_key
                or registered_manifest.version != semantic_version
            ):
                raise ValueError("worker manifest identity mismatch")
            runtime_manifest_id = str(runtime_data["runtime_manifest_id"])
            runtime_manifest_version = str(runtime_data["runtime_manifest_version"])
            runtime_manifest_sha256 = str(runtime_data["runtime_manifest_sha256"])
        except (KeyError, TypeError, ValueError) as error:
            raise TaskPinInvalidError from error
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
            skill_pin=skill_pin,
            skill_key=skill_key,
            semantic_version=semantic_version,
            leaf_binding=leaf_binding,
            registered_manifest=registered_manifest,
            runtime_manifest_id=runtime_manifest_id,
            runtime_manifest_version=runtime_manifest_version,
            runtime_manifest_sha256=runtime_manifest_sha256,
            supersedes_run_id=row.supersedes_run_id,
            attempt_no=row.attempt_count,
        )

    async def start(self, claim: AgentTaskClaim, worker_id: str, input_sha256: str) -> None:
        await self._set_organization(claim.organization_id)
        try:
            await self._session.execute(
                text("SELECT app.start_agent_task(:org,:task,:worker,:generation,:input_sha256)"),
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
    def _transition_parameters(claim: AgentTaskClaim, worker_id: str) -> dict[str, object]:
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
        if sqlstate == "NV022":
            raise TaskPinInvalidError from error
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
