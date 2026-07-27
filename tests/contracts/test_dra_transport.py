from __future__ import annotations

import json
import tomllib
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from night_voyager.adapters.dra_readonly import (
    DraClientConfig,
    DraOutputLimitExceeded,
    Httpx2DraTransport,
)
from night_voyager.dra.fixtures import load_strict_live_closure_scenario
from night_voyager.dra.live_http import (
    EphemeralHttpAuthority,
    NightVoyagerAuthorityGateway,
)
from night_voyager.dra.models import (
    DraCandidateImportV2,
    DraEvidenceProjectionV1,
    DraObservedProfileManifestV1,
    DraRunAcceptanceV1,
    DraRunProjectionV1,
    DraStrictConsumerIdentityV2,
)
from night_voyager.identity.models import ActorContext, ActorRole

ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize(
    "url",
    (
        "https://example.com",
        "http://127.0.0.1:8000/path",
        "http://user@127.0.0.1:8000",
        "http://127.0.0.1:8000?x=1",
        "http://127.0.0.1:8000#fragment",
        "http://0.0.0.0:8000",
    ),
)
def test_dra_base_url_is_loopback_origin_only(url: str) -> None:
    with pytest.raises(ValueError, match="dra_base_url_invalid"):
        DraClientConfig(base_url=url, poll_seconds=1, deadline_seconds=30)


def test_loopback_ipv4_and_ipv6_origins_are_allowed() -> None:
    assert str(
        DraClientConfig(
            base_url="http://127.0.0.1:8000", poll_seconds=1, deadline_seconds=30
        ).base_url
    ) == "http://127.0.0.1:8000"
    assert str(
        DraClientConfig(
            base_url="http://[::1]:8000", poll_seconds=1, deadline_seconds=30
        ).base_url
    ) == "http://[::1]:8000"


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.status_code = 200
        self._body = json.dumps(payload).encode()

    async def aiter_bytes(self) -> AsyncIterator[bytes]:
        yield self._body


class StreamContext:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    async def __aenter__(self) -> FakeResponse:
        return self.response

    async def __aexit__(self, *args: object) -> None:
        return None


class FakeClient:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def stream(self, method: str, path: str, **kwargs: Any) -> StreamContext:
        self.calls.append((method, path, kwargs))
        return StreamContext(FakeResponse(self.payload))


class CapturingFactory:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.kwargs: dict[str, Any] = {}
        self.client = FakeClient(payload)

    def __call__(self, **kwargs: Any) -> FakeClient:
        self.kwargs = kwargs
        return self.client


class AuthorityResponse:
    status_code = 201

    def json(self) -> object:
        return {
            "schema_version": 1,
            "candidate_id": "90000000-0000-0000-0000-000000000001",
            "verification": None,
            "replayed": False,
        }

    def raise_for_status(self) -> None:
        return None


class AuthorityClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: object,
    ) -> AuthorityResponse:
        assert isinstance(json, dict)
        self.calls.append((url, {"headers": headers, "json": json}))
        return AuthorityResponse()


@pytest.mark.asyncio
async def test_transport_disables_environment_and_redirects_and_redacts_key() -> None:
    factory = CapturingFactory(
        {"status": "ok", "service": "decision-research-agent"}
    )
    secret = "synthetic-secret-value"
    transport = Httpx2DraTransport(
        DraClientConfig(
            base_url="http://127.0.0.1:8000",
            poll_seconds=1,
            deadline_seconds=30,
        ),
        environ={"DECISION_RESEARCH_AGENT_API_KEY": secret},
        client_factory=factory,
    )
    health = await transport.health()
    assert health.status == "ok"
    assert factory.client.calls[0][:2] == ("GET", "/health")
    assert factory.client.calls[0][1] != "/api/health"
    assert factory.kwargs["trust_env"] is False
    assert factory.kwargs["follow_redirects"] is False
    assert secret not in repr(transport)
    headers = factory.client.calls[0][2]["headers"]
    assert headers == {"X-API-Key": secret}


@pytest.mark.asyncio
async def test_transport_enforces_bounded_stream_read() -> None:
    factory = CapturingFactory({"value": "x" * 200})
    transport = Httpx2DraTransport(
        DraClientConfig(
            base_url="http://127.0.0.1:8000",
            poll_seconds=1,
            deadline_seconds=30,
            response_bytes=32,
        ),
        environ={},
        client_factory=factory,
    )
    with pytest.raises(DraOutputLimitExceeded, match="dra_response_limit"):
        await transport.health()


