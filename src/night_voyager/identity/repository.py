from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from night_voyager.identity.errors import AuthenticationFailedError, StaleSessionError
from night_voyager.identity.models import ActorContext, ActorRole, DemoActorChoice


class IdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def mint(
        self,
        choice: DemoActorChoice,
        session_id: UUID,
        session_digest: bytes,
        csrf_digest: bytes,
        expires_at: datetime,
    ) -> ActorContext:
        return await self._context_from_function(
            "SELECT * FROM auth.mint_demo_session(:choice, :session_id, :session_digest, "
            ":csrf_digest, :expires_at)",
            {
                "choice": choice.value,
                "session_id": session_id,
                "session_digest": session_digest,
                "csrf_digest": csrf_digest,
                "expires_at": expires_at,
            },
        )

    async def resolve(self, session_digest: bytes) -> ActorContext | None:
        result = await self._session.execute(
            text("SELECT * FROM auth.resolve_demo_session(:session_digest)"),
            {"session_digest": session_digest},
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        context = self._map_context(row)
        await self.set_actor_context(context)
        return context

    async def rotate(
        self,
        old_digest: bytes,
        old_csrf_digest: bytes,
        choice: DemoActorChoice,
        session_id: UUID,
        session_digest: bytes,
        csrf_digest: bytes,
        expires_at: datetime,
    ) -> ActorContext:
        try:
            return await self._context_from_function(
                "SELECT * FROM auth.rotate_demo_session(:old_digest, :old_csrf_digest, :choice, "
                ":session_id, :session_digest, :csrf_digest, :expires_at)",
                {
                    "old_digest": old_digest,
                    "old_csrf_digest": old_csrf_digest,
                    "choice": choice.value,
                    "session_id": session_id,
                    "session_digest": session_digest,
                    "csrf_digest": csrf_digest,
                    "expires_at": expires_at,
                },
            )
        except DBAPIError as error:
            sqlstate = getattr(error.orig, "sqlstate", None)
            if sqlstate == "NV001":
                raise StaleSessionError from error
            if sqlstate == "NV002":
                raise AuthenticationFailedError from error
            raise

    async def revoke(self, session_digest: bytes, csrf_digest: bytes) -> bool:
        result = await self._session.execute(
            text("SELECT auth.revoke_demo_session(:session_digest, :csrf_digest)"),
            {"session_digest": session_digest, "csrf_digest": csrf_digest},
        )
        return bool(result.scalar_one())

    async def set_actor_context(self, context: ActorContext) -> None:
        for key, value in (
            ("organization_id", context.organization_id),
            ("actor_id", context.actor_id),
            ("role", context.role.value),
            ("session_id", context.session_id),
        ):
            await self._session.execute(
                text("SELECT set_config(:key, :value, true)"),
                {"key": f"night_voyager.{key}", "value": str(value)},
            )

    async def _context_from_function(self, sql: str, parameters: dict[str, object]) -> ActorContext:
        result = await self._session.execute(text(sql), parameters)
        context = self._map_context(result.mappings().one())
        await self.set_actor_context(context)
        return context

    @staticmethod
    def _map_context(row: object) -> ActorContext:
        mapping = row  # kept explicit so all database output crosses one mapping boundary
        return ActorContext(
            organization_id=mapping["organization_id"],  # type: ignore[index]
            actor_id=mapping["actor_id"],  # type: ignore[index]
            role=ActorRole(mapping["role"]),  # type: ignore[index]
            session_id=mapping["session_id"],  # type: ignore[index]
        )
