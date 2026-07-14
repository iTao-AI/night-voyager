#!/usr/bin/env python3
"""Bounded M4B candidate identity checks and proof controller entry point."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

from night_voyager.evidence.candidate_lock import (
    build_candidate_lock,
    verify_candidate_artifact,
)
from night_voyager.evidence.mke_models import MkeConsumerError

REPOSITORY = Path(__file__).resolve().parents[1]
LOCK_PATH = REPOSITORY / "fixtures" / "m4b" / "candidate-artifact-lock.json"


def render(value: dict[str, object]) -> None:
    print(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")))


def record_lock(args: argparse.Namespace) -> int:
    lock = build_candidate_lock(
        args.wheel,
        args.candidate_receipt,
        artifact_locator=args.artifact_locator,
        reviewed_at=date.fromisoformat(args.reviewed_at),
    )
    encoded = lock.model_dump_json(indent=2) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded, encoding="utf-8")
    return 0


def doctor(args: argparse.Namespace) -> int:
    if sys.version_info[:2] != (3, 12) or shutil.which("uv") is None:
        raise MkeConsumerError("mke_environment_failed")
    with tempfile.TemporaryDirectory(prefix="night-voyager-m4b-doctor-") as directory:
        probe = Path(directory) / "probe"
        probe.write_text("ok", encoding="utf-8")
    verified = verify_candidate_artifact(args.wheel, args.candidate_receipt, LOCK_PATH)
    render(
        {
            "schema_version": "night_voyager.mke_doctor.v1",
            "status": "passed",
            "wheel_sha256": verified.wheel_sha256,
            "receipt_sha256": verified.receipt_sha256,
        }
    )
    return 0


def artifact_check(args: argparse.Namespace) -> int:
    verified = verify_candidate_artifact(args.wheel, args.candidate_receipt, LOCK_PATH)
    render(
        {
            "schema_version": "night_voyager.mke_artifact_check.v1",
            "status": "passed",
            "source_commit": verified.source_commit,
            "package_version": verified.package_version,
            "wheel_bytes": verified.wheel_bytes,
            "wheel_sha256": verified.wheel_sha256,
            "receipt_sha256": verified.receipt_sha256,
        }
    )
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("doctor", "artifact-check"):
        command = commands.add_parser(name)
        command.add_argument("--wheel", required=True, type=Path)
        command.add_argument("--candidate-receipt", required=True, type=Path)
        if name == "artifact-check":
            command.add_argument("--json", action="store_true")
    record = commands.add_parser("record-lock")
    record.add_argument("--wheel", required=True, type=Path)
    record.add_argument("--candidate-receipt", required=True, type=Path)
    record.add_argument("--artifact-locator", required=True)
    record.add_argument("--reviewed-at", required=True)
    record.add_argument("--output", required=True, type=Path)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "record-lock":
            return record_lock(args)
        if args.command == "doctor":
            return doctor(args)
        return artifact_check(args)
    except (MkeConsumerError, ValueError) as error:
        code = (
            error.failure.code
            if isinstance(error, MkeConsumerError)
            else "mke_candidate_mismatch"
        )
        print(code, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