@pytest.mark.asyncio
async def test_transport_exposes_bounded_allowlisted_run_and_result_projections() -> None:
    run_factory = CapturingFactory(
        {
            "run_id": "run-1",
            "thread_id": "thread-1",
            "profile_id": "generic",
            "state_version": 1,
            "execution_status": "completed",
            "review_status": "not_required",
            "delivery_status": "ready",
            "failure_cause": None,
            "segments": [
                {
                    "segment_id": "segment-1",
                    "run_id": "run-1",
                    "kind": "initial",
                    "sequence": 0,
                }
            ],
            "evidence": [
                {
                    "evidence_id": "evidence-1",
                    "run_id": "run-1",
                    "segment_id": "segment-1",
                    "source_url": "https://example.com/%7Esource?b=2&a=1#raw",
                    "source_identity": "https://example.com/%7Esource?b=2&a=1#raw",
                    "retrieved_at": "2026-07-25T00:00:00Z",
                    "citation_status": "cited",
                    "verification_status": "unverified",
                    "snippet": "discarded",
                }
            ],
            "private_additive_field": "/" + "Users/private/provider-payload",
        }
    )
    run_transport = Httpx2DraTransport(
        DraClientConfig(base_url="http://127.0.0.1:8000", poll_seconds=1, deadline_seconds=30),
        environ={},
        client_factory=run_factory,
    )
    run = await run_transport.get_run("run-1")
    assert run.segment_id == "segment-1"
    assert run.evidence[0].source_url == (
        "https://example.com/%7Esource?b=2&a=1#raw"
    )
    assert "private_additive_field" not in run.model_dump()
    assert "snippet" not in run.evidence[0].model_dump()
    assert run_factory.client.calls[0][:2] == ("GET", "/api/runs/run-1")

    result_factory = CapturingFactory(
        {
            "run_id": "run-1",
            "execution_status": "completed",
            "delivery_status": "ready",
            "artifact": {
                "artifact_id": "research-report.md",
                "kind": "research_report_markdown",
                "media_type": "text/markdown",
                "content": "safe",
                "content_hash": "8b3369944dd2a3fab39e32d1aeb1f763946a458ae3e6368a46432adc8f3a0860",
            },
            "raw": "discarded",
        }
    )
    result_transport = Httpx2DraTransport(
        DraClientConfig(base_url="http://127.0.0.1:8000", poll_seconds=1, deadline_seconds=30),
        environ={},
        client_factory=result_factory,
    )
    result = await result_transport.get_result("run-1")
    assert result.artifact.content == "safe"
    assert "raw" not in result.model_dump()
    assert result_factory.client.calls[0][:2] == (
        "GET",
        "/api/runs/run-1/result",
    )


@pytest.mark.asyncio
async def test_transport_reads_only_exact_strict_profile_manifest() -> None:
    factory = CapturingFactory(
        {
            "profile": {
                "profile_id": "generic-strict-citation",
                "version": "1",
                "private_additive_field": "discarded",
            }
        }
    )
    transport = Httpx2DraTransport(
        DraClientConfig(
            base_url="http://127.0.0.1:8000",
            poll_seconds=1,
            deadline_seconds=30,
        ),
        environ={},
        client_factory=factory,
    )
    observed = await transport.get_profile("generic-strict-citation")
    assert observed == DraObservedProfileManifestV1(
        schema_version="night-voyager.dra-observed-profile-manifest.v1",
        profile_id="generic-strict-citation",
        profile_version="1",
    )
    assert factory.client.calls[0][:2] == (
        "GET",
        "/api/profiles/generic-strict-citation",
    )
    with pytest.raises(ValueError, match="dra_profile_id_invalid"):
        await transport.get_profile("generic")

    wrong_version = Httpx2DraTransport(
        DraClientConfig(
            base_url="http://127.0.0.1:8000",
            poll_seconds=1,
            deadline_seconds=30,
        ),
        environ={},
        client_factory=CapturingFactory(
            {
                "profile": {
                    "profile_id": "generic-strict-citation",
                    "version": "2",
                }
            }
        ),
    )
    with pytest.raises(ValueError):
        await wrong_version.get_profile("generic-strict-citation")


