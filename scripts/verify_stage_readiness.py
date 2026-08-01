#!/usr/bin/env python3
"""Fail-closed verifier for an exact merged stage readiness receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import cast

from pydantic import ValidationError

from night_voyager.evidence_loop.canonicalization import canonical_json_bytes
from night_voyager.evidence_loop.models import (
    EXPECTED_HOSTED_CHECKS,
    StageReadinessContractV1,
    StageReadinessReceiptV1,
    validate_safe_relative_path,
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


def _load_contract(stage: str) -> StageReadinessContractV1:
    try:
        return StageReadinessContractV1.model_validate_json(
            (
                ROOT / "tests/fixtures/evidence_loop/stage-contracts" / CONTRACT_PATHS[stage]
            ).read_text(encoding="utf-8")
        )
    except (KeyError, OSError, ValidationError) as error:
        raise VerificationFailure(
            13,
            "stage_contract_invalid",
            "restore the canonical closed stage contract",
        ) from error


def _safe_proof_path(relative: str) -> Path:
    try:
        validate_safe_relative_path(relative)
    except ValueError as error:
        raise VerificationFailure(
            13,
            "proof_path_invalid",
            "restore the canonical repository-relative proof path",
        ) from error
    try:
        root_metadata = ROOT.lstat()
        root = ROOT.resolve(strict=True)
        if stat.S_ISLNK(root_metadata.st_mode):
            raise ValueError("repository root symlink")
        candidate = ROOT / PurePosixPath(relative)
        current = ROOT
        for part in PurePosixPath(relative).parts:
            current = current / part
            metadata = current.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                raise ValueError("proof path symlink")
            if current != candidate and not stat.S_ISDIR(metadata.st_mode):
                raise ValueError("proof path parent invalid")
        metadata = candidate.lstat()
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("proof path is not a regular file")
    except (OSError, ValueError) as error:
        raise VerificationFailure(
            13,
            "proof_path_invalid",
            "restore the canonical repository-relative proof path",
        ) from error
    return candidate


def _canonical_required_checks(
    raw_checks: object,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not isinstance(raw_checks, list):
        raise VerificationFailure(
            12,
            "required_checks_invalid",
            "restore exactly the passing python, frontend, and compose checks",
        )
    found: dict[str, str] = {}
    for raw in cast(list[object], raw_checks):
        if not isinstance(raw, dict):
            raise VerificationFailure(
                12,
                "required_checks_invalid",
                "restore exactly the passing python, frontend, and compose checks",
            )
        check = cast(dict[str, object], raw)
        name = check.get("name")
        link = check.get("link")
        if (
            not isinstance(name, str)
            or name not in EXPECTED_HOSTED_CHECKS
            or name in found
            or check.get("bucket") != "pass"
            or not isinstance(link, str)
            or not link.startswith("https://github.com/")
        ):
            raise VerificationFailure(
                12,
                "required_checks_invalid",
                "restore exactly the passing python, frontend, and compose checks",
            )
        found[name] = link
    if set(found) != set(EXPECTED_HOSTED_CHECKS) or len(set(found.values())) != len(found):
        raise VerificationFailure(
            12,
            "required_checks_invalid",
            "restore exactly the passing python, frontend, and compose checks",
        )
    return EXPECTED_HOSTED_CHECKS, tuple(found[name] for name in EXPECTED_HOSTED_CHECKS)


def _receipt_digest(receipt: StageReadinessReceiptV1) -> str:
    return hashlib.sha256(
        canonical_json_bytes(receipt.model_dump(mode="json"))
    ).hexdigest()


def _merged_pull(merge_commit: str) -> tuple[int, dict[str, object]]:
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
            20, "external_readback_invalid", "repeat the required GitHub readback"
        )
    matches: list[dict[str, object]] = []
    for raw in cast(list[object], pulls):
        if not isinstance(raw, dict):
            continue
        pull = cast(dict[str, object], raw)
        merge = pull.get("mergeCommit")
        if isinstance(merge, dict) and cast(dict[str, object], merge).get("oid") == merge_commit:
            matches.append(pull)
    if len(matches) != 1:
        raise VerificationFailure(
            10,
            "merged_pr_identity_not_unique",
            "supply one exact merged predecessor PR",
        )
    number = matches[0].get("number")
    if not isinstance(number, int):
        raise VerificationFailure(
            20, "external_readback_invalid", "repeat the required GitHub readback"
        )
    return number, matches[0]


def _merged_tree_and_ancestry(merge_commit: str, expected_main: str) -> str:
    resolved = git("rev-parse", f"{merge_commit}^{{commit}}")
    if resolved != merge_commit:
        raise VerificationFailure(10, "merge_identity_mismatch", "supply the exact merged commit")
    try:
        run(["git", "merge-base", "--is-ancestor", merge_commit, expected_main])
    except VerificationFailure as error:
        raise VerificationFailure(
            10, "merge_not_in_main", "supply a merged commit on current main"
        ) from error
    return git("rev-parse", f"{merge_commit}^{{tree}}")


def _commit_is_ancestor(ancestor: str, descendant: str) -> bool:
    """Require both exact commit identities and their ordered ancestry."""

    try:
        if git("rev-parse", f"{ancestor}^{{commit}}") != ancestor:
            return False
        if git("rev-parse", f"{descendant}^{{commit}}") != descendant:
            return False
        run(["git", "merge-base", "--is-ancestor", ancestor, descendant])
    except VerificationFailure:
        return False
    return True


def _validate_receipt_identity(
    contract: StageReadinessContractV1,
    receipt: StageReadinessReceiptV1,
    *,
    merge_commit: str,
    merge_tree: str,
    expected_main: str,
    check_names: tuple[str, ...],
    check_urls: tuple[str, ...],
) -> None:
    proof_path = _safe_proof_path(receipt.proof_path)
    proof_sha256 = hashlib.sha256(proof_path.read_bytes()).hexdigest()
    main_sync_valid = _commit_is_ancestor(
        merge_commit, receipt.main_sync_commit
    ) and _commit_is_ancestor(receipt.main_sync_commit, expected_main)
    if not (
        receipt.stage == contract.stage
        and receipt.merge_commit == merge_commit
        and receipt.merge_tree == merge_tree
        and receipt.reviewed_tree == merge_tree
        and receipt.reviewed_tree_equals_merge_tree
        and main_sync_valid
        and receipt.proof_path == contract.proof_path
        and receipt.proof_sha256 == proof_sha256
        and receipt.terminal_disposition in contract.allowed_terminal_dispositions
        and receipt.required_checks == check_names
        and receipt.check_urls == check_urls
        and receipt.next_stage_unlock == contract.next_stage_unlock
        and receipt.non_claims == contract.non_claims
    ):
        raise VerificationFailure(
            12,
            "stage_readiness_not_unlocked",
            "reconcile the exact proof, receipt, and required hosted checks",
        )


def _verify_predecessor_chain(
    contract: StageReadinessContractV1,
    receipt: StageReadinessReceiptV1,
    *,
    expected_main: str,
    seen_commits: set[str],
) -> None:
    predecessor_stage = contract.predecessor_stage
    if predecessor_stage is None:
        if any(
            value is not None
            for value in (
                receipt.predecessor_stage,
                receipt.predecessor_merge_commit,
                receipt.predecessor_merge_tree,
                receipt.predecessor_receipt_sha256,
                receipt.predecessor_terminal_disposition,
            )
        ):
            raise VerificationFailure(
                12,
                "predecessor_chain_invalid",
                "remove the unexpected slice0 predecessor",
            )
        return
    if (
        receipt.predecessor_stage != predecessor_stage
        or receipt.predecessor_merge_commit is None
        or receipt.predecessor_merge_tree is None
        or receipt.predecessor_receipt_sha256 is None
        or receipt.predecessor_terminal_disposition != contract.predecessor_terminal_disposition
    ):
        raise VerificationFailure(
            12,
            "predecessor_chain_invalid",
            "bind the complete merged predecessor receipt",
        )
    predecessor_commit = receipt.predecessor_merge_commit
    if predecessor_commit in seen_commits:
        raise VerificationFailure(
            12, "predecessor_chain_cycle", "remove the predecessor chain cycle"
        )
    predecessor_tree = _merged_tree_and_ancestry(predecessor_commit, expected_main)
    if predecessor_tree != receipt.predecessor_merge_tree:
        raise VerificationFailure(
            12, "predecessor_chain_invalid", "bind the predecessor merge tree"
        )
    number, pull = _merged_pull(predecessor_commit)
    body = pull.get("body")
    if not isinstance(body, str):
        raise VerificationFailure(
            20,
            "external_readback_invalid",
            "repeat the merged predecessor readback",
        )
    predecessor_receipt = extract_terminal_receipt(body)
    if (
        predecessor_receipt.stage != predecessor_stage
        or predecessor_receipt.terminal_disposition != contract.predecessor_terminal_disposition
        or _receipt_digest(predecessor_receipt) != receipt.predecessor_receipt_sha256
    ):
        raise VerificationFailure(
            12,
            "predecessor_chain_invalid",
            "bind the exact predecessor terminal receipt",
        )
    predecessor_contract = _load_contract(predecessor_stage)
    if predecessor_contract.next_stage_unlock != contract.stage:
        raise VerificationFailure(
            12,
            "predecessor_chain_order_invalid",
            "bind predecessor stages in order",
        )
    raw_checks = gh_json(
        "pr",
        "checks",
        str(number),
        "--repo",
        "iTao-AI/night-voyager",
        "--required",
        "--json",
        "name,state,bucket,link",
    )
    check_names, check_urls = _canonical_required_checks(raw_checks)
    _validate_receipt_identity(
        predecessor_contract,
        predecessor_receipt,
        merge_commit=predecessor_commit,
        merge_tree=predecessor_tree,
        expected_main=expected_main,
        check_names=check_names,
        check_urls=check_urls,
    )
    _verify_predecessor_chain(
        predecessor_contract,
        predecessor_receipt,
        expected_main=expected_main,
        seen_commits={*seen_commits, predecessor_commit},
    )


def verify() -> dict[str, str]:
    args = parse_args()
    contract = _load_contract(args.stage)
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
    check_names, check_urls = _canonical_required_checks(cast(list[object], checks))
    _validate_receipt_identity(
        contract,
        receipt,
        merge_commit=merge_commit,
        merge_tree=merge_tree,
        expected_main=expected_main,
        check_names=check_names,
        check_urls=check_urls,
    )
    _verify_predecessor_chain(
        contract,
        receipt,
        expected_main=expected_main,
        seen_commits={merge_commit},
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
