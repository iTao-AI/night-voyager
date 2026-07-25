from __future__ import annotations

import asyncio
import hashlib
import os
import stat
import time
from dataclasses import dataclass
from pathlib import Path

from night_voyager.dra.errors import DraAuthorizationError, DraConflictError
from night_voyager.dra.live_models import (
    DraArtifactIdentityV1,
    DraCaptureIntentV1,
    DraCaptureReceiptV1,
    DraControllerStopReceiptV1,
    DraInspectionRequiredReceiptV1,
    DraLiveFailurePhase,
    DraPollRecoveryReceiptV1,
    DraPreflightReceiptV1,
    DraPromotionInputV1,
    DraPromotionReceiptV1,
    DraReceiptIdentityV1,
    DraReconciliationRequiredReceiptV1,
    DraStageStateV1,
    derive_identity_hash,
    derive_stage_key,
)
from night_voyager.dra.live_ports import (
    DraCandidateGatewayPort,
    DraLiveClockPort,
    DraLiveSleepPort,
    DraLiveTransportPort,
    DraPromotionGatewayPort,
)
from night_voyager.dra.live_projection import (
    DraLiveConsumerEvidenceV1,
    DraLiveContractError,
    DraTerminalProjectionV1,
    project_terminal_result,
    select_cited_evidence,
)
from night_voyager.dra.live_storage import (
    LiveReceiptStore,
    LiveStorageError,
    supplied_snapshot,
)
from night_voyager.dra.models import (
    DraCandidateImportV1,
    DraCanonicalArtifactInputV1,
    DraEvidenceProjectionV1,
    DraRunAcceptanceV1,
    DraRunProjectionV1,
    DraRunRequestIdentityV1,
)
from night_voyager.dra.ports import VerifyDraCandidateCommand
from night_voyager.dra.reconciliation import (
    DraAmbiguousOutcome,
    DraTransportConflict,
    DraTransportError,
)
from night_voyager.identity.models import ActorContext, ActorRole

CaptureResult = (
    DraInspectionRequiredReceiptV1
    | DraReconciliationRequiredReceiptV1
    | DraPollRecoveryReceiptV1
    | DraControllerStopReceiptV1
)


class _SystemClock:
    def monotonic(self) -> float:
        return time.monotonic()


class _AsyncioSleeper:
    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


@dataclass(frozen=True, slots=True)
class CaptureLiveCommand:
    intent: DraCaptureIntentV1
    preflight: DraPreflightReceiptV1
    query_path: Path


@dataclass(frozen=True, slots=True)
class ReconcileCreateCommand:
    intent: DraCaptureIntentV1
    preflight: DraPreflightReceiptV1
    prior: DraReconciliationRequiredReceiptV1
    query_path: Path
    exact_replay_authorized: bool


@dataclass(frozen=True, slots=True)
class ResumePollCommand:
    intent: DraCaptureIntentV1
    prior: DraPollRecoveryReceiptV1


@dataclass(frozen=True, slots=True)
class SelectAndImportCommand:
    intent: DraCaptureIntentV1
    inspection: DraInspectionRequiredReceiptV1
    declared_raw_url: str
    context: ActorContext


@dataclass(frozen=True, slots=True)
class PromoteCommand:
    promotion: DraPromotionInputV1
    context: ActorContext
    snapshot_root: Path


