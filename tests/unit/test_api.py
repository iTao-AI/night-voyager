from typing import cast

from fastapi.testclient import TestClient
from httpx import Response

from night_voyager.api import create_app


def test_health_reports_bootstrap_service() -> None:
    response = cast(
        Response,
        TestClient(create_app()).get("/health"),  # pyright: ignore[reportUnknownMemberType]
    )

    assert response.status_code == 200
    assert response.json() == {"service": "night-voyager-api", "status": "ok"}
