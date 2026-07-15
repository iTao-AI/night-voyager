from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from night_voyager.dra.models import (
    DraCanonicalResultProjectionV1,
    DraRunStateProjectionV1,
)
from night_voyager.identity.demo_seed import CONNECTED_DEMO_CASE_ID, DRA_PROOF_CASE_ID
from scripts import verify_dra_consumer

ROOT = Path(__file__).parents[3]


def run_verifier(*arguments: str, environment: dict[str, str] | None = None):
    return subprocess.run(
        [sys.executable, "scripts/verify_dra_consumer.py", *arguments],
        cwd=ROOT,
        env={"PATH": os.environ["PATH"], **(environment or {})},
        text=True,
        capture_output=True,
        check=False,
    )


def test_dra_proof_case_is_dedicated() -> None:
    assert DRA_PROOF_CASE_ID != CONNECTED_DEMO_CASE_ID
    assert str(DRA_PROOF_CASE_ID) not in (ROOT / "fixtures/m3a/manifest.json").read_text()


def test_fixture_mode_is_offline_and_emits_exact_pins() -> None:
    result = run_verifier("fixture", "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "verified"
    assert payload["mode"] == "fixture"
    assert payload["fixture_sha256"] == (
        "cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157"
    )
    assert payload["source_sha256"] == (
        "87e314e801dca1aeaf9b751c149c53629a4cf23ee04698939fdc87def5a90a13"
    )


def test_live_mode_fails_before_transport_without_exact_authorization() -> None:
    result = run_verifier("live", "--json")
    assert result.returncode != 0
    assert "dra_live_proof_not_authorized" in result.stderr
    assert "Traceback" not in result.stderr


def test_live_source_validation_is_root_bounded_and_hash_pinned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.html"
    source.write_text("public fixture", encoding="utf-8")
    monkeypatch.setenv("DRA_SOURCE_ROOT", str(tmp_path))
    monkeypatch.setenv("DRA_SOURCE_LOGICAL_PATH", "source.html")
    monkeypatch.setenv(
        "DRA_SOURCE_SHA256", hashlib.sha256(source.read_bytes()).hexdigest()
    )
    verify_dra_consumer.validate_live_source()

    monkeypatch.setenv("DRA_SOURCE_LOGICAL_PATH", "../source.html")
    with pytest.raises(SystemExit, match="dra_live_source_invalid"):
        verify_dra_consumer.validate_live_source()


def test_live_authority_requires_separate_advisor_attestation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DRA_LIVE_PROOF_ACK", verify_dra_consumer.LIVE_ACK)
    with pytest.raises(SystemExit, match="dra_live_proof_not_authorized"):
        verify_dra_consumer.required_environment()


def test_make_and_ci_keep_live_proof_out_of_required_gates() -> None:
    makefile = (ROOT / "Makefile").read_text()
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "dra-check:" in makefile
    assert "dra-consumer-proof:" in makefile
    assert "$(MAKE) dra-check" in makefile
    assert "make dra-check" in workflow
    assert "dra-consumer-proof" not in workflow


def test_public_docs_close_pr1_without_claiming_mixed_planning() -> None:
    reference = (ROOT / "docs/reference/dra-governed-evidence.md").read_text()
    runbook = (ROOT / "docs/operations/dra-consumer-proof.md").read_text()
    assert "candidate import and atomic human verification/promotion are implemented" in reference
    assert "governed mixed PlanningRun is not implemented" in reference
    assert "separately-authorized-one-attempt" in runbook
    assert "live provider proof is not a required CI gate" in runbook


def test_main_normalizes_unexpected_live_errors_without_private_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        verify_dra_consumer,
        "parse_args",
        lambda: type("Args", (), {"mode": "live", "json": True})(),
    )

    def fail_without_awaiting(coroutine: object) -> None:
        coroutine.close()  # type: ignore[attr-defined]
        raise RuntimeError("/" + "Users/private raw-provider-value credential-value")

    monkeypatch.setattr(verify_dra_consumer.asyncio, "run", fail_without_awaiting)
    with pytest.raises(SystemExit):
        verify_dra_consumer.main()
    captured = capsys.readouterr()
    assert captured.err.strip() == "dra_live_proof_failed"
    assert captured.out == ""


