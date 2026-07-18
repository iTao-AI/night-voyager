from __future__ import annotations

import os

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from night_voyager.api import create_app
from night_voyager.config import Settings
from night_voyager.identity.models import DemoActorChoice
from night_voyager.identity.repository import IdentityRepository
from night_voyager.identity.service import IdentityService, IssuedSession
from tests.integration.skills.test_skill_lifecycle import (
    registration_command,
    reset_nonseed_skill_history,
)

pytestmark = pytest.mark.database

ORIGIN = "http://127.0.0.1:3000"


async def _mint(
    sessions: async_sessionmaker[AsyncSession], choice: DemoActorChoice
) -> IssuedSession:
    async with sessions() as session, session.begin():
        return await IdentityService(IdentityRepository(session), "test-session-secret").mint(
            choice
        )


@pytest.mark.asyncio
async def test_real_skill_catalog_http_is_advisor_only_no_store_and_strict() -> None:
    database_url = os.environ["NIGHT_VOYAGER_API_DATABASE_URL"]
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings.model_validate(
        {
            "environment": "test",
            "database_url": database_url,
            "demo_mode": True,
            "demo_allow_insecure_cookie": True,
            "allowed_origins": [ORIGIN],
            "secret_key": "test-session-secret",
        }
    )
    try:
        advisor = await _mint(sessions, DemoActorChoice.ADVISOR)
        student = await _mint(sessions, DemoActorChoice.STUDENT)
        app = create_app(settings=settings, session_factory=sessions)
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            client.cookies.set("night_voyager_session", advisor.raw_session_token)
            catalog = await client.get("/api/v1/skills")
            assert catalog.status_code == 200, catalog.text
            assert catalog.headers["cache-control"] == "no-store"
            assert catalog.json()["schema_version"] == 1
            assert [item["skill_key"] for item in catalog.json()["items"]] == sorted(
                [
                    "student-profile-intake",
                    "study-destination-compare",
                    "evidence-research",
                    "document-evidence-retrieval",
                    "family-decision-brief",
                    "application-timeline-guard",
                ]
            )

            detail = await client.get("/api/v1/skills/study-destination-compare")
            assert detail.status_code == 200, detail.text
            assert detail.headers["cache-control"] == "no-store"
            assert detail.json()["binding_kind"] == "planning_runtime"
            assert [row["semantic_version"] for row in detail.json()["versions"]] == ["1.0.0"]

            client.cookies.set("night_voyager_session", student.raw_session_token)
            denied = await client.get("/api/v1/skills")
            assert denied.status_code == 404
            assert denied.headers["cache-control"] == "no-store"
            assert denied.json()["code"] == "resource_unavailable"

            client.cookies.set("night_voyager_session", advisor.raw_session_token)
            strict = await client.post(
                "/api/v1/skills/study-destination-compare/change-candidates",
                headers={
                    "Origin": ORIGIN,
                    "X-CSRF-Token": advisor.raw_csrf_token,
                    "Idempotency-Key": "strict-skill-candidate",
                },
                json={
                    "schema_version": 1,
                    "proposed_version": "1.0.1",
                    "provenance": "maintainer_proposal",
                    "reason": "Deterministic compatibility coverage",
                    "runtime_binding_sha256": "f" * 64,
                },
            )
            assert strict.status_code == 422
            assert strict.headers["cache-control"] == "no-store"
            assert strict.json()["code"] == "request_validation_failed"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_real_http_owner_evaluates_activates_and_rolls_back_registered_version() -> None:
    await reset_nonseed_skill_history()
    registered = registration_command(
        "--skill-key",
        "study-destination-compare",
        "--version",
        "1.0.1",
    )
    assert registered.returncode == 0, registered.stderr

    database_url = os.environ["NIGHT_VOYAGER_API_DATABASE_URL"]
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings.model_validate(
        {
            "environment": "test",
            "database_url": database_url,
            "demo_mode": True,
            "demo_allow_insecure_cookie": True,
            "allowed_origins": [ORIGIN],
            "secret_key": "test-session-secret",
        }
    )

    def headers(session: IssuedSession, key: str) -> dict[str, str]:
        return {
            "Origin": ORIGIN,
            "X-CSRF-Token": session.raw_csrf_token,
            "Idempotency-Key": key,
        }

    candidate_payload = {
        "schema_version": 1,
        "proposed_version": "1.0.1",
        "provenance": "maintainer_proposal",
        "reason": "Add deterministic compatibility and negative coverage",
    }
    try:
        advisor = await _mint(sessions, DemoActorChoice.ADVISOR)
        student = await _mint(sessions, DemoActorChoice.STUDENT)
        app = create_app(settings=settings, session_factory=sessions)
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            client.cookies.set("night_voyager_session", student.raw_session_token)
            denied = await client.post(
                "/api/v1/skills/study-destination-compare/change-candidates",
                headers=headers(student, "http-skill-student-denied"),
                json=candidate_payload,
            )
            assert denied.status_code == 404
            assert denied.headers["cache-control"] == "no-store"
            assert denied.json()["code"] == "resource_unavailable"

            client.cookies.set("night_voyager_session", advisor.raw_session_token)
            created = await client.post(
                "/api/v1/skills/study-destination-compare/change-candidates",
                headers=headers(advisor, "http-skill-candidate"),
                json=candidate_payload,
            )
            assert created.status_code == 201, created.text
            assert created.headers["cache-control"] == "no-store"
            assert created.json()["replayed"] is False
            candidate_id = created.json()["candidate_id"]

            replay = await client.post(
                "/api/v1/skills/study-destination-compare/change-candidates",
                headers=headers(advisor, "http-skill-candidate"),
                json=candidate_payload,
            )
            assert replay.status_code == 201
            assert replay.json() == {**created.json(), "replayed": True}

            conflict = await client.post(
                "/api/v1/skills/study-destination-compare/change-candidates",
                headers=headers(advisor, "http-skill-candidate"),
                json={**candidate_payload, "reason": "Conflicting replay"},
            )
            assert conflict.status_code == 409
            assert conflict.json()["code"] == "idempotency_conflict"

            evaluated = await client.post(
                f"/api/v1/skill-change-candidates/{candidate_id}/evaluations",
                headers=headers(advisor, "http-skill-evaluation"),
                json={"schema_version": 1},
            )
            assert evaluated.status_code == 201, evaluated.text
            assert evaluated.json()["status"] == "passed"
            assert evaluated.json()["replayed"] is False

            activated = await client.post(
                f"/api/v1/skill-change-candidates/{candidate_id}/activations",
                headers=headers(advisor, "http-skill-activation"),
                json={
                    "schema_version": 1,
                    "expected_active_version": "1.0.0",
                    "expected_activation_sequence": 1,
                    "reason": "Promote evaluated deterministic compatibility",
                },
            )
            assert activated.status_code == 201, activated.text
            assert activated.json()["activation_sequence"] == 2

            stale_activation = await client.post(
                f"/api/v1/skill-change-candidates/{candidate_id}/activations",
                headers=headers(advisor, "http-skill-activation-stale"),
                json={
                    "schema_version": 1,
                    "expected_active_version": "1.0.0",
                    "expected_activation_sequence": 1,
                    "reason": "Stale duplicate activation",
                },
            )
            assert stale_activation.status_code == 409
            assert stale_activation.json()["code"] == "skill_activation_stale"

            rolled_back = await client.post(
                "/api/v1/skills/study-destination-compare/rollbacks",
                headers=headers(advisor, "http-skill-rollback"),
                json={
                    "schema_version": 1,
                    "target_version": "1.0.0",
                    "expected_active_version": "1.0.1",
                    "expected_activation_sequence": 2,
                    "reason": "Restore canonical supported runtime",
                },
            )
            assert rolled_back.status_code == 201, rolled_back.text
            assert rolled_back.json()["activation_sequence"] == 3

            stale_rollback = await client.post(
                "/api/v1/skills/study-destination-compare/rollbacks",
                headers=headers(advisor, "http-skill-rollback-stale"),
                json={
                    "schema_version": 1,
                    "target_version": "1.0.0",
                    "expected_active_version": "1.0.1",
                    "expected_activation_sequence": 2,
                    "reason": "Stale rollback must fail closed",
                },
            )
            assert stale_rollback.status_code == 409
            assert stale_rollback.json()["code"] == "skill_activation_stale"

            catalog = await client.get("/api/v1/skills")
            runtime = next(
                item
                for item in catalog.json()["items"]
                if item["skill_key"] == "study-destination-compare"
            )
            assert runtime["latest_version"] == "1.0.1"
            assert runtime["active_version"] == "1.0.0"
            assert runtime["activation_sequence"] == 3
    finally:
        await engine.dispose()
        await reset_nonseed_skill_history()
