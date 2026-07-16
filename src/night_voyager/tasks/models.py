from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, PositiveInt


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AgentTaskState(StrEnum):
    QUEUED = "queued"
    LEASED = "leased"
    RUNNING = "running"
    WAITING_REVIEW = "waiting_review"
    SUCCEEDED = "succeeded"
    BLOCKED = "blocked"
    TIMED_OUT = "timed_out"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentExecutionState(StrEnum):
    LEASED = "leased"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    RETRY_SCHEDULED = "retry_scheduled"
    BLOCKED = "blocked"
    TIMED_OUT = "timed_out"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DISCARDED = "discarded"


class TaskViewStatus(StrEnum):
    PREPARING = "preparing"
    NEEDS_ADVISOR_REVIEW = "needs_advisor_review"
    READY = "ready"
    NEEDS_EVIDENCE = "needs_evidence"
    TIMED_OUT = "timed_out"
    FAILED = "failed"
    CANCELLED = "cancelled"
    OUTDATED = "outdated"


class TaskEventCode(StrEnum):
    QUEUED = "queued"
    LEASE_ACQUIRED = "lease_acquired"
    EXECUTION_STARTED = "execution_started"
    HEARTBEAT_RECORDED = "heartbeat_recorded"
    RETRY_SCHEDULED = "retry_scheduled"
    LEASE_RECLAIMED = "lease_reclaimed"
    WAITING_REVIEW = "waiting_review"
    SUCCEEDED = "succeeded"
    BLOCKED = "blocked"
    TIMED_OUT = "timed_out"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskRuntimePolicy(FrozenModel):
    lease_seconds: int = 60
    heartbeat_seconds: int = 15
    poll_seconds: int = 1
    sse_heartbeat_seconds: int = 15
    max_attempts: int = 3
    sse_page_size: int = 100
    max_payload_bytes: int = 1024 * 1024
    max_narrative_bytes: int = 64 * 1024
    max_evidence_refs: int = 20


type PlanningOperation = Literal[
    "generate_planning_run_v1",
    "generate_governed_mixed_planning_run_v1",
]


class CreateTaskCommand(FrozenModel):
    case_id: UUID
    operation: PlanningOperation = "generate_planning_run_v1"
    expected_case_revision: PositiveInt
    source_pack_id: UUID
    source_pack_version: PositiveInt
    policy_version: Literal["m3a-policy-v1"] = "m3a-policy-v1"


class CancelTaskCommand(FrozenModel):
    task_id: UUID
    expected_row_version: PositiveInt
