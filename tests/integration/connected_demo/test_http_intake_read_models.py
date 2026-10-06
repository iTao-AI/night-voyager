from __future__ import annotations

import os

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from night_voyager.api import create_app
from night_voyager.config import Settings
from night_voyager.identity.demo_seed import INTAKE_REVISION_CASE_ID
from night_voyager.identity.models import DemoActorChoice
from night_voyager.identity.repository import IdentityRepository
from night_voyager.identity.service import IdentityService

pytestmark = pytest.mark.database


@pytest.mark.asyncio
async def test_controlled_intake_http_reads_are_versioned_and_role_safe() -> None:
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
        for role in (DemoActorChoice.ADVISOR, DemoActorChoice.PARENT):
            async with sessions() as session, session.begin():
                issued = await IdentityService(
                    IdentityRepository(session), settings.secret_key
                ).mint(role)
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://127.0.0.1:3000"
            ) as client:
                client.cookies.set("night_voyager_session", issued.raw_session_token)
                response = await client.get(
                    f"/api/v1/cases/{INTAKE_REVISION_CASE_ID}/advisor-ledger?contract_version=3"
                )
                if role is DemoActorChoice.PARENT:
                    assert response.status_code == 404
                    assert response.json()["code"] == "resource_unavailable"
                    continue
                assert response.status_code == 200, response.text
                assert response.headers["cache-control"] == "no-store"
                ledger = response.json()
                assert (ledger["schema_version"], ledger["case_intake"], ledger["phase"]) == (
                    3,
                    "2027-02",
                    "review_required",
                )
                for version in (None, "2"):
                    suffix = "" if version is None else f"?contract_version={version}"
                    legacy = await client.get(
                        f"/api/v1/cases/{INTAKE_REVISION_CASE_ID}/advisor-ledger{suffix}"
                    )
                    assert legacy.status_code == 503
                    assert legacy.json()["code"] == "demo_contract_unavailable"
                    assert legacy.json()["detail"] == "connected demo contract unavailable"
                    assert "intake" not in legacy.json()
    finally:
        await engine.dispose()
