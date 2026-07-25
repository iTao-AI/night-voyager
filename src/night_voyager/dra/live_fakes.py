from __future__ import annotations

from collections.abc import Mapping

from night_voyager.dra.fixtures import build_fixture_candidate_import
from night_voyager.dra.live_models import (
    DraLiveRunEnvelopeV1,
    DraLiveScenarioV1,
)
from night_voyager.dra.models import (
    DraCanonicalResultProjectionV1,
    DraHealthProjectionV1,
    DraRunAcceptanceV1,
)


class ScenarioDraLiveTransport:
    def __init__(self, scenario: DraLiveScenarioV1) -> None:
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

    async def health(self) -> DraHealthProjectionV1:
        return DraHealthProjectionV1(
            status="ok", service="decision-research-agent"
        )

    async def create_run(
        self, request: Mapping[str, object], idempotency_key: str
    ) -> DraRunAcceptanceV1:
        del request, idempotency_key
        self.create_calls += 1
        return DraRunAcceptanceV1(
            thread_id=self.run.thread_id,
            run_id=self.run.run_id,
            segment_id=self.run.segment_id,
            idempotent_replay=False,
        )

    async def get_run(self, run_id: str) -> DraLiveRunEnvelopeV1:
        if run_id != self.run.run_id:
            raise ValueError("dra_live_fake_run_identity_invalid")
        return self.run

    async def get_result(self, run_id: str) -> DraCanonicalResultProjectionV1:
        if run_id != self.result.run_id:
            raise ValueError("dra_live_fake_run_identity_invalid")
        return self.result
