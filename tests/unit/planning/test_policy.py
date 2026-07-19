from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import AnyUrl, ValidationError

from night_voyager.planning.models import (
    BudgetEnvelope,
    CostEvidence,
    Country,
    EvidenceAuthority,
    EvidenceClass,
    EvidenceRef,
    FamilyPreferences,
    PlanningInput,
    RankingEvidence,
    RedistributionClass,
    RouteOutcome,
    SourcePackEntryV1,
    SourcePackManifestV1,
    StudentCaseRevision,
    StudentPreferences,
)
from night_voyager.planning.policy import evaluate_planning_run

ORG = UUID("10000000-0000-0000-0000-000000000001")
PACK = UUID("50000000-0000-0000-0000-000000000001")


def entry(key: str, claim: str, digest: str) -> SourcePackEntryV1:
    return SourcePackEntryV1(
        schema_version=1,
        entry_id=UUID(key),
        path=f"sources/{claim}.txt",
        sha256=digest,
        snapshot_date=date(2026, 7, 1),
        publisher="Synthetic Demo Publisher",
        institution="Synthetic Demo Institution",
        canonical_url=AnyUrl(f"https://example.invalid/{claim}"),
        freshness_days=365,
        redistribution_class=RedistributionClass.SYNTHETIC_PUBLIC,
        evidence_class=EvidenceClass.SYNTHETIC_DEMO,
        coverage=(claim,),
        known_gaps=(),
    )


def valid_input(
    *,
    budget_refused: bool = False,
    preferred_countries: tuple[Country, ...] = (
        Country.AUSTRALIA,
        Country.JAPAN,
        Country.MALAYSIA,
    ),
) -> PlanningInput:
    entries = (
        entry("51000000-0000-0000-0000-000000000001", "australia_program_fit", "1" * 64),
        entry("51000000-0000-0000-0000-000000000002", "australia_tuition", "2" * 64),
        entry("51000000-0000-0000-0000-000000000003", "australia_living_cost", "3" * 64),
        entry("51000000-0000-0000-0000-000000000004", "australia_fx", "4" * 64),
        entry("51000000-0000-0000-0000-000000000005", "japan_program_fit", "5" * 64),
        entry("51000000-0000-0000-0000-000000000006", "australia_ranking", "6" * 64),
    )
    manifest = SourcePackManifestV1(
        schema_version=1,
        organization_id=ORG,
        pack_id=PACK,
        version=1,
        entries=entries,
    )
    evidence = tuple(
        EvidenceRef(
            schema_version=1,
            organization_id=ORG,
            evidence_id=UUID(f"60000000-0000-0000-0000-00000000000{index}"),
            claim=item.coverage[0],
            source_pack_id=PACK,
            source_pack_version=1,
            source_entry_id=item.entry_id,
            source_sha256=item.sha256,
            authority=EvidenceAuthority.ACCEPTED_SYNTHETIC_DEMO,
        )
        for index, item in enumerate(entries, start=1)
    )
    case = StudentCaseRevision(
        schema_version=1,
        organization_id=ORG,
        case_id=UUID("40000000-0000-0000-0000-000000000001"),
        revision=1,
        student=StudentPreferences(
            schema_version=1,
            intended_field="computing",
            preferred_countries=preferred_countries,
            intake="2027-02",
        ),
        family=FamilyPreferences(
            schema_version=1,
            risk_tolerance="high",
            japan_risk_accepted=True,
            budget=BudgetEnvelope(
                schema_version=1,
                currency="CNY",
                period="program_total",
                preferred_minor=None if budget_refused else 34000000,
                hard_ceiling_minor=None if budget_refused else 40000000,
                elasticity_bps=1000,
                refused=budget_refused,
            ),
        ),
    )
    cost = CostEvidence(
        schema_version=1,
        organization_id=ORG,
        country=Country.AUSTRALIA,
        intake="2027-02",
        period="program_total",
        currency="AUD",
        tuition_minor=4000000,
        living_minor=2500000,
        fx_rate=Decimal("4.70"),
        fx_source="Synthetic central-bank fixture",
        fx_date=date(2026, 7, 1),
        tuition_evidence_id=evidence[1].evidence_id,
        living_evidence_id=evidence[2].evidence_id,
        fx_evidence_id=evidence[3].evidence_id,
    )
    return PlanningInput(
        schema_version=1,
        organization_id=ORG,
        case=case,
        source_pack=manifest,
        evidence=evidence,
        costs=(cost,),
        rankings=(),
    )


