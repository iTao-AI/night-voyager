from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from night_voyager.identity.models import ActorContext
from night_voyager.tasks.errors import TaskAuthorizationError
from night_voyager.tasks.models import TaskRuntimePolicy

CLOSING_STATES = frozenset(
    {
        "waiting_review",
        "succeeded",
        "blocked",
        "timed_out",
        "failed",
        "cancelled",
    }
)


class EventCursorAheadError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class TaskPublicEvent:
    task_id: UUID
    event_sequence: int
    event_code: str
    status: str
    public_code: str | None
    attempt_count: int
    planning_run_id: UUID | None
    created_at: datetime

    def public_data(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "task_id": str(self.task_id),
            "event_sequence": self.event_sequence,
            "status": self.status,
            "public_code": self.public_code,
            "attempt_count": self.attempt_count,
            "planning_run_id": (
                None if self.planning_run_id is None else str(self.planning_run_id)
            ),
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class TaskEventPage:
    events: tuple[TaskPublicEvent, ...]
    maximum_sequence: int
    closing: bool


def parse_last_event_id(raw: str | None) -> int:
    if raw is None:
        return 0
    if not raw or not raw.isascii() or not raw.isdecimal():
        raise ValueError("invalid_last_event_id")
    value = int(raw)
    if value < 0:
        raise ValueError("invalid_last_event_id")
    return value


class PostgresTaskEventReader:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def read_page(
        self,
        context: ActorContext,
        task_id: UUID,
        after: int,
        *,
        limit: int = 100,
    ) -> TaskEventPage:
        if limit < 1 or limit > TaskRuntimePolicy().sse_page_size:
            raise ValueError("invalid event page limit")
        task = (
            await self._session.execute(
                text(
                    "SELECT t.state,COALESCE(max(e.event_sequence),0) AS maximum_sequence "
                    "FROM app.agent_tasks t JOIN app.student_case_participants p "
                    "ON p.organization_id=t.organization_id AND p.case_id=t.case_id "
                    "AND p.actor_id=:actor AND p.role='advisor' "
                    "LEFT JOIN app.agent_task_events e ON e.organization_id=t.organization_id "
                    "AND e.task_id=t.id WHERE t.organization_id=:org AND t.id=:task "
                    "GROUP BY t.state"
                ),
                {
                    "org": context.organization_id,
                    "actor": context.actor_id,
                    "task": task_id,
                },
            )
        ).mappings().one_or_none()
        if task is None:
            raise TaskAuthorizationError
        maximum_sequence = int(task.maximum_sequence)
        if after > maximum_sequence:
            raise EventCursorAheadError
        rows = (
            await self._session.execute(
                text(
                    "SELECT task_id,event_sequence,event_code,public_status,public_code,"
                    "attempt_no,result_planning_run_id,created_at "
                    "FROM app.agent_task_events WHERE organization_id=:org AND task_id=:task "
                    "AND event_sequence>:after AND event_sequence<=:maximum "
                    "ORDER BY event_sequence LIMIT :limit"
                ),
                {
                    "org": context.organization_id,
                    "task": task_id,
                    "after": after,
                    "maximum": maximum_sequence,
                    "limit": limit,
                },
            )
        ).mappings()
        events = tuple(
            TaskPublicEvent(
                task_id=row.task_id,
                event_sequence=row.event_sequence,
                event_code=row.event_code,
                status=row.public_status,
                public_code=row.public_code,
                attempt_count=row.attempt_no,
                planning_run_id=row.result_planning_run_id,
                created_at=row.created_at,
            )
            for row in rows
        )
        return TaskEventPage(
            events=events,
            maximum_sequence=maximum_sequence,
            closing=task.state in CLOSING_STATES,
        )


def encode_task_event(event: TaskPublicEvent) -> str:
    data = json.dumps(
        event.public_data(),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return (
        f"id: {event.event_sequence}\n"
        f"event: {event.event_code}\n"
        f"data: {data}\n\n"
    )


type PageLoader = Callable[[int], Awaitable[TaskEventPage]]


async def stream_task_events(
    load_page: PageLoader,
    initial_page: TaskEventPage,
    *,
    after: int,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> AsyncGenerator[str]:
    policy = TaskRuntimePolicy()
    page = initial_page
    cursor = after
    last_heartbeat = monotonic()
    while True:
        for event in page.events:
            yield encode_task_event(event)
            cursor = event.event_sequence
        if page.closing and cursor >= page.maximum_sequence:
            return
        if len(page.events) == policy.sse_page_size:
            page = await load_page(cursor)
            continue
        await sleep(policy.poll_seconds)
        if monotonic() - last_heartbeat >= policy.sse_heartbeat_seconds:
            yield ": heartbeat\n\n"
            last_heartbeat = monotonic()
        page = await load_page(cursor)
