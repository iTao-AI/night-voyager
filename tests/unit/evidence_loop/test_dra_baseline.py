from __future__ import annotations

from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from night_voyager.evidence_loop.dra_baseline import GovernedDraBaselineExportV1


def baseline_payload() -> dict[str, object]:
    return {
        "schema_version": "night-voyager.governed-dra-baseline-export.v1",
        "case_id": str(UUID("40000000-0000-0000-0000-000000000001")),
        "case_revision": 2,
        "decision_dimension": "program_requirements",
        "typed_row_id": str(UUID("50000000-0000-0000-0000-000000000001")),
        "typed_value": "Synthetic program requires one prerequisite module.",
        "typed_value_sha256": "9" * 64,
        "producer": {
            "release": "v0.1.8",
            "tag_object": "f828606741f636bca7ddbb66244ca60019eaa3c8",
            "commit": "cb1f4660ee4ac7d81b04ffea014362e933487e61",
            "profile_id": "generic-strict-citation",
            "profile_version": "1",
            "run_id": "run_strict_000000000000000000000000000001",
            "evidence_id": "evidence-1",
        },
        "advisor_verification": {
            "receipt_id": str(UUID("60000000-0000-0000-0000-000000000001")),
            "assigned_advisor_id": str(
                UUID("30000000-0000-0000-0000-000000000002")
            ),
            "decision": "verified_for_baseline",
            "receipt_sha256": "8" * 64,
        },
        "origin_kind": "night_voyager_typed_governed_row",
        "row_sha256": "7" * 64,
        "export_sha256": "6" * 64,
    }


def test_governed_typed_row_retains_historical_provenance() -> None:
    baseline = GovernedDraBaselineExportV1.model_validate(baseline_payload())
    assert baseline.origin_kind == "night_voyager_typed_governed_row"
    assert baseline.producer.release == "v0.1.8"


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (("origin_kind",), "markdown_derived"),
        (("producer", "run_id"), ""),
        (("advisor_verification", "decision"), "model_verified"),
        (("producer", "commit"), "0" * 40),
    ),
)
def test_markdown_or_missing_historical_binding_is_rejected(
    path: tuple[str, ...], value: str
) -> None:
    payload = baseline_payload()
    target = payload
    for key in path[:-1]:
        nested = target[key]
        assert isinstance(nested, dict)
        target = cast(dict[str, object], nested)
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        GovernedDraBaselineExportV1.model_validate(payload)
