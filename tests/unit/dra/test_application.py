from __future__ import annotations

from datetime import date
from uuid import UUID, uuid5

import pytest
from pydantic import ValidationError

from night_voyager.decision.hashing import canonical_request_sha256
from night_voyager.dra.application import DraCandidateService
from night_voyager.dra.errors import DraAuthorizationError
from night_voyager.dra.fixtures import build_fixture_candidate_import
from night_voyager.dra.models import SourceAttestationV1
from night_voyager.dra.ports import (
    DraCandidateViewV1,
    DraVerificationViewV1,
    ImportDraCandidateCommand,
    PromotionIdentities,
    VerifyDraCandidateCommand,
)
from night_voyager.identity.models import ActorContext, ActorRole

ORG = UUID("10000000-0000-0000-0000-000000000001")
CASE = UUID("40000000-0000-0000-0000-000000000003")
ACTOR = UUID("20000000-0000-0000-0000-000000000001")
SESSION = UUID("30000000-0000-0000-0000-000000000001")
CANDIDATE = UUID("90000000-0000-0000-0000-000000000001")
DECISION = UUID("91000000-0000-0000-0000-000000000001")


def context(role: ActorRole = ActorRole.ADVISOR) -> ActorContext:
    return ActorContext(organization_id=ORG, actor_id=ACTOR, role=role, session_id=SESSION)


def attestation() -> SourceAttestationV1:
    return SourceAttestationV1.model_validate(
        {
            "canonical_url": "https://example.com/contract-source-1",
            "publisher": "Synthetic Public Source Publisher",
            "institution": "Synthetic Australia Institution",
            "snapshot_date": date(2026, 7, 11),
            "freshness_days": 365,
            "redistribution_class": "link_only",
            "evidence_class": "institutional",
            "logical_path": "sources/australia-program-fit.html",
            "snapshot_byte_length": 375,
            "snapshot_sha256": (
                "87e314e801dca1aeaf9b751c149c53629a4cf23ee04698939fdc87def5a90a13"
            ),
            "known_gaps": ("applicant_eligibility", "intake_availability"),
        }
    )


def verify_command(**changes: object) -> VerifyDraCandidateCommand:
    payload: dict[str, object] = {
        "case_id": CASE,
        "candidate_id": CANDIDATE,
        "expected_case_revision": 1,
        "dra_evidence_id": (
            "ev_run_00000000000000000000000000000003_"
            "0000000000000000000000000000000000000000000000000000000000000001"
        ),
        "decision": "approve",
        "reason": "Exact source inspected for the bounded program-fit claim.",
        "source_attestation": attestation(),
    }
    payload.update(changes)
    return VerifyDraCandidateCommand.model_validate(payload)


class RecordingDraRepository:
    def __init__(self) -> None:
        self.imported: ImportDraCandidateCommand | None = None
        self.identities: PromotionIdentities | None = None

    async def import_candidate(
        self,
        context: ActorContext,
        command: ImportDraCandidateCommand,
        candidate_id: UUID,
        idempotency_key: str,
    ) -> DraCandidateViewV1:
        self.imported = command
        return DraCandidateViewV1(candidate_id=candidate_id, verification=None)

    async def get_candidate(
        self, context: ActorContext, case_id: UUID, candidate_id: UUID
    ) -> DraCandidateViewV1 | None:
        return DraCandidateViewV1(candidate_id=candidate_id, verification=None)

    async def verify_and_promote(
        self,
        context: ActorContext,
        command: VerifyDraCandidateCommand,
        identities: PromotionIdentities,
        idempotency_key: str,
    ) -> DraVerificationViewV1:
        self.identities = identities
        return DraVerificationViewV1(
            verification_id=identities.verification_id,
            decision=command.decision,
            promoted_source_pack_version=2 if command.decision == "approve" else None,
            promoted_source_entry_id=(
                identities.external_source_entry_id if command.decision == "approve" else None
            ),
            promoted_evidence_id=(
                identities.promoted_external_evidence_id
                if command.decision == "approve"
                else None
            ),
        )


@pytest.mark.asyncio
async def test_import_discards_markdown_before_persistence_and_hashes_exact_request() -> None:
    repository = RecordingDraRepository()
    service = DraCandidateService(repository, id_factory=lambda: CANDIDATE)
    candidate_import = build_fixture_candidate_import()
    result = await service.import_candidate(
        context(), candidate_import, "import-key-1234567890"
    )
    assert result.candidate_id == CANDIDATE
    assert repository.imported is not None
    assert repository.imported.artifact_content is None
    assert repository.imported.artifact_sha256 == candidate_import.artifact.content_hash
    assert repository.imported.import_request_sha256 == canonical_request_sha256(
        candidate_import.model_dump(mode="json", exclude_computed_fields=True)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("role", (ActorRole.STUDENT, ActorRole.PARENT))
async def test_candidate_operations_are_advisor_only(role: ActorRole) -> None:
    service = DraCandidateService(RecordingDraRepository(), id_factory=lambda: CANDIDATE)
    with pytest.raises(DraAuthorizationError):
        await service.import_candidate(
            context(role), build_fixture_candidate_import(), "import-key-1234567890"
        )
    with pytest.raises(DraAuthorizationError):
        await service.get_candidate(context(role), CASE, CANDIDATE)
    with pytest.raises(DraAuthorizationError):
        await service.verify_candidate(
            context(role), verify_command(), "verify-key-1234567890"
        )


def test_reject_forbids_source_attestation_and_approve_requires_it() -> None:
    with pytest.raises(ValidationError, match="dra_verification_decision_shape_invalid"):
        verify_command(decision="reject")
    with pytest.raises(ValidationError, match="dra_verification_decision_shape_invalid"):
        verify_command(source_attestation=None)


def test_caller_cannot_supply_claim_role_authority_or_promoted_ids() -> None:
    for field, value in (
        ("claim", "australia_program_fit"),
        ("evidence_role", "program_fit"),
        ("authority", "externally_verified"),
        ("promoted_evidence_id", str(UUID(int=999))),
    ):
        with pytest.raises(ValidationError):
            verify_command(**{field: value})


@pytest.mark.asyncio
async def test_promotion_identities_are_server_generated_and_deterministic() -> None:
    generated = iter((DECISION,))
    repository = RecordingDraRepository()
    service = DraCandidateService(repository, id_factory=lambda: next(generated))
    result = await service.verify_candidate(
        context(), verify_command(), "verify-key-1234567890"
    )
    assert repository.identities is not None
    assert result.verification_id == repository.identities.verification_id
    assert repository.identities.external_source_entry_id != DECISION
    assert repository.identities.promoted_external_evidence_id != DECISION
    identity_key = f"{CANDIDATE}:{verify_command().dra_evidence_id}"
    assert repository.identities.external_source_entry_id == uuid5(
        DECISION, f"{identity_key}:external-source-entry"
    )
    assert repository.identities.claim == "australia_program_fit"
    assert repository.identities.evidence_role == "program_fit"
    assert repository.identities.authority == "externally_verified"
    assert {item.claim for item in repository.identities.copied_baseline_evidence} == {
        "australia_tuition",
        "australia_living_cost",
        "australia_fx",
        "japan_program_fit",
        "australia_ranking",
    }


def test_attestation_requires_both_closed_known_gaps() -> None:
    with pytest.raises(ValidationError, match="dra_source_known_gaps_missing"):
        SourceAttestationV1.model_validate(
            {
                **attestation().model_dump(mode="json"),
                "known_gaps": ["applicant_eligibility"],
            }
        )
