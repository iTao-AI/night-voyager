from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import AnyUrl, ValidationError

from night_voyager.planning.fixtures import DEFAULT_MANIFEST, validate_planning_fixture
from night_voyager.planning.mixed import materialize_governed_mixed_input
from night_voyager.planning.models import (
    EvidenceAuthority,
    EvidenceClass,
    EvidenceRef,
    EvidenceRole,
    RedistributionClass,
    RunState,
    SourcePackEntryV1,
)
from night_voyager.planning.policy import evaluate_planning_run
from night_voyager.planning.trusted import (
    GovernedMixedPlanningInput,
    GovernedMixedSnapshotV1,
    TrustedEvidenceRef,
)

EXTERNAL_ENTRY = UUID("63000000-0000-0000-0000-000000000001")
EXTERNAL_EVIDENCE = UUID("64000000-0000-0000-0000-000000000001")
BASELINE_MANIFEST_SHA = "84350ea5705d9681d3e6550e1bd06e3340a9fcf0e7e7bbed4478ed3403405f28"
BASELINE_RAW_SHA = "5d455d2c409c322e093f3a116387f3cef0fb7ea0f7357fec5e76e9da5b3a2a25"
EXTERNAL_SHA = "87e314e801dca1aeaf9b751c149c53629a4cf23ee04698939fdc87def5a90a13"


def governed_snapshot() -> GovernedMixedSnapshotV1:
    baseline = validate_planning_fixture().planning_input
    australia = baseline.source_pack.entries[0].model_copy(
        update={
            "coverage": tuple(
                claim
                for claim in baseline.source_pack.entries[0].coverage
                if claim != "australia_program_fit"
            )
        }
    )
    external_entry = SourcePackEntryV1(
        schema_version=1,
        entry_id=EXTERNAL_ENTRY,
        path="sources/australia-program-fit.html",
        sha256=EXTERNAL_SHA,
        snapshot_date=date(2026, 7, 11),
        publisher="Public Source Publisher",
        institution="Australia Institution",
        canonical_url=AnyUrl("https://public.example/australia-program-fit"),
        freshness_days=365,
        redistribution_class=RedistributionClass.LINK_ONLY,
        evidence_class=EvidenceClass.INSTITUTIONAL,
        coverage=("australia_program_fit",),
        known_gaps=("applicant_eligibility", "intake_availability"),
    )
    promoted_version = 2
    promoted_pack = baseline.source_pack.model_copy(
        update={
            "version": promoted_version,
            "entries": (australia, *baseline.source_pack.entries[1:], external_entry),
        }
    )
    copied = tuple(
        TrustedEvidenceRef.model_validate(
            item.model_dump()
            | {
                "evidence_id": UUID(int=0x62000000000000000000000000000000 + index),
                "source_pack_version": promoted_version,
            }
        )
        for index, item in enumerate(
            (item for item in baseline.evidence if item.claim != "australia_program_fit"),
            start=1,
        )
    )
    external = TrustedEvidenceRef(
        schema_version=1,
        organization_id=baseline.organization_id,
        evidence_id=EXTERNAL_EVIDENCE,
        claim="australia_program_fit",
        source_pack_id=baseline.source_pack.pack_id,
        source_pack_version=promoted_version,
        source_entry_id=EXTERNAL_ENTRY,
        source_sha256=EXTERNAL_SHA,
        authority=EvidenceAuthority.EXTERNALLY_VERIFIED,
    )
    return GovernedMixedSnapshotV1(
        schema_version=1,
        organization_id=baseline.organization_id,
        case=baseline.case,
        source_pack=promoted_pack,
        evidence=(external, *copied),
        verification_decision="approve",
        verification_claim="australia_program_fit",
        verification_evidence_role=EvidenceRole.PROGRAM_FIT,
        baseline_source_pack_id=baseline.source_pack.pack_id,
        baseline_source_pack_version=1,
        baseline_manifest_sha256=BASELINE_MANIFEST_SHA,
        baseline_raw_manifest_sha256=BASELINE_RAW_SHA,
        promoted_source_pack_version=promoted_version,
        promoted_source_entry_id=EXTERNAL_ENTRY,
        promoted_evidence_id=EXTERNAL_EVIDENCE,
    )


def governed_mixed_input() -> GovernedMixedPlanningInput:
    return materialize_governed_mixed_input(governed_snapshot())


def test_public_evidence_ref_still_rejects_external_authority() -> None:
    external = governed_snapshot().evidence[0]
    with pytest.raises(ValidationError, match="externally_verified"):
        EvidenceRef.model_validate(external.model_dump())


