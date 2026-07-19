from __future__ import annotations

import os
from uuid import UUID

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from night_voyager.adapters.deterministic_planning import DeterministicPlanningAdapter
from night_voyager.adapters.governed_mixed_planning import GovernedMixedPlanningAdapter
from night_voyager.adapters.router import PlanningAdapterRouter
from night_voyager.api import create_app
from night_voyager.config import Settings
from night_voyager.dra.fixtures import build_fixture_candidate_import
from night_voyager.identity.models import DemoActorChoice
from night_voyager.identity.repository import IdentityRepository
from night_voyager.identity.service import IdentityService, IssuedSession
from night_voyager.planning.mixed_postgres import PostgresMixedPlanningRepository
from night_voyager.planning.synthetic_postgres import (
    PersistedSyntheticSnapshotRepository,
)
from night_voyager.skills.registry import SkillRuntimeRegistry
from night_voyager.tasks.postgres import postgres_worker_repository_factory
from night_voyager.tasks.worker import TaskWorker
from scripts.seed_dra_proof import seed

pytestmark = pytest.mark.database
ORIGIN = "http://127.0.0.1:3000"
ORG = UUID("10000000-0000-0000-0000-000000000001")
PACK = UUID("50000000-0000-0000-0000-000000000001")
AUSTRALIA = UUID("71000000-0000-0000-0000-000000000001")
CLOSURE_CASE = UUID("40000000-0000-0000-0000-000000001300")


async def mint(
    sessions: async_sessionmaker[AsyncSession], choice: DemoActorChoice
) -> IssuedSession:
    async with sessions() as session, session.begin():
        return await IdentityService(
            IdentityRepository(session), "test-session-secret"
        ).mint(choice)


def headers(session: IssuedSession, key: str) -> dict[str, str]:
    return {
        "Origin": ORIGIN,
        "X-CSRF-Token": session.raw_csrf_token,
        "Idempotency-Key": key,
    }


