from datetime import UTC, datetime
from uuid import UUID

from night_voyager.timeline_execution.hashing import canonical_json_bytes, canonical_sha256
from night_voyager.timeline_execution.models import TimelineMutationReceiptV1


def test_receipt_round_trip_has_byte_identical_canonical_json() -> None:
    receipt = TimelineMutationReceiptV1(
        schema_version=1,
        receipt_id=UUID(int=1),
        operation="verify",
        result_kind="timeline_checkpoint_verified",
        result_id=UUID(int=2),
        execution_id=UUID(int=3),
        checkpoint_id=UUID(int=4),
        before_execution_version=2,
        after_execution_version=3,
        before_checkpoint_version=4,
        after_checkpoint_version=5,
        created_at=datetime(2026, 7, 29, tzinfo=UTC),
    )
    first = canonical_json_bytes(receipt)
    replay = TimelineMutationReceiptV1.model_validate_json(first)
    assert canonical_json_bytes(replay) == first
    assert canonical_sha256(replay) == canonical_sha256(receipt)
