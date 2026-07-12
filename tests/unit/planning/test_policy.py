from __future__ import annotations

from copy import deepcopy

import pytest

from night_voyager.planning.models import (
    EvidenceAuthority,
    EvidenceRef,
    PlanningInput,
    RouteCandidate,
    RouteOutcome,
    RunState,
)
from night_voyager.planning.policy import evaluate_planning_run


def evidence(claim: str) -> EvidenceRef:
    return EvidenceRef(
        schema_version=1,
        evidence_id=f"evidence-{claim}",
        claim=claim,
        source_pack_version=1,
        source_entry_id=f"source-{claim}",
        source_sha256="a" * 64,
        authority=EvidenceAuthority.ACCEPTED_SYNTHETIC_DEMO,
    )


def valid_input() -> PlanningInput:
    return PlanningInput(
        schema_version=1,
        organization_id="10000000-0000-0000-0000-000000000001",
        case_revision=1,
        source_pack_version=1,
        routes=(
            RouteCandidate(
                route_id="australia",
                outcome=RouteOutcome.RECOMMENDED_WITH_CONDITION,
                required_claims=("program_fit", "cost", "fx"),
                evidence=(evidence("program_fit"), evidence("cost"), evidence("fx")),
            ),
            RouteCandidate(
                route_id="japan",
                outcome=RouteOutcome.CONDITIONAL,
                required_claims=("program_fit",),
                evidence=(evidence("program_fit"),),
            ),
            RouteCandidate(
                route_id="malaysia",
                outcome=RouteOutcome.BLOCKED,
                required_claims=("program_fit",),
                evidence=(),
            ),
        ),
    )


def test_exactly_one_fully_evidenced_recommendation_requires_review() -> None:
    result = evaluate_planning_run(valid_input())
    assert result.state is RunState.REVIEW_REQUIRED
    assert result.reason_code == "single_fully_evidenced_recommendation"


@pytest.mark.parametrize("recommended", [0, 2])
def test_zero_or_multiple_recommendations_are_blocked(recommended: int) -> None:
    payload = valid_input()
    routes = list(payload.routes)
    routes[0] = routes[0].model_copy(
        update={"outcome": RouteOutcome.CONDITIONAL if recommended == 0 else routes[0].outcome}
    )
    if recommended == 2:
        routes[1] = routes[1].model_copy(
            update={"outcome": RouteOutcome.RECOMMENDED_WITH_CONDITION}
        )
    result = evaluate_planning_run(payload.model_copy(update={"routes": tuple(routes)}))
    assert result.state is RunState.BLOCKED
    assert result.reason_code == "recommendation_cardinality"


def test_untrusted_candidate_fails_even_when_complete() -> None:
    payload = valid_input()
    routes = list(payload.routes)
    evidence_refs = list(routes[0].evidence)
    evidence_refs[0] = evidence_refs[0].model_copy(
        update={"authority": EvidenceAuthority.UNTRUSTED_CANDIDATE}
    )
    routes[0] = routes[0].model_copy(update={"evidence": tuple(evidence_refs)})
    result = evaluate_planning_run(payload.model_copy(update={"routes": tuple(routes)}))
    assert result.state is RunState.FAILED
    assert result.reason_code == "untrusted_candidate"


def test_fixture_order_and_narrative_do_not_change_policy_result() -> None:
    original = valid_input()
    changed = deepcopy(original)
    changed = changed.model_copy(
        update={
            "routes": tuple(reversed(changed.routes)),
            "narrative": "Untrusted prose must have no authority.",
        }
    )
    assert evaluate_planning_run(original) == evaluate_planning_run(changed)


def test_unknown_cost_is_not_zero_filled() -> None:
    from night_voyager.planning.models import CostEvidence

    with pytest.raises(ValueError):
        CostEvidence(
            schema_version=1,
            currency="AUD",
            tuition_minor=None,
            living_minor=0,
            fx_rate=None,
            fx_boundary_bps=None,
        )
