from __future__ import annotations

import os
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from night_voyager.connected_demo.errors import DemoContractUnavailableError
from night_voyager.connected_demo.fixtures import (
    CanonicalDemoSourceContract,
    resolve_canonical_demo_source_contract,
)
from night_voyager.connected_demo.models import DemoPhase
from night_voyager.connected_demo.postgres import PostgresConnectedDemoRepository
from night_voyager.identity.demo_seed import CONNECTED_DEMO_CASE_ID
from night_voyager.identity.models import ActorContext, ActorRole

pytestmark = pytest.mark.database
DEMO_ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
PARENT = UUID("20000000-0000-0000-0000-000000000003")


def context(role: ActorRole = ActorRole.ADVISOR) -> ActorContext:
    return ActorContext(
        organization_id=DEMO_ORG,
        actor_id=ADVISOR if role is ActorRole.ADVISOR else PARENT,
        role=role,
        session_id=UUID("30000000-0000-0000-0000-000000000001"),
    )


async def set_context(session: AsyncSession) -> None:
    await session.execute(
        text("SELECT set_config('night_voyager.organization_id',:org,true)"),
        {"org": str(DEMO_ORG)},
    )


@pytest.mark.asyncio
async def test_task_ready_projection_uses_canonical_server_inputs_under_api_role() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with AsyncSession(engine) as session, session.begin():
            await set_context(session)
            projection = await PostgresConnectedDemoRepository(session).advisor_ledger(
                context(), CONNECTED_DEMO_CASE_ID, resolve_canonical_demo_source_contract()
            )

        assert projection is not None
        assert projection.phase is DemoPhase.TASK_READY
        assert projection.canonical_task_inputs is not None
        assert projection.canonical_task_inputs.case_id == CONNECTED_DEMO_CASE_ID
        assert projection.model_dump().keys() == {
            "schema_version",
            "proof_mode",
            "phase",
            "case_id",
            "case_revision",
            "case_state",
            "canonical_task_inputs",
            "task",
            "planning_run",
            "routes",
            "evidence",
            "review_inputs",
            "current_brief_id",
            "recovery",
        }
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_wrong_role_is_hidden_and_source_mismatch_fails_closed() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    source = resolve_canonical_demo_source_contract()
    bad_source = CanonicalDemoSourceContract(
        source_pack_id=source.source_pack_id,
        source_pack_version=source.source_pack_version,
        manifest_sha256="0" * 64,
        policy_version=source.policy_version,
    )
    try:
        async with AsyncSession(engine) as session, session.begin():
            await set_context(session)
            repository = PostgresConnectedDemoRepository(session)
            assert (
                await repository.advisor_ledger(
                    context(ActorRole.PARENT), CONNECTED_DEMO_CASE_ID, source
                )
                is None
            )
            with pytest.raises(DemoContractUnavailableError):
                await repository.advisor_ledger(context(), CONNECTED_DEMO_CASE_ID, bad_source)
    finally:
        await engine.dispose()
