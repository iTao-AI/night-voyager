# ruff: noqa: E501
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from typing import Protocol, cast
from uuid import UUID

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from night_voyager.api import create_app
from night_voyager.config import Settings
from night_voyager.identity.models import ActorContext, ActorRole, DemoActorChoice
from night_voyager.identity.repository import IdentityRepository
from night_voyager.identity.service import IdentityService, IssuedSession
from night_voyager.skills.registry import SkillRuntimeRegistry
from night_voyager.tasks.application import CreateTaskCommand, TaskService
from night_voyager.tasks.errors import TaskAuthorizationError
from night_voyager.tasks.postgres import PostgresTaskRepository
from night_voyager.tasks.streaming import (
    PostgresTaskEventReader,
    TaskEventPage,
    parse_last_event_id,
    stream_task_events,
)

pytestmark = pytest.mark.database
ORIGIN = "http://127.0.0.1:3000"
ORG = UUID("10000000-0000-0000-0000-000000000001")
FOREIGN_ORG = UUID("10000000-0000-0000-0000-000000000002")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
PARENT = UUID("20000000-0000-0000-0000-000000000003")
CASE = UUID("40000000-0000-0000-0000-000000000430")
TASK = UUID("80000000-0000-0000-0000-000000000430")
HEARTBEAT_CASE = UUID("40000000-0000-0000-0000-000000000431")
HEARTBEAT_TASK = UUID("80000000-0000-0000-0000-000000000431")
PACK = UUID("50000000-0000-0000-0000-000000000001")


class CheckedOutPool(Protocol):
    def checkedout(self) -> int: ...


async def mint(
    sessions: async_sessionmaker[AsyncSession], choice: DemoActorChoice
) -> IssuedSession:
    async with sessions() as session, session.begin():
        return await IdentityService(IdentityRepository(session), "test-session-secret").mint(
            choice
        )


async def seed_task(case_id: UUID = CASE, task_id: UUID = TASK) -> None:
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with migrator.begin() as connection:
            for name, value in (
                ("night_voyager.organization_id", str(ORG)),
                ("night_voyager.actor_id", str(ADVISOR)),
                ("night_voyager.role", "advisor"),
            ):
                await connection.execute(
                    text("SELECT set_config(:name,:value,true)"),
                    {"name": name, "value": value},
                )
            await connection.execute(
                text("SELECT app.publish_case_revision(:org,:case,NULL,1,'{}'::jsonb,'{}'::jsonb)"),
                {"org": ORG, "case": case_id},
            )
            await connection.execute(
                text("SELECT app.transition_case(:org,:case,'intake','planning')"),
                {"org": ORG, "case": case_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.student_case_participants(organization_id,case_id,actor_id,role) "
                    "VALUES(:org,:case,:advisor,'advisor'),(:org,:case,:parent,'parent')"
                ),
                {"org": ORG, "case": case_id, "advisor": ADVISOR, "parent": PARENT},
            )
        sessions = async_sessionmaker(api, expire_on_commit=False)
        async with sessions() as session, session.begin():
            for name, value in (
                ("night_voyager.organization_id", str(ORG)),
                ("night_voyager.actor_id", str(ADVISOR)),
                ("night_voyager.role", "advisor"),
            ):
                await session.execute(
                    text("SELECT set_config(:name,:value,true)"),
                    {"name": name, "value": value},
                )
            await TaskService(
                PostgresTaskRepository(session),
                registry=SkillRuntimeRegistry.load_packaged(),
                id_factory=lambda: task_id,
            ).create(
                ActorContext(ORG, ADVISOR, ActorRole.ADVISOR, UUID(int=1)),
                CreateTaskCommand(
                    case_id=case_id,
                    expected_case_revision=1,
                    source_pack_id=PACK,
                    source_pack_version=1,
                ),
                f"sse-task-{task_id}",
            )
    finally:
        await migrator.dispose()
        await api.dispose()


