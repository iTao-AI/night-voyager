from __future__ import annotations

from collections.abc import Callable
from uuid import UUID, uuid4, uuid5

from night_voyager.decision.hashing import canonical_request_sha256
from night_voyager.dra.errors import DraAuthorizationError
from night_voyager.dra.models import DraCandidateImportV1
from night_voyager.dra.ports import (
    CopiedEvidenceIdentity,
    DraCandidateRepository,
    DraCandidateViewV1,
    DraVerificationViewV1,
    ImportDraCandidateCommand,
    PromotionIdentities,
    VerifyDraCandidateCommand,
)
from night_voyager.identity.models import ActorContext, ActorRole

COPIED_SYNTHETIC_CLAIMS = (
    "australia_tuition",
    "australia_living_cost",
    "australia_fx",
    "japan_program_fit",
    "australia_ranking",
)


class DraCandidateService:
    def __init__(
        self,
        repository: DraCandidateRepository,
        *,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._id_factory = id_factory

    async def import_candidate(
        self,
        context: ActorContext,
        candidate_import: DraCandidateImportV1,
        idempotency_key: str,
    ) -> DraCandidateViewV1:
        self._require_advisor(context)
        if candidate_import.organization_id != context.organization_id:
            raise DraAuthorizationError("dra_candidate_organization_mismatch")
        artifact = candidate_import.artifact
        command = ImportDraCandidateCommand(
            organization_id=candidate_import.organization_id,
            case_id=candidate_import.case_id,
            expected_case_revision=candidate_import.expected_case_revision,
            producer=candidate_import.producer,
            request_identity=candidate_import.request_identity,
            run_id=candidate_import.run.run_id,
            artifact_id=artifact.artifact_id,
            artifact_kind=artifact.kind,
            artifact_media_type=artifact.media_type,
            artifact_byte_length=artifact.byte_length,
            artifact_sha256=artifact.content_hash,
            evidence=candidate_import.evidence,
            import_request_sha256=canonical_request_sha256(
                candidate_import.model_dump(mode="json", exclude_computed_fields=True)
            ),
        )
        return await self._repository.import_candidate(
            context, command, self._id_factory(), idempotency_key
        )

    async def get_candidate(
        self,
        context: ActorContext,
        case_id: UUID,
        candidate_id: UUID,
    ) -> DraCandidateViewV1 | None:
        self._require_advisor(context)
        return await self._repository.get_candidate(context, case_id, candidate_id)

    async def verify_candidate(
        self,
        context: ActorContext,
        command: VerifyDraCandidateCommand,
        idempotency_key: str,
    ) -> DraVerificationViewV1:
        self._require_advisor(context)
        verification_id = self._id_factory()
        identity_key = f"{command.candidate_id}:{command.dra_evidence_id}"
        identities = PromotionIdentities(
            verification_id=verification_id,
            external_source_entry_id=uuid5(
                verification_id, f"{identity_key}:external-source-entry"
            ),
            promoted_external_evidence_id=uuid5(
                verification_id,
                f"{identity_key}:australia_program_fit:externally_verified",
            ),
            copied_baseline_evidence=tuple(
                CopiedEvidenceIdentity(
                    claim=claim,
                    evidence_id=uuid5(
                        verification_id, f"{identity_key}:{claim}:synthetic"
                    ),
                )
                for claim in COPIED_SYNTHETIC_CLAIMS
            ),
        )
        return await self._repository.verify_and_promote(
            context, command, identities, idempotency_key
        )

    @staticmethod
    def _require_advisor(context: ActorContext) -> None:
        if context.role is not ActorRole.ADVISOR:
            raise DraAuthorizationError("dra_candidate_operation_requires_advisor")
