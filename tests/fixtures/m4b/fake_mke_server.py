#!/usr/bin/env python3
"""Scenario-driven fake MCP server for the isolated M4B adapter lane."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

SCENARIO = sys.argv[1]
FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "m4b" / "responses"
mcp = FastMCP("night-voyager-m4b-fake", log_level="ERROR")

if SCENARIO == "startup_timeout":
    time.sleep(2)
if SCENARIO == "nonzero_exit":
    raise SystemExit(7)


def payload(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@mcp.tool()
def list_libraries_v1() -> dict[str, Any]:
    if SCENARIO == "tool_timeout":
        time.sleep(2)
    if SCENARIO == "malformed":
        return {"ok": True, "schema_version": "wrong"}
    value = payload("list-active.json")
    if SCENARIO == "oversized_response":
        value["padding"] = "x" * 4096
    return value


@mcp.tool()
def search_library_v1(
    query: str, limit: int = 1, optional_hint: str | None = None
) -> dict[str, Any]:
    del optional_hint
    value = payload("search-match.json")
    value["query"] = query
    if SCENARIO == "oversized_text":
        value["results"][0]["text"] = "x" * 1024
    if limit != 1:
        return {"ok": False, "unexpected_limit": limit}
    return value


if SCENARIO != "missing_tool":

    @mcp.tool()
    def ask_library_v1(question: str, limit: int = 1) -> dict[str, Any]:
        value = payload("ask-match.json")
        value["question"] = question
        if limit != 1:
            return {"ok": False, "unexpected_limit": limit}
        return value


if SCENARIO == "stderr_overflow":
    sys.stderr.write("x" * 4096)
    sys.stderr.flush()


if __name__ == "__main__":
    mcp.run(transport="stdio")
    if SCENARIO == "ignore_stdin":
        while True:
            time.sleep(1)