class DraLiveClosureController:
    def __init__(
        self,
        authority: DraPromotionGatewayPort,
        store: LiveReceiptStore,
    ) -> None:
        self._authority = authority
        self._store = store

    async def promote(self, command: PromoteCommand) -> DraPromotionReceiptV1:
        promotion = command.promotion
        stored = self._store.read_receipt("capture.json", DraCaptureReceiptV1)
        if stored != promotion.capture:
            raise ValueError("promotion_capture_receipt_invalid")
        context = command.context
        if (
            context.role is not ActorRole.ADVISOR
            or context.organization_id != promotion.organization_id
            or derive_identity_hash("actor", str(context.actor_id))
            != promotion.advisor_actor_identity_sha256
            or derive_identity_hash("tenant", str(context.organization_id))
            != promotion.tenant_identity_sha256
        ):
            raise ValueError("promotion_actor_invalid")
        current = await self._authority.get_candidate(
            context, promotion.case_id, promotion.candidate_id
        )
        if current is None or current.candidate_id != promotion.candidate_id:
            raise ValueError("promotion_candidate_invalid")
        key = derive_stage_key(
            promotion.intent_sha256,
            "promotion",
            str(promotion.candidate_id),
        )
        request = VerifyDraCandidateCommand(
            case_id=promotion.case_id,
            candidate_id=promotion.candidate_id,
            expected_case_revision=promotion.expected_case_revision,
            dra_evidence_id=promotion.dra_evidence_id,
            decision="approve",
            reason=promotion.reason,
            source_attestation=promotion.source_attestation,
        )
        with supplied_snapshot(
            command.snapshot_root,
            promotion.source_attestation,
            promotion.selected_raw_url,
        ) as snapshot:
            if (
                promotion.capture.selected_evidence is None
                or promotion.capture.selected_evidence.source_url != promotion.selected_raw_url
            ):
                raise ValueError("selected_raw_url_invalid")
            if current.verification is None:
                try:
                    verification = await self._authority.promote_candidate(context, request, key)
                except DraAmbiguousOutcome:
                    reread = await self._authority.get_candidate(
                        context,
                        promotion.case_id,
                        promotion.candidate_id,
                    )
                    if reread is None or reread.verification is None:
                        raise
                    verification = reread.verification
            else:
                verification = current.verification
            if (
                verification.decision != "approve"
                or verification.promoted_source_pack_version is None
                or verification.promoted_source_entry_id is None
                or verification.promoted_evidence_id is None
            ):
                raise ValueError("promotion_authority_result_invalid")
            receipt = DraPromotionReceiptV1(
                intent_sha256=promotion.intent_sha256,
                attempt_id=promotion.capture.attempt_id,
                candidate_id=promotion.candidate_id,
                dra_evidence_id=promotion.dra_evidence_id,
                selected_raw_url=promotion.selected_raw_url,
                promotion_key=key,
                verification_id=verification.verification_id,
                promoted_source_pack_version=(verification.promoted_source_pack_version),
                promoted_source_entry_id=(verification.promoted_source_entry_id),
                promoted_evidence_id=verification.promoted_evidence_id,
                snapshot=snapshot,
                stage_states=(
                    *promotion.capture.stage_states,
                    DraStageStateV1(stage="promote", status="completed"),
                ),
            )
            self._store.write_receipt("promotion.json", receipt)
            return receipt


