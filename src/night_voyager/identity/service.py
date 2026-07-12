from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from night_voyager.identity.auth import digest_token, generate_token, session_expiry
from night_voyager.identity.models import ActorContext, DemoActorChoice
from night_voyager.identity.repository import IdentityRepository


@dataclass(frozen=True, slots=True)
class IssuedSession:
    raw_session_token: str
    raw_csrf_token: str
    context: ActorContext


class IdentityService:
    def __init__(self, repository: IdentityRepository, secret_key: str) -> None:
        self._repository = repository
        self._secret_key = secret_key

    async def mint(self, choice: DemoActorChoice) -> IssuedSession:
        raw_session, raw_csrf = generate_token(), generate_token()
        context = await self._repository.mint(
            choice,
            uuid4(),
            digest_token(self._secret_key, raw_session),
            digest_token(self._secret_key, raw_csrf),
            session_expiry(datetime.now(UTC)),
        )
        return IssuedSession(raw_session, raw_csrf, context)

    async def resolve(self, raw_session: str) -> ActorContext | None:
        return await self._repository.resolve(digest_token(self._secret_key, raw_session))

    async def rotate(
        self, old_token: str, csrf_token: str, choice: DemoActorChoice
    ) -> IssuedSession:
        raw_session, raw_csrf = generate_token(), generate_token()
        context = await self._repository.rotate(
            digest_token(self._secret_key, old_token),
            digest_token(self._secret_key, csrf_token),
            choice,
            uuid4(),
            digest_token(self._secret_key, raw_session),
            digest_token(self._secret_key, raw_csrf),
            session_expiry(datetime.now(UTC)),
        )
        return IssuedSession(raw_session, raw_csrf, context)

    async def revoke(self, session_token: str, csrf_token: str) -> None:
        revoked = await self._repository.revoke(
            digest_token(self._secret_key, session_token),
            digest_token(self._secret_key, csrf_token),
        )
        if not revoked:
            raise ValueError("inactive session")