def test_mixed_policy_requires_one_external_program_fit() -> None:
    planning_input = governed_mixed_input()
    result = evaluate_planning_run(planning_input)
    assert result.state is RunState.REVIEW_REQUIRED
    assert any(
        use.evidence_id == EXTERNAL_EVIDENCE
        for route in result.routes
        for dimension in route.dimensions
        for use in dimension.evidence_uses
    )
    assert planning_input.operation == "generate_governed_mixed_planning_run_v1"
    assert sum(
        item.authority is EvidenceAuthority.EXTERNALLY_VERIFIED
        for item in planning_input.evidence
    ) == 1


@pytest.mark.parametrize(
    "claim", ("australia_tuition", "australia_fx", "australia_ranking")
)
def test_external_non_program_fit_claim_fails_closed(claim: str) -> None:
    planning_input = governed_mixed_input()
    evidence = tuple(
        item.model_copy(update={"authority": EvidenceAuthority.EXTERNALLY_VERIFIED})
        if item.claim == claim
        else item.model_copy(update={"authority": EvidenceAuthority.ACCEPTED_SYNTHETIC_DEMO})
        if item.claim == "australia_program_fit"
        else item
        for item in planning_input.evidence
    )
    result = evaluate_planning_run(planning_input.model_copy(update={"evidence": evidence}))
    assert (result.state, result.reason_code) == (
        RunState.FAILED,
        "mixed_evidence_authority_invalid",
    )


@pytest.mark.parametrize("change", ("missing", "duplicate", "untrusted"))
def test_mixed_policy_rejects_missing_duplicate_or_untrusted_evidence(change: str) -> None:
    planning_input = governed_mixed_input()
    if change == "missing":
        evidence = planning_input.evidence[:-1]
    elif change == "duplicate":
        evidence = planning_input.evidence + (
            planning_input.evidence[-1].model_copy(
                update={"evidence_id": UUID("65000000-0000-0000-0000-000000000001")}
            ),
        )
    else:
        evidence = tuple(
            item.model_copy(update={"authority": EvidenceAuthority.UNTRUSTED_CANDIDATE})
            if item.claim == "australia_program_fit"
            else item
            for item in planning_input.evidence
        )
    result = evaluate_planning_run(planning_input.model_copy(update={"evidence": evidence}))
    assert result.state is RunState.FAILED
    assert result.reason_code in {
        "mixed_evidence_authority_invalid",
        "mixed_evidence_baseline_invalid",
    }


@pytest.mark.parametrize("change", ("pack", "hash", "coverage", "role"))
def test_materializer_rejects_wrong_pack_hash_coverage_or_role(change: str) -> None:
    snapshot = governed_snapshot()
    if change == "pack":
        snapshot = snapshot.model_copy(
            update={"baseline_source_pack_id": UUID("50000000-0000-0000-0000-000000000099")}
        )
    elif change == "hash":
        snapshot = snapshot.model_copy(
            update={
                "evidence": (
                    snapshot.evidence[0].model_copy(update={"source_sha256": "f" * 64}),
                    *snapshot.evidence[1:],
                )
            }
        )
    elif change == "coverage":
        external = snapshot.source_pack.entries[-1].model_copy(
            update={"coverage": ("australia_tuition",)}
        )
        snapshot = snapshot.model_copy(
            update={
                "source_pack": snapshot.source_pack.model_copy(
                    update={"entries": (*snapshot.source_pack.entries[:-1], external)}
                )
            }
        )
    else:
        snapshot = snapshot.model_copy(
            update={"verification_evidence_role": EvidenceRole.TUITION}
        )
    with pytest.raises(ValueError, match="governed mixed"):
        materialize_governed_mixed_input(snapshot)


def test_materializer_rejects_baseline_file_drift(tmp_path: Path) -> None:
    payload = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    payload["case"]["student"]["intended_field"] = "drifted"
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="baseline"):
        materialize_governed_mixed_input(governed_snapshot(), manifest_path=manifest)


def test_materializer_remaps_only_baseline_cost_and_ranking_ids() -> None:
    baseline = validate_planning_fixture().planning_input
    planning_input = governed_mixed_input()
    by_claim = {item.claim: item.evidence_id for item in planning_input.evidence}
    assert planning_input.costs[0].model_dump(exclude={"organization_id"}) == baseline.costs[
        0
    ].model_copy(
        update={
            "tuition_evidence_id": by_claim["australia_tuition"],
            "living_evidence_id": by_claim["australia_living_cost"],
            "fx_evidence_id": by_claim["australia_fx"],
        }
    ).model_dump(exclude={"organization_id"})
    assert planning_input.rankings[0].evidence_id == by_claim["australia_ranking"]
    assert all(
        by_claim[claim] != baseline_id
        for claim, baseline_id in {
            item.claim: item.evidence_id for item in baseline.evidence
        }.items()
        if claim != "australia_program_fit"
    )
