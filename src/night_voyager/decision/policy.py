from __future__ import annotations

from datetime import date
from uuid import UUID

from night_voyager.decision.models import (
    BriefRoute,
    DecisionBriefProjection,
    EvidenceRiskAcceptance,
    FamilyDecisionCommand,
    TimelineMilestone,
    TimelinePlan,
)
from night_voyager.planning.models import Country, RouteOutcome


def eligible_route_ids(routes: tuple[BriefRoute, ...]) -> tuple[UUID, ...]:
    return tuple(route.route_id for route in routes if route.outcome is not RouteOutcome.BLOCKED)


def validate_risk_acceptances(acceptances: tuple[EvidenceRiskAcceptance, ...]) -> None:
    if len({item.evidence_id for item in acceptances}) != len(acceptances):
        raise ValueError("Evidence risk acceptance must be unique")


def validate_family_decision(
    command: FamilyDecisionCommand,
    brief: DecisionBriefProjection,
    *,
    pinned_budget_hard_ceiling_minor: int,
    pinned_australia_cost_minor: int,
) -> None:
    if command.brief_id != brief.brief_id or command.expected_brief_version != brief.brief_version:
        raise ValueError("decision brief is stale")
    if command.selected_route_id not in brief.eligible_route_ids:
        raise ValueError("selected route is not eligible")
    route = next(route for route in brief.routes if route.route_id == command.selected_route_id)
    if command.accepted_budget_max_minor > pinned_budget_hard_ceiling_minor:
        raise ValueError("accepted budget exceeds pinned hard ceiling")
    if route.country is Country.AUSTRALIA:
        if "budget_elasticity" not in command.accepted_trade_offs:
            raise ValueError("Australia requires budget_elasticity trade-off")
        if not (
            command.accepted_budget_min_minor
            <= pinned_australia_cost_minor
            <= command.accepted_budget_max_minor
        ):
            raise ValueError("accepted budget must contain pinned cost")


def build_timeline_plan(country: Country, intake: str, decided_on: date) -> TimelinePlan:
    if country is not Country.AUSTRALIA:
        raise ValueError("M3B synthetic timeline supports the selected Australia route")
    year, month = (int(part) for part in intake.split("-", maxsplit=1))
    if month != 2:
        raise ValueError("M3B synthetic timeline requires the February intake")
    documents_year = year - 1
    if decided_on >= date(documents_year, 9, 1):
        raise ValueError("decision date is outside the deterministic timeline window")
    return TimelinePlan(
        schema_version=1,
        country=country,
        intake=intake,
        milestones=(
            TimelineMilestone(key="documents", due_date=date(documents_year, 9, 1)),
            TimelineMilestone(key="application", due_date=date(documents_year, 10, 15)),
            TimelineMilestone(key="visa", due_date=date(documents_year, 12, 15)),
            TimelineMilestone(key="arrival", due_date=date(year, 1, 20)),
        ),
    )
