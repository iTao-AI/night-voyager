from fastapi.testclient import TestClient
from httpx2 import Response

from night_voyager.api import create_app


def test_health_reports_bootstrap_service() -> None:
    response: Response = TestClient(create_app()).get("/health")

    assert response.status_code == 200
    assert response.json() == {"service": "night-voyager-api", "status": "ok"}
