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

from night_voyager.collaboration.errors import (
    ActiveTaskBlocksRevisionError,
    CaseRevisionStaleError,
    CollaborationAuthorizationError,
    CollaborationPersistenceError,
    CollaborationThreadFullError,
    IdempotencyConflictError,
    InvalidCollaborationMessageError,
    MemoryCandidateExpiredError,
    MemoryCandidateStaleError,
    MemoryCandidateTerminalError,
    UnsafeFactValueError,
)
from night_voyager.collaboration.models import (
    AppendMessageCommand,
    CollaborationThreadV1,
    ConfirmedFactAdvisorPageV1,
    ConfirmedFactAdvisorV1,
    ConfirmedFactHistoryCursorV1,
    ConfirmedFactParticipantPageV1,
    ConfirmedFactParticipantV1,
    MemoryCandidateAdvisorV1,
    MemoryCandidateParticipantV1,
    MemoryCandidateState,
    MessageEventV1,
    MessagePageV1,
    ProposeMemoryCandidateCommand,
    VerificationDecision,
    VerifyMemoryCandidateCommand,
)
from night_voyager.collaboration.ports import (
    MemoryCandidateProjection,
    MemoryCandidateVerificationV1,
)
from night_voyager.identity.models import ActorContext, ActorRole

ModelT = TypeVar("ModelT", bound=BaseModel)


