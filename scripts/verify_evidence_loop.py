#!/usr/bin/env python3
"""Verify one canonical Slice 0 evaluation receipt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import NoReturn

from night_voyager.evidence_loop.receipt import verify_terminal_receipt


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
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def _emit(error: CliFailure) -> int:
    print(json.dumps(error.payload, separators=(",", ":"), sort_keys=True))
    print(f"recovery: {error.payload['recovery']}", file=sys.stderr)
    return error.exit_code


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
