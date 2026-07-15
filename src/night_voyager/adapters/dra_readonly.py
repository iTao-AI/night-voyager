"""Optional loopback-only Decision Research Agent REST transport."""

from __future__ import annotations

import ipaddress
import json
from collections.abc import Callable, Mapping
from typing import Any, cast
from urllib.parse import urlsplit

import httpx2
from pydantic import BaseModel, ConfigDict, Field, model_validator

from night_voyager.dra.models import (
    DraHealthProjectionV1,
    DraRunAcceptanceV1,
)
from night_voyager.dra.reconciliation import (
    DraAmbiguousOutcome,
    DraTransportConflict,
    DraTransportError,
)


class DraOutputLimitExceeded(DraTransportError):
    code = "dra_response_limit"


class DraClientConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    base_url: str
    poll_seconds: float = Field(gt=0, le=60)
    deadline_seconds: float = Field(gt=0, le=3600)
    response_bytes: int = Field(default=1_048_576, gt=0, le=1_048_576)

    @model_validator(mode="after")
    def loopback_origin_only(self) -> DraClientConfig:
        parsed = urlsplit(self.base_url)
        try:
            host = parsed.hostname
            port = parsed.port
        except ValueError as error:
            raise ValueError("dra_base_url_invalid") from error
        if (
            parsed.scheme != "http"
            or host is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or port is None
        ):
            raise ValueError("dra_base_url_invalid")
        try:
            if not ipaddress.ip_address(host).is_loopback:
                raise ValueError("dra_base_url_invalid")
        except ValueError as error:
            if str(error) == "dra_base_url_invalid":
                raise
            if host != "localhost":
                raise ValueError("dra_base_url_invalid") from error
        return self


ClientFactory = Callable[..., Any]


class Httpx2DraTransport:
    def __init__(
        self,
        config: DraClientConfig,
        *,
        environ: Mapping[str, str],
        client_factory: ClientFactory = httpx2.AsyncClient,
    ) -> None:
        self._config = config
        self._api_key = environ.get("DECISION_RESEARCH_AGENT_API_KEY", "")
        self._client_factory = client_factory

    def __repr__(self) -> str:
        return f"Httpx2DraTransport(base_url={self._config.base_url!r})"

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, object] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, object]:
        try:
            client = self._client_factory(
                base_url=self._config.base_url,
                trust_env=False,
                follow_redirects=False,
                timeout=self._config.deadline_seconds,
            )
            async with client, client.stream(
                method,
                path,
                json=dict(payload) if payload is not None else None,
                headers=self._headers(idempotency_key),
            ) as response:
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > self._config.response_bytes:
                        raise DraOutputLimitExceeded()
                if response.status_code == 409:
                    raise DraTransportConflict()
                if not 200 <= response.status_code < 300:
                    raise DraTransportError()
        except (DraOutputLimitExceeded, DraTransportConflict):
            raise
        except (httpx2.TimeoutException, httpx2.NetworkError) as error:
            raise DraAmbiguousOutcome() from error
        except DraTransportError:
            raise
        except Exception as error:
            raise DraTransportError() from error
        try:
            value = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DraTransportError() from error
        if not isinstance(value, dict):
            raise DraTransportError()
        return cast(dict[str, object], value)

    async def health(self) -> DraHealthProjectionV1:
        payload = await self._request_json("GET", "/api/health")
        return DraHealthProjectionV1.model_validate(payload)

    async def create_run(
        self, request: Mapping[str, object], idempotency_key: str
    ) -> DraRunAcceptanceV1:
        payload = await self._request_json(
            "POST",
            "/api/runs",
            payload=request,
            idempotency_key=idempotency_key,
        )
        return DraRunAcceptanceV1.model_validate(
            {
                field: payload.get(field)
                for field in ("thread_id", "run_id", "segment_id", "idempotent_replay")
            }
        )
