"""Closed planning revision lineage and comparison contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import ConfigDict, Field, PositiveInt, StringConstraints, model_validator

from night_voyager.planning.hashing import canonical_sha256
from night_voyager.planning.models import (
    BudgetEnvelope,
    Country,
    FrozenModel,
    PlanningResult,
    RouteOutcome,
    RouteResult,
    RunState,
    preferred_country_scope_is_valid,
)

Sha256 = Annotated[
    str,
    StringConstraints(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    ),
]
PlanningReasonCode = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9_]{0,99}$",
    ),
]


class PlanningRevisionLineageV1(FrozenModel):
    schema_version: Literal[1]
    case_id: UUID
    previous_revision: PositiveInt
    current_revision: PositiveInt
    request_revision_review_id: UUID
    predecessor_planning_run_id: UUID

    @model_validator(mode="after")
    def adjacent_revision(self) -> Self:
        if self.current_revision != self.previous_revision + 1:
            raise ValueError("planning_revision_not_adjacent")
        return self


class PlanningRevisionDelta(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


class PreferredCountriesFactDeltaV1(FrozenModel):
    fact_key: Literal["student.preferred_countries"]
    previous_value: tuple[Country, ...]
    current_value: tuple[Country, ...]

    @model_validator(mode="after")
    def changed_closed_country_scopes(self) -> Self:
        if not preferred_country_scope_is_valid(
            self.previous_value
        ) or not preferred_country_scope_is_valid(self.current_value):
            raise ValueError("planning_revision_country_scope_invalid")
        if self.previous_value == self.current_value:
            raise ValueError("planning_revision_fact_unchanged")
        return self


class FamilyBudgetFactDeltaV1(FrozenModel):
    fact_key: Literal["family.budget"]
    previous_value: BudgetEnvelope
    current_value: BudgetEnvelope

    @model_validator(mode="after")
    def changed_budget(self) -> Self:
        if self.previous_value == self.current_value:
            raise ValueError("planning_revision_fact_unchanged")
        return self


PlanningRevisionFactDeltaV1 = Annotated[
    PreferredCountriesFactDeltaV1 | FamilyBudgetFactDeltaV1,
    Field(discriminator="fact_key"),
]


class PlanningRevisionCountryComparisonV1(FrozenModel):
    country: Country
    delta: PlanningRevisionDelta
    previous_outcome: RouteOutcome | None
    previous_reason_code: PlanningReasonCode | None
    current_outcome: RouteOutcome | None
    current_reason_code: PlanningReasonCode | None

    @model_validator(mode="after")
    def closed_delta_shape(self) -> Self:
        previous = (self.previous_outcome, self.previous_reason_code)
        current = (self.current_outcome, self.current_reason_code)
        if self.delta is PlanningRevisionDelta.ADDED:
            valid = previous == (None, None) and None not in current
        elif self.delta is PlanningRevisionDelta.REMOVED:
            valid = None not in previous and current == (None, None)
        elif self.delta is PlanningRevisionDelta.UNCHANGED:
            valid = None not in previous and previous == current
        else:
            valid = None not in previous and None not in current and previous != current
        if not valid:
            raise ValueError("planning_revision_country_delta_invalid")
        return self


class PlanningRevisionComparisonV1(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    schema_: Literal["night-voyager.planning-revision-comparison.v1"] = Field(
        alias="schema",
        serialization_alias="schema",
    )
    case_id: UUID
    previous_revision: PositiveInt
    current_revision: PositiveInt
    previous_planning_run_id: UUID
    current_planning_run_id: UUID
    previous_output_sha256: Sha256
    current_output_sha256: Sha256
    changed_fact: PlanningRevisionFactDeltaV1
    countries: tuple[PlanningRevisionCountryComparisonV1, ...]
    current_run_state: Literal["review_required", "blocked"]
    approval_eligible: bool

    @model_validator(mode="after")
    def canonical_closed_projection(self) -> Self:
        countries = tuple(item.country for item in self.countries)
        if countries != tuple(sorted(set(countries), key=lambda item: item.value)):
            raise ValueError("planning_revision_comparison_countries_invalid")
        if self.current_revision != self.previous_revision + 1:
            raise ValueError("planning_revision_not_adjacent")
        if self.approval_eligible != (self.current_run_state == "review_required"):
            raise ValueError("planning_revision_approval_eligibility_invalid")
        return self


class PersistedPlanningResultProjectionV1(FrozenModel):
    """Internal complete run projection used before public comparison."""

    case_id: UUID
    case_revision: PositiveInt
    planning_run_id: UUID
    supersedes_run_id: UUID | None
    state: RunState
    reason_code: PlanningReasonCode
    routes: tuple[RouteResult, ...]

    @model_validator(mode="after")
    def closed_result(self) -> Self:
        if self.state not in {RunState.REVIEW_REQUIRED, RunState.BLOCKED}:
            raise ValueError("planning_revision_run_state_invalid")
        countries = tuple(item.country for item in self.routes)
        if countries != tuple(sorted(set(countries), key=lambda item: item.value)):
            raise ValueError("planning_revision_result_countries_invalid")
        return self

    def planning_result(self) -> PlanningResult:
        return PlanningResult(
            state=self.state,
            reason_code=self.reason_code,
            routes=self.routes,
        )


def _verified_result(
    projection: PersistedPlanningResultProjectionV1,
    expected_sha256: str,
) -> PlanningResult:
    result = projection.planning_result()
    observed_sha256 = canonical_sha256(result.model_dump(mode="json"))
    if observed_sha256 != expected_sha256:
        raise ValueError("planning_result_hash_mismatch")
    return result


def build_planning_revision_comparison(
    *,
    changed_fact: PlanningRevisionFactDeltaV1,
    previous: PersistedPlanningResultProjectionV1,
    current: PersistedPlanningResultProjectionV1,
    previous_output_sha256: Sha256,
    current_output_sha256: Sha256,
) -> PlanningRevisionComparisonV1:
    if (
        current.case_id != previous.case_id
        or current.case_revision != previous.case_revision + 1
        or current.supersedes_run_id != previous.planning_run_id
        or current.planning_run_id == previous.planning_run_id
    ):
        raise ValueError("planning_revision_lineage_mismatch")

    previous_result = _verified_result(previous, previous_output_sha256)
    current_result = _verified_result(current, current_output_sha256)
    previous_routes = {item.country: item for item in previous_result.routes}
    current_routes = {item.country: item for item in current_result.routes}
    countries = tuple(
        sorted(previous_routes.keys() | current_routes.keys(), key=lambda item: item.value)
    )
    comparisons: list[PlanningRevisionCountryComparisonV1] = []
    for country in countries:
        previous_route = previous_routes.get(country)
        current_route = current_routes.get(country)
        if previous_route is None:
            delta = PlanningRevisionDelta.ADDED
        elif current_route is None:
            delta = PlanningRevisionDelta.REMOVED
        elif (
            previous_route.outcome == current_route.outcome
            and previous_route.reason_code == current_route.reason_code
        ):
            delta = PlanningRevisionDelta.UNCHANGED
        else:
            delta = PlanningRevisionDelta.CHANGED
        comparisons.append(
            PlanningRevisionCountryComparisonV1(
                country=country,
                delta=delta,
                previous_outcome=previous_route.outcome if previous_route else None,
                previous_reason_code=previous_route.reason_code if previous_route else None,
                current_outcome=current_route.outcome if current_route else None,
                current_reason_code=current_route.reason_code if current_route else None,
            )
        )

    current_state = (
        "review_required"
        if current_result.state is RunState.REVIEW_REQUIRED
        else "blocked"
    )
    return PlanningRevisionComparisonV1(
        schema="night-voyager.planning-revision-comparison.v1",
        case_id=current.case_id,
        previous_revision=previous.case_revision,
        current_revision=current.case_revision,
        previous_planning_run_id=previous.planning_run_id,
        current_planning_run_id=current.planning_run_id,
        previous_output_sha256=previous_output_sha256,
        current_output_sha256=current_output_sha256,
        changed_fact=changed_fact,
        countries=tuple(comparisons),
        current_run_state=current_state,
        approval_eligible=current_state == "review_required",
    )
