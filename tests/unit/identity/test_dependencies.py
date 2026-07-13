from __future__ import annotations

import pytest
from fastapi import HTTPException

from night_voyager.interfaces.http.dependencies import resolve_actor_context


class Resolver:
    async def resolve(self, raw_session: str) -> object | None:
        return {"session": raw_session} if raw_session == "active" else None

    async def resolve_with_csrf(self, raw_session: str, raw_csrf: str) -> object | None:
        if raw_session == "active" and raw_csrf == "bound":
            return {"session": raw_session}
        return None


@pytest.mark.asyncio
async def test_request_context_rejects_missing_or_inactive_sessions() -> None:
    with pytest.raises(HTTPException) as missing:
        await resolve_actor_context(None, Resolver())
    with pytest.raises(HTTPException) as inactive:
        await resolve_actor_context("revoked", Resolver())

    assert missing.value.status_code == 401
    assert inactive.value.status_code == 401


@pytest.mark.asyncio
async def test_request_context_returns_active_identity() -> None:
    assert await resolve_actor_context("active", Resolver()) == {"session": "active"}


@pytest.mark.asyncio
async def test_mutation_context_requires_session_bound_csrf() -> None:
    from night_voyager.interfaces.http.dependencies import resolve_mutation_actor_context

    with pytest.raises(HTTPException) as wrong:
        await resolve_mutation_actor_context("active", "wrong", Resolver())
    assert wrong.value.status_code == 401
    assert await resolve_mutation_actor_context("active", "bound", Resolver()) == {
        "session": "active"
    }
