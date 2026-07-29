from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

import pytest

from night_voyager.decision.models import TimelineMilestone, TimelinePlan
from night_voyager.planning.models import Country
from night_voyager.timeline_execution.errors import TimelineExecutionProjectionError
from night_voyager.timeline_execution.models import (
    CheckpointAttestationKind,
    CheckpointAttestationReasonCode,
    CheckpointStatusCode,
    CheckpointVerificationAction,
    CheckpointVerificationReasonCode,
    TimelineCheckpointState,
    TimelineCheckpointV1,
    TimelineCurrentActionCode,
    TimelineExecutionState,
    TimelineExecutionV1,
    TimelineExecutionViewV1,
    TimelineRiskState,
)
from night_voyager.timeline_execution.policy import (
    derive_current_action,
    derive_risk_state,
    snapshot_timeline_plan,
    validate_attestation_codes,
    validate_verification_codes,
)

U1 = UUID("00000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 7, 29, tzinfo=UTC)


def plan(keys: tuple[str, ...] = ("documents", "application", "visa", "arrival")) -> TimelinePlan:
    return TimelinePlan(
        schema_version=1,
        country=Country.AUSTRALIA,
        intake="2027-02",
        milestones=tuple(
            TimelineMilestone(key=key, due_date=date(2026, 9, index + 1))
            for index, key in enumerate(keys)
        ),
    )


def test_snapshot_requires_exact_order_and_assigns_server_owned_roles() -> None:
    seeds = snapshot_timeline_plan(plan())
    assert tuple(seed.milestone_key for seed in seeds) == (
        "documents",
        "application",
        "visa",
        "arrival",
    )
    assert tuple(seed.accountable_role for seed in seeds) == (
        "student",
        "student",
        "student",
        "parent",
    )
    assert tuple(seed.ordinal for seed in seeds) == (1, 2, 3, 4)
    for invalid in (
        ("application", "documents", "visa", "arrival"),
        ("documents", "application", "visa"),
        ("documents", "application", "visa", "visa"),
    ):
        with pytest.raises(TimelineExecutionProjectionError):
            snapshot_timeline_plan(plan(invalid))


@pytest.mark.parametrize(
    ("observed", "expected"),
    (
        (date(2026, 9, 1), "due_soon"),
        (date(2026, 8, 18), "due_soon"),
        (date(2026, 8, 17), "on_track"),
        (date(2026, 9, 2), "overdue"),
    ),
)
def test_risk_boundaries_use_supplied_observed_date(
    observed: date, expected: str
) -> None:
    risk = derive_risk_state(
        checkpoint_state=TimelineCheckpointState.IN_PROGRESS,
        due_date=date(2026, 9, 1),
        observed_date=observed,
    )
    assert risk.value == expected
    assert (
        derive_risk_state(
            checkpoint_state=TimelineCheckpointState.VERIFIED,
            due_date=date(2026, 9, 1),
            observed_date=date(2027, 1, 1),
        )
        is TimelineRiskState.ON_TRACK
    )


def test_closed_attestation_and_verification_combinations() -> None:
    validate_attestation_codes(
        milestone_key="documents",
        kind=CheckpointAttestationKind.COMPLETION,
        status_code=CheckpointStatusCode.READY_FOR_ADVISOR,
        attestation_code="documents_status_confirmed",
        reason_code=CheckpointAttestationReasonCode.NOT_APPLICABLE,
    )
    with pytest.raises(TimelineExecutionProjectionError):
        validate_attestation_codes(
            milestone_key="documents",
            kind=CheckpointAttestationKind.BLOCKED,
            status_code=CheckpointStatusCode.WORK_BLOCKED,
            attestation_code="visa_status_confirmed",
            reason_code=CheckpointAttestationReasonCode.NOT_APPLICABLE,
        )
    validate_verification_codes(
        action=CheckpointVerificationAction.VERIFY,
        reason_code=CheckpointVerificationReasonCode.ATTESTATION_VERIFIED,
    )
    with pytest.raises(TimelineExecutionProjectionError):
        validate_verification_codes(
            action=CheckpointVerificationAction.VERIFY,
            reason_code=CheckpointVerificationReasonCode.STATUS_UPDATE_REQUIRED,
        )


def test_current_action_fails_on_contradictory_current_checkpoint() -> None:
    execution = TimelineExecutionV1(
        schema_version=1,
        execution_id=U1,
        case_id=U1,
        case_revision=1,
        decision_id=U1,
        decision_receipt_id=U1,
        timeline_plan_id=U1,
        state=TimelineExecutionState.ACTIVE,
        row_version=1,
        created_at=NOW,
        updated_at=NOW,
    )
    checkpoints = tuple(
        TimelineCheckpointV1(
            schema_version=1,
            checkpoint_id=UUID(int=index + 2),
            execution_id=U1,
            ordinal=index + 1,
            milestone_key=key,
            due_date=date(2026, 9, index + 1),
            accountable_role="student",
            state=TimelineCheckpointState.IN_PROGRESS,
            risk_state=TimelineRiskState.ON_TRACK,
            row_version=1,
            created_at=NOW,
            updated_at=NOW,
        )
        for index, key in enumerate(("documents", "application"))
    )
    view = TimelineExecutionViewV1(
        schema_version=1,
        execution=execution,
        checkpoints=checkpoints,
        current_checkpoint=checkpoints[0],
        latest_attestation=None,
        latest_verification=None,
        reassessment=None,
        observed_date=date(2026, 7, 29),
        activity=(),
        activity_total=0,
        activity_truncated=False,
    )
    with pytest.raises(TimelineExecutionProjectionError):
        derive_current_action(view)

    valid = view.model_copy(update={"checkpoints": (checkpoints[0],)})
    action = derive_current_action(valid)
    assert action.code is TimelineCurrentActionCode.CHECKPOINT_ATTESTATION_REQUIRED
    assert action.owner_role == "student"
