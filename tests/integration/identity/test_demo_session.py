from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from night_voyager.api import create_app
from night_voyager.config import Settings
from night_voyager.identity.errors import AuthenticationFailedError, StaleSessionError
from night_voyager.identity.models import ActorContext, ActorRole, DemoActorChoice
from night_voyager.identity.service import IssuedSession

ORIGIN = "http://127.0.0.1:3000"


class FakeIdentityService:
    def __init__(self) -> None:
        self.revoked = False
        self.stale_tokens: set[str] = {"stale-session"}

    async def mint(self, choice: DemoActorChoice) -> IssuedSession:
        return self._issued(choice)

    async def rotate(
        self, old_token: str, csrf_token: str, choice: DemoActorChoice
    ) -> IssuedSession:
        if old_token in self.stale_tokens:
            raise StaleSessionError
        if old_token != "opaque-advisor" or csrf_token != "csrf-advisor":
            raise AuthenticationFailedError
        return self._issued(choice)

    async def revoke(self, session_token: str, csrf_token: str) -> None:
        if session_token == "stale-session":
            raise StaleSessionError
        if not session_token or not csrf_token:
            raise AuthenticationFailedError
        self.revoked = True

    @staticmethod
    def _issued(choice: DemoActorChoice) -> IssuedSession:
        return IssuedSession(
            raw_session_token=f"opaque-{choice.value}",
            raw_csrf_token=f"csrf-{choice.value}",
            context=ActorContext(
                organization_id=UUID("10000000-0000-0000-0000-000000000001"),
                actor_id=UUID("20000000-0000-0000-0000-000000000001"),
                role=ActorRole(choice.value),
                session_id=UUID("30000000-0000-0000-0000-000000000001"),
            ),
        )


def _client(service: FakeIdentityService | None = None) -> TestClient:
    settings = Settings.model_validate(
        {
            "environment": "test",
            "demo_mode": True,
            "demo_allow_insecure_cookie": True,
            "allowed_origins": [ORIGIN],
        }
    )
    instance = service or FakeIdentityService()
    return TestClient(
        create_app(settings=settings, identity_service_factory=lambda _session: instance)
    )


def test_bootstrap_then_mint_sets_opaque_session_cookie() -> None:
    with _client() as client:
        bootstrap = client.get("/api/v1/demo/session-bootstrap", headers={"Origin": ORIGIN})
        csrf = bootstrap.json()["csrf_token"]
        response = client.post(
            "/api/v1/demo/sessions",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={"demo_actor": "advisor"},
        )

    assert response.status_code == 201
    assert response.json() == {
        "role": "advisor",
        "proof_mode": "synthetic-demo",
        "csrf_token": "csrf-advisor",
    }
    cookie = response.headers["set-cookie"]
    assert "night_voyager_session=opaque-advisor" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Max-Age=1800" in cookie
    assert "Secure" not in cookie


def test_rotation_requires_session_bound_csrf_and_replaces_role() -> None:
    with _client() as client:
        client.cookies.set("night_voyager_session", "opaque-advisor")
        response = client.post(
            "/api/v1/demo/sessions",
            headers={"Origin": ORIGIN, "X-CSRF-Token": "csrf-advisor"},
            json={"demo_actor": "parent"},
        )

    assert response.status_code == 201
    assert response.json()["role"] == "parent"
    assert "night_voyager_session=opaque-parent" in response.headers["set-cookie"]


def test_wrong_session_csrf_is_non_enumerating_and_does_not_clear_cookie() -> None:
    with _client() as client:
        client.cookies.set("night_voyager_session", "opaque-advisor")
        response = client.post(
            "/api/v1/demo/sessions",
            headers={"Origin": ORIGIN, "X-CSRF-Token": "wrong"},
            json={"demo_actor": "parent"},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "authentication failed"}
    assert "night_voyager_session=" not in response.headers.get("set-cookie", "")


def test_stale_session_is_cleared_before_fresh_bootstrap_and_mint() -> None:
    service = FakeIdentityService()
    with _client(service) as client:
        first_bootstrap = client.get(
            "/api/v1/demo/session-bootstrap", headers={"Origin": ORIGIN}
        )
        first_csrf = first_bootstrap.json()["csrf_token"]
        first_mint = client.post(
            "/api/v1/demo/sessions",
            headers={"Origin": ORIGIN, "X-CSRF-Token": first_csrf},
            json={"demo_actor": "advisor"},
        )
        assert first_mint.status_code == 201
        service.stale_tokens.add("opaque-advisor")
        stale = client.post(
            "/api/v1/demo/sessions",
            headers={"Origin": ORIGIN, "X-CSRF-Token": "unknown"},
            json={"demo_actor": "advisor"},
        )
        bootstrap = client.get("/api/v1/demo/session-bootstrap", headers={"Origin": ORIGIN})
        csrf = bootstrap.json()["csrf_token"]
        minted = client.post(
            "/api/v1/demo/sessions",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={"demo_actor": "advisor"},
        )

    assert stale.status_code == 401
    assert stale.json() == {"detail": "authentication failed"}
    assert "night_voyager_session=" in stale.headers["set-cookie"]
    assert "Max-Age=0" in stale.headers["set-cookie"]
    assert minted.status_code == 201


def test_missing_origin_csrf_and_spoofed_identity_fields_are_rejected() -> None:
    with _client() as client:
        assert client.get("/api/v1/demo/session-bootstrap").status_code == 403
        assert (
            client.post("/api/v1/demo/sessions", json={"demo_actor": "advisor"}).status_code == 403
        )
        bootstrap = client.get("/api/v1/demo/session-bootstrap", headers={"Origin": ORIGIN}).json()
        response = client.post(
            "/api/v1/demo/sessions",
            headers={"Origin": ORIGIN, "X-CSRF-Token": bootstrap["csrf_token"]},
            json={"demo_actor": "advisor", "organization_id": "spoof"},
        )
    assert response.status_code == 422


def test_delete_revokes_and_expires_cookie() -> None:
    service = FakeIdentityService()
    with _client(service) as client:
        client.cookies.set("night_voyager_session", "opaque-advisor")
        response = client.delete(
            "/api/v1/demo/session",
            headers={"Origin": ORIGIN, "X-CSRF-Token": "csrf-advisor"},
        )

    assert response.status_code == 204
    assert service.revoked
    assert "night_voyager_session=" in response.headers["set-cookie"]


def test_delete_clears_stale_session_cookie() -> None:
    with _client() as client:
        client.cookies.set("night_voyager_session", "stale-session")
        response = client.delete(
            "/api/v1/demo/session",
            headers={"Origin": ORIGIN, "X-CSRF-Token": "unknown"},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "authentication failed"}
    assert "night_voyager_session=" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_demo_endpoints_are_unavailable_when_disabled() -> None:
    app = create_app(settings=Settings.model_validate({"environment": "test"}))
    with TestClient(app) as client:
        response = client.get("/api/v1/demo/session-bootstrap", headers={"Origin": ORIGIN})
    assert response.status_code == 404
