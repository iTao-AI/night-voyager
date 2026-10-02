# ruff: noqa: E501
from __future__ import annotations

import asyncio
import os
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from night_voyager.identity.models import ActorContext, ActorRole
from night_voyager.skills.models import SkillKey, SkillRuntimePin
from night_voyager.skills.registry import SkillRuntimeRegistry
from night_voyager.tasks.application import TaskService
from night_voyager.tasks.errors import TaskConflictError
from night_voyager.tasks.models import CreateTaskCommand, RetryTaskCommand
from night_voyager.tasks.postgres import PostgresTaskRepository
from scripts.register_skill_version import register_skill_version
from tests.integration.skills.test_skill_lifecycle import (
    _create_candidate,  # pyright: ignore[reportPrivateUsage]
    _promote,  # pyright: ignore[reportPrivateUsage]
    _record_evaluation,  # pyright: ignore[reportPrivateUsage]
    _rollback,  # pyright: ignore[reportPrivateUsage]
)
from tests.integration.tasks.test_postgres_tasks import ADVISOR, ORG, PACK, context
from tests.integration.tasks.test_terminal_recovery import failed_source, inspect_source, retry

pytestmark = pytest.mark.database


@pytest.mark.asyncio
async def test_native_retry_revalidates_activation_and_new_live_pin_cannot_duplicate():
    case, source, version = await failed_source("deadline_exceeded")
    source_before = await inspect_source(source)
    await register_skill_version(
        os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"],
        organization_id=ORG,
        skill_key=SkillKey.STUDY_DESTINATION_COMPARE,
        version="1.0.1",
    )
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    sessions = async_sessionmaker(api)
    suffix = str(uuid4())
    candidate, evaluation, activation = uuid4(), uuid4(), uuid4()
    try:
        async with api.begin() as c:
            await context(c)
            await _create_candidate(c, candidate_id=candidate, suffix=suffix)
            await _record_evaluation(
                c, candidate_id=candidate, evaluation_id=evaluation, suffix=suffix
            )
        async with api.connect() as c:
            tx = await c.begin()
            await context(c)
            await _promote(c, candidate_id=candidate, event_id=activation, suffix=suffix)
            stale_retry = asyncio.create_task(retry(source, version, suffix))
            async with migrator.begin() as observer:
                blocked = False
                for _ in range(100):
                    blocked = await observer.scalar(
                        text(
                            "SELECT EXISTS(SELECT 1 FROM pg_locks WHERE NOT granted AND locktype='transactionid' AND pid<>pg_backend_pid())"
                        )
                    )
                    if blocked:
                        break
                    await asyncio.sleep(0.01)
                assert blocked
            await tx.commit()
            with pytest.raises(DBAPIError) as stale:
                await asyncio.wait_for(stale_retry, 5)
            assert getattr(stale.value.orig, "sqlstate", None) == "NV022"
        async with sessions() as s, s.begin():
            for setting, value in [
                ("organization_id", ORG),
                ("actor_id", ADVISOR),
                ("role", "advisor"),
            ]:
                await s.execute(
                    text("SELECT set_config(:setting,:value,true)"),
                    {"setting": "night_voyager." + setting, "value": str(value)},
                )
            service = TaskService(
                PostgresTaskRepository(s), registry=SkillRuntimeRegistry.load_packaged()
            )
            fresh = await service.retry(
                ActorContext(ORG, ADVISOR, ActorRole.ADVISOR, uuid4()),
                RetryTaskCommand(
                    task_id=source, expected_row_version=version, expected_case_revision=1
                ),
                suffix,
            )
            pin = cast(SkillRuntimePin | None, fresh["skill_pin"])
            assert pin is not None
            assert pin.skill_activation_event_id == activation
            assert pin.skill_activation_sequence == 2
        assert await inspect_source(source) == source_before
        async with api.begin() as c:
            await context(c)
            await _rollback(c, event_id=uuid4(), suffix=suffix)
        async with sessions() as s, s.begin():
            for setting, value in [
                ("organization_id", ORG),
                ("actor_id", ADVISOR),
                ("role", "advisor"),
            ]:
                await s.execute(
                    text("SELECT set_config(:setting,:value,true)"),
                    {"setting": "night_voyager." + setting, "value": str(value)},
                )
            with pytest.raises(TaskConflictError):
                await TaskService(
                    PostgresTaskRepository(s), registry=SkillRuntimeRegistry.load_packaged()
                ).create(
                    ActorContext(ORG, ADVISOR, ActorRole.ADVISOR, uuid4()),
                    CreateTaskCommand(
                        case_id=case,
                        expected_case_revision=1,
                        source_pack_id=PACK,
                        source_pack_version=1,
                    ),
                    "ordinary-new-pin-" + suffix,
                )
    finally:
        await migrator.dispose()
        await api.dispose()
