from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from night_voyager.planning import revision
from night_voyager.planning.hashing import canonical_sha256
from night_voyager.planning.models import (
    BudgetEnvelope,
    Country,
    DimensionOutcome,
    DimensionResult,
    EvidenceRole,
    EvidenceUse,
    RouteOutcome,
    RouteResult,
    RunState,
)

CASE = UUID("40000000-0000-0000-0000-000000000401")
PREVIOUS_RUN = UUID("70000000-0000-0000-0000-000000000401")
CURRENT_RUN = UUID("70000000-0000-0000-0000-000000000402")
REVIEW = UUID("90000000-0000-0000-0000-000000000401")


def route(
    country: Country,
    outcome: RouteOutcome,
    reason_code: str,
    *,
    evidence_id: int,
) -> RouteResult:
    dimension_outcome = {
        RouteOutcome.RECOMMENDED_WITH_CONDITION: DimensionOutcome.SUPPORTED,
        RouteOutcome.CONDITIONAL: DimensionOutcome.CONDITIONAL,
        RouteOutcome.BLOCKED: DimensionOutcome.BLOCKED,
    }[outcome]
    return RouteResult(
        country=country,
        outcome=outcome,
        reason_code=reason_code,
        dimensions=(
            DimensionResult(
                dimension_key="route_assessment",
                outcome=dimension_outcome,
                reason_code=reason_code,
                evidence_uses=(
                    EvidenceUse(
                        role=EvidenceRole.PROGRAM_FIT,
                        evidence_id=UUID(int=evidence_id),
                    ),
                ),
            ),
        ),
    )


def projection(
    *,
    run_id: UUID,
    revision_number: int,
    supersedes_run_id: UUID | None,
    state: RunState,
    reason_code: str,
    routes: tuple[RouteResult, ...],
) -> revision.PersistedPlanningResultProjectionV1:
    return revision.PersistedPlanningResultProjectionV1(
        case_id=CASE,
        case_revision=revision_number,
        planning_run_id=run_id,
        supersedes_run_id=supersedes_run_id,
        state=state,
        reason_code=reason_code,
        routes=routes,
    )


def previous_projection() -> revision.PersistedPlanningResultProjectionV1:
    return projection(
        run_id=PREVIOUS_RUN,
        revision_number=1,
        supersedes_run_id=None,
        state=RunState.REVIEW_REQUIRED,
        reason_code="single_fully_evidenced_recommendation",
        routes=(
            route(
                Country.AUSTRALIA,
                RouteOutcome.RECOMMENDED_WITH_CONDITION,
                "complete_cost_and_fx_within_boundary",
                evidence_id=1,
            ),
            route(
                Country.JAPAN,
                RouteOutcome.CONDITIONAL,
                "synthetic_high_risk_alternative",
                evidence_id=2,
            ),
            route(
                Country.MALAYSIA,
                RouteOutcome.BLOCKED,
                "direct_program_fit_evidence_absent",
                evidence_id=3,
            ),
        ),
    )


def current_projection(
    *, blocked: bool = False
) -> revision.PersistedPlanningResultProjectionV1:
    return projection(
        run_id=CURRENT_RUN,
        revision_number=2,
        supersedes_run_id=PREVIOUS_RUN,
        state=RunState.BLOCKED if blocked else RunState.REVIEW_REQUIRED,
        reason_code=(
            "recommendation_cardinality"
            if blocked
            else "single_fully_evidenced_recommendation"
        ),
        routes=(
            route(
                Country.AUSTRALIA,
                RouteOutcome.BLOCKED
                if blocked
                else RouteOutcome.RECOMMENDED_WITH_CONDITION,
                "budget_hard_ceiling_or_elasticity_exceeded"
                if blocked
                else "complete_cost_and_fx_within_boundary",
                evidence_id=1,
            ),
            route(
                Country.JAPAN,
                RouteOutcome.BLOCKED if blocked else RouteOutcome.CONDITIONAL,
                "recommendation_cardinality"
                if blocked
                else "japan_risk_or_program_fit_unresolved",
                evidence_id=2,
            ),
        ),
    )


def preferred_country_delta() -> revision.PreferredCountriesFactDeltaV1:
    return revision.PreferredCountriesFactDeltaV1(
        fact_key="student.preferred_countries",
        previous_value=(
            Country.AUSTRALIA,
            Country.JAPAN,
            Country.MALAYSIA,
        ),
        current_value=(Country.AUSTRALIA, Country.JAPAN),
    )


def planning_hash(value: revision.PersistedPlanningResultProjectionV1) -> str:
    return canonical_sha256(value.planning_result().model_dump(mode="json"))


def build(
    *,
    current: revision.PersistedPlanningResultProjectionV1 | None = None,
    changed_fact: revision.PlanningRevisionFactDeltaV1 | None = None,
) -> revision.PlanningRevisionComparisonV1:
    previous = previous_projection()
    current = current or current_projection()
    return revision.build_planning_revision_comparison(
        changed_fact=changed_fact or preferred_country_delta(),
        previous=previous,
        current=current,
        previous_output_sha256=planning_hash(previous),
        current_output_sha256=planning_hash(current),
    )


def test_lineage_requires_one_adjacent_revision() -> None:
    lineage = revision.PlanningRevisionLineageV1(
        schema_version=1,
        case_id=CASE,
        previous_revision=1,
        current_revision=2,
        request_revision_review_id=REVIEW,
        predecessor_planning_run_id=PREVIOUS_RUN,
    )
    assert lineage.current_revision == 2

    with pytest.raises(ValidationError, match="planning_revision_not_adjacent"):
        lineage.model_copy(update={"current_revision": 3}, deep=True).__class__.model_validate(
            {**lineage.model_dump(), "current_revision": 3}
        )


