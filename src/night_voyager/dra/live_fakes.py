from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from night_voyager.dra.application import DraCandidateService
from night_voyager.dra.fixtures import build_fixture_candidate_import
from night_voyager.dra.live_models import (
    DraLiveRunEnvelopeV1,
    DraLiveScenarioV1,
)
from night_voyager.dra.models import (
    DraCandidateImportV1,
    DraCanonicalResultProjectionV1,
    DraHealthProjectionV1,
    DraRunAcceptanceV1,
)
from night_voyager.dra.ports import (
    DraCandidateViewV1,
    DraVerificationViewV1,
    ImportDraCandidateCommand,
    PromotionIdentities,
    VerifyDraCandidateCommand,
)
from night_voyager.dra.reconciliation import (
    DraAmbiguousOutcome,
    DraTransportConflict,
)
from night_voyager.identity.models import ActorContext

CANDIDATE_ID = UUID("90000000-0000-0000-0000-000000000001")


class ScenarioDraLiveTransport:
    def __init__(
        self,
        scenario: DraLiveScenarioV1,
        *,
        ambiguous_create_once: bool = False,
        in_progress_polls: int = 0,
    ) -> None:
        self._scenario = scenario
        self.run = DraLiveRunEnvelopeV1.model_validate(
            scenario.status.model_dump(mode="json")
            | {
                "evidence": [
                    row.model_dump(mode="json") for row in scenario.evidence
                ]
            }
        )
        fixture_artifact = build_fixture_candidate_import().artifact
        if (
            fixture_artifact.content_hash != scenario.result.artifact.sha256
            or fixture_artifact.byte_length != scenario.result.artifact.byte_length
        ):
            raise ValueError("dra_live_fake_artifact_identity_mismatch")
        self.result = DraCanonicalResultProjectionV1(
            run_id=scenario.result.run_id,
            execution_status=scenario.result.execution_status,
            delivery_status=scenario.result.delivery_status,
            artifact=fixture_artifact,
        )
        self.create_calls = 0
        self.health_calls = 0
        self.create_keys: list[str] = []
        self.requests: list[dict[str, object]] = []
        self._ambiguous_create_once = ambiguous_create_once
        self._in_progress_polls = in_progress_polls
        self._accepted_key: str | None = None
        self._accepted_request: dict[str, object] | None = None

    async def health(self) -> DraHealthProjectionV1:
        self.health_calls += 1
        return DraHealthProjectionV1(
            status="ok", service="decision-research-agent"
        )

    async def create_run(
        self, request: Mapping[str, object], idempotency_key: str
    ) -> DraRunAcceptanceV1:
        self.create_calls += 1
        frozen_request = dict(request)
        self.create_keys.append(idempotency_key)
        self.requests.append(frozen_request)
        if self._accepted_key is None:
            self._accepted_key = idempotency_key
            self._accepted_request = frozen_request
            if self._ambiguous_create_once:
                self._ambiguous_create_once = False
                raise DraAmbiguousOutcome()
            replay = False
        elif (
            self._accepted_key != idempotency_key
            or self._accepted_request != frozen_request
        ):
            raise DraTransportConflict()
        else:
            replay = True
        return DraRunAcceptanceV1(
            thread_id=self.run.thread_id,
            run_id=self.run.run_id,
            segment_id=self.run.segment_id,
            idempotent_replay=replay,
        )

    async def get_run(self, run_id: str) -> DraLiveRunEnvelopeV1:
        if run_id != self.run.run_id:
            raise ValueError("dra_live_fake_run_identity_invalid")
        if self._in_progress_polls > 0:
            self._in_progress_polls -= 1
            return self.run.model_copy(
                update={
                    "state_version": 0,
                    "execution_status": "running",
                    "review_status": "not_required",
                    "delivery_status": "pending",
                }
            )
        return self.run

    async def get_result(self, run_id: str) -> DraCanonicalResultProjectionV1:
        if run_id != self.result.run_id:
            raise ValueError("dra_live_fake_run_identity_invalid")
        return self.result


class _ScenarioCandidateRepository:
    def __init__(self) -> None:
        self.imported: ImportDraCandidateCommand | None = None

    async def import_candidate(
        self,
        context: ActorContext,
        command: ImportDraCandidateCommand,
        candidate_id: UUID,
        idempotency_key: str,
    ) -> DraCandidateViewV1:
        del context, idempotency_key
        self.imported = command
        return DraCandidateViewV1(
            candidate_id=candidate_id,
            verification=None,
        )

    async def get_candidate(
        self,
        context: ActorContext,
        case_id: UUID,
        candidate_id: UUID,
    ) -> DraCandidateViewV1 | None:
        del context, case_id
        return DraCandidateViewV1(
            candidate_id=candidate_id,
            verification=None,
        )

    async def verify_and_promote(
        self,
        context: ActorContext,
        command: VerifyDraCandidateCommand,
        identities: PromotionIdentities,
        idempotency_key: str,
    ) -> DraVerificationViewV1:
        del context, command, identities, idempotency_key
        raise AssertionError("promotion is outside Stage 1")


class ScenarioCandidateGateway:
    def __init__(self) -> None:
        self._repository = _ScenarioCandidateRepository()
        self._service = DraCandidateService(
            self._repository,
            id_factory=lambda: CANDIDATE_ID,
        )
        self.import_calls = 0
        self.last_view: DraCandidateViewV1 | None = None
        self.last_import: DraCandidateImportV1 | None = None

    async def import_candidate(
        self,
        context: ActorContext,
        candidate_import: DraCandidateImportV1,
        idempotency_key: str,
    ) -> DraCandidateViewV1:
        self.import_calls += 1
        self.last_import = candidate_import
        self.last_view = await self._service.import_candidate(
            context,
            candidate_import,
            idempotency_key,
        )
        return self.last_view
