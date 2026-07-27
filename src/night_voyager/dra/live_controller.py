from __future__ import annotations

import asyncio
import hashlib
import os
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from night_voyager.decision.hashing import canonical_request_sha256
from night_voyager.dra.errors import DraAuthorizationError, DraConflictError
from night_voyager.dra.live_evaluation import DraLiveCandidateReadinessV4
from night_voyager.dra.live_models import (
    DraArtifactIdentityV1,
    DraCandidateReadinessReceiptV2,
    DraCaptureIntentV2,
    DraCaptureIntentV3,
    DraCaptureReceiptV1,
    DraCaptureReceiptV2,
    DraControllerStopReceiptV1,
    DraDecisionInputV1,
    DraDecisionReceiptV1,
    DraInspectionRequiredReceiptV1,
    DraInspectionRequiredReceiptV2,
    DraLiveFailurePhase,
    DraLiveRunEnvelopeV1,
    DraLiveScenarioV2,
    DraMutationAmbiguousReceiptV1,
    DraPollRecoveryReceiptV1,
    DraPollRecoveryReceiptV2,
    DraPreflightReceiptV2,
    DraPreflightReceiptV3,
    DraPromotionInputV1,
    DraPromotionReceiptV1,
    DraProviderAttemptEvidenceV1,
    DraReceiptIdentityV1,
    DraReconciliationRequiredReceiptV1,
    DraReconciliationRequiredReceiptV2,
    DraReviewInputV1,
    DraReviewReceiptV1,
    DraStageStateV1,
    derive_identity_hash,
    derive_stage_key,
    validate_effective_query_v2,
)
from night_voyager.dra.live_ports import (
    DraCandidateGatewayPort,
    DraClosureGatewayPort,
    DraLiveClockPort,
    DraLiveSleepPort,
    DraLiveTransportPort,
    DraPromotionGatewayPort,
    DraStrictCandidateGatewayPort,
)
from night_voyager.dra.live_projection import (
    DraLiveConsumerEvidenceV1,
    DraLiveContractError,
    DraStrictLiveRunEnvelopeV2,
    DraStrictTerminalProjectionV2,
    DraTerminalProjectionV1,
    project_strict_terminal_result,
    project_terminal_result,
    select_cited_evidence,
    select_strict_cited_evidence,
)
from night_voyager.dra.live_storage import (
    LiveReceiptStore,
    LiveStorageError,
    supplied_snapshot,
)
from night_voyager.dra.models import (
    DraCandidateImportV1,
    DraCandidateImportV2,
    DraCanonicalArtifactInputV1,
    DraEvidenceProjectionV1,
    DraObservedProfileManifestV1,
    DraRunAcceptanceV1,
    DraRunProjectionV1,
    DraRunRequestIdentityV1,
    DraRunRequestIdentityV2,
    DraStrictConsumerIdentityV2,
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
    | DraInspectionRequiredReceiptV2
    | DraReconciliationRequiredReceiptV1
    | DraReconciliationRequiredReceiptV2
    | DraPollRecoveryReceiptV1
    | DraPollRecoveryReceiptV2
    | DraControllerStopReceiptV1
)
CaptureIntent = DraCaptureIntentV2 | DraCaptureIntentV3
PreflightReceipt = DraPreflightReceiptV2 | DraPreflightReceiptV3


class _SystemClock:
    def monotonic(self) -> float:
        return time.monotonic()


class _AsyncioSleeper:
    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


@dataclass(frozen=True, slots=True)
class CaptureLiveCommand:
    intent: CaptureIntent
    preflight: PreflightReceipt
    query_path: Path


@dataclass(frozen=True, slots=True)
class ReconcileCreateCommand:
    intent: CaptureIntent
    preflight: PreflightReceipt
    prior: DraReconciliationRequiredReceiptV1 | DraReconciliationRequiredReceiptV2
    query_path: Path
    exact_replay_authorized: bool


@dataclass(frozen=True, slots=True)
class ResumePollCommand:
    intent: CaptureIntent
    prior: DraPollRecoveryReceiptV1 | DraPollRecoveryReceiptV2


@dataclass(frozen=True, slots=True)
class SelectAndImportCommand:
    intent: CaptureIntent
    inspection: DraInspectionRequiredReceiptV1 | DraInspectionRequiredReceiptV2
    declared_raw_url: str
    context: ActorContext


@dataclass(frozen=True, slots=True)
class PromoteCommand:
    promotion: DraPromotionInputV1
    context: ActorContext
    snapshot_root: Path


@dataclass(frozen=True, slots=True)
class ReviewCommand:
    review: DraReviewInputV1
    context: ActorContext


