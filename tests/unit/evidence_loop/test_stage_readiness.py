from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from night_voyager.evidence_loop.models import (
    StageReadinessCandidateV1,
    StageReadinessContractV1,
    StageReadinessReceiptV1,
)

ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = ROOT / "tests/fixtures/evidence_loop/stage-contracts"


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
        required_checks=("python", "frontend"),
        check_urls=("https://github.com/example/check/1", "https://github.com/example/check/2"),
        next_stage_unlock="candidate-authority",
        non_claims=("source_truth", "production_deployment"),
    )
    assert candidate.stage == "slice0"
    with pytest.raises(ValidationError):
        StageReadinessReceiptV1.model_validate(candidate.model_dump())


def test_stage_contract_rejects_unknown_fields() -> None:
    payload = json.loads(
        (CONTRACTS / "slice0-v1.json").read_text(encoding="utf-8")
    )
    payload["generic_framework"] = True
    with pytest.raises(ValidationError):
        StageReadinessContractV1.model_validate(payload)
