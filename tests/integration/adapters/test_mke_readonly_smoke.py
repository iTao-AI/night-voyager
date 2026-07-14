from __future__ import annotations

import sys
from contextlib import suppress
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from night_voyager.adapters.mke_readonly import MkeReadOnlyConfig, MkeReadOnlyConsumer
from night_voyager.evidence.mke_models import EvidenceQuery, MkeConsumerError
from night_voyager.planning.models import EvidenceRole

pytestmark = pytest.mark.mke
REPOSITORY = Path(__file__).parents[3]
SERVER = REPOSITORY / "tests" / "fixtures" / "m4b" / "fake_mke_server.py"


def config(tmp_path: Path, scenario: str, **limits: object) -> MkeReadOnlyConfig:
    tmp_path.mkdir(parents=True, exist_ok=True)
    launcher = tmp_path / f"fake-mke-{scenario}"
    launcher.write_text(
        f"#!/bin/sh\nexec {sys.executable!s} {SERVER!s} {scenario!s}\n",
        encoding="utf-8",
    )
    launcher.chmod(0o700)
    values: dict[str, object] = {
        "executable": launcher,
        "database": tmp_path / "mke.sqlite",
        "allowed_root": tmp_path,
        "cwd": REPOSITORY,
        "child_environment": {},
        "startup_timeout_seconds": 5.0,
        "tool_timeout_seconds": 5.0,
        "parsed_response_bytes": 1_048_576,
        "selected_text_bytes": 65_536,
        "stderr_bytes": 65_536,
    }
    values.update(limits)
    return MkeReadOnlyConfig.model_validate(values)


def query() -> EvidenceQuery:
    from uuid import UUID

    return EvidenceQuery(
        schema_version=1,
        organization_id=UUID("11111111-1111-4111-8111-111111111111"),
        source_pack_id=UUID("22222222-2222-4222-8222-222222222222"),
        source_pack_version=1,
        claim="Synthetic Australia program fit requires advisor evidence review.",
        evidence_role=EvidenceRole.PROGRAM_FIT,
        query="synthetic australia program fit advisor evidence review",
        allowed_locator_kinds=("page",),
        limit=1,
    )


@pytest.mark.anyio
async def test_list_search_ask_and_normal_close(tmp_path: Path) -> None:
    consumer = MkeReadOnlyConsumer(config(tmp_path, "normal"))
    listed = await consumer.initialize()
    searched = await consumer.search(query())
    asked = await consumer.ask(query())
    await consumer.aclose()
    assert listed.root.ok is True
    assert searched.root.ok is True
    assert asked.root.ok is True


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("scenario", "expected", "limits"),
    [
        ("missing_tool", "mke_contract_incompatible", {}),
        ("malformed", "mke_response_invalid", {}),
        ("tool_timeout", "mke_tool_timeout", {"tool_timeout_seconds": 0.05}),
        ("stderr_overflow", "mke_output_limit_exceeded", {"stderr_bytes": 32}),
        ("startup_timeout", "mke_startup_timeout", {"startup_timeout_seconds": 0.05}),
        ("oversized_response", "mke_output_limit_exceeded", {"parsed_response_bytes": 128}),
        ("nonzero_exit", "mke_server_exit", {}),
    ],
)
async def test_process_failures_are_closed_and_public(
    tmp_path: Path, scenario: str, expected: str, limits: dict[str, object]
) -> None:
    consumer = MkeReadOnlyConsumer(config(tmp_path, scenario, **limits))
    try:
        with pytest.raises(MkeConsumerError) as captured:
            await consumer.initialize()
        assert captured.value.failure.code == expected
        assert str(tmp_path) not in str(captured.value)
        assert "ev_" not in str(captured.value)
    finally:
        with suppress(MkeConsumerError):
            await consumer.aclose()


@pytest.mark.anyio
async def test_selected_text_bound_and_sdk_termination_fallback(tmp_path: Path) -> None:
    oversized = MkeReadOnlyConsumer(
        config(tmp_path / "oversized", "oversized_text", selected_text_bytes=64)
    )
    await oversized.initialize()
    with pytest.raises(MkeConsumerError) as captured:
        await oversized.search(query())
    assert captured.value.failure.code == "mke_output_limit_exceeded"
    await oversized.aclose()

    stubborn = MkeReadOnlyConsumer(config(tmp_path / "stubborn", "ignore_stdin"))
    await stubborn.initialize()
    await stubborn.aclose()