@dataclass(frozen=True, slots=True)
class DecideCommand:
    decision: DraDecisionInputV1
    context: ActorContext


class DraLiveClosureController:
    def __init__(
        self,
        authority: DraPromotionGatewayPort | DraClosureGatewayPort,
        store: LiveReceiptStore,
    ) -> None:
        self._authority = authority
        self._store = store

    @staticmethod
    def _target_hash(stage: str, value: object) -> str:
        return hashlib.sha256(
            f"night-voyager.dra-live.target.v1\0{stage}\0{value}".encode()
        ).hexdigest()

    async def promote(self, command: PromoteCommand) -> DraPromotionReceiptV1:
        authority = cast(DraPromotionGatewayPort, self._authority)
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
        current = await authority.get_candidate(
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
        request_sha256 = canonical_request_sha256(request.model_dump(mode="json"))
        parent_identity = self._store.write_receipt("capture.json", stored)
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
                    verification = await authority.promote_candidate(context, request, key)
                except DraAmbiguousOutcome:
                    self._store.write_receipt(
                        "promotion-ambiguous.json",
                        DraMutationAmbiguousReceiptV1(
                            intent_sha256=promotion.intent_sha256,
                            attempt_id=promotion.capture.attempt_id,
                            stage="promote",
                            parent_receipt=parent_identity,
                            mutation_key=key,
                            request_sha256=request_sha256,
                            target_identity_sha256=self._target_hash(
                                "promote", promotion.candidate_id
                            ),
                            permitted_next_command="promote",
                        ),
                    )
                    reread = await authority.get_candidate(
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
                or verification.decision_request_sha256 != request_sha256
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

    async def review(self, command: ReviewCommand) -> DraReviewReceiptV1:
        authority = cast(DraClosureGatewayPort, self._authority)
        review = command.review
        stored = self._store.read_receipt(
            "promotion.json", DraPromotionReceiptV1
        )
        if stored != review.promotion:
            raise ValueError("review_promotion_receipt_invalid")
        context = command.context
        if (
            context.role is not ActorRole.ADVISOR
            or context.organization_id != review.organization_id
            or derive_identity_hash("actor", str(context.actor_id))
            != review.advisor_actor_identity_sha256
            or derive_identity_hash("tenant", str(context.organization_id))
            != review.tenant_identity_sha256
        ):
            raise ValueError("review_actor_invalid")
        mapping = await authority.get_promoted_mapping(
            context, review.case_id, review.candidate_id
        )
        if mapping != (
            review.promoted_source_pack_id,
            review.promoted_source_pack_version,
        ):
            raise ValueError("promoted_mapping_invalid")
        task_key = derive_stage_key(
            review.intent_sha256, "planning-task", str(review.case_id)
        )
        task_request_sha256 = canonical_request_sha256(
            {
                "case_id": str(review.case_id),
                "operation": "generate_governed_mixed_planning_run_v1",
                "expected_case_revision": review.expected_case_revision,
                "source_pack_id": str(review.promoted_source_pack_id),
                "source_pack_version": review.promoted_source_pack_version,
                "policy_version": "m3a-policy-v1",
            }
        )
        task = await authority.get_task(context, task_key)
        if task is None:
            try:
                task = await authority.create_task(
                    context,
                    review.case_id,
                    review.expected_case_revision,
                    review.promoted_source_pack_id,
                    review.promoted_source_pack_version,
                    task_key,
                )
            except DraAmbiguousOutcome:
                self._store.write_receipt(
                    "review-ambiguous.json",
                    DraMutationAmbiguousReceiptV1(
                        intent_sha256=review.intent_sha256,
                        attempt_id=review.promotion.attempt_id,
                        stage="review",
                        parent_receipt=self._store.write_receipt(
                            "promotion.json", stored
                        ),
                        mutation_key=task_key,
                        request_sha256=task_request_sha256,
                        target_identity_sha256=self._target_hash(
                            "review-task", review.case_id
                        ),
                        permitted_next_command="review",
                    ),
                )
                task = await authority.get_task(context, task_key)
                if task is None:
                    task = await authority.create_task(
                        context,
                        review.case_id,
                        review.expected_case_revision,
                        review.promoted_source_pack_id,
                        review.promoted_source_pack_version,
                        task_key,
                    )
        if (
            task.operation != "generate_governed_mixed_planning_run_v1"
            or task.source_pack_id != review.promoted_source_pack_id
            or task.source_pack_version
            != review.promoted_source_pack_version
            or task.status != "needs_advisor_review"
            or task.case_id != review.case_id
            or task.case_revision != review.expected_case_revision
            or task.request_sha256 != task_request_sha256
        ):
            raise ValueError("planning_task_projection_invalid")
        review_key = derive_stage_key(
            review.intent_sha256,
            "advisor-review",
            str(task.planning_run_id),
        )
        review_request_sha256 = canonical_request_sha256(
            {
                "case_id": str(review.case_id),
                "planning_run_id": str(task.planning_run_id),
                "expected_case_revision": review.expected_case_revision,
                "action": "approve_for_consultation",
                "eligible_route_ids": [str(item) for item in review.eligible_route_ids],
                "risk_acceptances": [],
                "reviewer_notes": None,
            }
        )
        recorded = await authority.get_review(
            context, review.case_id, task.planning_run_id, review_key
        )
        if recorded is None:
            try:
                recorded = await authority.record_review(
                    context,
                    review.case_id,
                    review.expected_case_revision,
                    task.planning_run_id,
                    review.eligible_route_ids,
                    review_key,
                )
            except DraAmbiguousOutcome:
                self._store.write_receipt(
                    "review-ambiguous.json",
                    DraMutationAmbiguousReceiptV1(
                        intent_sha256=review.intent_sha256,
                        attempt_id=review.promotion.attempt_id,
                        stage="review",
                        parent_receipt=self._store.write_receipt(
                            "promotion.json", stored
                        ),
                        mutation_key=review_key,
                        request_sha256=review_request_sha256,
                        target_identity_sha256=self._target_hash(
                            "review", task.planning_run_id
                        ),
                        permitted_next_command="review",
                    ),
                )
                recorded = await authority.get_review(
                    context, review.case_id, task.planning_run_id, review_key
                )
                if recorded is None:
                    recorded = await authority.record_review(
                        context,
                        review.case_id,
                        review.expected_case_revision,
                        task.planning_run_id,
                        review.eligible_route_ids,
                        review_key,
                    )
        if (
            recorded.planning_run_id != task.planning_run_id
            or recorded.eligible_route_ids != review.eligible_route_ids
            or recorded.case_id != review.case_id
            or recorded.expected_case_revision != review.expected_case_revision
            or recorded.action != "approve_for_consultation"
            or recorded.request_sha256 != review_request_sha256
        ):
            raise ValueError("advisor_review_projection_invalid")
        receipt = DraReviewReceiptV1(
            intent_sha256=review.intent_sha256,
            attempt_id=review.promotion.attempt_id,
            candidate_id=review.candidate_id,
            source_pack_id=review.promoted_source_pack_id,
            source_pack_version=review.promoted_source_pack_version,
            task_key=task_key,
            review_key=review_key,
            task=task,
            review=recorded,
            stage_states=(
                *review.promotion.stage_states,
                DraStageStateV1(stage="review", status="completed"),
            ),
        )
        self._store.write_receipt("review.json", receipt)
        return receipt

    async def decide(self, command: DecideCommand) -> DraDecisionReceiptV1:
        authority = cast(DraClosureGatewayPort, self._authority)
        decision = command.decision
        stored = self._store.read_receipt(
            "review.json", DraReviewReceiptV1
        )
        if stored != decision.review:
            raise ValueError("decision_review_receipt_invalid")
        context = command.context
        if (
            context.role not in {ActorRole.PARENT, ActorRole.STUDENT}
            or context.organization_id != decision.organization_id
            or derive_identity_hash("actor", str(context.actor_id))
            != decision.family_actor_identity_sha256
            or derive_identity_hash("tenant", str(context.organization_id))
            != decision.tenant_identity_sha256
        ):
            raise ValueError("decision_actor_invalid")
        decision_key = derive_stage_key(
            decision.intent_sha256, "family-decision", str(decision.brief_id)
        )
        decision_request_sha256 = canonical_request_sha256(
            {
                "brief_id": str(decision.brief_id),
                "expected_brief_version": decision.expected_brief_version,
                "selected_route_id": str(decision.selected_route_id),
                "accepted_budget_min_minor": decision.accepted_budget_min_minor,
                "accepted_budget_max_minor": decision.accepted_budget_max_minor,
                "currency": "CNY",
                "accepted_trade_offs": list(decision.accepted_trade_offs),
            }
        )
        recorded = await authority.get_decision(
            context, decision.brief_id
        )
        if recorded is None:
            try:
                recorded = await authority.record_decision(
                    context,
                    decision.brief_id,
                    decision.expected_brief_version,
                    decision.selected_route_id,
                    decision.accepted_budget_min_minor,
                    decision.accepted_budget_max_minor,
                    decision.accepted_trade_offs,
                    decision_key,
                )
            except DraAmbiguousOutcome:
                self._store.write_receipt(
                    "decision-ambiguous.json",
                    DraMutationAmbiguousReceiptV1(
                        intent_sha256=decision.intent_sha256,
                        attempt_id=decision.review.attempt_id,
                        stage="decide",
                        parent_receipt=self._store.write_receipt(
                            "review.json", stored
                        ),
                        mutation_key=decision_key,
                        request_sha256=decision_request_sha256,
                        target_identity_sha256=self._target_hash(
                            "decide", decision.brief_id
                        ),
                        permitted_next_command="decide",
                    ),
                )
                recorded = await authority.get_decision(
                    context, decision.brief_id
                )
                if recorded is None:
                    recorded = await authority.record_decision(
                        context,
                        decision.brief_id,
                        decision.expected_brief_version,
                        decision.selected_route_id,
                        decision.accepted_budget_min_minor,
                        decision.accepted_budget_max_minor,
                        decision.accepted_trade_offs,
                        decision_key,
                    )
        if (
            recorded.brief_id != decision.brief_id
            or recorded.selected_route_id != decision.selected_route_id
            or recorded.expected_brief_version != decision.expected_brief_version
            or recorded.accepted_budget_min_minor
            != decision.accepted_budget_min_minor
            or recorded.accepted_budget_max_minor
            != decision.accepted_budget_max_minor
            or recorded.currency != "CNY"
            or recorded.accepted_trade_offs != decision.accepted_trade_offs
            or recorded.request_sha256 != decision_request_sha256
        ):
            raise ValueError("family_decision_projection_invalid")
        receipt = DraDecisionReceiptV1(
            intent_sha256=decision.intent_sha256,
            attempt_id=decision.review.attempt_id,
            decision_key=decision_key,
            review_id=decision.review.review.review_id,
            planning_run_id=decision.review.task.planning_run_id,
            decision=recorded,
            stage_states=(
                *decision.review.stage_states,
                DraStageStateV1(stage="decide", status="completed"),
            ),
        )
        self._store.write_receipt("decision.json", receipt)
        return receipt


class DraLiveCaptureController:
    def __init__(
        self,
        transport: DraLiveTransportPort,
        candidate_gateway: (
            DraCandidateGatewayPort | DraStrictCandidateGatewayPort
        ),
        store: LiveReceiptStore,
        *,
        clock: DraLiveClockPort | None = None,
        sleeper: DraLiveSleepPort | None = None,
        strict_scenario: DraLiveScenarioV2 | None = None,
    ) -> None:
        self._transport = transport
        self._candidate_gateway = candidate_gateway
        self._store = store
        self._clock = clock or _SystemClock()
        self._sleeper = sleeper or _AsyncioSleeper()
        self._strict_scenario = strict_scenario
        self._observed_profile: DraObservedProfileManifestV1 | None = None

    def _strict_identity(self, intent: CaptureIntent) -> DraStrictConsumerIdentityV2 | None:
        if isinstance(intent, DraCaptureIntentV3):
            return intent.capture.consumer_identity
        scenario = self._strict_scenario
        if scenario is None:
            return None
        return DraStrictConsumerIdentityV2(
            schema_version="night-voyager.dra-strict-consumer-identity.v2",
            producer=scenario.producer,
            request=DraRunRequestIdentityV2(
                schema_version="night-voyager.dra-run-request-identity.v2",
                profile_id=scenario.producer.profile_id,
                request_sha256=intent.capture.request.effective_sha256,
            ),
            observed_profile=scenario.profile_manifest,
        )

    async def _load_strict_profile(self, intent: CaptureIntent) -> DraObservedProfileManifestV1:
        identity = self._strict_identity(intent)
        if identity is None:
            raise ValueError("dra_strict_identity_required")
        observed = await self._transport.get_profile(identity.producer.profile_id)
        if observed != identity.observed_profile:
            raise ValueError("dra_strict_profile_identity_invalid")
        self._observed_profile = observed
        return observed

    def _strict_request_identity(self, intent: CaptureIntent) -> DraRunRequestIdentityV2:
        identity = self._strict_identity(intent)
        if identity is None:
            raise ValueError("dra_strict_identity_required")
        return identity.request

    def preflight(self, intent: CaptureIntent) -> PreflightReceipt:
        if isinstance(intent, DraCaptureIntentV3):
            capture = intent.capture
            readiness = self._store.read_receipt(
                "readiness.json",
                DraLiveCandidateReadinessV4,
            )
            readiness_identity = self._store.write_receipt(
                "readiness.json",
                readiness,
            )
            if (
                readiness_identity.sha256 != capture.candidate_readiness_sha256
                or readiness.consumer_identity != capture.consumer_identity
                or readiness.evidence_bundle != capture.readiness_evidence
            ):
                raise ValueError("candidate_readiness_identity_invalid")
            intent_receipt = self._store.write_receipt("intent.json", intent)
            receipt = DraPreflightReceiptV3(
                intent_sha256=intent.intent_sha256,
                attempt_id=intent.attempt_id,
                intent_receipt=intent_receipt,
                candidate_readiness_receipt=readiness_identity,
                effective_request_sha256=capture.request.effective_sha256,
                scenario_id=capture.scenario_id,
                consumer_identity=capture.consumer_identity,
                readiness_evidence=capture.readiness_evidence,
                advisor_actor_identity_sha256=(capture.advisor_actor_identity_sha256),
                tenant_identity_sha256=capture.tenant_identity_sha256,
                receipt_root_id=capture.receipt_root_id,
            )
            self._store.write_receipt("preflight.json", receipt)
            return receipt
        capture = intent.capture
        readiness = self._store.read_receipt(
            "readiness.json",
            DraCandidateReadinessReceiptV2,
        )
        readiness_identity = self._store.write_receipt(
            "readiness.json",
            readiness,
        )
        if (
            readiness_identity.sha256 != capture.candidate_readiness_sha256
            or readiness.request != capture.request
            or readiness.producer != capture.producer
        ):
            raise ValueError("candidate_readiness_identity_invalid")
        intent_receipt = self._store.write_receipt("intent.json", intent)
        receipt = DraPreflightReceiptV2(
            intent_sha256=intent.intent_sha256,
            attempt_id=intent.attempt_id,
            intent_receipt=intent_receipt,
            candidate_readiness_receipt=readiness_identity,
            effective_request_sha256=capture.request.effective_sha256,
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
        intent: CaptureIntent,
        preflight: PreflightReceipt,
    ) -> DraReceiptIdentityV1:
        if isinstance(intent, DraCaptureIntentV3):
            if not isinstance(preflight, DraPreflightReceiptV3):
                raise ValueError("preflight_identity_invalid")
            stored_intent = self._store.read_receipt("intent.json", DraCaptureIntentV3)
            stored_preflight = self._store.read_receipt("preflight.json", DraPreflightReceiptV3)
            readiness = self._store.read_receipt("readiness.json", DraLiveCandidateReadinessV4)
            readiness_identity = self._store.write_receipt("readiness.json", readiness)
            if (
                stored_intent != intent
                or stored_preflight != preflight
                or preflight.intent_sha256 != intent.intent_sha256
                or preflight.attempt_id != intent.attempt_id
                or preflight.candidate_readiness_receipt != readiness_identity
                or readiness_identity.sha256 != intent.capture.candidate_readiness_sha256
                or readiness.consumer_identity != intent.capture.consumer_identity
                or readiness.evidence_bundle != intent.capture.readiness_evidence
                or preflight.consumer_identity != intent.capture.consumer_identity
                or preflight.readiness_evidence != intent.capture.readiness_evidence
                or preflight.effective_request_sha256 != intent.capture.request.effective_sha256
            ):
                raise ValueError("preflight_identity_invalid")
            return self._store.write_receipt("preflight.json", preflight)
        if not isinstance(preflight, DraPreflightReceiptV2):
            raise ValueError("preflight_identity_invalid")
        stored_intent = self._store.read_receipt("intent.json", DraCaptureIntentV2)
        stored_preflight = self._store.read_receipt(
            "preflight.json",
            DraPreflightReceiptV2,
        )
        readiness = self._store.read_receipt(
            "readiness.json",
            DraCandidateReadinessReceiptV2,
        )
        readiness_identity = self._store.write_receipt(
            "readiness.json",
            readiness,
        )
        if (
            stored_intent != intent
            or stored_preflight != preflight
            or preflight.intent_sha256 != intent.intent_sha256
            or preflight.attempt_id != intent.attempt_id
            or preflight.candidate_readiness_receipt != readiness_identity
            or readiness_identity.sha256
            != intent.capture.candidate_readiness_sha256
            or readiness.request != intent.capture.request
            or preflight.effective_request_sha256
            != intent.capture.request.effective_sha256
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
                or metadata.st_size != expected.base_byte_length
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
        try:
            effective = validate_effective_query_v2(encoded, expected)
            return effective.decode("utf-8", errors="strict")
        except (UnicodeDecodeError, ValueError) as error:
            raise ValueError("request_identity_mismatch") from error

    def _stop(
        self,
        intent: CaptureIntent,
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
            profile_id = "generic"
            strict_identity = self._strict_identity(command.intent)
            if strict_identity is not None:
                await self._load_strict_profile(command.intent)
                profile_id = strict_identity.producer.profile_id
            acceptance = await self._transport.create_run(
                {"profile_id": profile_id, "query": query},
                create_key,
            )
        except DraAmbiguousOutcome:
            if isinstance(command.intent, DraCaptureIntentV3):
                receipt: DraReconciliationRequiredReceiptV1 | DraReconciliationRequiredReceiptV2 = (
                    DraReconciliationRequiredReceiptV2(
                        intent_sha256=command.intent.intent_sha256,
                        attempt_id=command.intent.attempt_id,
                        intent_receipt=command.preflight.intent_receipt,
                        consumer_identity=command.intent.capture.consumer_identity,
                        readiness_evidence=command.intent.capture.readiness_evidence,
                        create_key=create_key,
                        provider_attempt_consumed=True,
                    )
                )
            else:
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
                (
                    DraReconciliationRequiredReceiptV2
                    if isinstance(command.intent, DraCaptureIntentV3)
                    else DraReconciliationRequiredReceiptV1
                ),
            )
        except LiveStorageError as error:
            raise ValueError("reconciliation_identity_invalid") from error
        if (
            stored_prior != command.prior
            or command.prior.intent_sha256 != command.intent.intent_sha256
            or command.prior.attempt_id != command.intent.attempt_id
            or command.prior.create_key != expected_key
            or command.prior.intent_receipt != command.preflight.intent_receipt
            or (
                isinstance(command.intent, DraCaptureIntentV3)
                and (
                    not isinstance(
                        command.prior,
                        DraReconciliationRequiredReceiptV2,
                    )
                    or command.prior.consumer_identity != command.intent.capture.consumer_identity
                    or command.prior.readiness_evidence != command.intent.capture.readiness_evidence
                )
            )
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
            profile_id = "generic"
            strict_identity = self._strict_identity(command.intent)
            if strict_identity is not None:
                await self._load_strict_profile(command.intent)
                profile_id = strict_identity.producer.profile_id
            acceptance = await self._transport.create_run(
                {"profile_id": profile_id, "query": query},
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
        intent: CaptureIntent,
        preflight_identity: DraReceiptIdentityV1,
        acceptance: DraRunAcceptanceV1,
    ) -> CaptureResult:
        last_state_version = 0
        deadline = self._clock.monotonic() + intent.capture.deadline_seconds
        while True:
            try:
                strict_identity = self._strict_identity(intent)
                if strict_identity is None:
                    run: (
                        DraLiveRunEnvelopeV1
                        | DraStrictLiveRunEnvelopeV2
                    ) = await self._transport.get_run(acceptance.run_id)
                else:
                    run = await self._transport.get_strict_run(
                        acceptance.run_id
                    )
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
                if strict_identity is None:
                    if not isinstance(run, DraLiveRunEnvelopeV1):
                        raise DraLiveContractError(
                            "terminal_profile_invalid"
                        )
                    projection: (
                        DraTerminalProjectionV1
                        | DraStrictTerminalProjectionV2
                    ) = project_terminal_result(acceptance, run, result)
                else:
                    if not isinstance(run, DraStrictLiveRunEnvelopeV2):
                        raise DraLiveContractError("terminal_profile_invalid")
                    observed = self._observed_profile or await self._load_strict_profile(intent)
                    projection = project_strict_terminal_result(
                        acceptance,
                        run,
                        result,
                        strict_identity.producer,
                        self._strict_request_identity(intent),
                        observed,
                    )
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
            if isinstance(intent, DraCaptureIntentV3):
                receipt: DraInspectionRequiredReceiptV1 | DraInspectionRequiredReceiptV2 = (
                    DraInspectionRequiredReceiptV2(
                        intent_sha256=intent.intent_sha256,
                        attempt_id=intent.attempt_id,
                        preflight_receipt=preflight_identity,
                        consumer_identity=intent.capture.consumer_identity,
                        readiness_evidence=intent.capture.readiness_evidence,
                        case_id=intent.capture.case_id,
                        expected_case_revision=intent.capture.expected_case_revision,
                        advisor_actor_identity_sha256=(
                            intent.capture.advisor_actor_identity_sha256
                        ),
                        tenant_identity_sha256=(intent.capture.tenant_identity_sha256),
                        thread_id=acceptance.thread_id,
                        run_id=acceptance.run_id,
                        segment_id=acceptance.segment_id,
                        state_version=projection.state_version,
                        acceptance_idempotent_replay=(acceptance.idempotent_replay),
                        artifact=artifact_identity,
                        evidence=run.evidence,
                        provider_attempt_consumed=True,
                    )
                )
            else:
                receipt = DraInspectionRequiredReceiptV1(
                    intent_sha256=intent.intent_sha256,
                    attempt_id=intent.attempt_id,
                    preflight_receipt=preflight_identity,
                    producer=intent.capture.producer,
                    case_id=intent.capture.case_id,
                    expected_case_revision=(intent.capture.expected_case_revision),
                    advisor_actor_identity_sha256=(intent.capture.advisor_actor_identity_sha256),
                    tenant_identity_sha256=(intent.capture.tenant_identity_sha256),
                    thread_id=acceptance.thread_id,
                    run_id=acceptance.run_id,
                    segment_id=acceptance.segment_id,
                    state_version=projection.state_version,
                    acceptance_idempotent_replay=(acceptance.idempotent_replay),
                    artifact=artifact_identity,
                    evidence=run.evidence,
                    provider_attempt_consumed=True,
                )
            self._store.write_receipt("inspection-required.json", receipt)
            return receipt
        if isinstance(intent, DraCaptureIntentV3):
            recovery_receipt: DraPollRecoveryReceiptV1 | DraPollRecoveryReceiptV2 = (
                DraPollRecoveryReceiptV2(
                    intent_sha256=intent.intent_sha256,
                    attempt_id=intent.attempt_id,
                    preflight_receipt=preflight_identity,
                    consumer_identity=intent.capture.consumer_identity,
                    readiness_evidence=intent.capture.readiness_evidence,
                    thread_id=acceptance.thread_id,
                    run_id=acceptance.run_id,
                    segment_id=acceptance.segment_id,
                    last_state_version=last_state_version,
                    provider_attempt_consumed=True,
                )
            )
        else:
            recovery_receipt = DraPollRecoveryReceiptV1(
                intent_sha256=intent.intent_sha256,
                attempt_id=intent.attempt_id,
                preflight_receipt=preflight_identity,
                thread_id=acceptance.thread_id,
                run_id=acceptance.run_id,
                segment_id=acceptance.segment_id,
                last_state_version=last_state_version,
                provider_attempt_consumed=True,
            )
        self._store.write_receipt("poll-recovery.json", recovery_receipt)
        return recovery_receipt

    async def resume_poll(self, command: ResumePollCommand) -> CaptureResult:
        prior = command.prior
        try:
            stored_prior = self._store.read_receipt(
                "poll-recovery.json",
                (
                    DraPollRecoveryReceiptV2
                    if isinstance(command.intent, DraCaptureIntentV3)
                    else DraPollRecoveryReceiptV1
                ),
            )
            stored_preflight = self._store.read_receipt(
                "preflight.json",
                (
                    DraPreflightReceiptV3
                    if isinstance(command.intent, DraCaptureIntentV3)
                    else DraPreflightReceiptV2
                ),
            )
            preflight_identity = self._validate_preflight(command.intent, stored_preflight)
        except (LiveStorageError, ValueError) as error:
            raise ValueError("poll_recovery_identity_invalid") from error
        if (
            stored_prior != prior
            or prior.intent_sha256 != command.intent.intent_sha256
            or prior.attempt_id != command.intent.attempt_id
            or prior.preflight_receipt != preflight_identity
            or (
                isinstance(command.intent, DraCaptureIntentV3)
                and (
                    not isinstance(prior, DraPollRecoveryReceiptV2)
                    or prior.consumer_identity != command.intent.capture.consumer_identity
                    or prior.readiness_evidence != command.intent.capture.readiness_evidence
                )
            )
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
    ) -> DraCaptureReceiptV1 | DraCaptureReceiptV2 | DraControllerStopReceiptV1:
        intent = command.intent
        inspection = command.inspection
        capture = intent.capture
        try:
            stored = self._store.read_receipt(
                "inspection-required.json",
                (
                    DraInspectionRequiredReceiptV2
                    if isinstance(intent, DraCaptureIntentV3)
                    else DraInspectionRequiredReceiptV1
                ),
            )
            if (
                stored != inspection
                or inspection.intent_sha256 != intent.intent_sha256
                or inspection.attempt_id != intent.attempt_id
                or (
                    isinstance(intent, DraCaptureIntentV3)
                    and (
                        not isinstance(inspection, DraInspectionRequiredReceiptV2)
                        or inspection.consumer_identity != intent.capture.consumer_identity
                        or inspection.readiness_evidence != intent.capture.readiness_evidence
                    )
                )
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
            strict_identity = self._strict_identity(intent)
            if strict_identity is None:
                selected = select_cited_evidence(projection, command.declared_raw_url)
            else:
                strict_projection = DraStrictTerminalProjectionV2(
                    **projection.model_dump(exclude_computed_fields=True),
                    consumer_identity=strict_identity,
                )
                selected = select_strict_cited_evidence(
                    strict_projection, command.declared_raw_url
                )
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

        acceptance = DraRunAcceptanceV1(
            thread_id=inspection.thread_id,
            run_id=inspection.run_id,
            segment_id=inspection.segment_id,
            idempotent_replay=inspection.acceptance_idempotent_replay,
        )
        run_projection = DraRunProjectionV1(
            run_id=inspection.run_id,
            state_version=inspection.state_version,
            execution_status="completed",
            review_status="not_required",
            delivery_status="ready",
        )
        evidence = (
            DraEvidenceProjectionV1(
                evidence_id=selected.evidence_id,
                source_url=selected.source_url,
                source_identity=selected.source_identity,
                retrieved_at=selected.retrieved_at,
                citation_status=selected.citation_status,
                verification_status=selected.verification_status,
            ),
        )
        candidate_import: DraCandidateImportV1 | DraCandidateImportV2
        strict_identity = self._strict_identity(intent)
        if strict_identity is None:
            if isinstance(intent, DraCaptureIntentV3):
                raise AssertionError("strict intent identity unavailable")
            legacy_capture = intent.capture
            candidate_import = DraCandidateImportV1(
                schema_version="night-voyager.dra-candidate-import.v1",
                organization_id=legacy_capture.organization_id,
                case_id=legacy_capture.case_id,
                expected_case_revision=(legacy_capture.expected_case_revision),
                producer=legacy_capture.producer.pin,
                request_identity=DraRunRequestIdentityV1(
                    profile_id="generic",
                    request_sha256=(legacy_capture.request.effective_sha256),
                ),
                acceptance=acceptance,
                run=run_projection,
                artifact=projection.artifact,
                evidence=evidence,
            )
        else:
            candidate_import = DraCandidateImportV2(
                schema_version="night-voyager.dra-candidate-import.v2",
                organization_id=capture.organization_id,
                case_id=capture.case_id,
                expected_case_revision=capture.expected_case_revision,
                consumer_identity=strict_identity,
                acceptance=acceptance,
                run=run_projection,
                artifact=projection.artifact,
                evidence=evidence,
            )
        import_key = derive_stage_key(
            intent.intent_sha256,
            "candidate-import",
            str(capture.case_id),
        )
        try:
            if isinstance(candidate_import, DraCandidateImportV1):
                gateway = cast(
                    DraCandidateGatewayPort, self._candidate_gateway
                )
                view = await gateway.import_candidate(
                    command.context,
                    candidate_import,
                    import_key,
                )
            else:
                strict_gateway = cast(
                    DraStrictCandidateGatewayPort,
                    self._candidate_gateway,
                )
                view = await strict_gateway.import_strict_candidate(
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
        provider_attempt_evidence = DraProviderAttemptEvidenceV1(
            create_keys=(
                derive_stage_key(
                    intent.intent_sha256,
                    "create",
                    intent.attempt_id,
                ),
            ),
            observed_run_ids=(inspection.run_id,),
            accepted_run_id=inspection.run_id,
        )
        if isinstance(intent, DraCaptureIntentV3):
            receipt: DraCaptureReceiptV1 | DraCaptureReceiptV2 = DraCaptureReceiptV2(
                intent_sha256=intent.intent_sha256,
                attempt_id=intent.attempt_id,
                consumer_identity=intent.capture.consumer_identity,
                readiness_evidence=intent.capture.readiness_evidence,
                run_id=inspection.run_id,
                segment_id=inspection.segment_id,
                artifact=inspection.artifact,
                selected_evidence=selected,
                stage_states=(DraStageStateV1(stage="capture-live", status="completed"),),
                provider_attempt_consumed=True,
                provider_attempt_evidence=provider_attempt_evidence,
                candidate_id=view.candidate_id,
                candidate_authority="untrusted_candidate",
                candidate_import_key=import_key,
                cleanup_status=cleanup_status,
            )
        else:
            legacy_capture = intent.capture
            receipt = DraCaptureReceiptV1(
                schema_version=("night-voyager.dra-live-capture-receipt.v1"),
                intent_sha256=intent.intent_sha256,
                attempt_id=intent.attempt_id,
                producer=legacy_capture.producer,
                run_id=inspection.run_id,
                segment_id=inspection.segment_id,
                artifact=inspection.artifact,
                selected_evidence=selected,
                stage_states=(DraStageStateV1(stage="capture-live", status="completed"),),
                provider_attempt_consumed=True,
                provider_attempt_evidence=provider_attempt_evidence,
                candidate_id=view.candidate_id,
                candidate_authority="untrusted_candidate",
                candidate_import_key=import_key,
                cleanup_status=cleanup_status,
            )
        self._store.write_receipt("capture.json", receipt)
        return receipt