class FakeLiveTransport:
    def __init__(
        self,
        runs: list[DraRunStateProjectionV1 | Exception],
        result: DraCanonicalResultProjectionV1 | Exception,
    ) -> None:
        self.runs = runs
        self.result = result
        self.result_calls = 0

    async def get_run(self, run_id: str) -> DraRunStateProjectionV1:
        _ = run_id
        value = self.runs.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    async def get_result(self, run_id: str) -> DraCanonicalResultProjectionV1:
        _ = run_id
        self.result_calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def run_state(execution: str, review: str, delivery: str) -> DraRunStateProjectionV1:
    return DraRunStateProjectionV1.model_validate(
        {
            "run_id": "run-1",
            "state_version": 1,
            "execution_status": execution,
            "review_status": review,
            "delivery_status": delivery,
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("execution", "review", "delivery"),
    [
        ("failed", "not_required", "failed"),
        ("completed", "not_required", "blocked"),
        ("completed", "required", "review_required"),
    ],
)
async def test_polling_fails_immediately_for_terminal_invalid_states(
    execution: str, review: str, delivery: str
) -> None:
    transport = FakeLiveTransport([run_state(execution, review, delivery)], RuntimeError())
    with pytest.raises(SystemExit, match="dra_live_run_terminal_invalid"):
        await verify_dra_consumer.poll_canonical_result(
            transport, "run-1", deadline=30, poll_seconds=0
        )
    assert transport.result_calls == 0


@pytest.mark.asyncio
async def test_polling_timeout_is_bounded() -> None:
    transport = FakeLiveTransport(
        [run_state("running", "not_required", "pending")], RuntimeError()
    )
    clock = iter((0.0, 2.0))
    with pytest.raises(SystemExit, match="dra_poll_deadline_exceeded"):
        await verify_dra_consumer.poll_canonical_result(
            transport,
            "run-1",
            deadline=1,
            poll_seconds=0,
            monotonic=lambda: next(clock),
            sleep=lambda _seconds: _completed_sleep(),
        )


async def _completed_sleep() -> object:
    return None


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [ValueError("raw payload"), TypeError("bad artifact")])
async def test_polling_normalizes_malformed_run_or_result(failure: Exception) -> None:
    ready = run_state("completed", "not_required", "ready")
    transport = (
        FakeLiveTransport([failure], RuntimeError())
        if isinstance(failure, ValueError)
        else FakeLiveTransport([ready], failure)
    )
    expected = (
        "dra_live_run_terminal_invalid"
        if isinstance(failure, ValueError)
        else "dra_live_result_invalid"
    )
    with pytest.raises(SystemExit, match=expected):
        await verify_dra_consumer.poll_canonical_result(
            transport, "run-1", deadline=30, poll_seconds=0
        )


@pytest.mark.asyncio
async def test_polling_returns_only_validated_canonical_result() -> None:
    result = DraCanonicalResultProjectionV1.model_validate(
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
        }
    )
    transport = FakeLiveTransport(
        [run_state("completed", "not_required", "ready")], result
    )
    assert await verify_dra_consumer.poll_canonical_result(
        transport, "run-1", deadline=30, poll_seconds=0
    ) == result


@pytest.mark.asyncio
async def test_polling_rejects_canonical_state_from_a_different_run() -> None:
    result = DraCanonicalResultProjectionV1.model_validate(
        {
            "run_id": "expected-run",
            "execution_status": "completed",
            "delivery_status": "ready",
            "artifact": {
                "artifact_id": "research-report.md",
                "kind": "research_report_markdown",
                "media_type": "text/markdown",
                "content": "safe",
                "content_hash": (
                    "8b3369944dd2a3fab39e32d1aeb1f763946a458ae3e6368a46432adc8f3a0860"
                ),
            },
        }
    )
    wrong_run = run_state("completed", "not_required", "ready").model_copy(
        update={"run_id": "wrong-run"}
    )
    transport = FakeLiveTransport([wrong_run], result)

    with pytest.raises(SystemExit, match="dra_live_run_terminal_invalid"):
        await verify_dra_consumer.poll_canonical_result(
            transport, "expected-run", deadline=30, poll_seconds=0
        )
    assert transport.result_calls == 0
