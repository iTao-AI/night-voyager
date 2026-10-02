# ruff: noqa: E501
from __future__ import annotations

import os
from uuid import uuid4

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from night_voyager.api import create_app
from night_voyager.config import Settings
from night_voyager.identity.models import DemoActorChoice
from tests.integration.tasks.test_http_tasks import ORIGIN, mint, mutation_headers
from tests.integration.tasks.test_terminal_recovery import failed_source

pytestmark = pytest.mark.database


@pytest.mark.asyncio
async def test_retry_real_http_security_versions_conflict_and_exact_replay():
    _, source, version = await failed_source("deadline_exceeded")
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
        body = {"schema_version": 1, "expected_row_version": version, "expected_case_revision": 1}
        key = str(uuid4())
        path = f"/api/v1/tasks/{source}/retry"
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            assert (
                await client.post(path, headers={"Origin": "https://evil.invalid"}, json=body)
            ).status_code == 403
            client.cookies.set("night_voyager_session", parent.raw_session_token)
            assert (
                await client.post(path, headers=mutation_headers(parent, key), json=body)
            ).status_code == 404
            client.cookies.set("night_voyager_session", advisor.raw_session_token)
            assert (
                await client.post(
                    path,
                    headers={**mutation_headers(advisor, key), "X-CSRF-Token": "wrong"},
                    json=body,
                )
            ).status_code == 401
            assert (
                await client.post(
                    path,
                    headers=mutation_headers(advisor, key),
                    json={**body, "source_pack_version": 1},
                )
            ).status_code == 422
            assert (
                await client.post(
                    path,
                    headers=mutation_headers(advisor, key),
                    json={**body, "expected_row_version": version - 1},
                )
            ).status_code == 409
            first = await client.post(path, headers=mutation_headers(advisor, key), json=body)
            assert first.status_code == 202, first.text
            new_task = first.json()
            assert new_task["task_id"] != str(source)
            assert new_task["status"] == "preparing"
            assert first.headers["Cache-Control"] == "no-store"
            replay = await client.post(path, headers=mutation_headers(advisor, key), json=body)
            assert replay.status_code == 202 and replay.json()["task_id"] == new_task["task_id"]
            assert replay.json()["replayed"] is True
            stale_ledger_click = await client.post(
                path, headers=mutation_headers(advisor, str(uuid4())), json=body
            )
            assert stale_ledger_click.status_code == 409
            assert stale_ledger_click.json()["code"] == "task_retry_ineligible"
    finally:
        await engine.dispose()
