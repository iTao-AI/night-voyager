from __future__ import annotations

import json
import os
from uuid import UUID

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from night_voyager.api import create_app
from night_voyager.config import Settings
from night_voyager.dra.fixtures import build_fixture_candidate_import
from night_voyager.identity.models import DemoActorChoice
from night_voyager.identity.repository import IdentityRepository
from night_voyager.identity.service import IdentityService, IssuedSession

pytestmark = pytest.mark.database
ORIGIN = "http://127.0.0.1:3000"
ORG = UUID("10000000-0000-0000-0000-000000000001")
CASE = UUID("40000000-0000-0000-0000-000000000310")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
STUDENT = UUID("20000000-0000-0000-0000-000000000002")
PARENT = UUID("20000000-0000-0000-0000-000000000003")


async def ensure_case() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            if not await connection.scalar(
                text("SELECT EXISTS(SELECT 1 FROM app.student_cases WHERE id=:case)"),
                {"case": CASE},
            ):
                await connection.execute(
                    text("SELECT app.publish_case_revision(:org,:case,NULL,1,'{}','{}')"),
                    {"org": ORG, "case": CASE},
                )
                await connection.execute(
                    text("SELECT app.transition_case(:org,:case,'intake','planning')"),
                    {"org": ORG, "case": CASE},
                )
            await connection.execute(
                text("SELECT app.seed_case_participants(:org,:case,:advisor,:student,:parent)"),
                {
                    "org": ORG,
                    "case": CASE,
                    "advisor": ADVISOR,
                    "student": STUDENT,
                    "parent": PARENT,
                },
            )
    finally:
        await engine.dispose()


async def mint(
    sessions: async_sessionmaker[AsyncSession], choice: DemoActorChoice
) -> IssuedSession:
    async with sessions() as session, session.begin():
        return await IdentityService(IdentityRepository(session), "test-session-secret").mint(
            choice
        )


def import_payload() -> dict[str, object]:
    payload = build_fixture_candidate_import().model_dump(mode="json", exclude_computed_fields=True)
    payload.pop("organization_id")
    payload.pop("case_id")
    return payload


def request_headers(session: IssuedSession, key: str) -> dict[str, str]:
    return {
        "Origin": ORIGIN,
        "X-CSRF-Token": session.raw_csrf_token,
        "Idempotency-Key": key,
    }


@pytest.mark.asyncio
async def test_dra_http_is_strict_bounded_and_advisor_only() -> None:
    await ensure_case()
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
            payload = import_payload()
            client.cookies.set("night_voyager_session", advisor.raw_session_token)
            invalid = await client.post(
                f"/api/v1/cases/{CASE}/dra-candidates",
                headers=request_headers(advisor, "dra-http-invalid-0001"),
                json={**payload, "authority": "externally_verified"},
            )
            assert invalid.status_code == 422
            assert invalid.headers["cache-control"] == "no-store"
            missing_key = await client.post(
                f"/api/v1/cases/{CASE}/dra-candidates",
                headers={"Origin": ORIGIN, "X-CSRF-Token": advisor.raw_csrf_token},
                json=payload,
            )
            assert missing_key.status_code == 400
            rejected_origin = await client.post(
                f"/api/v1/cases/{CASE}/dra-candidates",
                headers={
                    **request_headers(advisor, "dra-http-origin-0001"),
                    "Origin": "https://evil.invalid",
                },
                json=payload,
            )
            assert rejected_origin.status_code == 403
            imported = await client.post(
                f"/api/v1/cases/{CASE}/dra-candidates",
                headers=request_headers(advisor, "dra-http-import-0001"),
                json=payload,
            )
            assert imported.status_code == 201, imported.text
            assert imported.headers["cache-control"] == "no-store"
            assert "content" not in json.dumps(imported.json()).lower()
            candidate_id = imported.json()["candidate_id"]
            replay = await client.post(
                f"/api/v1/cases/{CASE}/dra-candidates",
                headers=request_headers(advisor, "dra-http-import-0001"),
                json=payload,
            )
            assert replay.json() == {**imported.json(), "replayed": True}
            read = await client.get(f"/api/v1/cases/{CASE}/dra-candidates/{candidate_id}")
            assert read.status_code == 200
            assert read.headers["cache-control"] == "no-store"
            bounded = json.dumps(read.json()).lower()
            assert "synthetic research report" not in bounded
            assert "snapshot_byte" not in bounded
            client.cookies.set("night_voyager_session", parent.raw_session_token)
            hidden = await client.get(f"/api/v1/cases/{CASE}/dra-candidates/{candidate_id}")
            assert hidden.status_code == 404
            assert "synthetic research report" not in hidden.text.lower()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_dra_http_reject_is_terminal_and_conflicts_are_closed() -> None:
    await ensure_case()
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
        app = create_app(settings=settings, session_factory=sessions)
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            client.cookies.set("night_voyager_session", advisor.raw_session_token)
            imported = await client.post(
                f"/api/v1/cases/{CASE}/dra-candidates",
                headers=request_headers(advisor, "dra-http-import-0002"),
                json=import_payload(),
            )
            candidate_id = imported.json()["candidate_id"]
            evidence_id = build_fixture_candidate_import().evidence[0].evidence_id
            payload = {
                "schema_version": 1,
                "expected_case_revision": 1,
                "dra_evidence_id": evidence_id,
                "decision": "reject",
                "reason": "Source does not support the bounded claim.",
            }
            decision = await client.post(
                f"/api/v1/cases/{CASE}/dra-candidates/{candidate_id}/verification-decisions",
                headers=request_headers(advisor, "dra-http-reject-0001"),
                json=payload,
            )
            assert decision.status_code == 201, decision.text
            assert decision.json()["decision"] == "reject"
            replay = await client.post(
                f"/api/v1/cases/{CASE}/dra-candidates/{candidate_id}/verification-decisions",
                headers=request_headers(advisor, "dra-http-reject-0001"),
                json=payload,
            )
            assert replay.json()["replayed"] is True
            conflict = await client.post(
                f"/api/v1/cases/{CASE}/dra-candidates/{candidate_id}/verification-decisions",
                headers=request_headers(advisor, "dra-http-reject-0002"),
                json=payload,
            )
            assert conflict.status_code == 409
            assert conflict.headers["cache-control"] == "no-store"
    finally:
        await engine.dispose()
