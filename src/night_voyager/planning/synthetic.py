from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, PositiveInt, model_validator

from night_voyager.planning.fixtures import DEFAULT_MANIFEST, validate_planning_fixture
from night_voyager.planning.models import (
    CostEvidence,
    FrozenModel,
    PlanningInput,
    RankingEvidence,
    StudentCaseRevision,
    preferred_country_scope_is_valid,
)

BASELINE_SOURCE_PACK_ID = UUID("50000000-0000-0000-0000-000000000001")
BASELINE_SOURCE_PACK_VERSION = 1
BASELINE_POLICY_VERSION = "m3a-policy-v1"
BASELINE_MANIFEST_SHA256 = "84350ea5705d9681d3e6550e1bd06e3340a9fcf0e7e7bbed4478ed3403405f28"
BASELINE_RAW_MANIFEST_SHA256 = (
    "5d455d2c409c322e093f3a116387f3cef0fb7ea0f7357fec5e76e9da5b3a2a25"
)


class PersistedSyntheticSnapshotV1(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    schema_version: Literal[1]
    organization_id: UUID
    case: StudentCaseRevision
    source_pack_id: UUID
    source_pack_version: PositiveInt
    policy_version: Literal["m3a-policy-v1"]

    @model_validator(mode="after")
    def exact_case_organization(self) -> PersistedSyntheticSnapshotV1:
        if self.organization_id != self.case.organization_id:
            raise ValueError("snapshot organization must match the persisted Case")
        return self


def load_exact_synthetic_baseline(
    *, manifest_path: Path = DEFAULT_MANIFEST
) -> PlanningInput:
    raw_manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if raw_manifest_sha256 != BASELINE_RAW_MANIFEST_SHA256:
        raise ValueError("synthetic baseline raw manifest mismatch")
    fixture = validate_planning_fixture(manifest_path)
    planning_input = fixture.planning_input
    if (
        planning_input.source_pack.pack_id != BASELINE_SOURCE_PACK_ID
        or planning_input.source_pack.version != BASELINE_SOURCE_PACK_VERSION
        or fixture.manifest_sha256 != BASELINE_MANIFEST_SHA256
    ):
        raise ValueError("synthetic baseline identity mismatch")
    return planning_input


def project_selected_country_rows(
    case: StudentCaseRevision,
    costs: tuple[CostEvidence, ...],
    rankings: tuple[RankingEvidence, ...],
) -> tuple[tuple[CostEvidence, ...], tuple[RankingEvidence, ...]]:
    countries = case.student.preferred_countries
    if not preferred_country_scope_is_valid(countries):
        raise ValueError("persisted preferred_countries scope is invalid")
    selected = frozenset(countries)
    return (
        tuple(item for item in costs if item.country in selected),
        tuple(item for item in rankings if item.country in selected),
    )


def materialize_persisted_synthetic_input(
    snapshot: PersistedSyntheticSnapshotV1,
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> PlanningInput:
    baseline = load_exact_synthetic_baseline(manifest_path=manifest_path)
    if (
        snapshot.source_pack_id != baseline.source_pack.pack_id
        or snapshot.source_pack_version != baseline.source_pack.version
        or snapshot.policy_version != BASELINE_POLICY_VERSION
    ):
        raise ValueError("persisted synthetic snapshot pins are invalid")

    costs = tuple(
        item.model_copy(update={"organization_id": snapshot.organization_id})
        for item in baseline.costs
    )
    rankings = tuple(
        item.model_copy(update={"organization_id": snapshot.organization_id})
        for item in baseline.rankings
    )
    costs, rankings = project_selected_country_rows(snapshot.case, costs, rankings)
    return PlanningInput(
        schema_version=1,
        organization_id=snapshot.organization_id,
        case=snapshot.case,
        source_pack=baseline.source_pack.model_copy(
            update={"organization_id": snapshot.organization_id}
        ),
        evidence=tuple(
            item.model_copy(update={"organization_id": snapshot.organization_id})
            for item in baseline.evidence
        ),
        costs=costs,
        rankings=rankings,
        narrative=baseline.narrative,
    )
