from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from night_voyager.identity.demo_seed import CONNECTED_DEMO_CASE_ID, DRA_PROOF_CASE_ID

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
