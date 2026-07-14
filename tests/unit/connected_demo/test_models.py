from __future__ import annotations

from copy import deepcopy
from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from night_voyager.connected_demo.models import (
    AdvisorLedgerV1,
    CurrentDecisionBriefV1,
    DemoPhase,
    FamilyDecisionRequirements,
)

CASE_ID = "40000000-0000-0000-0000-000000000002"
TASK_ID = "80000000-0000-0000-0000-000000000001"
RUN_ID = "70000000-0000-0000-0000-000000000002"
BRIEF_ID = "90000000-0000-0000-0000-000000000001"
ROUTE_ID = "71000000-0000-0000-0000-000000000001"


def canonical_inputs() -> dict[str, object]:
    return {
        "schema_version": 1,
        "operation": "generate_planning_run_v1",
        "case_id": CASE_ID,
        "expected_case_revision": 1,
        "source_pack_id": "50000000-0000-0000-0000-000000000001",
        "source_pack_version": 1,
        "policy_version": "m3a-policy-v1",
    }


def task(status: str = "preparing") -> dict[str, object]:
    return {
        "task_id": TASK_ID,
        "row_version": 1,
        "status": status,
        "public_code": None,
        "attempt_count": 0,
        "planning_run_id": RUN_ID if status == "needs_advisor_review" else None,
        "updated_at": datetime(2026, 7, 14, tzinfo=UTC),
    }


def planning_run() -> dict[str, object]:
    return {
        "planning_run_id": RUN_ID,
        "state": "review_required",
        "source_pack_id": "50000000-0000-0000-0000-000000000001",
        "source_pack_version": 1,
        "policy_version": "m3a-policy-v1",
        "source_snapshot_date": date(2026, 7, 1),
    }


def route() -> dict[str, object]:
    return {
        "route_id": ROUTE_ID,
        "country": "australia",
        "outcome": "recommended_with_condition",
        "reason_code": "complete_cost_and_fx_within_boundary",
        "eligible": True,
        "dimensions": (
            {
                "key": "route_assessment",
                "outcome": "supported",
                "reason_code": "complete_cost_and_fx_within_boundary",
            },
        ),
        "cost": {
            "source_currency": "AUD",
            "tuition_minor": 100,
            "living_minor": 50,
            "fx_rate": "5.0",
            "cny_total_minor": 750,
            "fx_source": "synthetic-fixture",
            "fx_date": "2026-07-01",
        },
        "ranking": None,
        "required_claims": ("australia_program_fit",),
        "known_gaps": (),
    }


def evidence() -> dict[str, object]:
    return {
        "claim": "australia_program_fit",
        "role": "program_fit",
        "publisher": "Synthetic publisher",
        "institution": "Synthetic institution",
        "snapshot_date": "2026-07-01",
        "authority": "accepted_synthetic_demo",
        "limitation": "Local synthetic proof only.",
        "known_gaps": (),
    }


def base_ledger(phase: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "proof_mode": "synthetic-demo",
        "phase": phase,
        "case_id": CASE_ID,
        "case_revision": 1,
        "case_state": "planning",
        "canonical_task_inputs": canonical_inputs(),
        "task": None,
        "planning_run": None,
        "routes": (),
        "evidence": (),
        "review_inputs": None,
        "current_brief_id": None,
        "recovery": None,
    }


def review_required_payload() -> dict[str, object]:
    payload = base_ledger("review-required")
    payload.update(
        {
            "case_state": "advisor_review",
            "task": task("needs_advisor_review"),
            "planning_run": planning_run(),
            "routes": (route(),),
            "evidence": (evidence(),),
            "review_inputs": {
                "planning_run_id": RUN_ID,
                "expected_case_revision": 1,
                "eligible_route_ids": (ROUTE_ID,),
                "risk_acceptance_options": (),
            },
        }
    )
    return payload


