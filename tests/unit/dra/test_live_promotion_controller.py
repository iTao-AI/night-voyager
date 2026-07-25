from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

import pytest

from night_voyager.dra.live_controller import (
    DraLiveClosureController,
    PromoteCommand,
)
from night_voyager.dra.live_models import (
    DraArtifactIdentityV1,
    DraCaptureReceiptV1,
    DraLiveProducerIdentityV1,
    DraPromotionInputV1,
    DraSelectedEvidenceV1,
    DraStageStateV1,
    derive_identity_hash,
)
from night_voyager.dra.live_storage import LiveReceiptStore, LiveStorageInvalid
from night_voyager.dra.models import SourceAttestationV1
from night_voyager.dra.ports import (
    DraCandidateViewV1,
    DraVerificationViewV1,
    VerifyDraCandidateCommand,
)
from night_voyager.identity.models import ActorContext, ActorRole

ORG_ID = UUID("00000000-0000-4000-8000-000000000001")
ACTOR_ID = UUID("00000000-0000-4000-8000-000000000002")
SESSION_ID = UUID("00000000-0000-4000-8000-000000000003")
CASE_ID = UUID("00000000-0000-4000-8000-000000000004")
CANDIDATE_ID = UUID("00000000-0000-4000-8000-000000000005")
VERIFICATION_ID = UUID("00000000-0000-4000-8000-000000000006")
SOURCE_ENTRY_ID = UUID("00000000-0000-4000-8000-000000000007")
PROMOTED_EVIDENCE_ID = UUID("00000000-0000-4000-8000-000000000008")
URL = "https://example.edu/program?year=2026#requirements"
CONTENT = b"public source snapshot\n"


class FakePromotionGateway:
    def __init__(self, *, lose_ack: bool = False) -> None:
        self.current = DraCandidateViewV1(candidate_id=CANDIDATE_ID, verification=None)
        self.calls = 0
        self.lose_ack = lose_ack

    async def get_candidate(
        self,
        context: ActorContext,
        case_id: UUID,
        candidate_id: UUID,
    ) -> DraCandidateViewV1 | None:
        assert context.organization_id == ORG_ID
        assert case_id == CASE_ID
        assert candidate_id == CANDIDATE_ID
        return self.current

    async def promote_candidate(
        self,
        context: ActorContext,
        command: VerifyDraCandidateCommand,
        idempotency_key: str,
    ) -> DraVerificationViewV1:
        self.calls += 1
        verification = DraVerificationViewV1(
            verification_id=VERIFICATION_ID,
            decision="approve",
            promoted_source_pack_version=2,
            promoted_source_entry_id=SOURCE_ENTRY_ID,
            promoted_evidence_id=PROMOTED_EVIDENCE_ID,
        )
        self.current = DraCandidateViewV1(candidate_id=CANDIDATE_ID, verification=verification)
        if self.lose_ack:
            from night_voyager.dra.reconciliation import DraAmbiguousOutcome

            raise DraAmbiguousOutcome()
        return verification


def _capture() -> DraCaptureReceiptV1:
    return DraCaptureReceiptV1(
        schema_version="night-voyager.dra-live-capture-receipt.v1",
        intent_sha256="a" * 64,
        attempt_id="attempt-1",
        producer=DraLiveProducerIdentityV1(),
        run_id="run-1",
        segment_id="segment-1",
        artifact=DraArtifactIdentityV1(
            artifact_id="research-report.md",
            kind="research_report_markdown",
            media_type="text/markdown",
            byte_length=1,
            sha256="b" * 64,
        ),
        selected_evidence=DraSelectedEvidenceV1(
            evidence_id="evidence-1",
            run_id="run-1",
            segment_id="segment-1",
            source_url=URL,
            source_identity=URL,
            retrieved_at=datetime(2026, 7, 25, tzinfo=UTC),
            citation_status="cited",
            verification_status="verified",
        ),
        stage_states=(DraStageStateV1(stage="capture-live", status="completed"),),
        provider_attempt_consumed=True,
        candidate_id=CANDIDATE_ID,
        candidate_authority="untrusted_candidate",
        candidate_import_key="c" * 64,
        cleanup_status="removed",
    )


def _attestation() -> SourceAttestationV1:
    return SourceAttestationV1(
        canonical_url=URL,
        publisher="Example University",
        institution="Example University",
        snapshot_date=date(2026, 7, 25),
        freshness_days=30,
        redistribution_class="link_only",
        evidence_class="institutional",
        logical_path="source/snapshot.html",
        snapshot_byte_length=len(CONTENT),
        snapshot_sha256=hashlib.sha256(CONTENT).hexdigest(),
        known_gaps=("applicant_eligibility", "intake_availability"),
    )