class PostgresCollaborationRepository:
    """Closed PostgreSQL boundary for governed collaboration authority."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_thread(
        self,
        context: ActorContext,
        case_id: UUID,
        thread_id: UUID,
        request_sha256: str,
        idempotency_key: str,
    ) -> CollaborationThreadV1:
        result = await self._execute(
            "SELECT * FROM app.create_collaboration_thread("
            ":org,:actor,:role,:case,:thread,:request_sha256,:key_sha256)",
            {
                **self._context_parameters(context),
                "case": case_id,
                "thread": thread_id,
                "request_sha256": request_sha256,
                "key_sha256": self._key_sha256(idempotency_key),
            },
        )
        return self._parse_row(
            self._one(result),
            CollaborationThreadV1,
            allowed_extra=frozenset({"replayed"}),
        )

    async def get_thread(
        self, context: ActorContext, case_id: UUID
    ) -> CollaborationThreadV1 | None:
        result = await self._execute(
            "SELECT * FROM app.read_collaboration_thread(:org,:actor,:role,:case)",
            {**self._context_parameters(context), "case": case_id},
        )
        row = self._one_or_none(result)
        if row is None:
            return None
        return self._parse_row(row, CollaborationThreadV1)

    async def list_messages(
        self,
        context: ActorContext,
        thread_id: UUID,
        after_sequence: int,
        limit: int,
    ) -> MessagePageV1:
        result = await self._execute(
            "SELECT * FROM app.read_collaboration_messages("
            ":org,:actor,:role,:thread,:after_sequence,:limit)",
            {
                **self._context_parameters(context),
                "thread": thread_id,
                "after_sequence": after_sequence,
                "limit": limit,
            },
        )
        try:
            rows = self._all(result)
            if len(rows) > limit:
                raise ValueError("database returned more messages than requested")
            items = tuple(self._parse_row(row, MessageEventV1) for row in rows)
            next_after_sequence = (
                items[-1].sequence_no if len(items) == limit and items else None
            )
            return MessagePageV1(
                schema_version=1,
                items=items,
                next_after_sequence=next_after_sequence,
            )
        except (KeyError, TypeError, ValueError, SQLAlchemyError) as error:
            self._raise_persistence(error)

    async def append_message(
        self,
        context: ActorContext,
        command: AppendMessageCommand,
        message_event_id: UUID,
        content_sha256: str,
        request_sha256: str,
        idempotency_key: str,
    ) -> MessageEventV1:
        result = await self._execute(
            "SELECT * FROM app.append_collaboration_message("
            ":org,:actor,:role,:thread,:message,:body,:content_sha256,"
            ":request_sha256,:key_sha256)",
            {
                **self._context_parameters(context),
                "thread": command.thread_id,
                "message": message_event_id,
                "body": command.body,
                "content_sha256": content_sha256,
                "request_sha256": request_sha256,
                "key_sha256": self._key_sha256(idempotency_key),
            },
            invalid_message=True,
            thread_full=True,
        )
        return self._parse_row(
            self._one(result),
            MessageEventV1,
            allowed_extra=frozenset({"replayed"}),
        )

    async def propose_candidate(
        self,
        context: ActorContext,
        command: ProposeMemoryCandidateCommand,
        candidate_id: UUID,
        value_sha256: str,
        request_sha256: str,
        idempotency_key: str,
    ) -> MemoryCandidateParticipantV1:
        proposal = command.proposal.model_dump(mode="json")
        result = await self._execute(
            "SELECT * FROM app.propose_memory_candidate("
            ":org,:actor,:role,:message,:candidate,:case_revision,:fact_key,"
            "CAST(:value AS jsonb),:value_sha256,:request_sha256,:key_sha256)",
            {
                **self._context_parameters(context),
                "message": command.message_event_id,
                "candidate": candidate_id,
                "case_revision": command.case_revision,
                "fact_key": command.proposal.fact_key.value,
                "value": self._json_value(proposal["value"]),
                "value_sha256": value_sha256,
                "request_sha256": request_sha256,
                "key_sha256": self._key_sha256(idempotency_key),
            },
            stale_error=CaseRevisionStaleError,
        )
        return self._parse_row(
            self._one(result),
            MemoryCandidateParticipantV1,
            allowed_extra=frozenset({"replayed"}),
        )

    async def list_candidates(
        self,
        context: ActorContext,
        case_id: UUID,
        limit: int,
    ) -> tuple[MemoryCandidateProjection, ...]:
        result = await self._execute(
            "SELECT projection FROM app.read_memory_candidates("
            ":org,:actor,:role,:case,:limit)",
            {
                **self._context_parameters(context),
                "case": case_id,
                "limit": limit,
            },
        )
        model = (
            MemoryCandidateAdvisorV1
            if context.role is ActorRole.ADVISOR
            else MemoryCandidateParticipantV1
        )
        return self._parse_projection_rows(self._all(result), model)

    async def verify_candidate(
        self,
        context: ActorContext,
        command: VerifyMemoryCandidateCommand,
        verification_id: UUID,
        confirmed_fact_id: UUID | None,
        request_sha256: str,
        idempotency_key: str,
    ) -> MemoryCandidateVerificationV1:
        result = await self._execute(
            "SELECT * FROM app.verify_memory_candidate("
            ":org,:actor,:candidate,:expected_revision,:decision,:reason,"
            ":verification,:fact,:request_sha256,:key_sha256)",
            {
                "org": context.organization_id,
                "actor": context.actor_id,
                "candidate": command.candidate_id,
                "expected_revision": command.expected_case_revision,
                "decision": command.decision.value,
                "reason": command.reason,
                "verification": verification_id,
                "fact": confirmed_fact_id,
                "request_sha256": request_sha256,
                "key_sha256": self._key_sha256(idempotency_key),
            },
            stale_error=MemoryCandidateStaleError,
            terminal_error=True,
        )
        return self._parse_row(
            {"schema_version": 1, **dict(self._one(result))},
            MemoryCandidateVerificationV1,
        )

    async def list_confirmed_facts(
        self,
        context: ActorContext,
        case_id: UUID,
        limit: int,
        cursor: ConfirmedFactHistoryCursorV1 | None = None,
    ) -> ConfirmedFactAdvisorPageV1 | ConfirmedFactParticipantPageV1:
        result = await self._execute(
            "SELECT section,projection,page_snapshot FROM app.read_confirmed_facts("
            ":org,:actor,:role,:case,:snapshot,:after_fact_key,"
            ":after_fact_version,:limit)",
            {
                **self._context_parameters(context),
                "case": case_id,
                "snapshot": cursor.snapshot if cursor is not None else None,
                "after_fact_key": cursor.fact_key.value if cursor is not None else None,
                "after_fact_version": cursor.fact_version if cursor is not None else None,
                "limit": limit,
            },
        )
        try:
            rows = self._all(result)
            if any(set(row) != {"section", "projection", "page_snapshot"} for row in rows):
                raise ValueError("unexpected confirmed fact page row")
            if context.role is not ActorRole.ADVISOR:
                if any(row["section"] != "current" for row in rows):
                    raise ValueError("participant confirmed fact page exposed history")
                return ConfirmedFactParticipantPageV1(
                    schema_version=1,
                    current=tuple(
                        self._parse_fact_projection(row, ConfirmedFactParticipantV1)
                        for row in rows
                    ),
                )

            current_rows = [row for row in rows if row["section"] == "current"]
            history_rows = [row for row in rows if row["section"] == "history"]
            if len(current_rows) + len(history_rows) != len(rows) or len(current_rows) > 6:
                raise ValueError("unexpected advisor confirmed fact page section")
            has_more = len(history_rows) > limit
            returned_history_rows = history_rows[:limit]
            history = tuple(
                self._parse_fact_projection(row, ConfirmedFactAdvisorV1)
                for row in returned_history_rows
            )
            next_cursor = None
            if has_more:
                if not history or not returned_history_rows:
                    raise ValueError("invalid confirmed fact history continuation")
                snapshot = returned_history_rows[-1]["page_snapshot"]
                if not isinstance(snapshot, datetime) or snapshot.tzinfo is None:
                    raise ValueError("invalid confirmed fact history snapshot")
                last = history[-1]
                next_cursor = ConfirmedFactHistoryCursorV1(
                    schema_version=1,
                    snapshot=snapshot,
                    fact_key=last.fact_key,
                    fact_version=last.fact_version,
                ).encode()
            return ConfirmedFactAdvisorPageV1(
                schema_version=1,
                current=tuple(
                    self._parse_fact_projection(row, ConfirmedFactAdvisorV1)
                    for row in current_rows
                ),
                history=history,
                next_cursor=next_cursor,
            )
        except (KeyError, TypeError, ValueError, SQLAlchemyError) as error:
            self._raise_persistence(error)

    async def _execute(
        self,
        statement: str,
        parameters: dict[str, object],
        *,
        stale_error: type[CaseRevisionStaleError | MemoryCandidateStaleError] | None = None,
        terminal_error: bool = False,
        invalid_message: bool = False,
        thread_full: bool = False,
    ) -> Any:
        try:
            return await self._session.execute(text(statement), parameters)
        except DBAPIError as error:
            self._raise_mapped(
                error,
                stale_error=stale_error,
                terminal_error=terminal_error,
                invalid_message=invalid_message,
                thread_full=thread_full,
            )
        except SQLAlchemyError as error:
            self._raise_persistence(error)

    @classmethod
    def _one(cls, result: Any) -> Mapping[str, Any]:
        try:
            row = result.mappings().one()
            if not isinstance(row, Mapping):
                raise ValueError("unexpected collaboration result row")
            return cast(Mapping[str, Any], row)
        except (KeyError, TypeError, ValueError, SQLAlchemyError) as error:
            cls._raise_persistence(error)

    @classmethod
    def _one_or_none(cls, result: Any) -> Mapping[str, Any] | None:
        try:
            row = result.mappings().one_or_none()
            if row is None:
                return None
            if not isinstance(row, Mapping):
                raise ValueError("unexpected collaboration result row")
            return cast(Mapping[str, Any], row)
        except (KeyError, TypeError, ValueError, SQLAlchemyError) as error:
            cls._raise_persistence(error)

    @classmethod
    def _all(cls, result: Any) -> list[Mapping[str, Any]]:
        try:
            rows = result.mappings().all()
            if any(not isinstance(row, Mapping) for row in rows):
                raise ValueError("unexpected collaboration result rows")
            return [cast(Mapping[str, Any], row) for row in rows]
        except (KeyError, TypeError, ValueError, SQLAlchemyError) as error:
            cls._raise_persistence(error)

    @classmethod
    def _parse_projection_rows(
        cls,
        rows: list[Mapping[str, Any]],
        model: type[ModelT],
    ) -> tuple[ModelT, ...]:
        try:
            projections: list[ModelT] = []
            for row in rows:
                if set(row) != {"projection"} or not isinstance(
                    row["projection"], Mapping
                ):
                    raise ValueError("unexpected collaboration projection row")
                raw_projection = cast(Mapping[str, Any], row["projection"])
                projection = cls._normalize_closed_scalars(dict(raw_projection))
                projections.append(model.model_validate(projection, strict=True))
            return tuple(projections)
        except (KeyError, TypeError, ValueError, SQLAlchemyError) as error:
            cls._raise_persistence(error)

    @classmethod
    def _parse_fact_projection(
        cls,
        row: Mapping[str, Any],
        model: type[ModelT],
    ) -> ModelT:
        projection = row.get("projection")
        if not isinstance(projection, Mapping):
            raise ValueError("unexpected confirmed fact projection")
        normalized = cls._normalize_closed_scalars(
            dict(cast(Mapping[str, Any], projection))
        )
        return model.model_validate(normalized, strict=True)

    @classmethod
    def _parse_row(
        cls,
        row: Mapping[str, Any],
        model: type[ModelT],
        *,
        allowed_extra: frozenset[str] = frozenset(),
    ) -> ModelT:
        try:
            model_fields = frozenset(model.model_fields)
            if frozenset(row) != model_fields | allowed_extra:
                raise ValueError("unexpected collaboration result shape")
            projection = cls._normalize_closed_scalars(
                {field: row[field] for field in model_fields}
            )
            return model.model_validate(projection, strict=True)
        except (KeyError, TypeError, ValueError, SQLAlchemyError) as error:
            cls._raise_persistence(error)

    @staticmethod
    def _context_parameters(context: ActorContext) -> dict[str, object]:
        return {
            "org": context.organization_id,
            "actor": context.actor_id,
            "role": context.role.value,
        }

    @staticmethod
    def _normalize_closed_scalars(projection: dict[str, Any]) -> dict[str, Any]:
        for field in (
            "actor_role",
            "subject_role",
            "confirming_advisor_role",
        ):
            value = projection.get(field)
            if isinstance(value, str):
                projection[field] = ActorRole(value)
        state = projection.get("state")
        if isinstance(state, str):
            projection["state"] = MemoryCandidateState(state)
        decision = projection.get("decision")
        if isinstance(decision, str):
            projection["decision"] = VerificationDecision(decision)
        for field in (
            "thread_id",
            "case_id",
            "created_by_actor_id",
            "message_event_id",
            "actor_id",
            "candidate_id",
            "subject_actor_id",
            "verification_id",
            "confirmed_fact_id",
            "source_message_event_id",
            "confirming_advisor_actor_id",
            "supersedes_fact_id",
            "result_fact_id",
        ):
            value = projection.get(field)
            if isinstance(value, str):
                projection[field] = UUID(value)
        for field in ("created_at", "expires_at", "confirmed_at"):
            value = projection.get(field)
            if isinstance(value, str):
                parsed = datetime.fromisoformat(value)
                if parsed.tzinfo is None:
                    raise ValueError("collaboration timestamp must include a timezone")
                projection[field] = parsed
        return projection

    @staticmethod
    def _key_sha256(idempotency_key: str) -> str:
        return hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()

    @staticmethod
    def _json_value(value: object) -> str:
        return json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @staticmethod
    def _raise_mapped(
        error: DBAPIError,
        *,
        stale_error: type[CaseRevisionStaleError | MemoryCandidateStaleError] | None,
        terminal_error: bool,
        invalid_message: bool,
        thread_full: bool,
    ) -> NoReturn:
        sqlstate = getattr(error.orig, "sqlstate", None)
        if sqlstate == "NV003" and stale_error is not None:
            code = (
                "case_revision_stale"
                if stale_error is CaseRevisionStaleError
                else "memory_candidate_stale"
            )
            raise stale_error(code) from error
        if sqlstate == "NV012":
            if terminal_error:
                raise MemoryCandidateTerminalError("memory_candidate_terminal") from error
            if thread_full:
                raise CollaborationThreadFullError("collaboration_thread_full") from error
            PostgresCollaborationRepository._raise_persistence(error)
        if sqlstate == "NV006" and invalid_message:
            raise InvalidCollaborationMessageError("invalid_collaboration_message") from error
        mapped: dict[str, tuple[type[Exception], str]] = {
            "NV006": (UnsafeFactValueError, "unsafe_fact_value"),
            "NV007": (CollaborationAuthorizationError, "resource_unavailable"),
            "NV008": (IdempotencyConflictError, "idempotency_conflict"),
            "NV013": (MemoryCandidateExpiredError, "memory_candidate_expired"),
            "NV014": (ActiveTaskBlocksRevisionError, "active_task_blocks_revision"),
        }
        mapping = mapped.get(str(sqlstate))
        if mapping is None:
            PostgresCollaborationRepository._raise_persistence(error)
        error_type, code = mapping
        raise error_type(code) from error

    @staticmethod
    def _raise_persistence(error: BaseException) -> NoReturn:
        raise CollaborationPersistenceError("persistence_unavailable") from error


__all__ = ["PostgresCollaborationRepository"]
