from __future__ import annotations

from uuid import UUID

from night_voyager.planning.hashing import canonical_sha256
from night_voyager.planning.models import (
    CaseState,
    EvidenceRef,
    PlanningInput,
    SourcePackManifestV1,
    StudentCaseRevision,
)
from night_voyager.planning.policy import evaluate_planning_run
from night_voyager.planning.ports import (
    CaseRepository,
    PlanningRepository,
    SourceEvidenceRepository,
)

POLICY_VERSION = "m3a-policy-v1"


class CaseService:
    def __init__(self, repository: CaseRepository) -> None:
        self._repository = repository

    async def publish_revision(
        self, revision: StudentCaseRevision, *, expected_current: int | None
    ) -> None:
        await self._repository.create_revision(revision, expected_current)

    async def start_planning(self, organization_id: UUID, case_id: UUID) -> None:
        await self._repository.transition_case(
            organization_id, case_id, CaseState.INTAKE, CaseState.PLANNING
        )


class PlanningService:
    def __init__(self, repository: PlanningRepository) -> None:
        self._repository = repository

    async def evaluate_and_persist(
        self, planning_input: PlanningInput, *, supersedes_run_id: UUID | None
    ) -> UUID:
        result = evaluate_planning_run(planning_input)
        evidence_hash = canonical_sha256(
            [item.model_dump(mode="json") for item in planning_input.evidence]
        )
        output_hash = canonical_sha256(result.model_dump(mode="json"))
        return await self._repository.publish_result(
            planning_input,
            result,
            POLICY_VERSION,
            evidence_hash,
            output_hash,
            supersedes_run_id,
        )


class SourceEvidenceService:
    def __init__(self, repository: SourceEvidenceRepository) -> None:
        self._repository = repository

    async def persist(
        self, manifest: SourcePackManifestV1, evidence: tuple[EvidenceRef, ...]
    ) -> None:
        manifest_hash = canonical_sha256(manifest.model_dump(mode="json"))
        await self._repository.persist_source_pack(manifest, manifest_hash)
        for item in evidence:
            await self._repository.persist_evidence_ref(item)
