from __future__ import annotations

import hashlib
from pathlib import Path

from night_voyager.planning.fixtures import DEFAULT_MANIFEST, validate_planning_fixture
from night_voyager.planning.models import EvidenceAuthority, PlanningInput
from night_voyager.planning.trusted import (
    GovernedMixedPlanningInput,
    GovernedMixedSnapshotV1,
)

BASELINE_SOURCE_PACK_ID = "50000000-0000-0000-0000-000000000001"
BASELINE_SOURCE_PACK_VERSION = 1
BASELINE_MANIFEST_SHA256 = "84350ea5705d9681d3e6550e1bd06e3340a9fcf0e7e7bbed4478ed3403405f28"
BASELINE_RAW_MANIFEST_SHA256 = (
    "5d455d2c409c322e093f3a116387f3cef0fb7ea0f7357fec5e76e9da5b3a2a25"
)
EXTERNAL_CLAIM = "australia_program_fit"


def _load_exact_baseline(*, manifest_path: Path = DEFAULT_MANIFEST) -> PlanningInput:
    raw_manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if raw_manifest_sha256 != BASELINE_RAW_MANIFEST_SHA256:
        raise ValueError("governed mixed baseline raw manifest mismatch")
    baseline = validate_planning_fixture(manifest_path)
    if (
        str(baseline.planning_input.source_pack.pack_id) != BASELINE_SOURCE_PACK_ID
        or baseline.planning_input.source_pack.version != BASELINE_SOURCE_PACK_VERSION
        or baseline.manifest_sha256 != BASELINE_MANIFEST_SHA256
    ):
        raise ValueError("governed mixed baseline identity mismatch")
    return baseline.planning_input


def validate_governed_mixed_payload_baseline(
    planning_input: GovernedMixedPlanningInput,
) -> None:
    baseline = _load_exact_baseline()
    if (
        planning_input.case.student != baseline.case.student
        or planning_input.case.family != baseline.case.family
        or str(planning_input.source_pack.pack_id) != BASELINE_SOURCE_PACK_ID
        or planning_input.source_pack.version <= BASELINE_SOURCE_PACK_VERSION
    ):
        raise ValueError("governed mixed payload baseline drift")

    entries = {entry.entry_id: entry for entry in planning_input.source_pack.entries}
    evidence_by_claim = {item.claim: item for item in planning_input.evidence}
    if (
        len(entries) != len(planning_input.source_pack.entries)
        or len(evidence_by_claim) != len(planning_input.evidence)
        or set(evidence_by_claim) != {item.claim for item in baseline.evidence}
    ):
        raise ValueError("governed mixed payload baseline drift")

    for baseline_entry in baseline.source_pack.entries:
        expected = baseline_entry.model_copy(
            update={
                "coverage": tuple(
                    claim
                    for claim in baseline_entry.coverage
                    if claim != EXTERNAL_CLAIM
                )
            }
        )
        if entries.get(baseline_entry.entry_id) != expected:
            raise ValueError("governed mixed payload baseline drift")

    external = evidence_by_claim[EXTERNAL_CLAIM]
    external_entry = entries.get(external.source_entry_id)
    evidence_ids = {item.evidence_id for item in planning_input.evidence}
    if (
        set(entries) != {
            *(entry.entry_id for entry in baseline.source_pack.entries),
            external.source_entry_id,
        }
        or len(evidence_ids) != len(planning_input.evidence)
        or external.authority is not EvidenceAuthority.EXTERNALLY_VERIFIED
        or external_entry is None
        or external_entry.coverage != (EXTERNAL_CLAIM,)
        or external_entry.sha256 != external.source_sha256
        or external_entry.redistribution_class.value != "link_only"
    ):
        raise ValueError("governed mixed payload baseline drift")

    baseline_by_claim = {item.claim: item for item in baseline.evidence}
    for claim, evidence in evidence_by_claim.items():
        entry = entries.get(evidence.source_entry_id)
        if (
            evidence.organization_id != planning_input.organization_id
            or evidence.source_pack_id != planning_input.source_pack.pack_id
            or evidence.source_pack_version != planning_input.source_pack.version
            or entry is None
            or evidence.source_sha256 != entry.sha256
            or claim not in entry.coverage
        ):
            raise ValueError("governed mixed payload baseline drift")
        if claim == EXTERNAL_CLAIM:
            continue
        expected = baseline_by_claim[claim].model_dump(
            exclude={"organization_id", "evidence_id", "source_pack_version"}
        )
        actual = evidence.model_dump(
            exclude={"organization_id", "evidence_id", "source_pack_version"}
        )
        if actual != expected:
            raise ValueError("governed mixed payload baseline drift")

    evidence_id_by_claim = {
        claim: evidence.evidence_id for claim, evidence in evidence_by_claim.items()
    }
    expected_costs = tuple(
        item.model_copy(
            update={
                "organization_id": planning_input.organization_id,
                "tuition_evidence_id": evidence_id_by_claim[f"{item.country.value}_tuition"],
                "living_evidence_id": evidence_id_by_claim[
                    f"{item.country.value}_living_cost"
                ],
                "fx_evidence_id": evidence_id_by_claim[f"{item.country.value}_fx"],
            }
        )
        for item in baseline.costs
    )
    expected_rankings = tuple(
        item.model_copy(
            update={
                "organization_id": planning_input.organization_id,
                "evidence_id": evidence_id_by_claim[f"{item.country.value}_ranking"],
            }
        )
        for item in baseline.rankings
    )
    if planning_input.costs != expected_costs or planning_input.rankings != expected_rankings:
        raise ValueError("governed mixed payload baseline drift")


