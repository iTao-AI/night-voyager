from __future__ import annotations

from typing import Protocol

from fastapi import HTTPException, status


class ContextResolver[T](Protocol):
    async def resolve(self, raw_session: str) -> T | None: ...


class MutationContextResolver[T](Protocol):
    async def resolve_with_csrf(self, raw_session: str, raw_csrf: str) -> T | None: ...


async def resolve_actor_context[T](raw_session: str | None, service: ContextResolver[T]) -> T:
    if raw_session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication failed")
    context = await service.resolve(raw_session)
    if context is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication failed")
    return context


async def resolve_mutation_actor_context[T](
    raw_session: str | None, raw_csrf: str | None, service: MutationContextResolver[T]
) -> T:
    if raw_session is None or raw_csrf is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication failed")
    context = await service.resolve_with_csrf(raw_session, raw_csrf)
    if context is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication failed")
    return context