def test_preferred_country_comparison_is_closed_country_keyed_and_canonical() -> None:
    comparison = build()

    assert tuple(item.country for item in comparison.countries) == (
        Country.AUSTRALIA,
        Country.JAPAN,
        Country.MALAYSIA,
    )
    assert tuple(item.delta for item in comparison.countries) == (
        revision.PlanningRevisionDelta.UNCHANGED,
        revision.PlanningRevisionDelta.CHANGED,
        revision.PlanningRevisionDelta.REMOVED,
    )
    malaysia = comparison.countries[-1]
    assert malaysia.current_outcome is None
    assert malaysia.current_reason_code is None
    assert comparison.approval_eligible is True
    assert comparison.current_run_state == "review_required"


def test_lower_budget_blocked_successor_preserves_comparison_without_approval() -> None:
    budget_delta = revision.FamilyBudgetFactDeltaV1(
        fact_key="family.budget",
        previous_value=BudgetEnvelope(
            schema_version=1,
            currency="CNY",
            period="program_total",
            preferred_minor=34_000_000,
            hard_ceiling_minor=40_000_000,
            elasticity_bps=1000,
        ),
        current_value=BudgetEnvelope(
            schema_version=1,
            currency="CNY",
            period="program_total",
            preferred_minor=10_000_000,
            hard_ceiling_minor=12_000_000,
            elasticity_bps=500,
        ),
    )

    comparison = build(current=current_projection(blocked=True), changed_fact=budget_delta)

    assert comparison.current_run_state == "blocked"
    assert comparison.approval_eligible is False
    assert comparison.changed_fact.fact_key == "family.budget"


@pytest.mark.parametrize(
    "payload",
    (
        {
            "fact_key": "student.preferred_countries",
            "previous_value": ["australia", "japan"],
            "current_value": ["australia", "japan"],
        },
        {
            "fact_key": "student.preferred_countries",
            "previous_value": ["japan", "australia"],
            "current_value": ["australia"],
        },
        {
            "fact_key": "student.preferred_countries",
            "previous_value": ["australia", "australia"],
            "current_value": ["australia"],
        },
        {
            "fact_key": "student.preferred_countries",
            "previous_value": ["canada"],
            "current_value": ["australia"],
        },
        {
            "fact_key": "unsupported",
            "previous_value": ["australia"],
            "current_value": ["japan"],
        },
    ),
)
def test_changed_fact_rejects_unchanged_malformed_or_unsupported_values(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        revision.PlanningRevisionComparisonV1.model_validate(
            {
                **build().model_dump(mode="json"),
                "changed_fact": payload,
            }
        )


def test_comparison_rejects_mismatched_predecessor_or_revision() -> None:
    current = current_projection().model_copy(
        update={"supersedes_run_id": UUID(int=999)}
    )
    with pytest.raises(ValueError, match="planning_revision_lineage_mismatch"):
        build(current=current)

    current = current_projection().model_copy(update={"case_revision": 3})
    with pytest.raises(ValueError, match="planning_revision_lineage_mismatch"):
        build(current=current)


def test_builder_owns_approval_eligibility() -> None:
    builder = cast(Callable[..., object], revision.build_planning_revision_comparison)
    with pytest.raises(TypeError):
        builder(
            changed_fact=preferred_country_delta(),
            previous=previous_projection(),
            current=current_projection(),
            previous_output_sha256=planning_hash(previous_projection()),
            current_output_sha256=planning_hash(current_projection()),
            approval_eligible=False,
        )


def test_known_complete_planning_result_hashes_are_stable() -> None:
    assert planning_hash(previous_projection()) == (
        "13b299c2eaf3eab8ba6cf832c4dfaae592dbfe9b0dfe03eaf264777953bcfefd"
    )
    assert planning_hash(current_projection()) == (
        "9ee2c99a11e58d1bc2be2b326032bb7ec2c219818234c33f94827604acd00641"
    )


@pytest.mark.parametrize(
    ("path", "replacement"),
    (
        (("state",), "blocked"),
        (("reason_code",), "tampered_reason"),
        (("routes", 0, "outcome"), "blocked"),
        (("routes", 0, "dimensions", 0, "outcome"), "blocked"),
        (
            ("routes", 0, "dimensions", 0, "evidence_uses", 0, "evidence_id"),
            str(UUID(int=999)),
        ),
    ),
)
def test_complete_result_hash_rejects_tampered_persisted_rows(
    path: tuple[object, ...],
    replacement: object,
) -> None:
    previous = previous_projection()
    current = current_projection()
    stored_hash = planning_hash(current)
    payload = current.model_dump(mode="json")
    target: object = payload
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    target[path[-1]] = replacement  # type: ignore[index]
    tampered = revision.PersistedPlanningResultProjectionV1.model_validate(payload)

    with pytest.raises(ValueError, match="planning_result_hash_mismatch"):
        revision.build_planning_revision_comparison(
            changed_fact=preferred_country_delta(),
            previous=previous,
            current=tampered,
            previous_output_sha256=planning_hash(previous),
            current_output_sha256=stored_hash,
        )


def test_public_comparison_rejects_duplicate_or_unknown_country_rows() -> None:
    payload = build().model_dump(mode="json")
    duplicate = deepcopy(payload)
    duplicate["countries"].append(deepcopy(duplicate["countries"][0]))
    with pytest.raises(ValidationError):
        revision.PlanningRevisionComparisonV1.model_validate(duplicate)

    unknown = deepcopy(payload)
    unknown["countries"][0]["country"] = "canada"
    with pytest.raises(ValidationError):
        revision.PlanningRevisionComparisonV1.model_validate(unknown)
