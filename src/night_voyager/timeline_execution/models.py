from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, PositiveInt, field_validator, model_validator


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    @field_validator("created_at", "updated_at", mode="after", check_fields=False)
    @classmethod
    def aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class TimelineExecutionState(StrEnum):
    ACTIVE = "active"
    REASSESSMENT_REQUIRED = "reassessment_required"
    COMPLETED = "completed"


class TimelineCheckpointState(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_ADVISOR = "awaiting_advisor"
    VERIFIED = "verified"
    BLOCKED = "blocked"


class TimelineRiskState(StrEnum):
    ON_TRACK = "on_track"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"


class CheckpointAttestationKind(StrEnum):
    PROGRESS = "progress"
    COMPLETION = "completion"
    BLOCKED = "blocked"


class CheckpointStatusCode(StrEnum):
    WORK_IN_PROGRESS = "work_in_progress"
    READY_FOR_ADVISOR = "ready_for_advisor"
    WORK_BLOCKED = "work_blocked"


class CheckpointAttestationCode(StrEnum):
    DOCUMENTS_STATUS_CONFIRMED = "documents_status_confirmed"
    APPLICATION_STATUS_CONFIRMED = "application_status_confirmed"
    VISA_STATUS_CONFIRMED = "visa_status_confirmed"
    ARRIVAL_STATUS_CONFIRMED = "arrival_status_confirmed"


class CheckpointAttestationReasonCode(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    MISSING_REQUIRED_INPUT = "missing_required_input"
    EXTERNAL_DEPENDENCY_UNAVAILABLE = "external_dependency_unavailable"
    DEADLINE_AT_RISK = "deadline_at_risk"


class CheckpointVerificationAction(StrEnum):
    VERIFY = "verify"
    REQUEST_UPDATE = "request_update"


class CheckpointVerificationReasonCode(StrEnum):
    ATTESTATION_VERIFIED = "attestation_verified"
    STATUS_UPDATE_REQUIRED = "status_update_required"
    STATUS_INCONSISTENT = "status_inconsistent"


class ReassessmentTrigger(StrEnum):
    BLOCKED_ATTESTATION = "blocked_attestation"
    DEADLINE_ELAPSED = "deadline_elapsed"


class TimelineCurrentActionCode(StrEnum):
    CHECKPOINT_ATTESTATION_REQUIRED = "checkpoint_attestation_required"
    ADVISOR_VERIFICATION_REQUIRED = "advisor_verification_required"
    EXECUTION_COMPLETED = "execution_completed"
    REASSESSMENT_HANDOFF_REQUIRED = "reassessment_handoff_required"


class TimelineRiskCode(StrEnum):
    CHECKPOINT_DUE_SOON = "checkpoint_due_soon"
    CHECKPOINT_OVERDUE = "checkpoint_overdue"
    CHECKPOINT_BLOCKED = "checkpoint_blocked"


class TimelineChecklistCode(StrEnum):
    DOCUMENTS_CONFIRM_STATUS = "documents_confirm_status"
    DOCUMENTS_PREPARE_REQUIRED_ITEMS = "documents_prepare_required_items"
    APPLICATION_CONFIRM_STATUS = "application_confirm_status"
    APPLICATION_REVIEW_DEADLINE = "application_review_deadline"
    VISA_CONFIRM_STATUS = "visa_confirm_status"
    VISA_REVIEW_DEADLINE = "visa_review_deadline"
    ARRIVAL_CONFIRM_STATUS = "arrival_confirm_status"
    ARRIVAL_REVIEW_DEADLINE = "arrival_review_deadline"


class CheckpointSeed(FrozenModel):
    ordinal: PositiveInt
    milestone_key: Literal["documents", "application", "visa", "arrival"]
    due_date: date
    accountable_role: Literal["student", "parent"]


class TimelineExecutionV1(FrozenModel):
    schema_version: Literal[1]
    execution_id: UUID
    case_id: UUID
    case_revision: PositiveInt
    decision_id: UUID
    decision_receipt_id: UUID
    timeline_plan_id: UUID
    state: TimelineExecutionState
    row_version: PositiveInt
    created_at: datetime
    updated_at: datetime


class TimelineCheckpointV1(FrozenModel):
    schema_version: Literal[1]
    checkpoint_id: UUID
    execution_id: UUID
    ordinal: PositiveInt
    milestone_key: Literal["documents", "application", "visa", "arrival"]
    due_date: date
    accountable_role: Literal["student", "parent"]
    state: TimelineCheckpointState
    risk_state: TimelineRiskState
    row_version: PositiveInt
    created_at: datetime
    updated_at: datetime


class TimelineCheckpointAttestationV1(FrozenModel):
    schema_version: Literal[1]
    attestation_id: UUID
    execution_id: UUID
    checkpoint_id: UUID
    reporter_actor_id: UUID
    reporter_role: Literal["student", "parent"]
    attestation_kind: CheckpointAttestationKind
    status_code: CheckpointStatusCode
    attestation_code: CheckpointAttestationCode
    reason_code: CheckpointAttestationReasonCode
    observed_execution_version: PositiveInt
    observed_checkpoint_version: PositiveInt
    created_at: datetime


class TimelineCheckpointVerificationV1(FrozenModel):
    schema_version: Literal[1]
    verification_id: UUID
    execution_id: UUID
    checkpoint_id: UUID
    attestation_id: UUID
    advisor_actor_id: UUID
    action: CheckpointVerificationAction
    reason_code: CheckpointVerificationReasonCode
    observed_execution_version: PositiveInt
    observed_checkpoint_version: PositiveInt
    created_at: datetime


class TimelineReassessmentRequestV1(FrozenModel):
    schema_version: Literal[1]
    reassessment_id: UUID
    execution_id: UUID
    checkpoint_id: UUID
    advisor_actor_id: UUID
    trigger: ReassessmentTrigger
    trigger_reference_id: UUID | None
    accepted_database_date: date
    accepted_trigger_projection_sha256: str
    handoff_schema_version: Literal[1]
    predecessor_case_id: UUID
    predecessor_case_revision: PositiveInt
    predecessor_decision_id: UUID
    predecessor_decision_receipt_id: UUID
    predecessor_timeline_plan_id: UUID
    predecessor_execution_id: UUID
    predecessor_checkpoint_id: UUID
    owner_role: Literal["advisor"]
    successor_status: Literal["pending_future_authorization"]
    created_at: datetime

    @field_validator("accepted_trigger_projection_sha256")
    @classmethod
    def valid_sha256(cls, value: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
        return value


class TimelineMutationReceiptV1(FrozenModel):
    schema_version: Literal[1]
    receipt_id: UUID
    operation: Literal["start", "attest", "verify", "reassess"]
    result_kind: Literal[
        "timeline_execution_started",
        "timeline_checkpoint_attested",
        "timeline_checkpoint_verified",
        "timeline_reassessment_requested",
    ]
    result_id: UUID
    execution_id: UUID
    checkpoint_id: UUID | None
    before_execution_version: PositiveInt | None
    after_execution_version: PositiveInt
    before_checkpoint_version: PositiveInt | None
    after_checkpoint_version: PositiveInt | None
    created_at: datetime


class TimelineActivityItemV1(FrozenModel):
    schema_version: Literal[1]
    kind: Literal[
        "attestation_recorded",
        "verification_recorded",
        "reassessment_recorded",
        "mutation_receipt_recorded",
    ]
    durable_id: UUID
    execution_id: UUID
    checkpoint_id: UUID | None
    created_at: datetime


class TimelineCurrentActionV1(FrozenModel):
    schema_version: Literal[1]
    code: TimelineCurrentActionCode
    owner_role: Literal["advisor", "student", "parent", "none"]
    checkpoint_id: UUID | None
    execution_version: PositiveInt
    checkpoint_version: PositiveInt | None


class TimelineExecutionViewV1(FrozenModel):
    schema_version: Literal[1]
    execution: TimelineExecutionV1
    checkpoints: tuple[TimelineCheckpointV1, ...]
    current_checkpoint: TimelineCheckpointV1 | None
    latest_attestation: TimelineCheckpointAttestationV1 | None
    latest_verification: TimelineCheckpointVerificationV1 | None
    reassessment: TimelineReassessmentRequestV1 | None
    current_action: TimelineCurrentActionV1
    observed_date: date
    activity: tuple[TimelineActivityItemV1, ...]
    activity_total: int
    activity_truncated: bool

    @model_validator(mode="after")
    def bounded_activity(self) -> Self:
        if self.activity_total < 0 or self.activity_total < len(self.activity):
            raise ValueError("activity_total must cover the returned activity")
        if len(self.activity) > 64:
            raise ValueError("activity is limited to 64 items")
        if self.activity_truncated != (self.activity_total > len(self.activity)):
            raise ValueError("activity_truncated must reflect the exact total")
        expected = tuple(
            sorted(
                self.activity,
                key=lambda item: (item.created_at, item.durable_id.int),
                reverse=True,
            )
        )
        if self.activity != expected:
            raise ValueError("activity must use stable descending order")
        return self


class PlanExecutionContextV1(FrozenModel):
    schema_version: Literal[1]
    scenario: Literal["governed-plan-execution-v1"]
    case_id: UUID
    case_revision: PositiveInt
    decision_id: UUID
    decision_receipt_id: UUID
    timeline_plan_id: UUID
    execution_id: UUID | None
    active_role: Literal["advisor", "student", "parent"]
    assignment_status: Literal["assigned"]
