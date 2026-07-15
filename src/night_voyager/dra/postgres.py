from __future__ import annotations

import hashlib
import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from night_voyager.decision.hashing import canonical_request_sha256
from night_voyager.dra.errors import (
    DraAuthorizationError,
    DraConflictError,
)
from night_voyager.dra.ports import (
    DraCandidateViewV1,
    DraVerificationViewV1,
    ImportDraCandidateCommand,
    PromotionIdentities,
    VerifyDraCandidateCommand,
)
from night_voyager.identity.models import ActorContext

BASELINE_SOURCE_PACK_ID = UUID("50000000-0000-0000-0000-000000000001")
BASELINE_MANIFEST_SHA256 = "84350ea5705d9681d3e6550e1bd06e3340a9fcf0e7e7bbed4478ed3403405f28"
BASELINE_RAW_MANIFEST_SHA256 = "5d455d2c409c322e093f3a116387f3cef0fb7ea0f7357fec5e76e9da5b3a2a25"


class PostgresDraCandidateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def import_candidate(
        self,
        context: ActorContext,
        command: ImportDraCandidateCommand,
        candidate_id: UUID,
        idempotency_key: str,
    ) -> DraCandidateViewV1:
        try:
            result = await self._session.execute(
                text(
                    "SELECT * FROM app.import_dra_research_candidate("
                    ":org,:actor,:case,:candidate,:revision,:release,:commit,:schema,:fixture,"
                    ":profile,:identity_hash,:run_id,:artifact_id,:artifact_kind,:media_type,"
                    ":artifact_bytes,:artifact_sha,CAST(:evidence AS jsonb),"
                    ":request_hash,:key_hash)"
                ),
                {
                    "org": context.organization_id,
                    "actor": context.actor_id,
                    "case": command.case_id,
                    "candidate": candidate_id,
                    "revision": command.expected_case_revision,
                    "release": command.producer.release,
                    "commit": command.producer.commit,
                    "schema": command.producer.contract_schema,
                    "fixture": command.producer.fixture_sha256,
                    "profile": command.request_identity.profile_id,
                    "identity_hash": command.request_identity.request_sha256,
                    "run_id": command.run_id,
                    "artifact_id": command.artifact_id,
                    "artifact_kind": command.artifact_kind,
                    "media_type": command.artifact_media_type,
                    "artifact_bytes": command.artifact_byte_length,
                    "artifact_sha": command.artifact_sha256,
                    "evidence": json.dumps(
                        [
                            item.model_dump(mode="json", exclude_computed_fields=True)
                            for item in command.evidence
                        ]
                    ),
                    "request_hash": command.import_request_sha256,
                    "key_hash": self._key_hash(idempotency_key),
                },
            )
        except DBAPIError as error:
            self._raise_mapped(error)
            raise
        row = result.mappings().one()
        return DraCandidateViewV1(
            candidate_id=row["candidate_id"], verification=None, replayed=row["replayed"]
        )

    async def get_candidate(
        self, context: ActorContext, case_id: UUID, candidate_id: UUID
    ) -> DraCandidateViewV1 | None:
        result = await self._session.execute(
            text(
                "SELECT c.id AS candidate_id,v.id AS verification_id,v.decision,"
                "v.promoted_source_pack_version,v.promoted_source_entry_id,"
                "v.promoted_evidence_id FROM app.dra_research_candidates c "
                "JOIN app.student_case_participants p ON p.organization_id=c.organization_id "
                "AND p.case_id=c.case_id AND p.actor_id=:actor AND p.role='advisor' "
                "LEFT JOIN app.external_evidence_verifications v "
                "ON v.organization_id=c.organization_id AND v.candidate_id=c.id "
                "WHERE c.organization_id=:org AND c.case_id=:case AND c.id=:candidate"
            ),
            {
                "org": context.organization_id,
                "actor": context.actor_id,
                "case": case_id,
                "candidate": candidate_id,
            },
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        verification = None
        if row["verification_id"] is not None:
            verification = DraVerificationViewV1(
                verification_id=row["verification_id"],
                decision=row["decision"],
                promoted_source_pack_version=row["promoted_source_pack_version"],
                promoted_source_entry_id=row["promoted_source_entry_id"],
                promoted_evidence_id=row["promoted_evidence_id"],
            )
        return DraCandidateViewV1(candidate_id=row["candidate_id"], verification=verification)

    async def verify_and_promote(
        self,
        context: ActorContext,
        command: VerifyDraCandidateCommand,
        identities: PromotionIdentities,
        idempotency_key: str,
    ) -> DraVerificationViewV1:
        attestation = command.source_attestation
        copied = (
            [item.model_dump(mode="json") for item in identities.copied_baseline_evidence]
            if attestation is not None
            else None
        )
        request_hash = canonical_request_sha256(command.model_dump(mode="json"))
        try:
            result = await self._session.execute(
                text(
                    "SELECT * FROM app.verify_and_promote_dra_candidate("
                    ":org,:actor,:case,:candidate,:revision,:dra_evidence_id,:decision,:reason,"
                    ":source_url,:publisher,:institution,:snapshot_date,:freshness_days,"
                    ":redistribution_class,:evidence_class,:declared_path,:source_byte_length,"
                    ":source_sha256,CAST(:known_gaps AS jsonb),:pack,1,:manifest_sha,"
                    ":raw_manifest_sha,:verification,:external_entry,:external_evidence,"
                    "CAST(:copied_ids AS jsonb),:request_hash,:key_hash)"
                ),
                {
                    "org": context.organization_id,
                    "actor": context.actor_id,
                    "case": command.case_id,
                    "candidate": command.candidate_id,
                    "revision": command.expected_case_revision,
                    "dra_evidence_id": command.dra_evidence_id,
                    "decision": command.decision,
                    "reason": command.reason,
                    "source_url": str(attestation.canonical_url) if attestation else None,
                    "publisher": attestation.publisher if attestation else None,
                    "institution": attestation.institution if attestation else None,
                    "snapshot_date": attestation.snapshot_date if attestation else None,
                    "freshness_days": attestation.freshness_days if attestation else None,
                    "redistribution_class": attestation.redistribution_class
                    if attestation
                    else None,
                    "evidence_class": attestation.evidence_class if attestation else None,
                    "declared_path": attestation.logical_path if attestation else None,
                    "source_byte_length": attestation.snapshot_byte_length if attestation else None,
                    "source_sha256": attestation.snapshot_sha256 if attestation else None,
                    "known_gaps": json.dumps(attestation.known_gaps) if attestation else None,
                    "pack": BASELINE_SOURCE_PACK_ID,
                    "manifest_sha": BASELINE_MANIFEST_SHA256,
                    "raw_manifest_sha": BASELINE_RAW_MANIFEST_SHA256,
                    "verification": identities.verification_id,
                    "external_entry": identities.external_source_entry_id if attestation else None,
                    "external_evidence": identities.promoted_external_evidence_id
                    if attestation
                    else None,
                    "copied_ids": json.dumps(copied) if copied is not None else None,
                    "request_hash": request_hash,
                    "key_hash": self._key_hash(idempotency_key),
                },
            )
        except DBAPIError as error:
            self._raise_mapped(error)
            raise
        row = result.mappings().one()
        return DraVerificationViewV1(
            verification_id=row["verification_id"],
            decision=row["terminal_decision"],
            promoted_source_pack_version=row["promoted_source_pack_version"],
            promoted_source_entry_id=row["promoted_source_entry_id"],
            promoted_evidence_id=row["promoted_evidence_id"],
            replayed=row["replayed"],
        )

    @staticmethod
    def _key_hash(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    @staticmethod
    def _raise_mapped(error: DBAPIError) -> None:
        sqlstate = getattr(error.orig, "sqlstate", None)
        if sqlstate == "NV007":
            raise DraAuthorizationError("resource_unavailable") from error
        if sqlstate in {"NV003", "NV006", "NV008", "NV011", "NV012", "23505", "40001"}:
            raise DraConflictError(sqlstate or "dra_conflict") from error