def _private_roots(tmp_path: Path) -> tuple[Path, Path]:
    receipt_root = tmp_path / "receipts"
    snapshot_root = tmp_path / "snapshot"
    receipt_root.mkdir(mode=0o700)
    snapshot_root.mkdir(mode=0o700)
    source = snapshot_root / "source"
    source.mkdir(mode=0o700)
    snapshot = source / "snapshot.html"
    snapshot.write_bytes(CONTENT)
    snapshot.chmod(0o600)
    return receipt_root, snapshot_root


def _command(snapshot_root: Path) -> PromoteCommand:
    capture = _capture()
    return PromoteCommand(
        promotion=DraPromotionInputV1(
            intent_sha256=capture.intent_sha256,
            capture=capture,
            organization_id=ORG_ID,
            case_id=CASE_ID,
            expected_case_revision=3,
            candidate_id=CANDIDATE_ID,
            dra_evidence_id="evidence-1",
            selected_raw_url=URL,
            advisor_actor_identity_sha256=derive_identity_hash("actor", str(ACTOR_ID)),
            tenant_identity_sha256=derive_identity_hash("tenant", str(ORG_ID)),
            reason="Operator verified the supplied institutional snapshot.",
            source_attestation=_attestation(),
        ),
        context=ActorContext(
            organization_id=ORG_ID,
            actor_id=ACTOR_ID,
            role=ActorRole.ADVISOR,
            session_id=SESSION_ID,
        ),
        snapshot_root=snapshot_root,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("lose_ack", [False, True])
async def test_promote_validates_snapshot_and_reconciles_lost_ack(
    tmp_path: Path, lose_ack: bool
) -> None:
    receipt_root, snapshot_root = _private_roots(tmp_path)
    gateway = FakePromotionGateway(lose_ack=lose_ack)
    with LiveReceiptStore.open(receipt_root) as store:
        store.write_receipt("capture.json", _capture())
        receipt = await DraLiveClosureController(gateway, store).promote(_command(snapshot_root))

    assert receipt.acknowledgement == "promotion_recorded"
    assert receipt.verification_id == VERIFICATION_ID
    assert receipt.promoted_source_entry_id == SOURCE_ENTRY_ID
    assert receipt.promoted_evidence_id == PROMOTED_EVIDENCE_ID
    assert receipt.snapshot.sha256 == hashlib.sha256(CONTENT).hexdigest()
    assert gateway.calls == 1
    assert not (snapshot_root / "source" / "snapshot.html").exists()


@pytest.mark.asyncio
async def test_promote_rejects_url_substitution_before_authority(
    tmp_path: Path,
) -> None:
    receipt_root, snapshot_root = _private_roots(tmp_path)
    gateway = FakePromotionGateway()
    command = _command(snapshot_root)
    command = PromoteCommand(
        promotion=command.promotion.model_copy(
            update={"selected_raw_url": URL.replace("#requirements", "#other")}
        ),
        context=command.context,
        snapshot_root=command.snapshot_root,
    )
    with LiveReceiptStore.open(receipt_root) as store:
        store.write_receipt("capture.json", _capture())
        with pytest.raises(LiveStorageInvalid, match="snapshot_selected_url_invalid"):
            await DraLiveClosureController(gateway, store).promote(command)

    assert gateway.calls == 0
    assert not (snapshot_root / "source" / "snapshot.html").exists()


@pytest.mark.asyncio
async def test_promote_rejects_cross_tenant_actor_before_authority(
    tmp_path: Path,
) -> None:
    receipt_root, snapshot_root = _private_roots(tmp_path)
    gateway = FakePromotionGateway()
    command = _command(snapshot_root)
    command = PromoteCommand(
        promotion=command.promotion,
        context=ActorContext(
            organization_id=UUID("00000000-0000-4000-8000-000000000099"),
            actor_id=ACTOR_ID,
            role=ActorRole.ADVISOR,
            session_id=SESSION_ID,
        ),
        snapshot_root=command.snapshot_root,
    )
    with LiveReceiptStore.open(receipt_root) as store:
        store.write_receipt("capture.json", _capture())
        with pytest.raises(ValueError, match="promotion_actor_invalid"):
            await DraLiveClosureController(gateway, store).promote(command)
    assert gateway.calls == 0
