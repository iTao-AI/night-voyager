from __future__ import annotations

from typing import Protocol
from uuid import UUID

from night_voyager.planning.models import (
    CaseState,
    EvidenceRef,
    PlanningInput,
    PlanningResult,
    SourcePackManifestV1,
    StudentCaseRevision,
)


class CaseRepository(Protocol):
    async def create_revision(
        self, revision: StudentCaseRevision, expected_current: int | None
    ) -> None: ...

    async def transition_case(
        self,
        organization_id: UUID,
        case_id: UUID,
        expected: CaseState,
        target: CaseState,
    ) -> None: ...


class PlanningRepository(Protocol):
    async def persist_result(
        self,
        planning_input: PlanningInput,
        result: PlanningResult,
        policy_version: str,
        evidence_projection_sha256: str,
        output_sha256: str,
        supersedes_run_id: UUID | None,
    ) -> UUID: ...


class SourceEvidenceRepository(Protocol):
    async def persist_source_pack(
        self, manifest: SourcePackManifestV1, manifest_sha256: str
    ) -> None: ...

    async def persist_evidence_ref(self, evidence: EvidenceRef) -> None: ...