def materialize_governed_mixed_input(
    snapshot: GovernedMixedSnapshotV1,
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> GovernedMixedPlanningInput:
    baseline_input = _load_exact_baseline(manifest_path=manifest_path)
    if (
        str(snapshot.baseline_source_pack_id) != BASELINE_SOURCE_PACK_ID
        or snapshot.baseline_source_pack_version != BASELINE_SOURCE_PACK_VERSION
        or snapshot.baseline_manifest_sha256 != BASELINE_MANIFEST_SHA256
        or snapshot.baseline_raw_manifest_sha256 != BASELINE_RAW_MANIFEST_SHA256
        or snapshot.organization_id != snapshot.case.organization_id
        or snapshot.organization_id != snapshot.source_pack.organization_id
        or snapshot.source_pack.pack_id != snapshot.baseline_source_pack_id
        or snapshot.source_pack.version != snapshot.promoted_source_pack_version
        or snapshot.promoted_source_pack_version <= BASELINE_SOURCE_PACK_VERSION
    ):
        raise ValueError("governed mixed snapshot pins are invalid")

    baseline_by_claim = {item.claim: item for item in baseline_input.evidence}
    evidence_by_claim = {item.claim: item for item in snapshot.evidence}
    if (
        len(evidence_by_claim) != len(snapshot.evidence)
        or evidence_by_claim.keys() != baseline_by_claim.keys()
    ):
        raise ValueError("governed mixed Evidence baseline is invalid")

    external = evidence_by_claim[EXTERNAL_CLAIM]
    if (
        snapshot.verification_decision != "approve"
        or snapshot.verification_claim != EXTERNAL_CLAIM
        or snapshot.verification_evidence_role.value != "program_fit"
        or snapshot.promoted_source_entry_id != external.source_entry_id
        or snapshot.promoted_evidence_id != external.evidence_id
        or external.authority is not EvidenceAuthority.EXTERNALLY_VERIFIED
    ):
        raise ValueError("governed mixed verification linkage is invalid")

    entries = {entry.entry_id: entry for entry in snapshot.source_pack.entries}
    if len(entries) != len(snapshot.source_pack.entries):
        raise ValueError("governed mixed source entry identity is invalid")
    baseline_entry_ids = {entry.entry_id for entry in baseline_input.source_pack.entries}
    if set(entries) != baseline_entry_ids | {snapshot.promoted_source_entry_id}:
        raise ValueError("governed mixed source entry baseline is invalid")

    for baseline_entry in baseline_input.source_pack.entries:
        promoted_entry = entries.get(baseline_entry.entry_id)
        expected_coverage = tuple(
            claim
            for claim in baseline_entry.coverage
            if claim != EXTERNAL_CLAIM
        )
        expected = baseline_entry.model_copy(update={"coverage": expected_coverage})
        if promoted_entry != expected:
            raise ValueError("governed mixed synthetic source entry drifted")

    external_entry = entries[snapshot.promoted_source_entry_id]
    if (
        external_entry.coverage != (EXTERNAL_CLAIM,)
        or external_entry.sha256 != external.source_sha256
        or external_entry.redistribution_class.value != "link_only"
    ):
        raise ValueError("governed mixed external source entry is invalid")

    for claim, evidence in evidence_by_claim.items():
        entry = entries.get(evidence.source_entry_id)
        if (
            evidence.organization_id != snapshot.organization_id
            or evidence.source_pack_id != snapshot.source_pack.pack_id
            or evidence.source_pack_version != snapshot.source_pack.version
            or entry is None
            or evidence.source_sha256 != entry.sha256
            or claim not in entry.coverage
        ):
            raise ValueError("governed mixed Evidence provenance is invalid")
        if claim == EXTERNAL_CLAIM:
            continue
        baseline_evidence = baseline_by_claim[claim]
        if (
            evidence.authority is not EvidenceAuthority.ACCEPTED_SYNTHETIC_DEMO
            or evidence.source_entry_id != baseline_evidence.source_entry_id
            or evidence.source_sha256 != baseline_evidence.source_sha256
        ):
            raise ValueError("governed mixed synthetic Evidence baseline drifted")

    evidence_id_by_claim = {
        claim: evidence.evidence_id for claim, evidence in evidence_by_claim.items()
    }
    costs = tuple(
        item.model_copy(
            update={
                "organization_id": snapshot.organization_id,
                "tuition_evidence_id": evidence_id_by_claim[
                    f"{item.country.value}_tuition"
                ],
                "living_evidence_id": evidence_id_by_claim[
                    f"{item.country.value}_living_cost"
                ],
                "fx_evidence_id": evidence_id_by_claim[f"{item.country.value}_fx"],
            }
        )
        for item in baseline_input.costs
    )
    rankings = tuple(
        item.model_copy(
            update={
                "organization_id": snapshot.organization_id,
                "evidence_id": evidence_id_by_claim[f"{item.country.value}_ranking"],
            }
        )
        for item in baseline_input.rankings
    )
    return GovernedMixedPlanningInput(
        schema_version=1,
        operation="generate_governed_mixed_planning_run_v1",
        organization_id=snapshot.organization_id,
        case=snapshot.case,
        source_pack=snapshot.source_pack,
        evidence=snapshot.evidence,
        costs=costs,
        rankings=rankings,
    )
