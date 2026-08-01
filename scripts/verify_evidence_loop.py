#!/usr/bin/env python3
"""Verify one canonical Slice 0 evaluation receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, NoReturn, cast

from night_voyager.evidence_loop.canonicalization import canonical_json_bytes
from night_voyager.evidence_loop.evaluator import (
    evaluate_suite,
    normalize_revealed_dataset,
)
from night_voyager.evidence_loop.freeze import validate_runtime_identity
from night_voyager.evidence_loop.mke_capture import (
    validate_capture_for_dataset,
    verify_capture_artifact,
)
from night_voyager.evidence_loop.receipt import (
    build_terminal_receipt,
    verify_pre_registration_receipt,
    verify_terminal_receipt,
)
from night_voyager.evidence_loop.schema_validation import (
    validate_strict_json_schema,
)


class CliFailure(RuntimeError):
    def __init__(self, code: str, exit_code: int) -> None:
        self.payload = {
            "stage": "verification",
            "code": code,
            "problem": "The evidence-loop receipt could not be verified.",
            "cause": "The public receipt input or canonical digest was invalid.",
            "recovery": "Verify the canonical receipt and rerun the documented command.",
        }
        self.exit_code = exit_code
        super().__init__(code)


class BoundedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        del message
        raise CliFailure("invalid_cli", 2)


def _parser() -> argparse.ArgumentParser:
    parser = BoundedArgumentParser(allow_abbrev=False)
    parser.add_argument("--pre-registration", type=Path)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def _emit(error: CliFailure) -> int:
    print(json.dumps(error.payload, separators=(",", ":"), sort_keys=True))
    print(f"recovery: {error.payload['recovery']}", file=sys.stderr)
    return error.exit_code


def _object(content: bytes) -> dict[str, Any]:
    value = json.loads(content)
    if not isinstance(value, dict):
        raise ValueError("artifact must be an object")
    return cast(dict[str, Any], value)


def _case_commitment(case: dict[str, Any]) -> dict[str, object]:
    payload_value = case.get("payload")
    oracle_value = case.get("oracle")
    if not isinstance(payload_value, dict) or not isinstance(oracle_value, dict):
        raise ValueError("revealed case invalid")
    payload = cast(dict[str, object], payload_value)
    oracle = cast(dict[str, object], oracle_value)
    identity_value = payload.get("identity")
    if not isinstance(identity_value, dict):
        raise ValueError("revealed case invalid")
    identity = cast(dict[str, object], identity_value)
    payload_bytes = canonical_json_bytes(payload)
    oracle_bytes = canonical_json_bytes(oracle)
    full_bytes = canonical_json_bytes(case)
    return {
        **identity,
        "payload_byte_length": len(payload_bytes),
        "payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
        "oracle_byte_length": len(oracle_bytes),
        "oracle_sha256": hashlib.sha256(oracle_bytes).hexdigest(),
        "full_case_byte_length": len(full_bytes),
        "full_case_sha256": hashlib.sha256(full_bytes).hexdigest(),
    }


def _verify_holdout_artifacts(
    *,
    repo_root: Path,
    pre_registration_content: bytes,
    dataset_content: bytes,
    capture_content: bytes,
    receipt_content: bytes,
) -> dict[str, Any]:
    preregistration = verify_pre_registration_receipt(pre_registration_content)
    validate_runtime_identity(
        cast(dict[str, Any], preregistration.get("environment")),
        repo_root=repo_root,
    )
    dataset = _object(dataset_content)
    capture = verify_capture_artifact(capture_content)
    receipt = verify_terminal_receipt(receipt_content)
    if receipt.get("run_kind") != "holdout":
        raise ValueError("receipt contract invalid")
    schema_root = repo_root / "tests/fixtures/evidence_loop"
    schemas = {
        name: _object((schema_root / f"{name}-schema-v1.json").read_bytes())
        for name in (
            "holdout-dataset",
            "holdout-case",
            "holdout-payload",
            "holdout-oracle",
        )
    }
    validate_strict_json_schema(dataset, schemas["holdout-dataset"])
    cases_value = dataset.get("cases")
    if not isinstance(cases_value, list):
        raise ValueError("revealed dataset invalid")
    cases = cast(list[object], cases_value)
    for index, case_value in enumerate(cases):
        if not isinstance(case_value, dict):
            raise ValueError("revealed dataset invalid")
        case = cast(dict[str, Any], case_value)
        validate_strict_json_schema(case, schemas["holdout-case"], location=f"$.cases[{index}]")
        validate_strict_json_schema(
            case.get("payload"),
            schemas["holdout-payload"],
            location=f"$.cases[{index}].payload",
        )
        validate_strict_json_schema(
            case.get("oracle"),
            schemas["holdout-oracle"],
            location=f"$.cases[{index}].oracle",
        )
    commitments = [_case_commitment(cast(dict[str, Any], case)) for case in cases]
    if commitments != preregistration.get("holdout_commitments"):
        raise ValueError("holdout commitment mismatch")
    sealed_store = cast(dict[str, Any], preregistration.get("sealed_store"))
    validate_capture_for_dataset(
        capture,
        dataset,
        expected_active_set_fingerprint=str(sealed_store.get("active_set_fingerprint")),
        expected_store_tree_sha256=str(sealed_store.get("tree_sha256")),
    )
    normalized = normalize_revealed_dataset(dataset, capture)
    evaluation = evaluate_suite(normalized)
    bindings = {
        "pre_registration_sha256": hashlib.sha256(pre_registration_content).hexdigest(),
        "holdout_dataset_sha256": hashlib.sha256(dataset_content).hexdigest(),
        "mke_capture_sha256": hashlib.sha256(capture_content).hexdigest(),
    }
    if receipt.get("artifact_bindings") != bindings:
        raise ValueError("artifact binding mismatch")
    recomputed = build_terminal_receipt(
        evaluation,
        run_kind="holdout",
        artifact_bindings=bindings,
    )
    if recomputed != receipt_content:
        raise ValueError("terminal evaluation mismatch")
    return receipt


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if args.receipt is None:
            raise CliFailure("invalid_cli", 2)
        try:
            content = args.receipt.read_bytes()
        except OSError as error:
            raise CliFailure("input_unreadable", 2) from error
        try:
            receipt = verify_terminal_receipt(content)
        except (ValueError, json.JSONDecodeError) as error:
            raise CliFailure("receipt_invalid", 13) from error
        holdout_inputs = (
            args.pre_registration,
            args.dataset,
            args.capture,
        )
        if receipt.get("run_kind") == "holdout":
            if any(path is None for path in holdout_inputs):
                raise CliFailure("invalid_cli", 2)
            try:
                receipt = _verify_holdout_artifacts(
                    repo_root=Path(__file__).resolve().parents[1],
                    pre_registration_content=args.pre_registration.read_bytes(),
                    dataset_content=args.dataset.read_bytes(),
                    capture_content=args.capture.read_bytes(),
                    receipt_content=content,
                )
            except (OSError, ValueError, json.JSONDecodeError) as error:
                raise CliFailure("receipt_invalid", 13) from error
        elif any(path is not None for path in holdout_inputs):
            raise CliFailure("invalid_cli", 2)
    except CliFailure as error:
        return _emit(error)
    print(
        json.dumps(
            {
                "schema_version": "night-voyager.evidence-loop-verification-response.v1",
                "ok": True,
                "code": "evidence_loop_receipt_verified",
                "terminal_disposition": receipt["terminal_disposition"],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
