from datetime import date
from uuid import UUID

import pytest

from night_voyager.decision.hashing import canonical_request_sha256
from night_voyager.decision.models import (
    BriefRoute,
    DecisionBriefProjection,
    DecisionSource,
    EvidenceRiskAcceptance,
    EvidenceRiskKind,
    FamilyDecisionCommand,
    ReviewAction,
    TimelineMilestone,
)
from night_voyager.decision.policy import (
    build_timeline_plan,
    eligible_route_ids,
    validate_family_decision,
    validate_risk_acceptances,
)
from night_voyager.planning.models import Country, RouteOutcome

AUSTRALIA = UUID("71000000-0000-0000-0000-000000000001")
JAPAN = UUID("71000000-0000-0000-0000-000000000002")
MALAYSIA = UUID("71000000-0000-0000-0000-000000000003")
BRIEF = UUID("81000000-0000-0000-0000-000000000001")
ACTOR = UUID("20000000-0000-0000-0000-000000000003")


def projection() -> DecisionBriefProjection:
    return DecisionBriefProjection(
        schema_version=1,
        brief_id=BRIEF,
        brief_version=1,
        source_snapshot_date=date(2026, 7, 1),
        routes=(
            BriefRoute(
                route_id=AUSTRALIA,
                country=Country.AUSTRALIA,
                outcome=RouteOutcome.RECOMMENDED_WITH_CONDITION,
                reason_code="eligible",
            ),
            BriefRoute(
                route_id=JAPAN,
                country=Country.JAPAN,
                outcome=RouteOutcome.CONDITIONAL,
                reason_code="high_risk_alternative",
            ),
            BriefRoute(
                route_id=MALAYSIA,
                country=Country.MALAYSIA,
                outcome=RouteOutcome.BLOCKED,
                reason_code="missing_program_fit",
            ),
        ),
        eligible_route_ids=(AUSTRALIA, JAPAN),
        accepted_evidence_risks=(),
        synthetic_proof=True,
    )


def decision(**changes: object) -> FamilyDecisionCommand:
    values: dict[str, object] = {
        "schema_version": 1,
        "brief_id": BRIEF,
        "expected_brief_version": 1,
        "selected_route_id": AUSTRALIA,
        "accepted_budget_min_minor": 30_000_000,
        "accepted_budget_max_minor": 40_000_000,
        "currency": "CNY",
        "accepted_trade_offs": ("budget_elasticity",),
        "decision_made_by_actor_id": ACTOR,
        "source": DecisionSource.DIRECT,
    }
    values.update(changes)
    return FamilyDecisionCommand.model_validate(values)


def test_only_nonblocked_reviewed_routes_can_be_eligible() -> None:
    assert eligible_route_ids(projection().routes) == (AUSTRALIA, JAPAN)


def test_evidence_risk_acceptance_is_narrow() -> None:
    validate_risk_acceptances(
        (
            EvidenceRiskAcceptance(
                evidence_id=UUID(int=1),
                kind=EvidenceRiskKind.STALE,
                reason="family accepts dated optional ranking",
            ),
        )
    )
    with pytest.raises(ValueError, match="cannot waive"):
        validate_risk_acceptances(
            (
                EvidenceRiskAcceptance(
                    evidence_id=UUID(int=1), kind="blocked_route", reason="waive Malaysia"
                ),
            )
        )


def test_australia_requires_budget_elasticity_and_pinned_range() -> None:
    validate_family_decision(
        decision(),
        projection(),
        pinned_budget_hard_ceiling_minor=40_000_000,
        pinned_australia_cost_minor=30_550_000,
    )
    with pytest.raises(ValueError, match="budget_elasticity"):
        validate_family_decision(
            decision(accepted_trade_offs=()),
            projection(),
            pinned_budget_hard_ceiling_minor=40_000_000,
            pinned_australia_cost_minor=30_550_000,
        )
    with pytest.raises(ValueError, match="pinned cost"):
        validate_family_decision(
            decision(accepted_budget_max_minor=30_000_000),
            projection(),
            pinned_budget_hard_ceiling_minor=40_000_000,
            pinned_australia_cost_minor=30_550_000,
        )


def test_blocked_route_cannot_be_selected() -> None:
    with pytest.raises(ValueError, match="eligible"):
        validate_family_decision(
            decision(selected_route_id=MALAYSIA),
            projection(),
            pinned_budget_hard_ceiling_minor=40_000_000,
            pinned_australia_cost_minor=30_550_000,
        )


def test_australia_timeline_is_deterministic_and_excludes_japan_note() -> None:
    first = build_timeline_plan(Country.AUSTRALIA, "2027-02", date(2026, 7, 13))
    second = build_timeline_plan(Country.AUSTRALIA, "2027-02", date(2026, 7, 13))
    assert first == second
    assert first.milestones[0] == TimelineMilestone(key="documents", due_date=date(2026, 9, 1))
    assert all("japan" not in item.key for item in first.milestones)


def test_canonical_hash_ignores_mapping_order_but_binds_action() -> None:
    left = canonical_request_sha256({"action": ReviewAction.APPROVE_FOR_CONSULTATION, "version": 1})
    right = canonical_request_sha256({"version": 1, "action": "approve_for_consultation"})
    reject = canonical_request_sha256({"version": 1, "action": ReviewAction.REJECT})
    assert left == right
    assert left != reject