async def add_events_and_cancel(extra_events: int = 105) -> None:
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with migrator.begin() as connection:
            for name, value in (
                ("night_voyager.organization_id", str(ORG)),
                ("night_voyager.actor_id", str(ADVISOR)),
                ("night_voyager.role", "advisor"),
            ):
                await connection.execute(
                    text("SELECT set_config(:name,:value,true)"),
                    {"name": name, "value": value},
                )
            for _ in range(extra_events):
                await connection.execute(
                    text(
                        "SELECT app.append_agent_task_event(:org,:task,'lease_acquired',"
                        "'preparing','lease_acquired',1,NULL)"
                    ),
                    {"org": ORG, "task": TASK},
                )
            await connection.execute(
                text(
                    "SELECT * FROM app.cancel_agent_task(:org,:actor,:task,1,"
                    "repeat('c',64),:key_hash)"
                ),
                {
                    "org": ORG,
                    "actor": ADVISOR,
                    "task": TASK,
                    "key_hash": hashlib.sha256(b"sse-cancel-430").hexdigest(),
                },
            )
    finally:
        await migrator.dispose()


def settings(url: str) -> Settings:
    return Settings.model_validate(
        {
            "environment": "test",
            "database_url": url,
            "demo_mode": True,
            "demo_allow_insecure_cookie": True,
            "allowed_origins": [ORIGIN],
            "secret_key": "test-session-secret",
        }
    )


def event_frames(body: str) -> list[tuple[int, str, dict[str, object]]]:
    frames: list[tuple[int, str, dict[str, object]]] = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        frames.append((int(fields["id"]), fields["event"], json.loads(fields["data"])))
    return frames


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, 0), ("0", 0), ("17", 17)],
)
def test_last_event_id_accepts_only_non_negative_decimal(raw: str | None, expected: int) -> None:
    assert parse_last_event_id(raw) == expected


@pytest.mark.parametrize("raw", ["", "-1", "+1", "1.0", "abc", " 1"])
def test_last_event_id_rejects_malformed_or_negative_values(raw: str) -> None:
    with pytest.raises(ValueError, match="invalid_last_event_id"):
        parse_last_event_id(raw)