def test_task_ready_phase_rejects_a_fabricated_run() -> None:
    payload = base_ledger("task-ready")
    payload["planning_run"] = planning_run()
    with pytest.raises(ValidationError, match="task-ready projection"):
        AdvisorLedgerV1.model_validate(payload)


def test_active_phase_rejects_placeholder_routes() -> None:
    payload = base_ledger("active-task")
    payload["task"] = task()
    payload["routes"] = (route(),)
    with pytest.raises(ValidationError, match="active-task projection"):
        AdvisorLedgerV1.model_validate(payload)


def test_review_required_requires_real_review_inputs() -> None:
    payload = review_required_payload()
    payload["review_inputs"] = None
    with pytest.raises(ValidationError, match="review-required projection"):
        AdvisorLedgerV1.model_validate(payload)


@pytest.mark.parametrize(
    "value",
    [(), ("budget_elasticity", "budget_elasticity"), ("route_authority",)],
)
def test_family_requirements_reject_non_exact_trade_off_tuple(value: tuple[str, ...]) -> None:
    with pytest.raises(ValidationError):
        FamilyDecisionRequirements(
            eligible_route_id=UUID(ROUTE_ID),
            currency="CNY",
            pinned_cost_minor=750,
            hard_ceiling_minor=900,
            required_trade_offs=value,
        )


def test_family_requirements_accept_exact_budget_elasticity_tuple() -> None:
    requirements = FamilyDecisionRequirements(
        eligible_route_id=UUID(ROUTE_ID),
        currency="CNY",
        pinned_cost_minor=750,
        hard_ceiling_minor=900,
        required_trade_offs=("budget_elasticity",),
    )
    assert requirements.required_trade_offs == ("budget_elasticity",)


def current_brief_payload(phase: DemoPhase) -> dict[str, object]:
    return {
        "schema_version": 1,
        "proof_mode": "synthetic-demo",
        "phase": phase,
        "case_id": CASE_ID,
        "brief_id": BRIEF_ID,
        "brief_version": 1,
        "source_snapshot_date": "2026-07-01",
        "family_safe_projection": {
            "schema_version": 1,
            "intake": "2027-02",
            "routes": (
                {
                    "route_id": ROUTE_ID,
                    "country": "australia",
                    "outcome": "recommended_with_condition",
                    "reason_code": "complete_cost_and_fx_within_boundary",
                },
            ),
            "eligible_route_ids": (ROUTE_ID,),
            "accepted_evidence_risks": (),
            "synthetic_proof": True,
        },
        "decision_requirements": {
            "eligible_route_id": ROUTE_ID,
            "currency": "CNY",
            "pinned_cost_minor": 750,
            "hard_ceiling_minor": 900,
            "required_trade_offs": ("budget_elasticity",),
        },
        "receipt": None,
        "timeline": None,
    }


def test_family_review_rejects_a_receipt_placeholder() -> None:
    payload = current_brief_payload(DemoPhase.FAMILY_REVIEW)
    payload["receipt"] = {
        "schema_version": 1,
        "decision_id": "91000000-0000-0000-0000-000000000001",
        "receipt_id": "92000000-0000-0000-0000-000000000001",
        "selected_route_id": ROUTE_ID,
        "accepted_budget_min_minor": 750,
        "accepted_budget_max_minor": 900,
        "currency": "CNY",
        "accepted_trade_offs": ("budget_elasticity",),
        "decision_made_by_actor_id": "20000000-0000-0000-0000-000000000003",
        "recorded_by_actor_id": "20000000-0000-0000-0000-000000000003",
        "source": "direct",
    }
    with pytest.raises(ValidationError, match="family-review projection"):
        CurrentDecisionBriefV1.model_validate(payload)


def test_plan_ready_requires_receipt_and_timeline() -> None:
    payload = current_brief_payload(DemoPhase.PLAN_READY)
    with pytest.raises(ValidationError, match="plan-ready projection"):
        CurrentDecisionBriefV1.model_validate(deepcopy(payload))