@pytest.mark.asyncio
async def test_fixture_candidate_closes_through_mixed_task_and_family_decision() -> None:
    migration_url = os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"]
    api_url = os.environ["NIGHT_VOYAGER_API_DATABASE_URL"]
    worker_url = os.environ["NIGHT_VOYAGER_WORKER_DATABASE_URL"]
    await seed(migration_url, CLOSURE_CASE)
    api_engine = create_async_engine(api_url)
    worker_engine = create_async_engine(worker_url)
    sessions = async_sessionmaker(api_engine, expire_on_commit=False)
    worker_sessions = async_sessionmaker(worker_engine, expire_on_commit=False)
    settings = Settings.model_validate(
        {
            "environment": "test",
            "database_url": api_url,
            "demo_mode": True,
            "demo_allow_insecure_cookie": True,
            "allowed_origins": [ORIGIN],
            "secret_key": "test-session-secret",
        }
    )
    try:
        advisor = await mint(sessions, DemoActorChoice.ADVISOR)
        parent = await mint(sessions, DemoActorChoice.PARENT)
        app = create_app(settings=settings, session_factory=sessions)
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            client.cookies.set("night_voyager_session", advisor.raw_session_token)
            candidate = build_fixture_candidate_import()
            import_payload = candidate.model_dump(
                mode="json", exclude_computed_fields=True
            )
            import_payload.pop("organization_id")
            import_payload.pop("case_id")
            imported = await client.post(
                f"/api/v1/cases/{CLOSURE_CASE}/dra-candidates",
                headers=headers(advisor, "closure-import-0001"),
                json=import_payload,
            )
            assert imported.status_code == 201, imported.text
            candidate_id = imported.json()["candidate_id"]
            evidence = next(item for item in candidate.evidence if item.is_promotable)

            approved = await client.post(
                f"/api/v1/cases/{CLOSURE_CASE}/dra-candidates/"
                f"{candidate_id}/verification-decisions",
                headers=headers(advisor, "closure-approve-0001"),
                json={
                    "schema_version": 1,
                    "expected_case_revision": 1,
                    "dra_evidence_id": evidence.evidence_id,
                    "decision": "approve",
                    "reason": "Exact bounded fixture source inspected.",
                    "source_attestation": {
                        "canonical_url": str(evidence.source_url),
                        "publisher": "Synthetic Public Source Publisher",
                        "institution": "Synthetic Australia Institution",
                        "snapshot_date": "2026-07-11",
                        "freshness_days": 365,
                        "redistribution_class": "link_only",
                        "evidence_class": "institutional",
                        "logical_path": "sources/australia-program-fit.html",
                        "snapshot_byte_length": 375,
                        "snapshot_sha256": (
                            "87e314e801dca1aeaf9b751c149c53629"
                            "a4cf23ee04698939fdc87def5a90a13"
                        ),
                        "known_gaps": [
                            "applicant_eligibility",
                            "intake_availability",
                        ],
                    },
                },
            )
            assert approved.status_code == 201, approved.text
            promoted_version = approved.json()["promoted_source_pack_version"]

            created = await client.post(
                f"/api/v1/cases/{CLOSURE_CASE}/agent-tasks",
                headers=headers(advisor, "closure-mixed-task-0001"),
                json={
                    "schema_version": 1,
                    "operation": "generate_governed_mixed_planning_run_v1",
                    "expected_case_revision": 1,
                    "source_pack_id": str(PACK),
                    "source_pack_version": promoted_version,
                    "policy_version": "m3a-policy-v1",
                },
            )
            assert created.status_code == 202, created.text
            task_id = created.json()["task_id"]

            worker = TaskWorker(
                postgres_worker_repository_factory(worker_sessions),
                PlanningAdapterRouter(
                    synthetic=DeterministicPlanningAdapter(
                        PersistedSyntheticSnapshotRepository(worker_sessions)
                    ),
                    mixed=GovernedMixedPlanningAdapter(
                        PostgresMixedPlanningRepository(worker_sessions)
                    ),
                ),
                SkillRuntimeRegistry.load_packaged(),
                worker_id="governed-closure-worker",
            )
            assert await worker.run_once() is True

            task = await client.get(f"/api/v1/tasks/{task_id}")
            assert task.status_code == 200
            assert task.json()["status"] == "needs_advisor_review"
            run_id = task.json()["planning_run_id"]
            events = await client.get(f"/api/v1/tasks/{task_id}/events")
            assert events.status_code == 200
            assert "event: waiting_review" in events.text

            review = await client.post(
                f"/api/v1/cases/{CLOSURE_CASE}/advisor-reviews",
                headers=headers(advisor, "closure-advisor-review-0001"),
                json={
                    "schema_version": 1,
                    "planning_run_id": run_id,
                    "expected_case_revision": 1,
                    "action": "approve_for_consultation",
                    "eligible_route_ids": [str(AUSTRALIA)],
                    "risk_acceptances": [],
                },
            )
            assert review.status_code == 200, review.text
            brief_id = review.json()["brief_id"]

            client.cookies.set("night_voyager_session", parent.raw_session_token)
            decision = await client.post(
                f"/api/v1/decision-briefs/{brief_id}/family-decisions",
                headers=headers(parent, "closure-family-decision-0001"),
                json={
                    "schema_version": 1,
                    "expected_brief_version": 1,
                    "selected_route_id": str(AUSTRALIA),
                    "accepted_budget_min_minor": 30_000_000,
                    "accepted_budget_max_minor": 40_000_000,
                    "currency": "CNY",
                    "accepted_trade_offs": ["budget_elasticity"],
                },
            )
            assert decision.status_code == 200, decision.text
            persisted = await client.get(f"/api/v1/decision-briefs/{brief_id}")
            assert persisted.json()["receipt_id"] == decision.json()["receipt_id"]
            assert persisted.json()["timeline_id"] == decision.json()["timeline_id"]

        inspector = create_async_engine(migration_url)
        try:
            async with inspector.begin() as connection:
                await connection.execute(
                    text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                    {"org": str(ORG)},
                )
                authority = (
                    await connection.execute(
                        text(
                            "SELECT count(*) FILTER "
                            "(WHERE authority='externally_verified') external,"
                            "count(*) FILTER (WHERE claim='australia_program_fit' AND "
                            "authority='externally_verified') bounded,count(*) total "
                            "FROM app.evidence_refs WHERE organization_id=:org "
                            "AND source_pack_id=:pack AND source_pack_version=:version"
                        ),
                        {"org": ORG, "pack": PACK, "version": promoted_version},
                    )
                ).mappings().one()
                assert dict(authority) == {"external": 1, "bounded": 1, "total": 6}
        finally:
            await inspector.dispose()
    finally:
        await api_engine.dispose()
        await worker_engine.dispose()
