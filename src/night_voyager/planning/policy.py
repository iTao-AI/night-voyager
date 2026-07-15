from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from uuid import UUID

from night_voyager.planning.models import (
    Country,
    DimensionOutcome,
    DimensionResult,
    EvidenceAuthority,
    EvidenceRef,
    EvidenceRole,
    EvidenceUse,
    PlanningInput,
    PlanningResult,
    RouteOutcome,
    RouteResult,
    RunState,
)
from night_voyager.planning.trusted import GovernedMixedPlanningInput, TrustedEvidenceRef

PlanningPolicyInput = PlanningInput | GovernedMixedPlanningInput
PolicyEvidenceRef = EvidenceRef | TrustedEvidenceRef
MIXED_BASELINE_CLAIMS = frozenset(
    {
        "australia_program_fit",
        "australia_tuition",
        "australia_living_cost",
        "australia_fx",
        "japan_program_fit",
        "australia_ranking",
    }
)


def evaluate_planning_run(planning_input: PlanningPolicyInput) -> PlanningResult:
    contract_error = _validate_contract(planning_input)
    if contract_error is not None:
        return PlanningResult(state=RunState.FAILED, reason_code=contract_error, routes=())
    provenance_error = _validate_provenance(planning_input)
    if provenance_error is not None:
        return PlanningResult(state=RunState.FAILED, reason_code=provenance_error, routes=())

    evidence_by_claim = {item.claim: item for item in planning_input.evidence}
    australia = _australia(planning_input, evidence_by_claim)
    japan_outcome = (
        RouteOutcome.CONDITIONAL
        if "japan_program_fit" in evidence_by_claim
        and planning_input.case.family.japan_risk_accepted
        else RouteOutcome.BLOCKED
    )
    japan_reason = (
        "synthetic_high_risk_alternative"
        if "japan_program_fit" in evidence_by_claim
        and planning_input.case.family.japan_risk_accepted
        else "japan_risk_or_program_fit_unresolved"
    )
    japan = _route_result(Country.JAPAN, japan_outcome, japan_reason, evidence_by_claim)
    malaysia_outcome = (
        RouteOutcome.CONDITIONAL
        if "malaysia_program_fit" in evidence_by_claim
        else RouteOutcome.BLOCKED
    )
    malaysia_reason = (
        "malaysia_program_fit_present"
        if "malaysia_program_fit" in evidence_by_claim
        else "direct_program_fit_evidence_absent"
    )
    malaysia = _route_result(Country.MALAYSIA, malaysia_outcome, malaysia_reason, evidence_by_claim)
    routes = (australia, japan, malaysia)
    recommended = sum(route.outcome is RouteOutcome.RECOMMENDED_WITH_CONDITION for route in routes)
    return PlanningResult(
        state=RunState.REVIEW_REQUIRED if recommended == 1 else RunState.BLOCKED,
        reason_code=(
            "single_fully_evidenced_recommendation"
            if recommended == 1
            else "recommendation_cardinality"
        ),
        routes=routes,
    )


def _validate_contract(planning_input: PlanningPolicyInput) -> str | None:
    versioned = (
        planning_input,
        planning_input.case,
        planning_input.case.student,
        planning_input.case.family,
        planning_input.case.family.budget,
        planning_input.source_pack,
        *planning_input.source_pack.entries,
        *planning_input.evidence,
        *planning_input.costs,
        *planning_input.rankings,
    )
    if any(getattr(item, "schema_version", None) != 1 for item in versioned):
        return "schema_or_version_invalid"
    if (
        not _is_uuid(planning_input.organization_id)
        or planning_input.case.revision <= 0
        or planning_input.source_pack.version <= 0
        or any(item.source_pack_version <= 0 for item in planning_input.evidence)
    ):
        return "schema_or_version_invalid"
    if isinstance(planning_input, GovernedMixedPlanningInput):
        evidence_by_claim = {item.claim: item for item in planning_input.evidence}
        if (
            len(evidence_by_claim) != len(planning_input.evidence)
            or set(evidence_by_claim) != set(MIXED_BASELINE_CLAIMS)
        ):
            return "mixed_evidence_baseline_invalid"
        if any(
            item.authority
            is not (
                EvidenceAuthority.EXTERNALLY_VERIFIED
                if item.claim == "australia_program_fit"
                else EvidenceAuthority.ACCEPTED_SYNTHETIC_DEMO
            )
            for item in planning_input.evidence
        ):
            return "mixed_evidence_authority_invalid"
    elif any(
        item.authority is not EvidenceAuthority.ACCEPTED_SYNTHETIC_DEMO
        for item in planning_input.evidence
    ):
        return "evidence_authority_invalid"
    if any(item.currency != "AUD" for item in planning_input.costs):
        return "cost_currency_invalid"
    return None


def _is_uuid(value: object) -> bool:
    return isinstance(value, UUID)


