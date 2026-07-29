from __future__ import annotations

from datetime import date
from typing import Literal, cast

from night_voyager.decision.models import TimelinePlan
from night_voyager.timeline_execution.errors import TimelineExecutionProjectionError
from night_voyager.timeline_execution.models import (
    CheckpointAttestationCode,
    CheckpointAttestationKind,
    CheckpointAttestationReasonCode,
    CheckpointSeed,
    CheckpointStatusCode,
    CheckpointVerificationAction,
    CheckpointVerificationReasonCode,
    TimelineCheckpointState,
    TimelineCurrentActionCode,
    TimelineCurrentActionV1,
    TimelineExecutionState,
    TimelineExecutionViewV1,
    TimelineRiskState,
)

MILESTONES = ("documents", "application", "visa", "arrival")
ACCOUNTABLE_ROLES = ("student", "student", "student", "parent")


def snapshot_timeline_plan(plan: TimelinePlan) -> tuple[CheckpointSeed, ...]:
    keys = tuple(milestone.key for milestone in plan.milestones)
    if keys != MILESTONES:
        raise TimelineExecutionProjectionError("timeline milestones must match canonical order")
    return tuple(
        CheckpointSeed(
            ordinal=index,
            milestone_key=cast(
                Literal["documents", "application", "visa", "arrival"],
                milestone.key,
            ),
            due_date=milestone.due_date,
            accountable_role=ACCOUNTABLE_ROLES[index - 1],
        )
        for index, milestone in enumerate(plan.milestones, start=1)
    )


def derive_risk_state(
    *,
    checkpoint_state: TimelineCheckpointState,
    due_date: date,
    observed_date: date,
) -> TimelineRiskState:
    if checkpoint_state is TimelineCheckpointState.VERIFIED:
        return TimelineRiskState.ON_TRACK
    remaining = (due_date - observed_date).days
    if remaining < 0:
        return TimelineRiskState.OVERDUE
    if remaining <= 14:
        return TimelineRiskState.DUE_SOON
    return TimelineRiskState.ON_TRACK


def validate_attestation_codes(
    *,
    milestone_key: str,
    kind: CheckpointAttestationKind,
    status_code: CheckpointStatusCode,
    attestation_code: CheckpointAttestationCode | str,
    reason_code: CheckpointAttestationReasonCode,
) -> None:
    expected_attestation = f"{milestone_key}_status_confirmed"
    if milestone_key not in MILESTONES or str(attestation_code) != expected_attestation:
        raise TimelineExecutionProjectionError("attestation code must match milestone")
    exact_status = {
        CheckpointAttestationKind.PROGRESS: CheckpointStatusCode.WORK_IN_PROGRESS,
        CheckpointAttestationKind.COMPLETION: CheckpointStatusCode.READY_FOR_ADVISOR,
        CheckpointAttestationKind.BLOCKED: CheckpointStatusCode.WORK_BLOCKED,
    }
    if status_code is not exact_status[kind]:
        raise TimelineExecutionProjectionError("status code must match attestation kind")
    if kind is CheckpointAttestationKind.BLOCKED:
        if reason_code is CheckpointAttestationReasonCode.NOT_APPLICABLE:
            raise TimelineExecutionProjectionError("blocked attestation requires a reason")
    elif reason_code is not CheckpointAttestationReasonCode.NOT_APPLICABLE:
        raise TimelineExecutionProjectionError("non-blocked attestation uses not_applicable")


def validate_verification_codes(
    *,
    action: CheckpointVerificationAction,
    reason_code: CheckpointVerificationReasonCode,
) -> None:
    if action is CheckpointVerificationAction.VERIFY:
        valid = reason_code is CheckpointVerificationReasonCode.ATTESTATION_VERIFIED
    else:
        valid = reason_code in {
            CheckpointVerificationReasonCode.STATUS_UPDATE_REQUIRED,
            CheckpointVerificationReasonCode.STATUS_INCONSISTENT,
        }
    if not valid:
        raise TimelineExecutionProjectionError("verification reason must match action")


def derive_current_action(view: TimelineExecutionViewV1) -> TimelineCurrentActionV1:
    execution = view.execution
    if execution.state is TimelineExecutionState.COMPLETED:
        if view.current_checkpoint is not None:
            raise TimelineExecutionProjectionError("completed execution has no current checkpoint")
        return TimelineCurrentActionV1(
            schema_version=1,
            code=TimelineCurrentActionCode.EXECUTION_COMPLETED,
            owner_role="none",
            checkpoint_id=None,
            execution_version=execution.row_version,
            checkpoint_version=None,
        )
    if execution.state is TimelineExecutionState.REASSESSMENT_REQUIRED:
        return TimelineCurrentActionV1(
            schema_version=1,
            code=TimelineCurrentActionCode.REASSESSMENT_HANDOFF_REQUIRED,
            owner_role="advisor",
            checkpoint_id=(
                view.current_checkpoint.checkpoint_id if view.current_checkpoint else None
            ),
            execution_version=execution.row_version,
            checkpoint_version=(
                view.current_checkpoint.row_version if view.current_checkpoint else None
            ),
        )
    current = tuple(
        checkpoint
        for checkpoint in view.checkpoints
        if checkpoint.state
        in {
            TimelineCheckpointState.IN_PROGRESS,
            TimelineCheckpointState.AWAITING_ADVISOR,
            TimelineCheckpointState.BLOCKED,
        }
    )
    if len(current) != 1 or view.current_checkpoint != current[0]:
        raise TimelineExecutionProjectionError("active execution must have one current checkpoint")
    checkpoint = current[0]
    if checkpoint.state is TimelineCheckpointState.AWAITING_ADVISOR:
        code = TimelineCurrentActionCode.ADVISOR_VERIFICATION_REQUIRED
        owner = "advisor"
    elif checkpoint.state is TimelineCheckpointState.BLOCKED:
        code = TimelineCurrentActionCode.REASSESSMENT_HANDOFF_REQUIRED
        owner = "advisor"
    else:
        code = TimelineCurrentActionCode.CHECKPOINT_ATTESTATION_REQUIRED
        owner = checkpoint.accountable_role
    return TimelineCurrentActionV1(
        schema_version=1,
        code=code,
        owner_role=owner,
        checkpoint_id=checkpoint.checkpoint_id,
        execution_version=execution.row_version,
        checkpoint_version=checkpoint.row_version,
    )
