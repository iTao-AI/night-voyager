from __future__ import annotations

from night_voyager.planning.models import (
    EvidenceAuthority,
    PlanningInput,
    PlanningResult,
    RouteOutcome,
    RunState,
)


def evaluate_planning_run(planning_input: PlanningInput) -> PlanningResult:
    evidence = tuple(item for route in planning_input.routes for item in route.evidence)
    if any(item.authority is EvidenceAuthority.UNTRUSTED_CANDIDATE for item in evidence):
        return PlanningResult(state=RunState.FAILED, reason_code="untrusted_candidate")

    recommended = tuple(
        route
        for route in planning_input.routes
        if route.outcome is RouteOutcome.RECOMMENDED_WITH_CONDITION
    )
    if len(recommended) != 1:
        return PlanningResult(state=RunState.BLOCKED, reason_code="recommendation_cardinality")

    route = recommended[0]
    evidenced_claims = {item.claim for item in route.evidence}
    if not set(route.required_claims) <= evidenced_claims:
        return PlanningResult(
            state=RunState.BLOCKED,
            reason_code="incomplete_recommendation_evidence",
        )
    return PlanningResult(
        state=RunState.REVIEW_REQUIRED,
        reason_code="single_fully_evidenced_recommendation",
    )
