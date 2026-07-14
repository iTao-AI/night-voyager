from __future__ import annotations

import argparse
import hashlib
import json
import runpy
import subprocess
import sys
import zipfile
from collections.abc import Callable
from datetime import date
from pathlib import Path
from types import FunctionType
from typing import cast

import pytest

pytest.importorskip("mcp")

pytestmark = pytest.mark.mke
REPOSITORY = Path(__file__).parents[3]
VERIFIER = runpy.run_path(str(REPOSITORY / "scripts" / "verify_mke_consumer.py"))
PROOF_STAGES = cast(tuple[str, ...], VERIFIER["PROOF_STAGES"])
proof_failure_payload = cast(Callable[[str], dict[str, str]], VERIFIER["proof_failure_payload"])


def synthetic_candidate(tmp_path: Path) -> tuple[Path, Path, Path]:
    from night_voyager.evidence.candidate_lock import (
        CandidateArtifactReceiptV1,
        canonical_sha256,
        lock_from_receipt,
    )

    wheel = tmp_path / "multimodal_knowledge_engine-0.1.1-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            "multimodal_knowledge_engine-0.1.1.dist-info/METADATA",
            "Metadata-Version: 2.4\nName: multimodal-knowledge-engine\nVersion: 0.1.1\n"
            "Requires-Python: >=3.12,<3.14\n",
        )
        archive.writestr(
            "multimodal_knowledge_engine-0.1.1.dist-info/entry_points.txt",
            "[console_scripts]\nmke = mke.cli:console_main\n",
        )
    wheel_sha256 = hashlib.sha256(wheel.read_bytes()).hexdigest()
    payload: dict[str, object] = {
        "schema_version": "mke.candidate_artifact_receipt.v1",
        "repository": "iTao-AI/multimodal-knowledge-engine",
        "source_commit": "1" * 40,
        "package_name": "multimodal-knowledge-engine",
        "package_version": "0.1.1",
        "wheel_filename": wheel.name,
        "wheel_bytes": wheel.stat().st_size,
        "wheel_sha256": wheel_sha256,
        "requires_python": ">=3.12,<3.14",
        "consumer_proof_schema": "mke.consumer_source_pack_proof.v1",
        "consumer_proof_status": "passed",
        "proof_input_wheel_sha256": wheel_sha256,
    }
    payload["receipt_sha256"] = canonical_sha256(payload)
    receipt = CandidateArtifactReceiptV1.model_validate(payload)
    receipt_path = tmp_path / "candidate-artifact-receipt.json"
    receipt_path.write_text(receipt.model_dump_json(), encoding="utf-8")
    lock = lock_from_receipt(
        receipt, artifact_locator="operator_supplied", reviewed_at=date(2026, 7, 14)
    )
    lock_path = tmp_path / "candidate-artifact-lock.json"
    lock_path.write_text(lock.model_dump_json(), encoding="utf-8")
    return wheel, receipt_path, lock_path


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


def test_proof_installs_controller_owned_bytes_after_operator_path_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wheel, receipt_path, lock_path = synthetic_candidate(tmp_path)
    expected_sha256 = hashlib.sha256(wheel.read_bytes()).hexdigest()
    installed_sha256: str | None = None

    def capture_stage(command: list[str], *, stage: str, code: str) -> None:
        nonlocal installed_sha256
        del code
        if stage == "wheel_install":
            installed_sha256 = hashlib.sha256(Path(command[-1]).read_bytes()).hexdigest()

    async def fake_reads(*args: object, **kwargs: object) -> dict[str, object]:
        del args, kwargs
        return {
            "source_count": 1,
            "active_publication_count": 1,
            "active_evidence_count": 1,
            "observation_state": "active",
            "identity_verified": True,
            "contracts_verified": True,
            "mapping_verified": True,
            "pairing_verified": True,
            "proof_pack_no_match": True,
            "redaction_verified": True,
        }

    run_proof_callable = cast(FunctionType, VERIFIER["run_proof"])
    run_proof_globals = cast(dict[str, object], run_proof_callable.__globals__)
    real_stage = cast(Callable[..., object], run_proof_globals["stage_candidate_artifact"])

    def stage_then_replace(*args: object, **kwargs: object) -> object:
        verified = real_stage(*args, **kwargs)
        wheel.write_bytes(b"replacement wheel bytes")
        return verified

    monkeypatch.setitem(run_proof_globals, "LOCK_PATH", lock_path)
    monkeypatch.setitem(run_proof_globals, "stage_candidate_artifact", stage_then_replace)
    monkeypatch.setitem(run_proof_globals, "_run_stage", capture_stage)
    monkeypatch.setitem(run_proof_globals, "_run_reads", fake_reads)

    receipt = cast(Callable[[argparse.Namespace], dict[str, object]], VERIFIER["run_proof"])(
        argparse.Namespace(wheel=wheel, candidate_receipt=receipt_path)
    )

    assert installed_sha256 == expected_sha256
    assert receipt["mke_wheel_sha256"] == installed_sha256