@pytest.mark.asyncio
async def test_night_voyager_gateway_transports_actual_v2_candidate() -> None:
    scenario = load_strict_live_closure_scenario()
    evidence = scenario.evidence[0]
    candidate = DraCandidateImportV2(
        schema_version="night-voyager.dra-candidate-import.v2",
        organization_id=UUID(
            "10000000-0000-0000-0000-000000000001"
        ),
        case_id=UUID("40000000-0000-0000-0000-000000000003"),
        expected_case_revision=1,
        consumer_identity=DraStrictConsumerIdentityV2(
            schema_version=(
                "night-voyager.dra-strict-consumer-identity.v2"
            ),
            producer=scenario.producer,
            request=scenario.request_identity,
            observed_profile=scenario.profile_manifest,
        ),
        acceptance=DraRunAcceptanceV1(
            thread_id=scenario.status.thread_id,
            run_id=scenario.status.run_id,
            segment_id=scenario.status.segment_id,
            idempotent_replay=False,
        ),
        run=DraRunProjectionV1(
            run_id=scenario.status.run_id,
            state_version=scenario.status.state_version,
            execution_status="completed",
            review_status="not_required",
            delivery_status="ready",
        ),
        artifact=scenario.canonical_artifact,
        evidence=(
            DraEvidenceProjectionV1(
                evidence_id=evidence.evidence_id,
                source_url=evidence.source_url,
                source_identity=evidence.source_identity,
                retrieved_at=evidence.retrieved_at,
                citation_status="cited",
                verification_status=evidence.verification_status,
            ),
        ),
    )
    client = AuthorityClient()
    gateway = NightVoyagerAuthorityGateway(
        client,
        EphemeralHttpAuthority(
            origin="http://127.0.0.1:3000",
            session_value="synthetic-session",
            csrf_value="synthetic-csrf",
        ),
    )
    context = ActorContext(
        organization_id=candidate.organization_id,
        actor_id=UUID("20000000-0000-0000-0000-000000000001"),
        role=ActorRole.ADVISOR,
        session_id=UUID("30000000-0000-0000-0000-000000000001"),
    )
    result = await gateway.import_strict_candidate(
        context, candidate, "strict-gateway-key-0001"
    )
    assert result.candidate_id == UUID(
        "90000000-0000-0000-0000-000000000001"
    )
    assert client.calls[0][0] == (
        f"/api/v1/cases/{candidate.case_id}/dra-candidates"
    )
    sent = client.calls[0][1]["json"]
    assert isinstance(sent, dict)
    assert sent["schema_version"] == "night-voyager.dra-candidate-import.v2"
    assert "organization_id" not in sent
    assert "case_id" not in sent


@pytest.mark.asyncio
async def test_transport_rejects_status_segment_ownership_mismatch() -> None:
    factory = CapturingFactory(
        {
            "run_id": "run-1",
            "thread_id": "thread-1",
            "profile_id": "generic",
            "state_version": 1,
            "execution_status": "completed",
            "review_status": "not_required",
            "delivery_status": "ready",
            "failure_cause": None,
            "segments": [{"segment_id": "segment-1", "run_id": "wrong-run"}],
            "evidence": [
                {
                    "evidence_id": "evidence-1",
                    "run_id": "run-1",
                    "segment_id": "segment-1",
                    "source_url": "https://example.com/source",
                    "source_identity": "https://example.com/source",
                    "retrieved_at": "2026-07-25T00:00:00Z",
                    "citation_status": "cited",
                    "verification_status": "unverified",
                }
            ],
        }
    )
    transport = Httpx2DraTransport(
        DraClientConfig(
            base_url="http://127.0.0.1:8000",
            poll_seconds=1,
            deadline_seconds=30,
        ),
        environ={},
        client_factory=factory,
    )
    with pytest.raises(RuntimeError, match="dra_transport_failed"):
        await transport.get_run("run-1")


def test_api_key_cannot_be_passed_in_config() -> None:
    with pytest.raises(ValueError):
        DraClientConfig.model_validate(
            {
                "base_url": "http://127.0.0.1:8000",
                "poll_seconds": 1,
                "deadline_seconds": 30,
                "api_key": "not-allowed",
            }
        )


def test_dra_transport_is_an_exact_optional_release_contract() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    verifier = (ROOT / "scripts/verify_release.py").read_text(encoding="utf-8")
    assert pyproject["project"]["optional-dependencies"]["dra"] == [
        "httpx2>=2.5,<2.6"
    ]
    locked = {
        package["name"]: package.get("version") for package in lock["package"]
    }
    assert locked["httpx2"] == "2.5.0"
    assert 'optional_dependencies.get("dra")' in verifier
    assert '\\"httpx2\\" not in sys.modules' in verifier
