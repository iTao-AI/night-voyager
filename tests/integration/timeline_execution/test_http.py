from __future__ import annotations

import os

import pytest
from httpx2 import ASGITransport, AsyncClient

from night_voyager.api import create_app
from night_voyager.config import Settings
from night_voyager.database import create_engine, create_session_factory

pytestmark = pytest.mark.database


@pytest.mark.asyncio
async def test_http_contract_closes_scenario_authentication_and_body_shape() -> None:
    engine = create_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    app = create_app(
        settings=Settings(database_url=os.environ["NIGHT_VOYAGER_API_DATABASE_URL"]),
        session_factory=create_session_factory(engine),
    )
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            invalid_scenario = await client.get(
                "/api/v1/plan-execution-context?scenario=arbitrary"
            )
            assert invalid_scenario.status_code == 422
            assert invalid_scenario.headers["content-type"].startswith(
                "application/problem+json"
            )
            assert invalid_scenario.json()["code"] == "request_validation_failed"

            unauthenticated = await client.get(
                "/api/v1/plan-execution-context"
                "?scenario=governed-plan-execution-v1"
            )
            assert unauthenticated.status_code == 401
            assert unauthenticated.json()["code"] == "authentication_failed"

            strict = await client.post(
                "/api/v1/timeline-plans/"
                "94000000-0000-0000-0000-000000000001/executions",
                headers={
                    "Origin": "http://127.0.0.1:3000",
                    "Content-Type": "application/json",
                },
                json={
                    "schema_version": 1,
                    "case_id": "40000000-0000-0000-0000-000000000001",
                    "expected_case_revision": 1,
                    "actor_id": "20000000-0000-0000-0000-000000000002",
                },
            )
            assert strict.status_code == 422
            assert strict.json()["code"] == "request_validation_failed"
    finally:
        await engine.dispose()
