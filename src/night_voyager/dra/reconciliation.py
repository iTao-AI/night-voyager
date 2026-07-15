from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from night_voyager.dra.models import DraRunAcceptanceV1


class DraTransportError(RuntimeError):
    code = "dra_transport_failed"

    def __init__(self) -> None:
        super().__init__(self.code)


class DraTransportConflict(DraTransportError):
    code = "dra_idempotency_conflict"


class DraReconciliationRequired(DraTransportError):
    code = "dra_reconciliation_required"


class DraAmbiguousOutcome(DraTransportError):
    code = "dra_transport_ambiguous"

    def __init__(self, observed: DraRunAcceptanceV1 | None = None) -> None:
        self.observed = observed
        super().__init__()


class DraTransport(Protocol):
    async def create_run(
        self, request: Mapping[str, object], idempotency_key: str
    ) -> DraRunAcceptanceV1: ...


class DraRunReconciler:
    def __init__(self, transport: DraTransport) -> None:
        self._transport = transport

    async def create(
        self, request: Mapping[str, object], idempotency_key: str
    ) -> DraRunAcceptanceV1:
        if len(idempotency_key) < 16 or any(character.isspace() for character in idempotency_key):
            raise ValueError("dra_idempotency_key_invalid")
        try:
            return await self._transport.create_run(request, idempotency_key)
        except DraAmbiguousOutcome as ambiguous:
            try:
                replay = await self._transport.create_run(request, idempotency_key)
            except DraAmbiguousOutcome as error:
                raise DraReconciliationRequired() from error
            if not replay.idempotent_replay:
                raise DraReconciliationRequired() from ambiguous
            if ambiguous.observed is not None and (
                replay.thread_id,
                replay.run_id,
                replay.segment_id,
            ) != (
                ambiguous.observed.thread_id,
                ambiguous.observed.run_id,
                ambiguous.observed.segment_id,
            ):
                raise DraReconciliationRequired() from ambiguous
            return replay
