#!/usr/bin/env python3
"""Validate the one-way holdout reveal boundary without locating custody."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, NoReturn, cast

from night_voyager.evidence_loop.canonicalization import canonical_json_bytes
from night_voyager.evidence_loop.freeze import (
    POST_REVEAL_ALLOWLIST,
    RUN_ROOT_PREREGISTRATION,
    validate_frozen_checkout,
    validate_run_root,
    validate_run_root_path,
)
from night_voyager.evidence_loop.native_store import validate_native_runtime_identity
from night_voyager.evidence_loop.receipt import verify_pre_registration_receipt
from night_voyager.evidence_loop.schema_validation import (
    validate_strict_json_schema,
)


class CliFailure(RuntimeError):
    def __init__(self, code: str, exit_code: int) -> None:
        self.payload = {
            "stage": "reveal",
            "code": code,
            "problem": "The one-way reveal boundary was not satisfied.",
            "cause": "A custody, order, identity, or destination check failed.",
            "recovery": "Use the exact pre-registration and custodian-owned reveal input.",
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
    parser.add_argument("--expected-pre-registration-sha256")
    parser.add_argument("--holdout-manifest", type=Path)
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--store-root", type=Path)
    parser.add_argument("--custody-root", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def _emit(error: CliFailure) -> int:
    print(json.dumps(error.payload, separators=(",", ":"), sort_keys=True))
    print(f"recovery: {error.payload['recovery']}", file=sys.stderr)
    return error.exit_code


def case_commitment(case: dict[str, object]) -> dict[str, object]:
    payload_value = case.get("payload")
    oracle_value = case.get("oracle")
    if not isinstance(payload_value, dict) or not isinstance(oracle_value, dict):
        raise ValueError("revealed case invalid")
    payload = cast(dict[str, object], payload_value)
    oracle = cast(dict[str, object], oracle_value)
    payload_bytes = canonical_json_bytes(payload)
    oracle_bytes = canonical_json_bytes(oracle)
    full_bytes = canonical_json_bytes(case)
    identity_value = payload.get("identity")
    commitment: dict[str, object] = {}
    if isinstance(identity_value, dict):
        identity = cast(dict[str, object], identity_value)
        commitment.update(identity)
    commitment.update(
        {
            "payload_byte_length": len(payload_bytes),
            "payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
            "oracle_byte_length": len(oracle_bytes),
            "oracle_sha256": hashlib.sha256(oracle_bytes).hexdigest(),
            "full_case_byte_length": len(full_bytes),
            "full_case_sha256": hashlib.sha256(full_bytes).hexdigest(),
        }
    )
    return commitment


def validate_revealed_dataset(
    dataset: dict[str, object],
    manifest: dict[str, object],
    *,
    schema_root: Path | None = None,
) -> None:
    cases_value = dataset.get("cases")
    commitments_value = manifest.get("holdouts")
    if not isinstance(cases_value, list) or not isinstance(commitments_value, list):
        raise ValueError("revealed dataset invalid")
    cases = cast(list[object], cases_value)
    commitments = cast(list[object], commitments_value)
    if schema_root is not None:
        schemas = {
            name: _object(schema_root / f"{name}-schema-v1.json")
            for name in (
                "holdout-dataset",
                "holdout-case",
                "holdout-payload",
                "holdout-oracle",
            )
        }
        validate_strict_json_schema(dataset, schemas["holdout-dataset"])
        for index, case_value in enumerate(cases):
            if not isinstance(case_value, dict):
                raise ValueError("revealed dataset invalid")
            case = cast(dict[str, object], case_value)
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
    actual = [
        case_commitment(cast(dict[str, object], case)) for case in cases if isinstance(case, dict)
    ]
    if len(actual) != len(cases) or actual != commitments:
        raise ValueError("revealed case commitment mismatch")
    if schema_root is not None:
        identities = [
            (
                item.get("holdout_id"),
                item.get("case_id"),
                item.get("case_revision"),
                item.get("query_id"),
                item.get("decision_dimension"),
            )
            for item in actual
        ]
        if len(identities) != 4 or len(set(identities)) != 4:
            raise ValueError("revealed case identity set invalid")


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise CliFailure("input_unreadable", 2) from error
    if not isinstance(value, dict):
        raise CliFailure("input_invalid", 13)
    return cast(dict[str, Any], value)


def _read_exact_custody_input(custody_root: Path) -> tuple[bytes, dict[str, Any]]:
    source = custody_root / "holdout-dataset-v1.json"
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(source, flags)
    except OSError as error:
        raise CliFailure("custody_input_invalid", 11) from error
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_size > 1_048_576
        ):
            raise CliFailure("custody_input_invalid", 11)
        content = b""
        while len(content) <= 1_048_576:
            chunk = os.read(descriptor, 65_536)
            if not chunk:
                break
            content += chunk
        if len(content) != metadata.st_size:
            raise CliFailure("custody_input_invalid", 11)
    finally:
        os.close(descriptor)
    try:
        value = json.loads(content)
    except json.JSONDecodeError as error:
        raise CliFailure("custody_input_invalid", 11) from error
    if not isinstance(value, dict):
        raise CliFailure("custody_input_invalid", 11)
    return content, cast(dict[str, Any], value)


def _publish_exclusive(destination: Path, content: bytes) -> None:
    temporary: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".holdout-reveal-",
            dir=destination.parent,
        )
        temporary = Path(temporary_name)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, destination)
    except OSError as error:
        raise CliFailure("destination_not_fresh", 11) from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


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


def _relative_destination(repo_root: Path, destination: Path) -> str:
    try:
        return destination.resolve(strict=False).relative_to(repo_root.resolve()).as_posix()
    except ValueError as error:
        raise CliFailure("destination_not_allowlisted", 11) from error


def _validate_reveal_authority(
    preregistration: dict[str, Any],
    *,
    repo_root: Path,
    store_root: Path,
) -> None:
    current_head = _git(repo_root, "rev-parse", "HEAD")
    current_tree = _git(repo_root, "rev-parse", "HEAD^{tree}")
    status_lines = _git(
        repo_root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    ).splitlines()
    try:
        validate_frozen_checkout(
            preregistration,
            repo_root=repo_root,
            store_root=store_root,
            current_head=current_head,
            current_tree=current_tree,
            status_paths=tuple(line[3:] for line in status_lines),
        )
        runtime_value = preregistration.get("native_runtime_identity")
        provider_locks_value = preregistration.get("provider_locks")
        if not isinstance(runtime_value, dict) or not isinstance(provider_locks_value, dict):
            raise ValueError("native runtime identity invalid")
        mke_lock_value = cast(dict[str, Any], provider_locks_value).get("mke")
        if not isinstance(mke_lock_value, dict):
            raise ValueError("native runtime identity invalid")
        wheel_sha256 = cast(dict[str, Any], mke_lock_value).get("wheel_sha256")
        if not isinstance(wheel_sha256, str):
            raise ValueError("native runtime identity invalid")
        validate_native_runtime_identity(
            cast(dict[str, object], runtime_value),
            run_root=store_root.parent,
            wheel_sha256=wheel_sha256,
        )
    except ValueError as error:
        raise CliFailure("freeze_order_invalid", 11) from error


def _prepare(args: argparse.Namespace) -> dict[str, object]:
    if any(
        value is None
        for value in (
            args.pre_registration,
            args.expected_pre_registration_sha256,
            args.holdout_manifest,
            args.run_root,
            args.store_root,
            args.custody_root,
            args.destination,
        )
    ):
        raise CliFailure("invalid_cli", 2)
    repo_root = Path(__file__).resolve().parents[1]
    try:
        run_root = validate_run_root(args.run_root)
        validate_run_root_path(
            run_root,
            args.pre_registration,
            RUN_ROOT_PREREGISTRATION,
            require_regular_file=True,
        )
        validate_run_root_path(run_root, args.store_root, "store")
    except ValueError as error:
        raise CliFailure("run_root_path_invalid", 11) from error
    relative = _relative_destination(repo_root, args.destination)
    if relative not in POST_REVEAL_ALLOWLIST or relative != POST_REVEAL_ALLOWLIST[0]:
        raise CliFailure("destination_not_allowlisted", 11)
    if args.destination.exists():
        raise CliFailure("destination_not_fresh", 11)
    try:
        pre_registration_content = args.pre_registration.read_bytes()
        if (
            not isinstance(args.expected_pre_registration_sha256, str)
            or len(args.expected_pre_registration_sha256) != 64
            or hashlib.sha256(pre_registration_content).hexdigest()
            != args.expected_pre_registration_sha256
        ):
            raise ValueError("reviewed pre-registration digest mismatch")
        preregistration = verify_pre_registration_receipt(pre_registration_content)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise CliFailure("pre_registration_invalid", 13) from error
    current_head = _git(repo_root, "rev-parse", "HEAD")
    current_tree = _git(repo_root, "rev-parse", "HEAD^{tree}")
    if (
        preregistration.get("reveal_procedure_id") != "nv.slice0.one-way-reveal.v1"
        or preregistration.get("post_reveal_generated_file_allowlist")
        != list(POST_REVEAL_ALLOWLIST)
        or cast(dict[str, Any], preregistration.get("pre_reveal_scan")).get("passed") is not True
        or preregistration.get("git")
        != {
            "head": current_head,
            "tree": current_tree,
            "clean": True,
        }
    ):
        raise CliFailure("freeze_order_invalid", 11)
    manifest_identity_value = preregistration.get("holdout_manifest")
    if not isinstance(manifest_identity_value, dict):
        raise CliFailure("freeze_order_invalid", 11)
    manifest_relative = cast(dict[str, Any], manifest_identity_value).get("path")
    if (
        not isinstance(manifest_relative, str)
        or args.holdout_manifest.resolve() != (repo_root / manifest_relative).resolve()
    ):
        raise CliFailure("freeze_order_invalid", 11)
    _validate_reveal_authority(
        preregistration,
        repo_root=repo_root,
        store_root=args.store_root,
    )
    custody_root = args.custody_root.resolve()
    try:
        custody_root.relative_to(repo_root.resolve())
    except ValueError:
        pass
    else:
        raise CliFailure("custody_root_not_separate", 11)
    if not custody_root.is_dir() or stat.S_IMODE(custody_root.stat().st_mode) != 0o700:
        raise CliFailure("custody_mode_invalid", 11)
    content, dataset = _read_exact_custody_input(custody_root)
    manifest = _object(args.holdout_manifest)
    try:
        validate_revealed_dataset(
            dataset,
            manifest,
            schema_root=repo_root / "tests/fixtures/evidence_loop",
        )
    except ValueError as error:
        raise CliFailure("holdout_commitment_mismatch", 13) from error
    _validate_reveal_authority(
        preregistration,
        repo_root=repo_root,
        store_root=args.store_root,
    )
    _publish_exclusive(args.destination, content)
    return {
        "schema_version": "night-voyager.evidence-loop-reveal-response.v1",
        "ok": True,
        "code": "evidence_loop_holdouts_revealed",
        "dataset": {
            "basename": args.destination.name,
            "byte_length": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        },
    }


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        payload = _prepare(args)
    except CliFailure as error:
        return _emit(error)
    except Exception:
        return _emit(CliFailure("reveal_failed", 13))
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
