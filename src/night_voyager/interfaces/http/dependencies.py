from __future__ import annotations

from typing import Protocol

from fastapi import HTTPException, status


class ContextResolver[T](Protocol):
    async def resolve(self, raw_session: str) -> T | None: ...


async def resolve_actor_context[T](raw_session: str | None, service: ContextResolver[T]) -> T:
    if raw_session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication failed")
    context = await service.resolve(raw_session)
    if context is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication failed")
    return context
