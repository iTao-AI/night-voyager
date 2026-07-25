from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Protocol, TypeVar

from pydantic import BaseModel

from night_voyager.dra.live_models import (
    DraLiveRunEnvelopeV1,
    DraReceiptIdentityV1,
)
from night_voyager.dra.models import (
    DraCandidateImportV1,
    DraCanonicalResultProjectionV1,
    DraHealthProjectionV1,
    DraRunAcceptanceV1,
)
from night_voyager.dra.ports import DraCandidateViewV1
from night_voyager.identity.models import ActorContext

ReceiptModel = TypeVar("ReceiptModel", bound=BaseModel)


class DraLiveTransportPort(Protocol):
    async def health(self) -> DraHealthProjectionV1: ...

    async def create_run(
        self,
        request: Mapping[str, object],
        idempotency_key: str,
    ) -> DraRunAcceptanceV1: ...

    async def get_run(self, run_id: str) -> DraLiveRunEnvelopeV1: ...

    async def get_result(
        self, run_id: str
    ) -> DraCanonicalResultProjectionV1: ...


class DraCandidateGatewayPort(Protocol):
    async def import_candidate(
        self,
        context: ActorContext,
        candidate_import: DraCandidateImportV1,
        idempotency_key: str,
    ) -> DraCandidateViewV1: ...


class DraLiveReceiptStorePort(Protocol):
    def write_receipt(
        self, logical_name: str, model: BaseModel
    ) -> DraReceiptIdentityV1: ...

    def read_receipt(
        self, logical_name: str, model_type: type[ReceiptModel]
    ) -> ReceiptModel: ...

    def artifact_path(self) -> Path | None: ...


class DraLiveClockPort(Protocol):
    def monotonic(self) -> float: ...


class DraLiveSleepPort(Protocol):
    async def sleep(self, seconds: float) -> None: ...


AttemptIdFactory = Callable[[], str]
AsyncSignalHook = Callable[[], Awaitable[None]]
