from __future__ import annotations

import json
import runpy
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

pytest.importorskip("mcp")

pytestmark = pytest.mark.mke
REPOSITORY = Path(__file__).parents[3]
VERIFIER = runpy.run_path(str(REPOSITORY / "scripts" / "verify_mke_consumer.py"))
PROOF_STAGES = cast(tuple[str, ...], VERIFIER["PROOF_STAGES"])
proof_failure_payload = cast(Callable[[str], dict[str, str]], VERIFIER["proof_failure_payload"])


def test_proof_stage_sequence_is_stable() -> None:
    assert PROOF_STAGES == (
        "artifact_verify",
        "env_create",
        "wheel_install",
        "store_setup",
        "initialize",
        "discover",
        "search",
        "ask",
        "cleanup",
    )


@pytest.mark.parametrize(
    "code",
    [
        "mke_candidate_inputs_missing",
        "mke_candidate_mismatch",
        "mke_install_failed",
        "mke_store_setup_failed",
        "mke_contract_incompatible",
        "mke_response_invalid",
        "mke_active_store_no_match",
        "mke_snapshot_pair_mismatch",
        "mke_cleanup_failed",
        "mke_consumer_failed",
    ],
)
def test_failure_payload_is_exact_and_redacted(code: str) -> None:
    assert proof_failure_payload(code) == {
        "schema_version": "night_voyager.m4b_proof.v1",
        "status": "failed",
        "code": code,
    }
    rendered = json.dumps(proof_failure_payload(code), sort_keys=True)
    assert "/" + "Users/" not in rendered
    assert "ev_" not in rendered


def test_cli_missing_inputs_fails_with_one_public_json(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/verify_mke_consumer.py",
            "proof",
            "--wheel",
            str(tmp_path / "missing.whl"),
            "--candidate-receipt",
            str(tmp_path / "missing.json"),
            "--json",
        ],
        cwd=REPOSITORY,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout) == proof_failure_payload("mke_candidate_inputs_missing")
    assert "FAILED CHECK" in result.stderr
    assert str(tmp_path) not in result.stderr
