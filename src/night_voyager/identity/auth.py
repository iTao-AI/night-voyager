from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

SESSION_LIFETIME = timedelta(minutes=30)
BOOTSTRAP_LIFETIME = timedelta(minutes=5)


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def digest_token(secret_key: str, raw_token: str) -> bytes:
    return hmac.new(secret_key.encode(), raw_token.encode(), hashlib.sha256).digest()


def require_origin(origin: str | None, allowed_origins: tuple[str, ...]) -> None:
    if origin is None or not any(hmac.compare_digest(origin, item) for item in allowed_origins):
        raise ValueError("origin rejected")


def require_csrf(presented: str | None, expected: str | None) -> None:
    if presented is None or expected is None or not hmac.compare_digest(presented, expected):
        raise ValueError("csrf rejected")


def session_expiry(now: datetime) -> datetime:
    return now + SESSION_LIFETIME
