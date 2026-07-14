from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from night_voyager.api import create_app
from night_voyager.config import Settings
from night_voyager.identity.demo_seed import CONNECTED_DEMO_CASE_ID
from night_voyager.identity.models import DemoActorChoice
from night_voyager.identity.repository import IdentityRepository
from night_voyager.identity.service import IdentityService

pytestmark = pytest.mark.database


def test_connected_demo_read_routes_are_registered() -> None:
    app = create_app()
    paths = app.openapi()["paths"]
    assert "get" in paths["/api/v1/cases/{case_id}/advisor-ledger"]
    assert "get" in paths["/api/v1/cases/{case_id}/current-decision-brief"]

def test_connected_demo_invalid_uuid_is_redacted_problem() -> None:
    response = TestClient(create_app()).get("/api/v1/cases/not-a-uuid/advisor-ledger")
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["code"] == "request_validation_failed"


@pytest.mark.asyncio
async def test_invalid_read_session_expires_both_identity_cookies() -> None:
    url = os.environ["NIGHT_VOYAGER_API_DATABASE_URL"]
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings.model_validate(
        {
            "environment": "test",
            "database_url": url,
            "demo_mode": True,
            "demo_allow_insecure_cookie": True,
            "allowed_origins": ["http://127.0.0.1:3000"],
            "secret_key": "test-session-secret",
        }
    )
    try:
        app = create_app(settings=settings, session_factory=sessions)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://127.0.0.1:3000"
        ) as client:
            client.cookies.set("night_voyager_session", "invalid")
            client.cookies.set("night_voyager_csrf_bootstrap", "stale")
            response = await client.get(
                f"/api/v1/cases/{CONNECTED_DEMO_CASE_ID}/advisor-ledger"
            )
        assert response.status_code == 401
        cookies = response.headers.get_list("set-cookie")
        assert len(cookies) == 2
        assert any("night_voyager_session=" in value and "Max-Age=0" in value for value in cookies)
        assert any(
            "night_voyager_csrf_bootstrap=" in value and "Max-Age=0" in value
            for value in cookies
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_task_ready_http_projection_is_real_and_no_store() -> None:
    url = os.environ["NIGHT_VOYAGER_API_DATABASE_URL"]
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings.model_validate(
        {
            "environment": "test",
            "database_url": url,
            "demo_mode": True,
            "demo_allow_insecure_cookie": True,
            "allowed_origins": ["http://127.0.0.1:3000"],
            "secret_key": "test-session-secret",
        }
    )
    try:
        async with sessions() as session, session.begin():
            issued = await IdentityService(
                IdentityRepository(session), settings.secret_key
            ).mint(DemoActorChoice.ADVISOR)
        app = create_app(settings=settings, session_factory=sessions)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://127.0.0.1:3000"
        ) as client:
            client.cookies.set("night_voyager_session", issued.raw_session_token)
            response = await client.get(
                f"/api/v1/cases/{CONNECTED_DEMO_CASE_ID}/advisor-ledger"
            )
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["phase"] == "task-ready"
        assert response.json()["task"] is None
    finally:
        await engine.dispose()
