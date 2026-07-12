from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from night_voyager.config import Settings
from night_voyager.identity.auth import (
    SESSION_LIFETIME,
    digest_token,
    generate_token,
    require_csrf,
    require_origin,
    session_expiry,
)
from night_voyager.identity.models import DemoActorChoice


def test_demo_actor_choices_are_closed() -> None:
    assert {choice.value for choice in DemoActorChoice} == {"advisor", "student", "parent"}
    with pytest.raises(ValueError):
        DemoActorChoice("organization-id")


def test_tokens_have_256_bits_and_digests_are_keyed() -> None:
    token = generate_token()
    raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))

    assert len(raw) == 32
    assert digest_token("secret-a", token) != digest_token("secret-b", token)
    assert len(digest_token("secret-a", token)) == 32


def test_origin_and_csrf_require_exact_matches() -> None:
    require_origin("http://127.0.0.1:3000", ("http://127.0.0.1:3000",))
    require_csrf("presented", "presented")

    with pytest.raises(ValueError, match="origin rejected"):
        require_origin(None, ("http://127.0.0.1:3000",))
    with pytest.raises(ValueError, match="origin rejected"):
        require_origin("http://localhost:3000", ("http://127.0.0.1:3000",))
    with pytest.raises(ValueError, match="csrf rejected"):
        require_csrf("wrong", "expected")


def test_session_expiry_is_exactly_thirty_minutes() -> None:
    now = datetime(2026, 7, 12, tzinfo=UTC)

    assert timedelta(minutes=30) == SESSION_LIFETIME
    assert session_expiry(now) == now + timedelta(minutes=30)


def test_production_rejects_demo_mode_and_insecure_cookie() -> None:
    with pytest.raises(ValidationError, match="production disables demo mode"):
        Settings.model_validate(
            {"environment": "production", "secret_key": "production-secret", "demo_mode": True}
        )
    with pytest.raises(ValidationError, match="production requires secure cookies"):
        Settings.model_validate(
            {
                "environment": "production",
                "secret_key": "production-secret",
                "demo_allow_insecure_cookie": True,
            }
        )


def test_insecure_cookie_requires_demo_mode_and_loopback_http_origins() -> None:
    with pytest.raises(ValidationError, match="insecure demo cookies require demo mode"):
        Settings.model_validate({"demo_allow_insecure_cookie": True})
    with pytest.raises(ValidationError, match="loopback HTTP origins"):
        Settings.model_validate(
            {
                "demo_mode": True,
                "demo_allow_insecure_cookie": True,
                "allowed_origins": ["https://example.com"],
            }
        )

    settings = Settings.model_validate(
        {
            "environment": "test",
            "demo_mode": True,
            "demo_allow_insecure_cookie": True,
            "allowed_origins": ["http://127.0.0.1:3000", "http://localhost:3000"],
        }
    )
    assert not settings.session_cookie_secure
