from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from night_voyager.evidence_loop import freeze as freeze_module
from night_voyager.evidence_loop.models import (
    StageReadinessCandidateV1,
    StageReadinessContractV1,
    StageReadinessReceiptV1,
)

ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = ROOT / "tests/fixtures/evidence_loop/stage-contracts"


def test_stage_contracts_bind_predecessors_and_exact_hosted_contexts() -> None:
    expected_checks = ("python", "frontend", "compose")
    expected_predecessors = {
        "slice0": None,
        "candidate-authority": "slice0",
        "candidate-journey": "candidate-authority",
        "composition-authority": "candidate-journey",
        "composition-journey": "composition-authority",
    }
    contracts = [
        StageReadinessContractV1.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(CONTRACTS.glob("*.json"))
    ]

    for contract in contracts:
        assert contract.required_hosted_checks == expected_checks
        assert contract.predecessor_stage == expected_predecessors[contract.stage]


@pytest.mark.parametrize(
    "path",
    ("a/../../outside.json", "a//b.json", "a/./b.json", "/tmp/outside.json", "a\\b.json"),
)
def test_stage_contract_rejects_noncanonical_or_traversing_proof_path(path: str) -> None:
    payload = json.loads((CONTRACTS / "slice0-v1.json").read_text(encoding="utf-8"))
    payload["proof_path"] = path
    with pytest.raises(ValidationError):
        StageReadinessContractV1.model_validate(payload)


def test_all_stage_contracts_are_closed_and_unique() -> None:
    contracts = [
        StageReadinessContractV1.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(CONTRACTS.glob("*.json"))
    ]
    assert len(contracts) == 5
    assert len({contract.stage for contract in contracts}) == 5
    assert contracts[0].schema_version == "night-voyager.stage-readiness-contract.v1"


def test_candidate_is_not_a_merged_receipt() -> None:
    candidate = StageReadinessCandidateV1(
        schema_version="night-voyager.stage-readiness-candidate.v1",
        stage="slice0",
        reviewed_head="a" * 40,
        reviewed_tree="b" * 40,
        proof_path="tests/fixtures/evidence_loop/slice0-receipt-v2.json",
        proof_sha256="c" * 64,
        terminal_disposition="incremental_value_confirmed",
        required_checks=("python", "frontend", "compose"),
        check_urls=(
            "https://github.com/example/check/python",
            "https://github.com/example/check/frontend",
            "https://github.com/example/check/compose",
        ),
        next_stage_unlock="candidate-authority",
        non_claims=("source_truth", "production_deployment"),
    )
    assert candidate.stage == "slice0"
    with pytest.raises(ValidationError):
        StageReadinessReceiptV1.model_validate(candidate.model_dump())


def test_later_stage_candidate_requires_a_legal_complete_predecessor() -> None:
    common = {
        "schema_version": "night-voyager.stage-readiness-candidate.v1",
        "stage": "candidate-authority",
        "reviewed_head": "a" * 40,
        "reviewed_tree": "b" * 40,
        "proof_path": "tests/fixtures/evidence_loop/b1-candidate-authority-proof-v1.json",
        "proof_sha256": "c" * 64,
        "terminal_disposition": "authority_verified",
        "required_checks": ("python", "frontend", "compose"),
        "check_urls": (
            "https://github.com/example/check/python",
            "https://github.com/example/check/frontend",
            "https://github.com/example/check/compose",
        ),
        "next_stage_unlock": "candidate-journey",
        "non_claims": ("source_truth", "production_deployment", "real_user_outcomes"),
    }
    with pytest.raises(ValidationError):
        StageReadinessCandidateV1.model_validate(common)

    complete = {
        **common,
        "predecessor_stage": "slice0",
        "predecessor_merge_commit": "d" * 40,
        "predecessor_merge_tree": "e" * 40,
        "predecessor_receipt_sha256": "f" * 64,
        "predecessor_terminal_disposition": "incremental_value_confirmed",
    }
    candidate = StageReadinessCandidateV1.model_validate(complete)
    assert candidate.predecessor_stage == "slice0"

    with pytest.raises(ValidationError):
        StageReadinessCandidateV1.model_validate(
            {
                **complete,
                "predecessor_terminal_disposition": "evaluation_invalid",
            }
        )


def test_stage_contract_rejects_unknown_fields() -> None:
    payload = json.loads(
        (CONTRACTS / "slice0-v1.json").read_text(encoding="utf-8")
    )
    payload["generic_framework"] = True
    with pytest.raises(ValidationError):
        StageReadinessContractV1.model_validate(payload)


def test_frozen_proof_identity_rejects_a_file_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    link = tmp_path / "proof.json"
    target.write_text("proof\n", encoding="utf-8")
    link.symlink_to(target)
    identity = {
        "byte_length": target.stat().st_size,
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "mode": "0644",
    }

    matches_identity = cast(Any, freeze_module._matches_identity)  # pyright: ignore[reportPrivateUsage]
    assert matches_identity(link, identity) is False


def _load_stage_verifier():
    script = ROOT / "scripts/verify_stage_readiness.py"
    spec = importlib.util.spec_from_file_location("stage_readiness_verifier", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stage_verifier_rejects_a_parent_symlink(tmp_path: Path) -> None:
    module = cast(Any, _load_stage_verifier())
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    real = checkout / "real"
    real.mkdir()
    (real / "proof.json").write_text("proof\n", encoding="utf-8")
    (checkout / "linked").symlink_to(real, target_is_directory=True)
    module.ROOT = checkout

    with pytest.raises(module.VerificationFailure) as raised:
        module._safe_proof_path("linked/proof.json")
    assert raised.value.code == "proof_path_invalid"


def test_stage_verifier_canonicalizes_required_checks_and_rejects_extra() -> None:
    module = _load_stage_verifier()
    names, urls = module._canonical_required_checks(
        [
            {"name": "compose", "bucket": "pass", "link": "https://github.com/c/1"},
            {"name": "python", "bucket": "pass", "link": "https://github.com/p/1"},
            {"name": "frontend", "bucket": "pass", "link": "https://github.com/f/1"},
        ]
    )
    assert names == ("python", "frontend", "compose")
    assert urls == ("https://github.com/p/1", "https://github.com/f/1", "https://github.com/c/1")
    with pytest.raises(module.VerificationFailure) as raised:
        module._canonical_required_checks(
            [
                {"name": "python", "bucket": "pass", "link": "https://github.com/p/1"},
                {"name": "frontend", "bucket": "pass", "link": "https://github.com/f/1"},
                {"name": "compose", "bucket": "pass", "link": "https://github.com/c/1"},
                {"name": "docs", "bucket": "pass", "link": "https://github.com/d/1"},
            ]
        )
    assert raised.value.exit_code == 12
