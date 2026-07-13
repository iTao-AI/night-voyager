from __future__ import annotations

import asyncio
import os
from uuid import UUID

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from night_voyager.api import create_app
from night_voyager.config import Settings
from night_voyager.identity.models import DemoActorChoice
from night_voyager.identity.repository import IdentityRepository
from night_voyager.identity.service import IdentityService, IssuedSession

pytestmark = pytest.mark.database
ORIGIN = "http://127.0.0.1:3000"
CASE = UUID("40000000-0000-0000-0000-000000000001")
RUN = UUID("70000000-0000-0000-0000-000000000001")
AUSTRALIA = UUID("71000000-0000-0000-0000-000000000001")
PARENT = UUID("20000000-0000-0000-0000-000000000003")


async def mint(
    sessions: async_sessionmaker[AsyncSession], choice: DemoActorChoice
) -> IssuedSession:
    async with sessions() as session, session.begin():
        return await IdentityService(IdentityRepository(session), "test-session-secret").mint(
            choice
        )


@pytest.mark.asyncio
async def test_real_http_advisor_to_parent_australia_flow_is_persistent() -> None:
    url = os.environ["NIGHT_VOYAGER_API_DATABASE_URL"]
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings.model_validate(
        {
            "environment": "test",
            "database_url": url,
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
            invalid = await client.post(
                f"/api/v1/cases/{CASE}/advisor-reviews",
                json={"schema_version": 1},
            )
            assert invalid.status_code == 422
            assert invalid.headers["content-type"].startswith("application/problem+json")
            rejected_origin = await client.post(
                f"/api/v1/cases/{CASE}/advisor-reviews",
                headers={"Origin": "https://evil.invalid", "Idempotency-Key": "rejected"},
                json={
                    "schema_version": 1,
                    "planning_run_id": str(RUN),
                    "expected_case_revision": 1,
                    "action": "request_revision",
                },
            )
            assert rejected_origin.status_code == 403
            assert rejected_origin.headers["content-type"].startswith("application/problem+json")
            client.cookies.set("night_voyager_session", advisor.raw_session_token)
            wrong_csrf = await client.post(
                f"/api/v1/cases/{CASE}/advisor-reviews",
                headers={
                    "Origin": ORIGIN,
                    "X-CSRF-Token": "wrong",
                    "Idempotency-Key": "wrong-csrf",
                },
                json={
                    "schema_version": 1,
                    "planning_run_id": str(RUN),
                    "expected_case_revision": 1,
                    "action": "request_revision",
                },
            )
            assert wrong_csrf.status_code == 401
            assert wrong_csrf.headers["content-type"].startswith("application/problem+json")
            approval = await client.post(
                f"/api/v1/cases/{CASE}/advisor-reviews",
                headers={
                    "Origin": ORIGIN,
                    "X-CSRF-Token": advisor.raw_csrf_token,
                    "Idempotency-Key": "approve-golden",
                },
                json={
                    "schema_version": 1,
                    "planning_run_id": str(RUN),
                    "expected_case_revision": 1,
                    "action": "approve_for_consultation",
                    "eligible_route_ids": [str(AUSTRALIA)],
                    "risk_acceptances": [],
                },
            )
            assert approval.status_code == 200, approval.text
            brief_id = approval.json()["brief_id"]
            replay = await client.post(
                f"/api/v1/cases/{CASE}/advisor-reviews",
                headers={
                    "Origin": ORIGIN,
                    "X-CSRF-Token": advisor.raw_csrf_token,
                    "Idempotency-Key": "approve-golden",
                },
                json={
                    "schema_version": 1,
                    "planning_run_id": str(RUN),
                    "expected_case_revision": 1,
                    "action": "approve_for_consultation",
                    "eligible_route_ids": [str(AUSTRALIA)],
                    "risk_acceptances": [],
                },
            )
            assert replay.json()["brief_id"] == brief_id
            assert replay.json()["replayed"] is True
            mismatched_replay = await client.post(
                f"/api/v1/cases/{CASE}/advisor-reviews",
                headers={
                    "Origin": ORIGIN,
                    "X-CSRF-Token": advisor.raw_csrf_token,
                    "Idempotency-Key": "approve-golden",
                },
                json={
                    "schema_version": 1,
                    "planning_run_id": str(RUN),
                    "expected_case_revision": 1,
                    "action": "approve_for_consultation",
                    "eligible_route_ids": [],
                    "risk_acceptances": [],
                },
            )
            assert mismatched_replay.status_code == 409
            assert mismatched_replay.headers["content-type"].startswith(
                "application/problem+json"
            )
            client.cookies.set("night_voyager_session", parent.raw_session_token)
            brief = await client.get(
                f"/api/v1/decision-briefs/{brief_id}",
            )
            assert brief.status_code == 200, brief.text
            projection = brief.json()["family_safe_projection"]
            assert str(AUSTRALIA) in projection["eligible_route_ids"]
            assert (
                next(r for r in projection["routes"] if r["country"] == "malaysia")["outcome"]
                == "blocked"
            )
            decision_payload = {
                "schema_version": 1,
                "expected_brief_version": 1,
                "selected_route_id": str(AUSTRALIA),
                "accepted_budget_min_minor": 30_000_000,
                "accepted_budget_max_minor": 40_000_000,
                "currency": "CNY",
                "accepted_trade_offs": ["budget_elasticity"],
            }
            browser_results = await asyncio.gather(
                *(
                    client.post(
                        f"/api/v1/decision-briefs/{brief_id}/family-decisions",
                        headers={
                            "Origin": ORIGIN,
                            "X-CSRF-Token": parent.raw_csrf_token,
                            "Idempotency-Key": key,
                        },
                        json=decision_payload,
                    )
                    for key in ("parent-australia-a", "parent-australia-b")
                )
            )
            assert sorted(result.status_code for result in browser_results) == [200, 409]
            decision = next(result for result in browser_results if result.status_code == 200)
            winning_key = (
                "parent-australia-a"
                if browser_results[0].status_code == 200
                else "parent-australia-b"
            )
            decision_replay = await client.post(
                f"/api/v1/decision-briefs/{brief_id}/family-decisions",
                headers={
                    "Origin": ORIGIN,
                    "X-CSRF-Token": parent.raw_csrf_token,
                    "Idempotency-Key": winning_key,
                },
                json=decision_payload,
            )
            assert decision_replay.json()["receipt_id"] == decision.json()["receipt_id"]
            assert decision_replay.json()["replayed"] is True
            persisted = await client.get(
                f"/api/v1/decision-briefs/{brief_id}",
            )
            assert persisted.json()["receipt_id"] == decision.json()["receipt_id"]
            assert persisted.json()["timeline_id"] == decision.json()["timeline_id"]
            receipt = persisted.json()["receipt"]
            assert receipt == {
                "schema_version": 1,
                "decision_id": decision.json()["decision_id"],
                "receipt_id": decision.json()["receipt_id"],
                "selected_route_id": str(AUSTRALIA),
                "accepted_budget_min_minor": 30_000_000,
                "accepted_budget_max_minor": 40_000_000,
                "currency": "CNY",
                "accepted_trade_offs": ["budget_elasticity"],
                "decision_made_by_actor_id": str(PARENT),
                "recorded_by_actor_id": str(PARENT),
                "source": "direct",
            }
            assert persisted.headers["cache-control"] == "no-store"
    finally:
        await engine.dispose()
