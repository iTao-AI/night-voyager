#!/usr/bin/env python3
"""Fail-closed verifier for an exact merged stage readiness receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import cast

from pydantic import ValidationError

from night_voyager.evidence_loop.models import (
    StageReadinessContractV1,
    StageReadinessReceiptV1,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATHS = {
    "slice0": "slice0-v1.json",
    "candidate-authority": "candidate-authority-v1.json",
    "candidate-journey": "candidate-journey-v1.json",
    "composition-authority": "composition-authority-v1.json",
    "composition-journey": "composition-journey-v1.json",
}
JSON_BLOCK = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


class VerificationFailure(RuntimeError):
    def __init__(self, exit_code: int, code: str, recovery: str) -> None:
        self.exit_code = exit_code
        self.code = code
        self.recovery = recovery
        super().__init__(code)


def run(command: list[str], *, external: bool = False) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise VerificationFailure(
            20 if external else 10,
            "external_readback_unavailable" if external else "identity_mismatch",
            "restore authenticated read-only GitHub access"
            if external
            else "supply exact merged and current-main identities",
        )
    return result.stdout.strip()


def git(*arguments: str) -> str:
    return run(["git", *arguments])


def gh_json(*arguments: str) -> object:
    output = run(["gh", *arguments], external=True)
    try:
        return json.loads(output)
    except json.JSONDecodeError as error:
        raise VerificationFailure(
            20,
            "external_readback_invalid",
            "repeat the authenticated GitHub readback",
        ) from error


def extract_terminal_receipt(body: str) -> StageReadinessReceiptV1:
    if "night-voyager.stage-readiness-candidate.v1" in body:
        raise VerificationFailure(
            13,
            "candidate_not_terminal",
            "reconcile the merged PR body to one terminal receipt",
        )
    receipts: list[StageReadinessReceiptV1] = []
    for raw in JSON_BLOCK.findall(body):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if value.get("schema_version") != "night-voyager.stage-readiness-receipt.v1":
            continue
        try:
            receipts.append(StageReadinessReceiptV1.model_validate(value))
        except ValidationError as error:
            raise VerificationFailure(
                13,
                "malformed_terminal_receipt",
                "persist one closed StageReadinessReceiptV1 JSON block",
            ) from error
    if len(receipts) != 1:
        raise VerificationFailure(
            13,
            "terminal_receipt_count_invalid",
            "persist exactly one terminal receipt JSON block",
        )
    return receipts[0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify an exact merged Night Voyager stage readiness identity."
    )
    parser.add_argument("--stage", choices=tuple(CONTRACT_PATHS), required=True)
    parser.add_argument("--merge-commit", required=True)
    parser.add_argument("--expected-main", required=True)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def verify() -> dict[str, str]:
    args = parse_args()
    contract_path = (
        ROOT
        / "tests/fixtures/evidence_loop/stage-contracts"
        / CONTRACT_PATHS[args.stage]
    )
    contract = StageReadinessContractV1.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    merge_commit = git("rev-parse", f"{args.merge_commit}^{{commit}}")
    expected_main = git("rev-parse", f"{args.expected_main}^{{commit}}")
    run(["git", "merge-base", "--is-ancestor", merge_commit, expected_main])
    merge_tree = git("rev-parse", f"{merge_commit}^{{tree}}")

    pulls = gh_json(
        "pr",
        "list",
        "--repo",
        "iTao-AI/night-voyager",
        "--state",
        "merged",
        "--search",
        merge_commit,
        "--json",
        "number,body,mergeCommit",
        "--limit",
        "20",
    )
    if not isinstance(pulls, list):
        raise VerificationFailure(
            20, "external_readback_invalid", "repeat the GitHub PR readback"
        )
    typed_pulls = cast(list[object], pulls)
    matches: list[dict[str, object]] = []
    for raw_pull in typed_pulls:
        if not isinstance(raw_pull, dict):
            continue
        pull = cast(dict[str, object], raw_pull)
        raw_merge = pull.get("mergeCommit")
        if not isinstance(raw_merge, dict):
            continue
        merge = cast(dict[str, object], raw_merge)
        if merge.get("oid") == merge_commit:
            matches.append(pull)
    if len(matches) != 1:
        raise VerificationFailure(
            10,
            "merged_pr_identity_not_unique",
            "supply the exact unique squash merge commit",
        )
    pull = matches[0]
    body = pull.get("body")
    number = pull.get("number")
    if not isinstance(body, str) or not isinstance(number, int):
        raise VerificationFailure(
            20, "external_readback_invalid", "repeat the GitHub PR readback"
        )
    receipt = extract_terminal_receipt(body)

    proof_path = ROOT / contract.proof_path
    if not proof_path.is_file():
        raise VerificationFailure(
            13, "committed_proof_missing", "restore the canonical committed proof"
        )
    proof_sha256 = hashlib.sha256(proof_path.read_bytes()).hexdigest()
    checks = gh_json(
        "pr",
        "checks",
        str(number),
        "--repo",
        "iTao-AI/night-voyager",
        "--required",
        "--json",
        "name,state,bucket,link",
    )
    if not isinstance(checks, list):
        raise VerificationFailure(
            20, "external_readback_invalid", "repeat the required-check readback"
        )
    passing: list[tuple[str, str]] = []
    for raw_check in cast(list[object], checks):
        if not isinstance(raw_check, dict):
            continue
        check = cast(dict[str, object], raw_check)
        name = check.get("name")
        link = check.get("link")
        if (
            check.get("bucket") == "pass"
            and isinstance(name, str)
            and isinstance(link, str)
        ):
            passing.append((name, link))
    check_names = tuple(name for name, _link in passing)
    check_urls = tuple(link for _name, link in passing)

    exact = (
        receipt.stage == contract.stage
        and receipt.merge_commit == merge_commit
        and receipt.merge_tree == merge_tree
        and receipt.reviewed_tree == merge_tree
        and receipt.reviewed_tree_equals_merge_tree
        and receipt.main_sync_commit == expected_main
        and receipt.proof_path == contract.proof_path
        and receipt.proof_sha256 == proof_sha256
        and receipt.terminal_disposition in contract.allowed_terminal_dispositions
        and receipt.required_checks == contract.required_hosted_checks
        and receipt.required_checks == check_names
        and receipt.check_urls == check_urls
        and receipt.next_stage_unlock == contract.next_stage_unlock
        and receipt.non_claims == contract.non_claims
    )
    if not exact:
        raise VerificationFailure(
            12,
            "stage_readiness_not_unlocked",
            "reconcile the exact proof, receipt, and required hosted checks",
        )
    return {
        "code": "stage_readiness_verified",
        "stage": contract.stage,
        "merge_commit": merge_commit,
        "expected_main": expected_main,
        "proof_path": contract.proof_path,
    }


def main() -> None:
    try:
        payload = verify()
    except (OSError, ValidationError, VerificationFailure) as error:
        failure = (
            error
            if isinstance(error, VerificationFailure)
            else VerificationFailure(
                13, "stage_readiness_invalid", "repair the closed readiness inputs"
            )
        )
        diagnostic = {
            "stage": "stage-readiness",
            "code": failure.code,
            "problem": "stage readiness verification failed",
            "cause": failure.code,
            "recovery": failure.recovery,
        }
        print(
            json.dumps(diagnostic, sort_keys=True, separators=(",", ":")),
            file=sys.stdout,
        )
        print(f"recovery: {failure.recovery}", file=sys.stderr)
        raise SystemExit(failure.exit_code) from error
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