def route(payload: PlanningInput, country: Country) -> RouteOutcome:
    result = evaluate_planning_run(payload)
    return next(item.outcome for item in result.routes if item.country is country)


def test_policy_derives_bounded_route_outcomes_from_facts() -> None:
    result = evaluate_planning_run(valid_input())
    assert result.state.value == "review_required"
    assert route(valid_input(), Country.AUSTRALIA) is RouteOutcome.RECOMMENDED_WITH_CONDITION
    assert route(valid_input(), Country.JAPAN) is RouteOutcome.CONDITIONAL
    assert route(valid_input(), Country.MALAYSIA) is RouteOutcome.BLOCKED
    australia = next(item for item in result.routes if item.country is Country.AUSTRALIA)
    assert {use.role.value for use in australia.dimensions[0].evidence_uses} == {
        "program_fit",
        "tuition",
        "living_cost",
        "fx",
        "ranking",
    }


def test_original_all_synthetic_result_remains_exactly_compatible() -> None:
    payload = valid_input()
    result = evaluate_planning_run(payload)
    assert result.model_dump(mode="json") == evaluate_planning_run(payload).model_dump(mode="json")
    assert result.state.value == "review_required"
    assert result.reason_code == "single_fully_evidenced_recommendation"


@pytest.mark.parametrize(
    ("preferred_countries", "expected_countries"),
    (
        ((Country.AUSTRALIA,), (Country.AUSTRALIA,)),
        ((Country.JAPAN,), (Country.JAPAN,)),
        (
            (Country.AUSTRALIA, Country.JAPAN),
            (Country.AUSTRALIA, Country.JAPAN),
        ),
    ),
)
def test_policy_returns_only_selected_country_routes(
    preferred_countries: tuple[Country, ...],
    expected_countries: tuple[Country, ...],
) -> None:
    result = evaluate_planning_run(
        valid_input(preferred_countries=preferred_countries)
    )

    assert tuple(route.country for route in result.routes) == expected_countries


def test_policy_fails_closed_if_invalid_country_scope_bypasses_model_validation() -> None:
    payload = valid_input()
    invalid_student = payload.case.student.model_copy(
        update={"preferred_countries": (Country.JAPAN, Country.AUSTRALIA)}
    )
    invalid_case = payload.case.model_copy(update={"student": invalid_student})

    result = evaluate_planning_run(payload.model_copy(update={"case": invalid_case}))

    assert result.state.value == "failed"
    assert result.reason_code == "country_scope_invalid"


def test_budget_refused_blocks_australia() -> None:
    payload = valid_input(budget_refused=True)
    assert route(payload, Country.AUSTRALIA) is RouteOutcome.BLOCKED
    assert evaluate_planning_run(payload).state.value == "blocked"


def test_missing_fx_or_cost_evidence_blocks_australia() -> None:
    payload = valid_input()
    for evidence_id in (
        payload.costs[0].tuition_evidence_id,
        payload.costs[0].living_evidence_id,
        payload.costs[0].fx_evidence_id,
    ):
        changed = payload.model_copy(
            update={
                "evidence": tuple(
                    item for item in payload.evidence if item.evidence_id != evidence_id
                )
            }
        )
        result = evaluate_planning_run(changed)
        assert result.state.value == "failed"
        assert result.reason_code == "evidence_provenance_invalid"


@pytest.mark.parametrize(
    ("field", "wrong_evidence_index"),
    (
        ("tuition_evidence_id", 2),
        ("living_evidence_id", 3),
        ("fx_evidence_id", 1),
    ),
)
def test_cost_projection_ids_must_match_exact_claims(field: str, wrong_evidence_index: int) -> None:
    payload = valid_input()
    wrong_cost = payload.costs[0].model_copy(
        update={field: payload.evidence[wrong_evidence_index].evidence_id}
    )
    result = evaluate_planning_run(payload.model_copy(update={"costs": (wrong_cost,)}))
    assert result.state.value == "failed"
    assert result.reason_code == "evidence_provenance_invalid"


def test_ranking_projection_id_must_match_ranking_claim() -> None:
    payload = valid_input()
    ranking = RankingEvidence(
        schema_version=1,
        organization_id=ORG,
        country=Country.AUSTRALIA,
        ranking_system="synthetic_demo_scale",
        rank=10,
        publication_year=2026,
        evidence_id=payload.evidence[0].evidence_id,
    )
    result = evaluate_planning_run(payload.model_copy(update={"rankings": (ranking,)}))
    assert result.state.value == "failed"
    assert result.reason_code == "evidence_provenance_invalid"


