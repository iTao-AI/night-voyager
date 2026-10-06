from __future__ import annotations

from typing import Any, cast

import pytest
from pydantic import ValidationError

from night_voyager.connected_demo import models
from tests.unit.connected_demo.test_models import canonical_inputs, review_required_payload


def task_ready_payload() -> dict[str, object]:
    inputs = canonical_inputs()
    inputs["expected_case_revision"] = 2
    inputs["source_pack_id"] = "50000000-0000-0000-0000-000000000017"
    return {
        "schema_version": 3,
        "phase": "replan_required",
        "case_id": inputs["case_id"],
        "case_revision": 2,
        "case_state": "planning",
        "case_intake": "2028-02",
        "canonical_task_inputs": inputs,
        "task": None,
        "planning_run": None,
        "comparison": None,
        "routes": [],
        "evidence": [],
        "review_inputs": None,
        "current_brief_id": None,
        "recovery": None,
    }


def test_v3_has_actual_intake_without_widening_v2() -> None:
    payload = task_ready_payload()
    assert models.AdvisorLedgerV3.model_validate(payload).case_intake == "2028-02"
    payload["schema_version"] = 2
    with pytest.raises(ValidationError):
        models.AdvisorLedgerV2.model_validate(payload)


@pytest.mark.parametrize("value", ["0000-02", "2028-13", "2028-2", "2028-02 ", 202802])
def test_v3_rejects_invalid_persisted_intake(value: object) -> None:
    payload = task_ready_payload()
    payload["case_intake"] = value
    with pytest.raises(ValidationError):
        models.AdvisorLedgerV3.model_validate(payload)


def test_v3_reuses_phase_and_identity_authority_checks() -> None:
    payload = task_ready_payload()
    payload["case_revision"] = 3
    with pytest.raises(ValidationError, match="canonical task identity"):
        models.AdvisorLedgerV3.model_validate(payload)


def test_v3_cost_intake_must_match_current_case() -> None:
    payload = cast(dict[str, Any], review_required_payload())
    payload.update(
        schema_version=3, phase="review_required", case_intake="2027-02", comparison=None
    )
    payload["routes"][0]["cost"]["intake"] = "2028-02"
    with pytest.raises(ValidationError, match="planning cost intake"):
        models.AdvisorLedgerV3.model_validate(payload)
