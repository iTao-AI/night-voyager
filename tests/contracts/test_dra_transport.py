from __future__ import annotations

import json
import tomllib
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from night_voyager.adapters.dra_readonly import (
    DraClientConfig,
    DraOutputLimitExceeded,
    Httpx2DraTransport,
)

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
            "state_version": 1,
            "execution_status": "completed",
            "review_status": "not_required",
            "delivery_status": "ready",
            "private_additive_field": "/" + "Users/private/provider-payload",
        }
    )
    run_transport = Httpx2DraTransport(
        DraClientConfig(base_url="http://127.0.0.1:8000", poll_seconds=1, deadline_seconds=30),
        environ={},
        client_factory=run_factory,
    )
    run = await run_transport.get_run("run-1")
    assert run.disposition == "canonical_ready"
    assert "private_additive_field" not in run.model_dump()

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
