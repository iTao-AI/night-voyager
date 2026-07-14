"""Official MCP SDK stdio adapter for the optional read-only MKE lane."""

from __future__ import annotations

import asyncio
import json
import tempfile
from contextlib import AsyncExitStack
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import McpError
from mcp.types import CallToolResult, TextContent, Tool
from pydantic import BaseModel, ConfigDict, Field

from night_voyager.evidence.mke_contract import (
    AskLibraryResponseV1,
    ListLibrariesResponseV1,
    SearchLibraryResponseV1,
)
from night_voyager.evidence.mke_models import EvidenceQuery, MkeConsumerError


class MkeReadOnlyConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    executable: Path
    database: Path
    allowed_root: Path
    cwd: Path
    child_environment: dict[str, str]
    startup_timeout_seconds: float = Field(gt=0, le=60)
    tool_timeout_seconds: float = Field(gt=0, le=60)
    parsed_response_bytes: int = Field(gt=0, le=1_048_576)
    selected_text_bytes: int = Field(gt=0, le=1_048_576)
    stderr_bytes: int = Field(gt=0, le=65_536)


class MkeReadOnlyConsumer:
    def __init__(self, config: MkeReadOnlyConfig) -> None:
        self._config = config
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._stderr = tempfile.TemporaryFile(  # noqa: SIM115 - closed with async stack
            mode="w+", encoding="utf-8"
        )

    def _parameters(self) -> StdioServerParameters:
        return StdioServerParameters(
            command=str(self._config.executable),
            args=[
                "--db",
                str(self._config.database),
                "mcp",
                "--allowed-root",
                str(self._config.allowed_root),
            ],
            env=dict(self._config.child_environment),
            cwd=self._config.cwd,
        )

    async def initialize(self) -> ListLibrariesResponseV1:
        if self._session is not None:
            return await self._call_list()
        stack = AsyncExitStack()
        self._stack = stack
        try:
            streams = await stack.enter_async_context(
                stdio_client(self._parameters(), errlog=self._stderr)
            )
            session = await stack.enter_async_context(
                ClientSession(
                    streams[0],
                    streams[1],
                    read_timeout_seconds=timedelta(
                        seconds=self._config.startup_timeout_seconds
                    ),
                )
            )
            await asyncio.wait_for(
                session.initialize(), timeout=self._config.startup_timeout_seconds
            )
            tools = await asyncio.wait_for(
                session.list_tools(), timeout=self._config.startup_timeout_seconds
            )
            self._validate_tools(tools.tools)
            self._session = session
            self._check_stderr()
            return await self._call_list()
        except TimeoutError as error:
            await self._close_after_failure()
            raise MkeConsumerError("mke_startup_timeout") from error
        except MkeConsumerError:
            await self._close_after_failure()
            raise
        except McpError as error:
            await self._close_after_failure()
            raise MkeConsumerError("mke_server_exit") from error
        except Exception as error:
            await self._close_after_failure()
            raise MkeConsumerError("mke_transport_failed") from error

    @staticmethod
    def _validate_tools(tools: list[Tool]) -> None:
        by_name = {tool.name: tool for tool in tools}
        requirements: dict[str, set[str]] = {
            "list_libraries_v1": set(),
            "search_library_v1": {"query"},
            "ask_library_v1": {"question"},
        }
        for name, required in requirements.items():
            tool = by_name.get(name)
            if tool is None:
                raise MkeConsumerError("mke_contract_incompatible")
            schema_required = set(tool.inputSchema.get("required", []))
            properties = set(tool.inputSchema.get("properties", {}))
            if schema_required != required or not required.issubset(properties):
                raise MkeConsumerError("mke_contract_incompatible")
            if name != "list_libraries_v1" and "limit" not in properties:
                raise MkeConsumerError("mke_contract_incompatible")

    async def _call(self, name: str, arguments: dict[str, Any]) -> CallToolResult:
        if self._session is None:
            raise MkeConsumerError("mke_consumer_failed")
        try:
            result = await asyncio.wait_for(
                self._session.call_tool(
                    name,
                    arguments,
                    read_timeout_seconds=timedelta(
                        seconds=self._config.tool_timeout_seconds
                    ),
                ),
                timeout=self._config.tool_timeout_seconds,
            )
        except TimeoutError as error:
            raise MkeConsumerError("mke_tool_timeout") from error
        except McpError as error:
            code = getattr(error.error, "code", None)
            if code == 408:
                raise MkeConsumerError("mke_tool_timeout") from error
            raise MkeConsumerError("mke_transport_failed") from error
        except Exception as error:
            raise MkeConsumerError("mke_transport_failed") from error
        self._check_stderr()
        if result.isError:
            raise MkeConsumerError("mke_response_invalid")
        return result

    def _payload(self, result: CallToolResult) -> dict[str, Any]:
        value: object = result.structuredContent
        if value is None:
            texts = [item.text for item in result.content if isinstance(item, TextContent)]
            if len(texts) != 1:
                raise MkeConsumerError("mke_response_invalid")
            try:
                value = json.loads(texts[0])
            except json.JSONDecodeError as error:
                raise MkeConsumerError("mke_response_invalid") from error
        try:
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
        except (TypeError, ValueError) as error:
            raise MkeConsumerError("mke_response_invalid") from error
        if len(encoded) > self._config.parsed_response_bytes or not isinstance(value, dict):
            raise MkeConsumerError("mke_output_limit_exceeded")
        return cast(dict[str, Any], value)

    def _check_selected_text(self, payload: dict[str, Any]) -> None:
        raw_evidence = payload.get("results", payload.get("evidence", []))
        if not isinstance(raw_evidence, list):
            return
        total = 0
        for raw_item in cast(list[object], raw_evidence):
            if not isinstance(raw_item, dict):
                continue
            item = cast(dict[str, object], raw_item)
            text = item.get("text")
            if isinstance(text, str):
                size = len(text.encode("utf-8"))
                if size > self._config.selected_text_bytes:
                    raise MkeConsumerError("mke_output_limit_exceeded")
                total += size
        if total > self._config.parsed_response_bytes:
            raise MkeConsumerError("mke_output_limit_exceeded")

    async def _call_list(self) -> ListLibrariesResponseV1:
        result = await self._call("list_libraries_v1", {})
        try:
            return ListLibrariesResponseV1.model_validate(self._payload(result))
        except ValueError as error:
            raise MkeConsumerError("mke_response_invalid") from error

    async def search(self, query: EvidenceQuery) -> SearchLibraryResponseV1:
        result = await self._call(
            "search_library_v1", {"query": query.query, "limit": 1}
        )
        payload = self._payload(result)
        self._check_selected_text(payload)
        try:
            return SearchLibraryResponseV1.model_validate(payload)
        except ValueError as error:
            raise MkeConsumerError("mke_response_invalid") from error

    async def ask(self, query: EvidenceQuery) -> AskLibraryResponseV1:
        result = await self._call(
            "ask_library_v1", {"question": query.query, "limit": 1}
        )
        payload = self._payload(result)
        self._check_selected_text(payload)
        try:
            return AskLibraryResponseV1.model_validate(payload)
        except ValueError as error:
            raise MkeConsumerError("mke_response_invalid") from error

    def _check_stderr(self) -> None:
        self._stderr.flush()
        self._stderr.seek(0, 2)
        if self._stderr.tell() > self._config.stderr_bytes:
            raise MkeConsumerError("mke_output_limit_exceeded")

    async def _close_after_failure(self) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        stack, self._stack = self._stack, None
        self._session = None
        if stack is None:
            return
        try:
            await stack.aclose()
        except Exception as error:
            raise MkeConsumerError("mke_cleanup_failed") from error
        finally:
            self._stderr.close()