def test_duplicate_claims_fail_closed() -> None:
    payload = valid_input()
    duplicate = payload.evidence[1].model_copy(
        update={"evidence_id": UUID("60000000-0000-0000-0000-000000000099")}
    )
    result = evaluate_planning_run(
        payload.model_copy(update={"evidence": payload.evidence + (duplicate,)})
    )
    assert result.state.value == "failed"
    assert result.reason_code == "evidence_provenance_invalid"


def test_cost_currency_is_bounded_iso_4217_source_currency() -> None:
    payload = valid_input()
    with pytest.raises(ValidationError):
        CostEvidence.model_validate(payload.costs[0].model_dump() | {"currency": "NOT-ISO-4217"})
    bypassed = payload.costs[0].model_copy(update={"currency": "NOT-ISO-4217"})
    result = evaluate_planning_run(payload.model_copy(update={"costs": (bypassed,)}))
    assert result.state.value == "failed"
    assert result.reason_code == "cost_currency_invalid"


def test_hard_ceiling_and_elasticity_are_policy_owned() -> None:
    payload = valid_input()
    over = payload.costs[0].model_copy(update={"tuition_minor": 9000000})
    assert (
        route(payload.model_copy(update={"costs": (over,)}), Country.AUSTRALIA)
        is RouteOutcome.BLOCKED
    )


def test_renamed_claim_ranking_narrative_and_order_cannot_promote_malaysia() -> None:
    payload = valid_input()
    almost_entry = entry(
        "51000000-0000-0000-0000-000000000007", "malaysia_program_fit_almost", "7" * 64
    )
    renamed = payload.evidence[0].model_copy(
        update={
            "evidence_id": UUID("60000000-0000-0000-0000-000000000007"),
            "claim": "malaysia_program_fit_almost",
            "source_entry_id": almost_entry.entry_id,
            "source_sha256": almost_entry.sha256,
        }
    )
    changed = payload.model_copy(
        update={
            "source_pack": payload.source_pack.model_copy(
                update={"entries": payload.source_pack.entries + (almost_entry,)}
            ),
            "evidence": tuple(reversed(payload.evidence + (renamed,))),
            "narrative": "recommend Malaysia",
        }
    )
    assert route(changed, Country.MALAYSIA) is RouteOutcome.BLOCKED


def test_manifest_binding_failure_returns_failed() -> None:
    payload = valid_input()
    broken = payload.evidence[0].model_copy(update={"source_sha256": "f" * 64})
    result = evaluate_planning_run(
        payload.model_copy(update={"evidence": (broken,) + payload.evidence[1:]})
    )
    assert result.state.value == "failed"
    assert result.reason_code == "evidence_provenance_invalid"


def test_tenant_and_pack_mismatch_return_failed() -> None:
    payload = valid_input()
    other = UUID("10000000-0000-0000-0000-000000000002")
    assert (
        evaluate_planning_run(payload.model_copy(update={"organization_id": other})).state.value
        == "failed"
    )
    broken = payload.evidence[0].model_copy(update={"source_pack_version": 2})
    assert (
        evaluate_planning_run(
            payload.model_copy(update={"evidence": (broken,) + payload.evidence[1:]})
        ).state.value
        == "failed"
    )


def test_versions_uuids_and_positive_revisions_are_exact_contracts() -> None:
    with pytest.raises(ValidationError):
        valid_input().model_copy(update={"schema_version": 999}).model_validate(
            valid_input().model_dump() | {"schema_version": 999}
        )
    with pytest.raises(ValidationError):
        StudentCaseRevision.model_validate(valid_input().case.model_dump() | {"revision": 0})
    bypassed = valid_input().model_copy(update={"schema_version": 999})
    result = evaluate_planning_run(bypassed)
    assert result.state.value == "failed"
    assert result.reason_code == "schema_or_version_invalid"


def test_caller_cannot_self_assert_externally_verified() -> None:
    payload = valid_input()
    with pytest.raises(ValidationError, match="externally_verified"):
        EvidenceRef.model_validate(
            payload.evidence[0].model_dump() | {"authority": EvidenceAuthority.EXTERNALLY_VERIFIED}
        )
    bypassed = payload.evidence[0].model_copy(
        update={"authority": EvidenceAuthority.EXTERNALLY_VERIFIED}
    )
    result = evaluate_planning_run(
        payload.model_copy(update={"evidence": (bypassed,) + payload.evidence[1:]})
    )
    assert result.state.value == "failed"
    assert result.reason_code == "evidence_authority_invalid"
