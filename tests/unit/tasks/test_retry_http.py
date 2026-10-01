import pytest
from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from night_voyager.config import Settings
from night_voyager.interfaces.http.tasks import create_task_router


@pytest.mark.asyncio
async def test_retry_http_enforces_origin_and_strict_pin_free_payload_before_io():
    engine = create_async_engine("postgresql+asyncpg://unused:unused@127.0.0.1:1/unused")
    app = FastAPI()
    app.include_router(
        create_task_router(
            Settings.model_validate(
                {
                    "environment": "test",
                    "secret_key": "test-secret",
                    "allowed_origins": ["http://127.0.0.1:3000"],
                }
            ),
            async_sessionmaker(engine),
        )
    )
    path = "/api/v1/tasks/80000000-0000-0000-0000-000000000001/retry"
    body = {"schema_version": 1, "expected_row_version": 7, "expected_case_revision": 1}
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://127.0.0.1:3000"
        ) as client:
            denied = await client.post(
                path,
                json=body,
                headers={"Origin": "https://evil.invalid", "Idempotency-Key": "key"},
            )
            assert denied.status_code == 403
            for invalid in (
                {**body, "source_pack_id": "50000000-0000-0000-0000-000000000001"},
                {**body, "expected_row_version": 0},
                {**body, "expected_case_revision": 0},
                {**body, "expected_row_version": "7"},
                {**body, "expected_row_version": True},
                {**body, "expected_case_revision": 1.0},
                {**body, "schema_version": True},
            ):
                assert (await client.post(path, json=invalid)).status_code == 422
            assert (
                await client.post(path, json=body, headers={"Origin": "http://127.0.0.1:3000"})
            ).status_code == 400
    finally:
        await engine.dispose()
