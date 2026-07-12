from __future__ import annotations

import json
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from night_voyager.planning.errors import StaleRevisionError
from night_voyager.planning.models import (
    CaseState,
    EvidenceRef,
    PlanningInput,
    PlanningResult,
    SourcePackManifestV1,
    StudentCaseRevision,
)


class PostgresPlanningRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_revision(
        self, revision: StudentCaseRevision, expected_current: int | None
    ) -> None:
        try:
            await self._session.execute(
                text(
                    "SELECT app.publish_case_revision("
                    ":org,:case,:expected,:revision,"
                    "CAST(:student AS jsonb),CAST(:family AS jsonb))"
                ),
                {
                    "org": revision.organization_id,
                    "case": revision.case_id,
                    "expected": expected_current,
                    "revision": revision.revision,
                    "student": json.dumps(revision.student.model_dump(mode="json")),
                    "family": json.dumps(revision.family.model_dump(mode="json")),
                },
            )
        except DBAPIError as error:
            if getattr(error.orig, "sqlstate", None) == "NV003":
                raise StaleRevisionError(expected_current, None) from error
            raise

    async def transition_case(
        self,
        organization_id: UUID,
        case_id: UUID,
        expected: CaseState,
        target: CaseState,
    ) -> None:
        await self._session.execute(
            text("SELECT app.transition_case(:org, :case, :expected, :target)"),
            {"org": organization_id, "case": case_id, "expected": expected, "target": target},
        )

    async def publish_result(
        self,
        planning_input: PlanningInput,
        result: PlanningResult,
        policy_version: str,
        evidence_projection_sha256: str,
        output_sha256: str,
        supersedes_run_id: UUID | None,
    ) -> UUID:
        run_id = uuid4()
        try:
            await self._session.execute(
                text(
                    "SELECT app.persist_planning_result("
                    ":org,:run,:case,:revision,:pack,:version,:policy,:evidence_hash,"
                    ":state,:reason,:output_hash,:supersedes,CAST(:output AS jsonb))"
                ),
                {
                    "org": planning_input.organization_id,
                    "run": run_id,
                    "case": planning_input.case.case_id,
                    "revision": planning_input.case.revision,
                    "pack": planning_input.source_pack.pack_id,
                    "version": planning_input.source_pack.version,
                    "policy": policy_version,
                    "evidence_hash": evidence_projection_sha256,
                    "state": result.state,
                    "reason": result.reason_code,
                    "output_hash": output_sha256,
                    "supersedes": supersedes_run_id,
                    "output": json.dumps(
                        {
                            "routes": [item.model_dump(mode="json") for item in result.routes],
                            "costs": [
                                item.model_dump(mode="json") for item in planning_input.costs
                            ],
                            "rankings": [
                                item.model_dump(mode="json") for item in planning_input.rankings
                            ],
                        }
                    ),
                },
            )
        except DBAPIError as error:
            if getattr(error.orig, "sqlstate", None) == "NV003":
                raise StaleRevisionError(planning_input.case.revision, None) from error
            raise
        return run_id

    async def persist_source_pack(
        self, manifest: SourcePackManifestV1, manifest_sha256: str
    ) -> None:
        await self._session.execute(
            text(
                "SELECT app.persist_source_pack(:org,:pack,:version,:hash,CAST(:entries AS jsonb))"
            ),
            {
                "org": manifest.organization_id,
                "pack": manifest.pack_id,
                "version": manifest.version,
                "hash": manifest_sha256,
                "entries": json.dumps([item.model_dump(mode="json") for item in manifest.entries]),
            },
        )

    async def persist_evidence_ref(self, evidence: EvidenceRef) -> None:
        await self._session.execute(
            text(
                "SELECT app.persist_evidence_ref("
                ":org,:id,:pack,:version,:entry,:claim,:authority,:hash)"
            ),
            {
                "org": evidence.organization_id,
                "id": evidence.evidence_id,
                "pack": evidence.source_pack_id,
                "version": evidence.source_pack_version,
                "entry": evidence.source_entry_id,
                "claim": evidence.claim,
                "authority": evidence.authority,
                "hash": evidence.source_sha256,
            },
        )