def _validate_provenance(planning_input: PlanningPolicyInput) -> str | None:
    organization_ids = {
        planning_input.organization_id,
        planning_input.case.organization_id,
        planning_input.source_pack.organization_id,
        *(item.organization_id for item in planning_input.evidence),
        *(item.organization_id for item in planning_input.costs),
        *(item.organization_id for item in planning_input.rankings),
    }
    if len(organization_ids) != 1:
        return "tenant_mismatch"
    evidence_ids = [item.evidence_id for item in planning_input.evidence]
    evidence_claims = [item.claim for item in planning_input.evidence]
    if len(set(evidence_ids)) != len(evidence_ids) or len(set(evidence_claims)) != len(
        evidence_claims
    ):
        return "evidence_provenance_invalid"
    entries = {entry.entry_id: entry for entry in planning_input.source_pack.entries}
    for evidence in planning_input.evidence:
        entry = entries.get(evidence.source_entry_id)
        if (
            evidence.authority is EvidenceAuthority.UNTRUSTED_CANDIDATE
            or evidence.source_pack_id != planning_input.source_pack.pack_id
            or evidence.source_pack_version != planning_input.source_pack.version
            or entry is None
            or evidence.source_sha256 != entry.sha256
            or evidence.claim not in entry.coverage
        ):
            return "evidence_provenance_invalid"
    evidence_by_id = {item.evidence_id: item for item in planning_input.evidence}
    for cost in planning_input.costs:
        expected_cost_claims = (
            (cost.tuition_evidence_id, f"{cost.country.value}_tuition"),
            (cost.living_evidence_id, f"{cost.country.value}_living_cost"),
            (cost.fx_evidence_id, f"{cost.country.value}_fx"),
        )
        if any(
            evidence_by_id.get(evidence_id) is None
            or evidence_by_id[evidence_id].claim != expected_claim
            for evidence_id, expected_claim in expected_cost_claims
        ):
            return "evidence_provenance_invalid"
    for ranking in planning_input.rankings:
        evidence = evidence_by_id.get(ranking.evidence_id)
        if evidence is None or evidence.claim != f"{ranking.country.value}_ranking":
            return "evidence_provenance_invalid"
    return None


def _australia(
    planning_input: PlanningPolicyInput,
    evidence_by_claim: Mapping[str, PolicyEvidenceRef],
) -> RouteResult:
    budget = planning_input.case.family.budget
    required_claims = {
        "australia_program_fit",
        "australia_tuition",
        "australia_living_cost",
        "australia_fx",
    }
    cost = next((item for item in planning_input.costs if item.country is Country.AUSTRALIA), None)
    evidence_ids = {item.evidence_id for item in planning_input.evidence}
    complete = (
        required_claims <= evidence_by_claim.keys()
        and cost is not None
        and cost.intake == planning_input.case.student.intake
        and cost.period == budget.period
        and {
            cost.tuition_evidence_id,
            cost.living_evidence_id,
            cost.fx_evidence_id,
        }
        <= evidence_ids
    )
    if budget.refused or not complete:
        return _route_result(
            Country.AUSTRALIA,
            RouteOutcome.BLOCKED,
            "budget_refused" if budget.refused else "cost_or_fx_evidence_incomplete",
            evidence_by_claim,
        )
    assert cost is not None
    assert budget.preferred_minor is not None and budget.hard_ceiling_minor is not None
    total = Decimal(cost.tuition_minor + cost.living_minor) * cost.fx_rate
    elastic_ceiling = Decimal(budget.preferred_minor) * (
        Decimal(1) + Decimal(budget.elasticity_bps) / Decimal(10000)
    )
    if total > budget.hard_ceiling_minor or total > elastic_ceiling:
        return _route_result(
            Country.AUSTRALIA,
            RouteOutcome.BLOCKED,
            "budget_hard_ceiling_or_elasticity_exceeded",
            evidence_by_claim,
        )
    return _route_result(
        Country.AUSTRALIA,
        RouteOutcome.RECOMMENDED_WITH_CONDITION,
        "complete_cost_and_fx_within_boundary",
        evidence_by_claim,
    )


def _route_result(
    country: Country,
    outcome: RouteOutcome,
    reason_code: str,
    evidence_by_claim: Mapping[str, PolicyEvidenceRef],
) -> RouteResult:
    claims_by_country: dict[Country, tuple[tuple[str, EvidenceRole], ...]] = {
        Country.AUSTRALIA: (
            ("australia_program_fit", EvidenceRole.PROGRAM_FIT),
            ("australia_tuition", EvidenceRole.TUITION),
            ("australia_living_cost", EvidenceRole.LIVING_COST),
            ("australia_fx", EvidenceRole.FX),
            ("australia_ranking", EvidenceRole.RANKING),
        ),
        Country.JAPAN: (("japan_program_fit", EvidenceRole.PROGRAM_FIT),),
        Country.MALAYSIA: (("malaysia_program_fit", EvidenceRole.PROGRAM_FIT),),
    }
    uses = tuple(
        EvidenceUse(role=role, evidence_id=evidence_by_claim[claim].evidence_id)
        for claim, role in claims_by_country[country]
        if claim in evidence_by_claim
    )
    dimension_outcome = (
        DimensionOutcome.BLOCKED
        if outcome is RouteOutcome.BLOCKED
        else DimensionOutcome.SUPPORTED
        if outcome is RouteOutcome.RECOMMENDED_WITH_CONDITION
        else DimensionOutcome.CONDITIONAL
    )
    return RouteResult(
        country=country,
        outcome=outcome,
        reason_code=reason_code,
        dimensions=(
            DimensionResult(
                dimension_key="route_assessment",
                outcome=dimension_outcome,
                reason_code=reason_code,
                evidence_uses=uses,
            ),
        ),
    )
