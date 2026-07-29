from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from night_voyager.identity.models import ActorContext, ActorRole
from night_voyager.timeline_execution.postgres import (
    PostgresTimelineExecutionRepository,
)
from tests.integration.timeline_execution.test_authority import (
    CASE,
    ORG,
    STUDENT,
)

pytestmark = pytest.mark.database


@pytest.mark.asyncio
async def test_repository_decodes_context_and_execution_view() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    actor = ActorContext(
        organization_id=ORG,
        actor_id=STUDENT,
        role=ActorRole.STUDENT,
        session_id=STUDENT,
    )
    try:
        async with AsyncSession(engine) as session:
            await session.execute(
                text(
                    "SELECT set_config('night_voyager.organization_id',:org,true),"
                    "set_config('night_voyager.actor_id',:actor,true),"
                    "set_config('night_voyager.role','student',true)"
                ),
                {"org": str(ORG), "actor": str(STUDENT)},
            )
            repository = PostgresTimelineExecutionRepository(session)
            view = await repository.read(actor, CASE)
            assert view is not None
            assert view.execution.case_id == CASE
            assert view.reassessment is not None
            assert view.activity_total == len(view.activity)
    finally:
        await engine.dispose()
