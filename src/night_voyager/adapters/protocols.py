from __future__ import annotations

from enum import StrEnum
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, PositiveInt, model_validator


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AdapterFailureCode(StrEnum):
    TRANSIENT_UNAVAILABLE = "transient_unavailable"
    TRANSPORT_INTERRUPTED = "transport_interrupted"
    LEASE_EXPIRED = "lease_expired"
    DEADLINE_EXCEEDED = "deadline_exceeded"
    REQUIRED_EVIDENCE_GAP = "required_evidence_gap"
    INVALID_SCHEMA = "invalid_schema"
    PIN_MISMATCH = "pin_mismatch"
    FALLBACK_AUTHORITY = "fallback_authority"
    OVERSIZE = "oversize"
    POLICY_REJECTED = "policy_rejected"
    UNKNOWN = "unknown"


class PlanningAdapterRequest(FrozenModel):
    schema_version: Literal[1]
    operation: Literal[
        "generate_planning_run_v1", "generate_governed_mixed_planning_run_v1"
    ]
    organization_id: UUID
    case_id: UUID
    case_revision: PositiveInt
    source_pack_id: UUID
    source_pack_version: PositiveInt
    policy_version: Literal["m3a-policy-v1"]


class AdapterPayload(FrozenModel):
    payload: bytes
    adapter_id: Literal["deterministic_planning", "governed_mixed_planning"] = (
        "deterministic_planning"
    )
    adapter_version: Literal["m4a-v1", "dra-mixed-v1"] = "m4a-v1"

    @model_validator(mode="after")
    def exact_adapter_pair(self) -> AdapterPayload:
        if (self.adapter_id, self.adapter_version) not in {
            ("deterministic_planning", "m4a-v1"),
            ("governed_mixed_planning", "dra-mixed-v1"),
        }:
            raise ValueError("adapter identity must be an approved exact pair")
        return self


class AdapterFailure(FrozenModel):
    code: AdapterFailureCode


type AdapterOutcome = AdapterPayload | AdapterFailure


class PlanningAdapter(Protocol):
    async def generate(self, request: PlanningAdapterRequest) -> AdapterOutcome: ...
