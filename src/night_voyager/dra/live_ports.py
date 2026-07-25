from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Protocol, TypeVar
from uuid import UUID

from pydantic import BaseModel

from night_voyager.dra.live_models import (
    DraDecisionAuthorityV1,
    DraLiveRunEnvelopeV1,
    DraPlanningTaskProjectionV1,
    DraReceiptIdentityV1,
    DraReviewAuthorityV1,
)
from night_voyager.dra.models import (
    DraCandidateImportV1,
    DraCanonicalResultProjectionV1,
    DraHealthProjectionV1,
    DraRunAcceptanceV1,
)
from night_voyager.dra.ports import (
    DraCandidateViewV1,
    DraVerificationViewV1,
    VerifyDraCandidateCommand,
)
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

    async def get_result(self, run_id: str) -> DraCanonicalResultProjectionV1: ...


class DraCandidateGatewayPort(Protocol):
    async def import_candidate(
        self,
        context: ActorContext,
        candidate_import: DraCandidateImportV1,
        idempotency_key: str,
    ) -> DraCandidateViewV1: ...


class DraPromotionGatewayPort(Protocol):
    async def get_candidate(
        self,
        context: ActorContext,
        case_id: UUID,
        candidate_id: UUID,
    ) -> DraCandidateViewV1 | None: ...

    async def promote_candidate(
        self,
        context: ActorContext,
        command: VerifyDraCandidateCommand,
        idempotency_key: str,
    ) -> DraVerificationViewV1: ...


class DraClosureGatewayPort(Protocol):
    async def get_promoted_mapping(
        self, context: ActorContext, case_id: UUID, candidate_id: UUID
    ) -> tuple[UUID, int] | None: ...

    async def get_task(
        self, context: ActorContext, idempotency_key: str
    ) -> DraPlanningTaskProjectionV1 | None: ...

    async def create_task(
        self,
        context: ActorContext,
        case_id: UUID,
        expected_revision: int,
        source_pack_id: UUID,
        source_pack_version: int,
        idempotency_key: str,
    ) -> DraPlanningTaskProjectionV1: ...

    async def get_review(
        self, context: ActorContext, case_id: UUID, planning_run_id: UUID
    ) -> DraReviewAuthorityV1 | None: ...

    async def record_review(
        self,
        context: ActorContext,
        case_id: UUID,
        expected_revision: int,
        planning_run_id: UUID,
        eligible_route_ids: tuple[UUID, ...],
        idempotency_key: str,
    ) -> DraReviewAuthorityV1: ...

    async def get_decision(
        self, context: ActorContext, brief_id: UUID
    ) -> DraDecisionAuthorityV1 | None: ...

    async def record_decision(
        self,
        context: ActorContext,
        brief_id: UUID,
        expected_brief_version: int,
        selected_route_id: UUID,
        budget_min: int,
        budget_max: int,
        trade_offs: tuple[str, ...],
        idempotency_key: str,
    ) -> DraDecisionAuthorityV1: ...


class DraLiveReceiptStorePort(Protocol):
    def write_receipt(self, logical_name: str, model: BaseModel) -> DraReceiptIdentityV1: ...

    def read_receipt(self, logical_name: str, model_type: type[ReceiptModel]) -> ReceiptModel: ...

    def artifact_path(self) -> Path | None: ...


class DraLiveClockPort(Protocol):
    def monotonic(self) -> float: ...


class DraLiveSleepPort(Protocol):
    async def sleep(self, seconds: float) -> None: ...


AttemptIdFactory = Callable[[], str]
AsyncSignalHook = Callable[[], Awaitable[None]]