@pytest.mark.asyncio
async def test_http_sse_replay_paginates_reconnects_and_reauthorizes() -> None:
    await seed_task()
    await add_events_and_cancel()
    url = os.environ["NIGHT_VOYAGER_API_DATABASE_URL"]
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        advisor = await mint(sessions, DemoActorChoice.ADVISOR)
        parent = await mint(sessions, DemoActorChoice.PARENT)
        app = create_app(settings=settings(url), session_factory=sessions)
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            client.cookies.set("night_voyager_session", advisor.raw_session_token)
            first = await client.get(f"/api/v1/tasks/{TASK}/events")
            assert first.status_code == 200, first.text
            assert first.headers["content-type"].startswith("text/event-stream")
            assert first.headers["cache-control"] == "no-store"
            assert first.headers["x-accel-buffering"] == "no"
            frames = event_frames(first.text)
            assert len(frames) == 107
            assert [item[0] for item in frames] == list(range(1, 108))
            assert frames[0][1] == "queued"
            assert frames[-1][1] == "cancelled"
            assert set(frames[0][2]) == {
                "schema_version",
                "task_id",
                "event_sequence",
                "status",
                "public_code",
                "attempt_count",
                "planning_run_id",
                "created_at",
            }
            assert "organization_id" not in first.text
            assert "lease_owner" not in first.text
            assert "lease_generation" not in first.text
            assert "lease_expires_at" not in first.text

            reconnect = await client.get(
                f"/api/v1/tasks/{TASK}/events", headers={"Last-Event-ID": "100"}
            )
            assert [item[0] for item in event_frames(reconnect.text)] == list(range(101, 108))

            ahead = await client.get(
                f"/api/v1/tasks/{TASK}/events", headers={"Last-Event-ID": "108"}
            )
            assert ahead.status_code == 409
            assert ahead.json()["code"] == "event_cursor_ahead"
            for raw in ("-1", "bad"):
                malformed = await client.get(
                    f"/api/v1/tasks/{TASK}/events", headers={"Last-Event-ID": raw}
                )
                assert malformed.status_code == 400
                assert malformed.json()["code"] == "invalid_last_event_id"

            client.cookies.set("night_voyager_session", parent.raw_session_token)
            hidden = await client.get(
                f"/api/v1/tasks/{TASK}/events", headers={"Last-Event-ID": "100"}
            )
            assert hidden.status_code == 404

            client.cookies.set("night_voyager_session", advisor.raw_session_token)
            results = await asyncio.gather(
                *(
                    client.get(
                        f"/api/v1/tasks/{TASK}/events",
                        headers={"Last-Event-ID": "106"},
                    )
                    for _ in range(25)
                )
            )
            assert all(response.status_code == 200 for response in results)
            assert all(
                [item[0] for item in event_frames(response.text)] == [107] for response in results
            )

        foreign_context = ActorContext(
            organization_id=FOREIGN_ORG,
            actor_id=ADVISOR,
            role=ActorRole.ADVISOR,
            session_id=advisor.context.session_id,
        )
        async with sessions() as session, session.begin():
            await IdentityRepository(session).set_actor_context(foreign_context)
            with pytest.raises(TaskAuthorizationError):
                await PostgresTaskEventReader(session).read_page(foreign_context, TASK, 0)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_heartbeat_is_comment_and_stream_holds_no_session_while_waiting() -> None:
    await seed_task(HEARTBEAT_CASE, HEARTBEAT_TASK)
    url = os.environ["NIGHT_VOYAGER_API_DATABASE_URL"]
    engine = create_async_engine(url, pool_size=2, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    advisor = await mint(sessions, DemoActorChoice.ADVISOR)
    context: ActorContext = advisor.context
    reader_sessions = 0
    clock = 0.0

    async def load(after: int) -> TaskEventPage:
        nonlocal reader_sessions
        reader_sessions += 1
        try:
            async with sessions() as session, session.begin():
                await IdentityRepository(session).set_actor_context(context)
                return await PostgresTaskEventReader(session).read_page(
                    context, HEARTBEAT_TASK, after
                )
        finally:
            reader_sessions -= 1

    async def sleep(_: float) -> None:
        nonlocal clock
        assert reader_sessions == 0
        clock += 1
        if clock == 15:
            migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
            try:
                async with migrator.begin() as connection:
                    for name, value in (
                        ("night_voyager.organization_id", str(ORG)),
                        ("night_voyager.actor_id", str(ADVISOR)),
                        ("night_voyager.role", "advisor"),
                    ):
                        await connection.execute(
                            text("SELECT set_config(:name,:value,true)"),
                            {"name": name, "value": value},
                        )
                    await connection.execute(
                        text(
                            "SELECT * FROM app.cancel_agent_task(:org,:actor,:task,1,"
                            "repeat('c',64),:key_hash)"
                        ),
                        {
                            "org": ORG,
                            "actor": ADVISOR,
                            "task": HEARTBEAT_TASK,
                            "key_hash": hashlib.sha256(b"sse-cancel-431").hexdigest(),
                        },
                    )
            finally:
                await migrator.dispose()

    try:
        initial = await load(0)
        chunks = [
            chunk
            async for chunk in stream_task_events(
                load, initial, after=0, sleep=sleep, monotonic=lambda: clock
            )
        ]
        assert ": heartbeat\n\n" in chunks
        assert chunks[-1].startswith("id: 2\nevent: cancelled\n")
        assert reader_sessions == 0
        assert cast(CheckedOutPool, engine.pool).checkedout() == 0
        async with sessions() as session, session.begin():
            await IdentityRepository(session).set_actor_context(context)
            count = await session.scalar(
                text(
                    "SELECT count(*) FROM app.agent_task_events "
                    "WHERE organization_id=:org AND task_id=:task"
                ),
                {"org": ORG, "task": HEARTBEAT_TASK},
            )
        assert count == 2
    finally:
        await engine.dispose()
