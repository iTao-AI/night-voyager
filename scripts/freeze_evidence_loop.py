#!/usr/bin/env python3
"""Create the final public-safe Slice 0 pre-registration receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

from night_voyager.evidence_loop.freeze import (
    RUN_ROOT_PREREGISTRATION,
    RUN_ROOT_SETUP_RECEIPT,
    build_pre_registration_receipt,
    validate_run_root,
    validate_run_root_path,
)


class CliFailure(RuntimeError):
    def __init__(self, code: str, exit_code: int) -> None:
        self.payload = {
            "stage": "freeze",
            "code": code,
            "problem": "The evidence-loop freeze boundary could not be established.",
            "cause": "A frozen identity, order, or reachability check failed.",
            "recovery": "Restore the exact clean candidate and public commitments.",
        }
        self.exit_code = exit_code
        super().__init__(code)


class BoundedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        del message
        raise CliFailure("invalid_cli", 2)


def _parser() -> argparse.ArgumentParser:
    parser = BoundedArgumentParser(allow_abbrev=False)
    parser.add_argument("--store-receipt", type=Path)
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--development-dataset", type=Path)
    parser.add_argument("--holdout-manifest", type=Path)
    parser.add_argument("--dra-baseline", type=Path)
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def _emit(error: CliFailure) -> int:
    print(json.dumps(error.payload, separators=(",", ":"), sort_keys=True))
    print(f"recovery: {error.payload['recovery']}", file=sys.stderr)
    return error.exit_code


def _git(repo_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise CliFailure("git_identity_unavailable", 11)
    return result.stdout.strip()


def _write_exclusive(path: Path, content: bytes) -> None:
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as error:
        raise CliFailure("receipt_destination_invalid", 11) from error
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)


def _require_repo_exact_path(repo_root: Path, actual: Path, relative: str) -> None:
    if actual.resolve(strict=False) != (repo_root / relative).resolve(strict=False):
        raise CliFailure("freeze_input_path_invalid", 11)


def _prepare(args: argparse.Namespace) -> dict[str, object]:
    required = (
        args.store_receipt,
        args.source_manifest,
        args.development_dataset,
        args.holdout_manifest,
        args.dra_baseline,
        args.run_root,
        args.output,
    )
    if any(path is None for path in required):
        raise CliFailure("invalid_cli", 2)
    paths = [
        path
        for path in (
            args.store_receipt,
            args.source_manifest,
            args.development_dataset,
            args.holdout_manifest,
            args.dra_baseline,
        )
        if isinstance(path, Path)
    ]
    if any(not path.is_file() for path in paths):
        raise CliFailure("input_unreadable", 2)
    repo_root = Path(__file__).resolve().parents[1]
    try:
        run_root = validate_run_root(args.run_root)
        store_receipt = validate_run_root_path(
            run_root,
            args.store_receipt,
            RUN_ROOT_SETUP_RECEIPT,
            require_regular_file=True,
        )
        output = validate_run_root_path(
            run_root,
            args.output,
            RUN_ROOT_PREREGISTRATION,
            allow_missing=True,
        )
    except ValueError as error:
        raise CliFailure("run_root_invalid", 11) from error
    for actual, relative in (
        (args.source_manifest, "tests/fixtures/evidence_loop/source-manifest-v1.json"),
        (
            args.development_dataset,
            "tests/fixtures/evidence_loop/development-dataset-v1.json",
        ),
        (
            args.holdout_manifest,
            "tests/fixtures/evidence_loop/holdout-manifest-v1.json",
        ),
        (
            args.dra_baseline,
            "tests/fixtures/evidence_loop/dra-governed-baseline-v1.json",
        ),
    ):
        _require_repo_exact_path(repo_root, actual, relative)
    if _git(repo_root, "status", "--porcelain"):
        raise CliFailure("candidate_not_clean", 11)
    head = _git(repo_root, "rev-parse", "HEAD")
    tree = _git(repo_root, "rev-parse", "HEAD^{tree}")
    try:
        receipt = build_pre_registration_receipt(
            repo_root=repo_root,
            exact_head=head,
            exact_tree=tree,
            store_receipt=store_receipt,
            source_manifest=args.source_manifest,
            development_dataset=args.development_dataset,
            holdout_manifest=args.holdout_manifest,
            dra_baseline=args.dra_baseline,
        )
    except (OSError, json.JSONDecodeError, ValueError) as error:
        message = str(error)
        exit_code = (
            10
            if any(token in message for token in ("store", "source", "provider"))
            else 11
            if any(token in message for token in ("custody", "reachable", "generated"))
            else 13
        )
        raise CliFailure("pre_registration_invalid", exit_code) from error
    _write_exclusive(output, receipt)
    return {
        "schema_version": "night-voyager.evidence-loop-freeze-response.v2",
        "ok": True,
        "code": "evidence_loop_preregistered",
        "receipt": {
            "basename": output.name,
            "byte_length": len(receipt),
            "sha256": hashlib.sha256(receipt).hexdigest(),
            "mode": "0600",
        },
    }


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        payload = _prepare(args)
    except CliFailure as error:
        return _emit(error)
    except Exception:
        return _emit(CliFailure("freeze_failed", 13))
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
