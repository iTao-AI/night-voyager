from fastapi.testclient import TestClient
from httpx2 import Response

from night_voyager.api import create_app


def test_health_reports_bootstrap_service() -> None:
    response: Response = TestClient(create_app()).get("/health")

    assert response.status_code == 200
    assert response.json() == {"service": "night-voyager-api", "status": "ok"}


def test_m3b_http_matrix_is_registered() -> None:
    paths = create_app().openapi()["paths"]
    assert "post" in paths["/api/v1/cases/{case_id}/advisor-reviews"]
    assert "get" in paths["/api/v1/decision-briefs/{brief_id}"]
    assert "post" in paths["/api/v1/decision-briefs/{brief_id}/family-decisions"]
    assert "post" in paths["/api/v1/decision-briefs/{brief_id}/advisor-recorded-decisions"]
