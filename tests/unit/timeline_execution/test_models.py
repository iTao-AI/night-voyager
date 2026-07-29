from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from night_voyager.timeline_execution.models import (
    CheckpointAttestationKind,
    CheckpointAttestationReasonCode,
    CheckpointStatusCode,
    PlanExecutionContextV1,
    TimelineActivityItemV1,
    TimelineCheckpointAttestationV1,
    TimelineCurrentActionCode,
    TimelineCurrentActionV1,
    TimelineExecutionState,
    TimelineExecutionV1,
    TimelineExecutionViewV1,
    TimelineMutationReceiptV1,
)

U1 = UUID("00000000-0000-0000-0000-000000000001")
U2 = UUID("00000000-0000-0000-0000-000000000002")
NOW = datetime(2026, 7, 29, tzinfo=UTC)


def execution() -> TimelineExecutionV1:
    return TimelineExecutionV1(
        schema_version=1,
        execution_id=U1,
        case_id=U2,
        case_revision=1,
        decision_id=U1,
        decision_receipt_id=U2,
        timeline_plan_id=U1,
        state=TimelineExecutionState.ACTIVE,
        row_version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def test_frozen_public_models_forbid_extra_fields_and_naive_timestamps() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        TimelineExecutionV1.model_validate({**execution().model_dump(), "tenant_id": U1})
    with pytest.raises(ValidationError, match="timezone"):
        TimelineExecutionV1.model_validate(
            {
                **execution().model_dump(exclude={"created_at"}),
                "created_at": datetime(2026, 7, 29),
            }
        )
    with pytest.raises(ValidationError):
        TimelineExecutionV1.model_validate(
            {**execution().model_dump(exclude={"row_version"}), "row_version": 0}
        )


def test_context_is_closed_and_contains_no_browser_authority_fields() -> None:
    context = PlanExecutionContextV1(
        schema_version=1,
        scenario="governed-plan-execution-v1",
        case_id=U1,
        case_revision=1,
        decision_id=U1,
        decision_receipt_id=U2,
        timeline_plan_id=U1,
        execution_id=None,
        active_role="student",
        assignment_status="assigned",
    )
    assert context.active_role == "student"
    for forbidden in ("organization_id", "actor_id", "as_of", "url", "filename"):
        with pytest.raises(ValidationError):
            PlanExecutionContextV1.model_validate(
                {**context.model_dump(), forbidden: "forbidden"}
            )


def test_attestation_rejects_narrative_url_file_and_unknown_codes() -> None:
    payload: dict[str, object] = {
        "schema_version": 1,
        "attestation_id": U1,
        "execution_id": U1,
        "checkpoint_id": U2,
        "reporter_actor_id": U1,
        "reporter_role": "student",
        "attestation_kind": CheckpointAttestationKind.PROGRESS,
        "status_code": CheckpointStatusCode.WORK_IN_PROGRESS,
        "attestation_code": "documents_status_confirmed",
        "reason_code": CheckpointAttestationReasonCode.NOT_APPLICABLE,
        "observed_execution_version": 1,
        "observed_checkpoint_version": 1,
        "created_at": NOW,
    }
    item = TimelineCheckpointAttestationV1.model_validate(payload)
    assert item.attestation_kind is CheckpointAttestationKind.PROGRESS
    for forbidden in ("narrative", "url", "file", "evidence_id", "external_account_id"):
        with pytest.raises(ValidationError):
            TimelineCheckpointAttestationV1.model_validate(
                {**payload, forbidden: "forbidden"}
            )
    with pytest.raises(ValidationError):
        TimelineCheckpointAttestationV1.model_validate(
            {**payload, "attestation_kind": "unknown"}
        )


def test_receipt_and_current_action_have_only_the_frozen_public_shape() -> None:
    receipt = TimelineMutationReceiptV1(
        schema_version=1,
        receipt_id=U1,
        operation="start",
        result_kind="timeline_execution_started",
        result_id=U2,
        execution_id=U1,
        checkpoint_id=U2,
        before_execution_version=None,
        after_execution_version=1,
        before_checkpoint_version=None,
        after_checkpoint_version=1,
        created_at=NOW,
    )
    assert "replayed" not in receipt.model_dump()
    action = TimelineCurrentActionV1(
        schema_version=1,
        code=TimelineCurrentActionCode.CHECKPOINT_ATTESTATION_REQUIRED,
        owner_role="student",
        checkpoint_id=U2,
        execution_version=1,
        checkpoint_version=1,
    )
    assert set(action.model_dump()) == {
        "schema_version",
        "code",
        "owner_role",
        "checkpoint_id",
        "execution_version",
        "checkpoint_version",
    }


def test_activity_view_enforces_latest_64_and_exact_truncation_flag() -> None:
    activity = tuple(
        TimelineActivityItemV1(
            schema_version=1,
            kind="mutation_receipt_recorded",
            durable_id=UUID(int=index + 1),
            execution_id=U1,
            checkpoint_id=None,
            created_at=NOW,
        )
        for index in reversed(range(64))
    )
    view = TimelineExecutionViewV1(
        schema_version=1,
        execution=execution(),
        checkpoints=(),
        current_checkpoint=None,
        latest_attestation=None,
        latest_verification=None,
        reassessment=None,
        current_action=TimelineCurrentActionV1(
            schema_version=1,
            code=TimelineCurrentActionCode.EXECUTION_COMPLETED,
            owner_role="none",
            checkpoint_id=None,
            execution_version=1,
            checkpoint_version=None,
        ),
        observed_date=date(2026, 7, 29),
        activity=activity,
        activity_total=65,
        activity_truncated=True,
    )
    assert view.activity_truncated
    with pytest.raises(ValidationError):
        TimelineExecutionViewV1(
            **view.model_dump(exclude={"activity_truncated"}),
            activity_truncated=False,
        )
