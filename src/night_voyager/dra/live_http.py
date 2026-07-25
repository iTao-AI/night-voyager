from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from night_voyager.dra.ports import (
    DraCandidateViewV1,
    DraVerificationViewV1,
    VerifyDraCandidateCommand,
)
from night_voyager.identity.models import ActorContext


class HttpResponsePort(Protocol):
    @property
    def status_code(self) -> int: ...

    def json(self) -> object: ...

    def raise_for_status(self) -> None: ...


class AsyncHttpClientPort(Protocol):
    async def get(self, url: str, *, headers: dict[str, str]) -> HttpResponsePort: ...

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: object,
    ) -> HttpResponsePort: ...


@dataclass(frozen=True, slots=True)
class EphemeralHttpAuthority:
    origin: str
    session_value: str
    csrf_value: str


class NightVoyagerAuthorityGateway:
    """Narrow HTTP adapter; ephemeral authority values never enter receipts."""

    def __init__(
        self,
        client: AsyncHttpClientPort,
        authority: EphemeralHttpAuthority,
    ) -> None:
        self._client = client
        self._authority = authority

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {
            "Origin": self._authority.origin,
            "X-CSRF-Token": self._authority.csrf_value,
            "Cookie": (f"night_voyager_session={self._authority.session_value}"),
        }
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    async def get_candidate(
        self,
        context: ActorContext,
        case_id: UUID,
        candidate_id: UUID,
    ) -> DraCandidateViewV1 | None:
        del context
        response = await self._client.get(
            f"/api/v1/cases/{case_id}/dra-candidates/{candidate_id}",
            headers=self._headers(),
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return DraCandidateViewV1.model_validate(response.json())

    async def promote_candidate(
        self,
        context: ActorContext,
        command: VerifyDraCandidateCommand,
        idempotency_key: str,
    ) -> DraVerificationViewV1:
        del context
        response = await self._client.post(
            (
                f"/api/v1/cases/{command.case_id}/dra-candidates/"
                f"{command.candidate_id}/verification-decisions"
            ),
            headers=self._headers(idempotency_key),
            json={
                "schema_version": 1,
                "expected_case_revision": command.expected_case_revision,
                "dra_evidence_id": command.dra_evidence_id,
                "decision": command.decision,
                "reason": command.reason,
                "source_attestation": (
                    command.source_attestation.model_dump(mode="json")
                    if command.source_attestation is not None
                    else None
                ),
            },
        )
        response.raise_for_status()
        return DraVerificationViewV1.model_validate(response.json())