class DraLiveCaptureController:
    def __init__(
        self,
        transport: DraLiveTransportPort,
        candidate_gateway: DraCandidateGatewayPort,
        store: LiveReceiptStore,
        *,
        clock: DraLiveClockPort | None = None,
        sleeper: DraLiveSleepPort | None = None,
    ) -> None:
        self._transport = transport
        self._candidate_gateway = candidate_gateway
        self._store = store
        self._clock = clock or _SystemClock()
        self._sleeper = sleeper or _AsyncioSleeper()

    def preflight(self, intent: DraCaptureIntentV1) -> DraPreflightReceiptV1:
        capture = intent.capture
        intent_receipt = self._store.write_receipt("intent.json", intent)
        receipt = DraPreflightReceiptV1(
            intent_sha256=intent.intent_sha256,
            attempt_id=intent.attempt_id,
            intent_receipt=intent_receipt,
            scenario_id=capture.scenario_id,
            producer=capture.producer,
            advisor_actor_identity_sha256=(capture.advisor_actor_identity_sha256),
            tenant_identity_sha256=capture.tenant_identity_sha256,
            receipt_root_id=capture.receipt_root_id,
        )
        self._store.write_receipt("preflight.json", receipt)
        return receipt

    def _validate_preflight(
        self,
        intent: DraCaptureIntentV1,
        preflight: DraPreflightReceiptV1,
    ) -> DraReceiptIdentityV1:
        stored_intent = self._store.read_receipt("intent.json", DraCaptureIntentV1)
        stored_preflight = self._store.read_receipt("preflight.json", DraPreflightReceiptV1)
        if (
            stored_intent != intent
            or stored_preflight != preflight
            or preflight.intent_sha256 != intent.intent_sha256
            or preflight.attempt_id != intent.attempt_id
        ):
            raise ValueError("preflight_identity_invalid")
        return self._store.write_receipt("preflight.json", preflight)

    @staticmethod
    def _read_frozen_query(command: CaptureLiveCommand) -> str:
        expected = command.intent.capture.request
        path = command.query_path
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        if nofollow == 0:
            raise ValueError("request_primitives_unavailable")
        descriptor = -1
        try:
            descriptor = os.open(path, os.O_RDONLY | nofollow)
            metadata = os.fstat(descriptor)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or metadata.st_size != expected.byte_length
                or metadata.st_size < 1
                or metadata.st_size > 1_048_576
            ):
                raise ValueError("request_identity_mismatch")
            content = bytearray()
            while len(content) < metadata.st_size:
                chunk = os.read(
                    descriptor,
                    min(65_536, metadata.st_size - len(content)),
                )
                if not chunk:
                    raise ValueError("request_identity_mismatch")
                content.extend(chunk)
            if os.read(descriptor, 1):
                raise ValueError("request_identity_mismatch")
        except (OSError, UnicodeError) as error:
            raise ValueError("request_identity_mismatch") from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        encoded = bytes(content)
        if hashlib.sha256(encoded).hexdigest() != expected.sha256:
            raise ValueError("request_identity_mismatch")
        try:
            return encoded.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise ValueError("request_identity_mismatch") from error

    def _stop(
        self,
        intent: DraCaptureIntentV1,
        *,
        phase: DraLiveFailurePhase,
        public_code: str,
        provider_attempt_consumed: bool,
    ) -> DraControllerStopReceiptV1:
        cleanup = self._store.delete_artifact()
        cleanup_status = "failed" if cleanup.status == "retained" else cleanup.status
        receipt = DraControllerStopReceiptV1(
            intent_sha256=intent.intent_sha256,
            attempt_id=intent.attempt_id,
            phase=phase,
            public_code=public_code,
            provider_attempt_consumed=provider_attempt_consumed,
            cleanup_status=cleanup_status,
            permitted_next_command=("cleanup" if cleanup.status == "failed" else "stop"),
        )
        self._store.write_receipt("failure.json", receipt)
        return receipt

    async def capture(self, command: CaptureLiveCommand) -> CaptureResult:
        create_key = derive_stage_key(
            command.intent.intent_sha256,
            "create",
            command.intent.attempt_id,
        )
        try:
            preflight_identity = self._validate_preflight(command.intent, command.preflight)
            query = self._read_frozen_query(command)
        except (ValueError, LiveStorageError):
            return self._stop(
                command.intent,
                phase=DraLiveFailurePhase.PREFLIGHT_INVALID,
                public_code="request_identity_mismatch",
                provider_attempt_consumed=False,
            )
        try:
            await self._transport.health()
            acceptance = await self._transport.create_run(
                {"profile_id": "generic", "query": query},
                create_key,
            )
        except DraAmbiguousOutcome:
            receipt = DraReconciliationRequiredReceiptV1(
                schema_version=("night-voyager.dra-live-reconciliation-required.v1"),
                intent_sha256=command.intent.intent_sha256,
                attempt_id=command.intent.attempt_id,
                intent_receipt=command.preflight.intent_receipt,
                create_key=create_key,
                provider_attempt_consumed=True,
                permitted_next_command="reconcile-create",
            )
            self._store.write_receipt("reconciliation-required.json", receipt)
            return receipt
        except DraTransportConflict:
            return self._stop(
                command.intent,
                phase=DraLiveFailurePhase.RUN_ACCEPTANCE_AMBIGUOUS,
                public_code="create_identity_conflict",
                provider_attempt_consumed=True,
            )
        except (DraTransportError, ValueError):
            return self._stop(
                command.intent,
                phase=DraLiveFailurePhase.PRODUCER_UNAVAILABLE,
                public_code="producer_unavailable",
                provider_attempt_consumed=False,
            )
        return await self._poll_to_inspection(
            command.intent,
            preflight_identity,
            acceptance,
        )

    async def reconcile_create(self, command: ReconcileCreateCommand) -> CaptureResult:
        if not command.exact_replay_authorized:
            raise ValueError("reconciliation_authorization_required")
        expected_key = derive_stage_key(
            command.intent.intent_sha256,
            "create",
            command.intent.attempt_id,
        )
        try:
            stored_prior = self._store.read_receipt(
                "reconciliation-required.json",
                DraReconciliationRequiredReceiptV1,
            )
        except LiveStorageError as error:
            raise ValueError("reconciliation_identity_invalid") from error
        if (
            stored_prior != command.prior
            or command.prior.intent_sha256 != command.intent.intent_sha256
            or command.prior.attempt_id != command.intent.attempt_id
            or command.prior.create_key != expected_key
            or command.prior.intent_receipt != command.preflight.intent_receipt
        ):
            raise ValueError("reconciliation_identity_invalid")
        preflight_identity = self._validate_preflight(command.intent, command.preflight)
        query = self._read_frozen_query(
            CaptureLiveCommand(
                intent=command.intent,
                preflight=command.preflight,
                query_path=command.query_path,
            )
        )
        try:
            await self._transport.health()
            acceptance = await self._transport.create_run(
                {"profile_id": "generic", "query": query},
                expected_key,
            )
        except DraAmbiguousOutcome:
            return command.prior
        except (DraTransportError, ValueError):
            return self._stop(
                command.intent,
                phase=DraLiveFailurePhase.RUN_ACCEPTANCE_AMBIGUOUS,
                public_code="reconciliation_failed",
                provider_attempt_consumed=True,
            )
        return await self._poll_to_inspection(
            command.intent,
            preflight_identity,
            acceptance,
        )

    async def _poll_to_inspection(
        self,
        intent: DraCaptureIntentV1,
        preflight_identity: DraReceiptIdentityV1,
        acceptance: DraRunAcceptanceV1,
    ) -> CaptureResult:
        last_state_version = 0
        deadline = self._clock.monotonic() + intent.capture.deadline_seconds
        while True:
            try:
                run = await self._transport.get_run(acceptance.run_id)
            except (DraTransportError, ValueError):
                return self._stop(
                    intent,
                    phase=DraLiveFailurePhase.TERMINAL_STATE_INVALID,
                    public_code="run_poll_invalid",
                    provider_attempt_consumed=True,
                )
            last_state_version = run.state_version
            if run.disposition == "in_progress":
                remaining = deadline - self._clock.monotonic()
                if remaining <= 0:
                    break
                await self._sleeper.sleep(min(intent.capture.poll_seconds, remaining))
                continue
            if run.disposition != "canonical_ready":
                return self._stop(
                    intent,
                    phase=DraLiveFailurePhase.TERMINAL_STATE_INVALID,
                    public_code="terminal_state_invalid",
                    provider_attempt_consumed=True,
                )
            try:
                result = await self._transport.get_result(acceptance.run_id)
                projection = project_terminal_result(acceptance, run, result)
                artifact = projection.artifact
                artifact_identity = DraArtifactIdentityV1(
                    artifact_id=artifact.artifact_id,
                    kind=artifact.kind,
                    media_type=artifact.media_type,
                    byte_length=artifact.byte_length,
                    sha256=artifact.content_hash,
                )
                self._store.write_artifact_for_inspection(
                    artifact_identity,
                    artifact.content.encode("utf-8"),
                )
            except (DraLiveContractError, LiveStorageError, ValueError):
                return self._stop(
                    intent,
                    phase=DraLiveFailurePhase.ARTIFACT_CONTRACT_INVALID,
                    public_code="terminal_projection_invalid",
                    provider_attempt_consumed=True,
                )
            receipt = DraInspectionRequiredReceiptV1(
                intent_sha256=intent.intent_sha256,
                attempt_id=intent.attempt_id,
                preflight_receipt=preflight_identity,
                producer=intent.capture.producer,
                case_id=intent.capture.case_id,
                expected_case_revision=intent.capture.expected_case_revision,
                advisor_actor_identity_sha256=(intent.capture.advisor_actor_identity_sha256),
                tenant_identity_sha256=intent.capture.tenant_identity_sha256,
                thread_id=acceptance.thread_id,
                run_id=acceptance.run_id,
                segment_id=acceptance.segment_id,
                state_version=projection.state_version,
                acceptance_idempotent_replay=acceptance.idempotent_replay,
                artifact=artifact_identity,
                evidence=run.evidence,
                provider_attempt_consumed=True,
            )
            self._store.write_receipt("inspection-required.json", receipt)
            return receipt
        receipt = DraPollRecoveryReceiptV1(
            intent_sha256=intent.intent_sha256,
            attempt_id=intent.attempt_id,
            preflight_receipt=preflight_identity,
            thread_id=acceptance.thread_id,
            run_id=acceptance.run_id,
            segment_id=acceptance.segment_id,
            last_state_version=last_state_version,
            provider_attempt_consumed=True,
        )
        self._store.write_receipt("poll-recovery.json", receipt)
        return receipt

    async def resume_poll(self, command: ResumePollCommand) -> CaptureResult:
        prior = command.prior
        try:
            stored_prior = self._store.read_receipt("poll-recovery.json", DraPollRecoveryReceiptV1)
            stored_preflight = self._store.read_receipt("preflight.json", DraPreflightReceiptV1)
            preflight_identity = self._validate_preflight(command.intent, stored_preflight)
        except (LiveStorageError, ValueError) as error:
            raise ValueError("poll_recovery_identity_invalid") from error
        if (
            stored_prior != prior
            or prior.intent_sha256 != command.intent.intent_sha256
            or prior.attempt_id != command.intent.attempt_id
            or prior.preflight_receipt != preflight_identity
        ):
            raise ValueError("poll_recovery_identity_invalid")
        acceptance = DraRunAcceptanceV1(
            thread_id=prior.thread_id,
            run_id=prior.run_id,
            segment_id=prior.segment_id,
            idempotent_replay=True,
        )
        return await self._poll_to_inspection(
            command.intent,
            preflight_identity,
            acceptance,
        )

    async def select_and_import(
        self, command: SelectAndImportCommand
    ) -> DraCaptureReceiptV1 | DraControllerStopReceiptV1:
        intent = command.intent
        inspection = command.inspection
        capture = intent.capture
        try:
            stored = self._store.read_receipt(
                "inspection-required.json",
                DraInspectionRequiredReceiptV1,
            )
            if (
                stored != inspection
                or inspection.intent_sha256 != intent.intent_sha256
                or inspection.attempt_id != intent.attempt_id
            ):
                raise ValueError("inspection_identity_invalid")
            context = command.context
            if (
                context.role is not ActorRole.ADVISOR
                or context.organization_id != capture.organization_id
                or derive_identity_hash("actor", str(context.actor_id))
                != capture.advisor_actor_identity_sha256
                or derive_identity_hash("tenant", str(context.organization_id))
                != capture.tenant_identity_sha256
            ):
                raise DraAuthorizationError("dra_candidate_operation_requires_advisor")
            artifact_bytes = self._store.read_artifact(inspection.artifact)
            artifact_text = artifact_bytes.decode("utf-8", errors="strict")
            projection = DraTerminalProjectionV1(
                run_id=inspection.run_id,
                segment_id=inspection.segment_id,
                state_version=inspection.state_version,
                artifact=DraCanonicalArtifactInputV1(
                    artifact_id=inspection.artifact.artifact_id,
                    kind=inspection.artifact.kind,
                    media_type=inspection.artifact.media_type,
                    content=artifact_text,
                    content_hash=inspection.artifact.sha256,
                ),
                evidence=tuple(
                    DraLiveConsumerEvidenceV1(
                        evidence_id=row.evidence_id,
                        source_url=row.source_url,
                        source_identity=row.source_identity,
                        retrieved_at=row.retrieved_at,
                        citation_status=row.citation_status,
                        verification_status=row.verification_status,
                    )
                    for row in inspection.evidence
                ),
            )
            selected = select_cited_evidence(projection, command.declared_raw_url)
        except DraAuthorizationError:
            return self._stop(
                intent,
                phase=DraLiveFailurePhase.CANDIDATE_AUTHORITY_DENIED,
                public_code="candidate_authority_denied",
                provider_attempt_consumed=True,
            )
        except (
            DraLiveContractError,
            LiveStorageError,
            UnicodeDecodeError,
            ValueError,
        ):
            return self._stop(
                intent,
                phase=DraLiveFailurePhase.SOURCE_SELECTION_INVALID,
                public_code="source_selection_invalid",
                provider_attempt_consumed=True,
            )

        candidate_import = DraCandidateImportV1(
            schema_version="night-voyager.dra-candidate-import.v1",
            organization_id=capture.organization_id,
            case_id=capture.case_id,
            expected_case_revision=capture.expected_case_revision,
            producer=capture.producer.pin,
            request_identity=DraRunRequestIdentityV1(
                profile_id="generic",
                request_sha256=capture.request.sha256,
            ),
            acceptance=DraRunAcceptanceV1(
                thread_id=inspection.thread_id,
                run_id=inspection.run_id,
                segment_id=inspection.segment_id,
                idempotent_replay=inspection.acceptance_idempotent_replay,
            ),
            run=DraRunProjectionV1(
                run_id=inspection.run_id,
                state_version=inspection.state_version,
                execution_status="completed",
                review_status="not_required",
                delivery_status="ready",
            ),
            artifact=projection.artifact,
            evidence=(
                DraEvidenceProjectionV1(
                    evidence_id=selected.evidence_id,
                    source_url=selected.source_url,
                    source_identity=selected.source_identity,
                    retrieved_at=selected.retrieved_at,
                    citation_status=selected.citation_status,
                    verification_status=selected.verification_status,
                ),
            ),
        )
        import_key = derive_stage_key(
            intent.intent_sha256,
            "candidate-import",
            str(capture.case_id),
        )
        try:
            view = await self._candidate_gateway.import_candidate(
                command.context,
                candidate_import,
                import_key,
            )
            if view.verification is not None:
                raise DraConflictError("dra_candidate_authority_invalid")
        except DraAuthorizationError:
            return self._stop(
                intent,
                phase=DraLiveFailurePhase.CANDIDATE_AUTHORITY_DENIED,
                public_code="candidate_authority_denied",
                provider_attempt_consumed=True,
            )
        except (DraConflictError, ValueError):
            return self._stop(
                intent,
                phase=DraLiveFailurePhase.CANDIDATE_IMPORT_CONFLICT,
                public_code="candidate_import_conflict",
                provider_attempt_consumed=True,
            )
        cleanup = self._store.delete_artifact()
        if cleanup.status not in {"removed", "absent"}:
            return self._stop(
                intent,
                phase=DraLiveFailurePhase.CLEANUP_INCOMPLETE,
                public_code="cleanup_incomplete",
                provider_attempt_consumed=True,
            )
        cleanup_status = "removed" if cleanup.status == "removed" else "absent"
        receipt = DraCaptureReceiptV1(
            schema_version="night-voyager.dra-live-capture-receipt.v1",
            intent_sha256=intent.intent_sha256,
            attempt_id=intent.attempt_id,
            producer=capture.producer,
            run_id=inspection.run_id,
            segment_id=inspection.segment_id,
            artifact=inspection.artifact,
            selected_evidence=selected,
            stage_states=(DraStageStateV1(stage="capture-live", status="completed"),),
            provider_attempt_consumed=True,
            candidate_id=view.candidate_id,
            candidate_authority="untrusted_candidate",
            candidate_import_key=import_key,
            cleanup_status=cleanup_status,
        )
        self._store.write_receipt("capture.json", receipt)
        return receipt
