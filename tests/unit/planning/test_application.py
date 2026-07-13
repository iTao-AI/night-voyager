from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast
from uuid import UUID

import pytest

from night_voyager.planning.application import (
    CaseService,
    PlanningService,
    SourceEvidenceService,
)
from night_voyager.planning.errors import StaleRevisionError
from night_voyager.planning.models import (
    CaseState,
    PlanningInput,
    PlanningResult,
    StudentCaseRevision,
)
from night_voyager.planning.ports import (
    CaseRepository,
    PlanningRepository,
    SourceEvidenceRepository,
)
from tests.unit.planning.test_policy import ORG, valid_input


@dataclass
class FakeRepository:
    current_revision: int | None = None
    case_state: CaseState = CaseState.INTAKE
    published: list[int] = field(default_factory=lambda: list[int]())
    planning_hashes: tuple[str, str, str] | None = None
    stored_pack: UUID | None = None
    stored_evidence: list[UUID] = field(default_factory=lambda: list[UUID]())
    published_result_state: str | None = None

    async def create_revision(
        self, revision: StudentCaseRevision, expected_current: int | None
    ) -> None:
        new_revision: int = int(revision.revision)
        if self.current_revision != expected_current:
            raise StaleRevisionError(expected_current, self.current_revision)
        self.current_revision = new_revision
        self.published.append(new_revision)

    async def transition_case(
        self, organization_id: UUID, case_id: UUID, expected: CaseState, target: CaseState
    ) -> None:
        assert organization_id == ORG
        if self.case_state is not expected:
            raise ValueError("unexpected state")
        self.case_state = target

    async def publish_result(
        self,
        planning_input: PlanningInput,
        result: PlanningResult,
        policy_version: str,
        evidence_projection_sha256: str,
        output_sha256: str,
        supersedes_run_id: UUID | None,
    ) -> UUID:
        self.planning_hashes = (
            policy_version,
            evidence_projection_sha256,
            output_sha256,
        )
        self.published_result_state = result.state.value
        if self.case_state is not CaseState.PLANNING:
            raise StaleRevisionError(1, self.current_revision)
        if self.published_result_state == "review_required":
            self.case_state = CaseState.ADVISOR_REVIEW
        return UUID("70000000-0000-0000-0000-000000000001")

    async def persist_source_pack(self, manifest: object, manifest_sha256: str) -> None:
        self.stored_pack = manifest.pack_id  # type: ignore[attr-defined]
        assert len(manifest_sha256) == 64

    async def persist_evidence_ref(self, evidence: object) -> None:
        self.stored_evidence.append(evidence.evidence_id)  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_case_revision_publication_uses_expected_version_cas() -> None:
    repository = FakeRepository()
    service = CaseService(cast(CaseRepository, repository))
    await service.publish_revision(valid_input().case, expected_current=None)
    assert repository.current_revision == 1
    with pytest.raises(StaleRevisionError):
        await service.publish_revision(
            valid_input().case.model_copy(update={"revision": 2}), expected_current=None
        )


@pytest.mark.asyncio
async def test_case_lifecycle_is_application_owned() -> None:
    repository = FakeRepository()
    service = CaseService(cast(CaseRepository, repository))
    await service.start_planning(ORG, valid_input().case.case_id)
    assert repository.case_state is CaseState.PLANNING


@pytest.mark.asyncio
async def test_planning_service_persists_pinned_versions_and_canonical_hashes() -> None:
    repository = FakeRepository(current_revision=1, case_state=CaseState.PLANNING)
    run_id = await PlanningService(cast(PlanningRepository, repository)).evaluate_and_persist(
        valid_input(), supersedes_run_id=None
    )
    assert run_id == UUID("70000000-0000-0000-0000-000000000001")
    assert repository.planning_hashes is not None
    assert repository.planning_hashes[0] == "m3a-policy-v1"
    assert all(len(value) == 64 for value in repository.planning_hashes[1:])
    assert repository.published_result_state == "review_required"
    assert repository.case_state is CaseState.ADVISOR_REVIEW


@pytest.mark.asyncio
async def test_source_evidence_service_persists_manifest_before_bound_evidence() -> None:
    repository = FakeRepository()
    service = SourceEvidenceService(cast(SourceEvidenceRepository, repository))
    payload = valid_input()
    await service.persist(payload.source_pack, payload.evidence)
    assert repository.stored_pack == payload.source_pack.pack_id
    assert repository.stored_evidence == [item.evidence_id for item in payload.evidence]
