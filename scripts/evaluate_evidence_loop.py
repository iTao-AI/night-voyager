#!/usr/bin/env python3
"""Evaluate the bounded Slice 0 development or revealed frozen suite."""

from __future__ import annotations

import argparse
import asyncio
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
from night_voyager.evidence_loop.evaluator import (
    evaluate_suite,
    normalize_revealed_dataset,
)
from night_voyager.evidence_loop.freeze import (
    POST_REVEAL_ALLOWLIST,
    validate_frozen_checkout,
    validate_runtime_identity,
)
from night_voyager.evidence_loop.mke_capture import (
    capture_case,
    validate_capture_for_dataset,
    verify_capture_artifact,
)
from night_voyager.evidence_loop.native_store import (
    NativeStoreValidationError,
    validate_native_runtime_identity,
    verify_store_seal,
)
from night_voyager.evidence_loop.receipt import (
    build_terminal_receipt,
    verify_pre_registration_receipt,
)


class CliFailure(RuntimeError):
    def __init__(self, *, stage: str, code: str, exit_code: int) -> None:
        self.payload = {
            "stage": stage,
            "code": code,
            "problem": "The bounded evidence evaluation could not proceed.",
            "cause": "A required public-safe input or frozen boundary was invalid.",
            "recovery": "Verify the frozen inputs and rerun the exact documented command.",
        }
        self.exit_code = exit_code
        super().__init__(code)


class BoundedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        del message
        raise CliFailure(stage="arguments", code="invalid_cli", exit_code=2)


def _parser() -> argparse.ArgumentParser:
    parser = BoundedArgumentParser(allow_abbrev=False)
    parser.add_argument("--development-dataset", type=Path)
    parser.add_argument("--store-receipt", type=Path)
    parser.add_argument("--pre-registration", type=Path)
    parser.add_argument("--store-root", type=Path)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--capture-output", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise CliFailure(stage="input", code="input_unreadable", exit_code=2) from error
    if not isinstance(value, dict):
        raise CliFailure(stage="input", code="input_invalid", exit_code=13)
    return cast(dict[str, Any], value)


def _write_exclusive(path: Path, content: bytes) -> None:
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as error:
        raise CliFailure(stage="receipt", code="output_not_fresh", exit_code=11) from error
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)


def _git(repo_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise CliFailure(stage="freeze", code="git_identity_unavailable", exit_code=11)
    return result.stdout.strip()


def _allowlisted_path(repo_root: Path, path: Path, expected: str) -> None:
    try:
        relative = path.resolve(strict=False).relative_to(repo_root.resolve()).as_posix()
    except ValueError as error:
        raise CliFailure(stage="freeze", code="post_reveal_path_invalid", exit_code=11) from error
    if relative != expected:
        raise CliFailure(stage="freeze", code="post_reveal_path_invalid", exit_code=11)


def _exact_path(repo_root: Path, path: Path, expected: str) -> None:
    if path.resolve(strict=False) != (repo_root / expected).resolve(strict=False):
        raise CliFailure(stage="freeze", code="frozen_input_path_invalid", exit_code=11)


def _capture_state(repo_root: Path, store_root: Path) -> dict[str, object]:
    store_files = sorted(path for path in store_root.rglob("*") if path.is_file())
    store_projection = [
        {
            "basename": path.relative_to(store_root).as_posix(),
            "byte_length": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "mode": f"{stat.S_IMODE(path.stat().st_mode):04o}",
        }
        for path in store_files
    ]
    return {
        "head": _git(repo_root, "rev-parse", "HEAD"),
        "tree": _git(repo_root, "rev-parse", "HEAD^{tree}"),
        "status": _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all").splitlines(),
        "store_root_mode": f"{stat.S_IMODE(store_root.stat().st_mode):04o}",
        "store_files": store_projection,
        "store_tree_sha256": hashlib.sha256(
            canonical_json_bytes({"files": store_projection})
        ).hexdigest(),
    }


def _verify_capture_authority(
    *,
    store_root: Path,
    sealed_store: dict[str, Any],
    native_runtime_identity: dict[str, Any],
    wheel_sha256: str,
) -> None:
    seal = {
        key: sealed_store.get(key)
        for key in (
            "schema_version",
            "tree_sha256",
            "files",
            "store_root_mode",
            "lifecycle_state",
        )
    }
    try:
        verify_store_seal(store_root, seal)
        validate_native_runtime_identity(
            native_runtime_identity,
            run_root=store_root.parent,
            wheel_sha256=wheel_sha256,
        )
    except NativeStoreValidationError as error:
        raise CliFailure(
            stage="guardrail",
            code="capture_mutation_prohibited",
            exit_code=14,
        ) from error


async def _capture_native_dataset(
    *,
    dataset: dict[str, Any],
    repo_root: Path,
    store_root: Path,
    expected_active_set_fingerprint: str,
) -> dict[str, Any]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    source_manifest = _object(repo_root / "tests/fixtures/evidence_loop/source-manifest-v1.json")
    sources_value = source_manifest.get("sources")
    cases_value = dataset.get("cases")
    if not isinstance(sources_value, list) or not isinstance(cases_value, list):
        raise NativeStoreValidationError("capture_dataset_invalid")
    sources = cast(list[dict[str, Any]], sources_value)
    cases = cast(list[object], cases_value)
    if len(cases) != 4:
        raise NativeStoreValidationError("capture_dataset_invalid")
    run_root = store_root.parent
    executable = run_root / "work/venv/bin/mke"
    corpus = run_root / "input/corpus"
    database = store_root / "store.sqlite"
    if not executable.is_file() or not corpus.is_dir() or not database.is_file():
        raise NativeStoreValidationError("capture_runtime_invalid")

    captured_cases: list[dict[str, Any]] = []
    for case_value in cases:
        case = cast(dict[str, Any], case_value)
        payload_value = case.get("payload")
        if not isinstance(payload_value, dict):
            raise NativeStoreValidationError("capture_dataset_invalid")
        payload = cast(dict[str, Any], payload_value)
        params = StdioServerParameters(
            command=str(executable),
            args=[
                "--db",
                str(database),
                "mcp",
                "--allowed-root",
                str(corpus),
            ],
        )
        output_bytes = 0
        with tempfile.TemporaryFile(mode="w+") as errlog:
            async with (
                stdio_client(params, errlog=errlog) as (read, write),
                ClientSession(read, write) as session,
            ):
                await asyncio.wait_for(session.initialize(), timeout=10)

                async def call_tool(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
                    nonlocal output_bytes
                    if tool not in {"search_library_v2", "read_evidence_v1"}:
                        raise NativeStoreValidationError("capture_tool_invalid")
                    result = await asyncio.wait_for(
                        session.call_tool(tool, arguments),
                        timeout=10,
                    )
                    if result.isError or not isinstance(result.structuredContent, dict):
                        raise NativeStoreValidationError("capture_tool_failed")
                    body = result.structuredContent
                    output_bytes += len(canonical_json_bytes(body))
                    if output_bytes > 1_048_576:
                        raise NativeStoreValidationError("capture_output_limit")
                    return body

                captured = await asyncio.wait_for(
                    capture_case(
                        payload,
                        call_tool=call_tool,
                        source_manifest=sources,
                    ),
                    timeout=120,
                )
            errlog.seek(0, os.SEEK_END)
            output_bytes += errlog.tell()
        if output_bytes > 1_048_576:
            raise NativeStoreValidationError("capture_output_limit")
        selection = cast(dict[str, Any], captured["selection"])
        if captured.get("active_set_fingerprint") != expected_active_set_fingerprint:
            raise NativeStoreValidationError("capture_authority_drift")
        selection["combined_output_bytes"] = output_bytes
        selection["mcp_call_seconds_max"] = 10
        selection["case_seconds"] = 120
        captured_cases.append(captured)

    body: dict[str, Any] = {
        "schema_version": "night-voyager.evidence-loop-mke-capture.v2",
        "canonicalization_id": ("night-voyager.slice0.compact-sorted-utf8-lf.v1"),
        "cases": captured_cases,
    }
    return {**body, "capture_sha256": hashlib.sha256(canonical_json_bytes(body)).hexdigest()}


def _seal_observed_capture_guardrails(
    capture: dict[str, Any],
    *,
    before: dict[str, object],
    after: dict[str, object],
) -> None:
    if before != after:
        raise CliFailure(
            stage="guardrail",
            code="capture_mutation_prohibited",
            exit_code=14,
        )
    cases_value = capture.get("cases")
    if not isinstance(cases_value, list):
        raise CliFailure(stage="producer", code="capture_invalid", exit_code=13)
    for case_value in cast(list[object], cases_value):
        if not isinstance(case_value, dict):
            raise CliFailure(stage="producer", code="capture_invalid", exit_code=13)
        case = cast(dict[str, Any], case_value)
        observations = case.get("guardrail_observations")
        if observations != {
            "allowed_read_tools_only": True,
            "retrieved_content_treated_as_untrusted_data": True,
            "authority_actions_emitted": 0,
        }:
            raise CliFailure(
                stage="guardrail",
                code="capture_tool_guardrail_invalid",
                exit_code=14,
            )
        case["guardrails"] = {
            "night_voyager_business_mutation": False,
            "filesystem_mutation": False,
            "database_mutation": False,
            "instruction_executed": False,
            "promotion_attempted": False,
            "human_authority_granted": False,
        }
        case["guardrail_proof"] = {
            "immutable_readback_verified": True,
            "checkout_head": before["head"],
            "checkout_tree": before["tree"],
            "status_entry_count": len(cast(list[object], before["status"])),
            "store_tree_sha256": before["store_tree_sha256"],
            "runtime_identity_verified_before_capture": True,
            "allowed_read_tools_only": True,
        }
    capture.pop("capture_sha256", None)
    capture["capture_sha256"] = hashlib.sha256(canonical_json_bytes(capture)).hexdigest()


def _emit_failure(error: CliFailure) -> int:
    print(json.dumps(error.payload, separators=(",", ":"), sort_keys=True))
    print(f"recovery: {error.payload['recovery']}", file=sys.stderr)
    return error.exit_code


def _fresh_holdout_receipt(
    *,
    repo_root: Path,
    dataset: dict[str, Any],
    artifact_bindings: dict[str, Any],
) -> bytes:
    request = canonical_json_bytes({"dataset": dataset, "artifact_bindings": artifact_bindings})
    receipts: list[bytes] = []
    for _ in range(3):
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts/evaluate_evidence_loop.py"),
                "--fresh-worker",
            ],
            cwd=repo_root,
            input=request,
            capture_output=True,
            check=False,
            timeout=30,
        )
        if result.returncode != 0 or result.stderr or len(result.stdout) > 1_048_576:
            raise CliFailure(
                stage="evaluator",
                code="fresh_process_determinism_failed",
                exit_code=13,
            )
        receipts.append(result.stdout)
    if not (receipts[0] == receipts[1] == receipts[2]):
        raise CliFailure(
            stage="evaluator",
            code="fresh_process_determinism_failed",
            exit_code=13,
        )
    return receipts[0]


def _fresh_worker() -> int:
    content = sys.stdin.buffer.read(1_048_577)
    if len(content) > 1_048_576:
        return 13
    try:
        request = json.loads(content)
        if not isinstance(request, dict):
            return 13
        typed_request = cast(dict[str, object], request)
        dataset = typed_request.get("dataset")
        bindings = typed_request.get("artifact_bindings")
        if not isinstance(dataset, dict) or not isinstance(bindings, dict):
            return 13
        evaluation = evaluate_suite(cast(dict[str, Any], dataset))
        receipt = build_terminal_receipt(
            evaluation,
            run_kind="holdout",
            artifact_bindings=cast(dict[str, Any], bindings),
        )
    except (json.JSONDecodeError, ValueError):
        return 13
    sys.stdout.buffer.write(receipt)
    return 0


def _prepare(args: argparse.Namespace) -> dict[str, object]:
    if args.output is None:
        raise CliFailure(stage="arguments", code="invalid_cli", exit_code=2)
    development = args.development_dataset is not None
    revealed = args.dataset is not None
    if development == revealed:
        raise CliFailure(stage="arguments", code="invalid_cli", exit_code=2)
    artifact_bindings: dict[str, Any] | None = None
    if development:
        if args.store_receipt is None or any(
            value is not None
            for value in (
                args.pre_registration,
                args.store_root,
                args.capture_output,
            )
        ):
            raise CliFailure(stage="arguments", code="invalid_cli", exit_code=2)
        store_receipt = _object(args.store_receipt)
        store_seal_value = store_receipt.get("store_seal")
        store_seal = (
            cast(dict[str, Any], store_seal_value) if isinstance(store_seal_value, dict) else {}
        )
        if (
            store_seal.get("lifecycle_state") != "sealed_read_only"
            or store_receipt.get("mutation_capability") != "closed_after_preparation"
            or store_receipt.get("read_only_reopen_verified") is not True
        ):
            raise CliFailure(stage="producer", code="store_receipt_invalid", exit_code=10)
        dataset = _object(args.development_dataset)
        run_kind = "development"
        success_code = "evidence_loop_development_evaluated"
    else:
        if None in (args.pre_registration, args.store_root) or args.capture_output is None:
            raise CliFailure(stage="arguments", code="invalid_cli", exit_code=2)
        repo_root = Path(__file__).resolve().parents[1]
        _allowlisted_path(repo_root, args.dataset, POST_REVEAL_ALLOWLIST[0])
        capture_path = args.capture_output
        _allowlisted_path(repo_root, capture_path, POST_REVEAL_ALLOWLIST[1])
        _allowlisted_path(repo_root, args.output, POST_REVEAL_ALLOWLIST[2])
        _exact_path(
            repo_root,
            args.pre_registration,
            "tmp/evidence-loop-a3-native-operator-final/receipts/pre-registration-v2.json",
        )
        _exact_path(
            repo_root,
            args.store_root,
            "tmp/evidence-loop-a3-native-operator-final/store",
        )
        try:
            pre_registration = verify_pre_registration_receipt(args.pre_registration.read_bytes())
        except (OSError, json.JSONDecodeError, ValueError) as error:
            raise CliFailure(
                stage="freeze", code="pre_registration_invalid", exit_code=13
            ) from error
        if pre_registration.get("post_reveal_generated_file_allowlist") != list(
            POST_REVEAL_ALLOWLIST
        ):
            raise CliFailure(stage="freeze", code="pre_registration_invalid", exit_code=13)
        try:
            validate_runtime_identity(
                cast(dict[str, Any], pre_registration.get("environment")),
                repo_root=repo_root,
            )
        except (TypeError, ValueError) as error:
            raise CliFailure(stage="freeze", code="runtime_identity_drift", exit_code=13) from error
        current_head = _git(repo_root, "rev-parse", "HEAD")
        current_tree = _git(repo_root, "rev-parse", "HEAD^{tree}")
        status_lines = _git(
            repo_root, "status", "--porcelain=v1", "--untracked-files=all"
        ).splitlines()
        try:
            validate_frozen_checkout(
                pre_registration,
                repo_root=repo_root,
                store_root=args.store_root,
                current_head=current_head,
                current_tree=current_tree,
                status_paths=tuple(line[3:] for line in status_lines),
                allowed_generated_paths=POST_REVEAL_ALLOWLIST[:1],
            )
        except ValueError as error:
            raise CliFailure(stage="freeze", code="freeze_order_invalid", exit_code=11) from error
        try:
            sealed_store = cast(dict[str, Any], pre_registration["sealed_store"])
            native_runtime_identity = cast(
                dict[str, Any],
                pre_registration["native_runtime_identity"],
            )
            provider_locks = cast(dict[str, Any], pre_registration["provider_locks"])
            mke_lock = cast(dict[str, Any], provider_locks["mke"])
            wheel_sha256 = str(mke_lock["wheel_sha256"])
            _verify_capture_authority(
                store_root=args.store_root,
                sealed_store=sealed_store,
                native_runtime_identity=native_runtime_identity,
                wheel_sha256=wheel_sha256,
            )
            before_capture = _capture_state(repo_root, args.store_root)
            revealed_dataset = _object(args.dataset)
            capture = asyncio.run(
                _capture_native_dataset(
                    dataset=revealed_dataset,
                    repo_root=repo_root,
                    store_root=args.store_root,
                    expected_active_set_fingerprint=str(sealed_store["active_set_fingerprint"]),
                )
            )
            _verify_capture_authority(
                store_root=args.store_root,
                sealed_store=sealed_store,
                native_runtime_identity=native_runtime_identity,
                wheel_sha256=wheel_sha256,
            )
            after_capture = _capture_state(repo_root, args.store_root)
            _seal_observed_capture_guardrails(capture, before=before_capture, after=after_capture)
            validate_capture_for_dataset(
                capture,
                revealed_dataset,
                expected_active_set_fingerprint=str(sealed_store["active_set_fingerprint"]),
                expected_store_tree_sha256=str(sealed_store["tree_sha256"]),
            )
        except (
            KeyError,
            TimeoutError,
            NativeStoreValidationError,
            ValueError,
        ) as error:
            raise CliFailure(
                stage="producer",
                code="mke_capture_inconclusive",
                exit_code=12,
            ) from error
        capture_content = canonical_json_bytes(capture)
        capture = verify_capture_artifact(capture_content)
        _write_exclusive(args.capture_output, capture_content)
        dataset = normalize_revealed_dataset(revealed_dataset, capture)
        artifact_bindings = {
            "pre_registration_sha256": hashlib.sha256(
                args.pre_registration.read_bytes()
            ).hexdigest(),
            "holdout_dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
            "mke_capture_sha256": hashlib.sha256(capture_path.read_bytes()).hexdigest(),
        }
        run_kind = "holdout"
        success_code = "evidence_loop_evaluated"
    try:
        evaluation = evaluate_suite(dataset)
    except ValueError as error:
        raise CliFailure(stage="evaluator", code="evaluation_invalid", exit_code=13) from error
    disposition = evaluation["terminal_disposition"]
    receipt = (
        _fresh_holdout_receipt(
            repo_root=Path(__file__).resolve().parents[1],
            dataset=dataset,
            artifact_bindings=cast(dict[str, Any], artifact_bindings),
        )
        if run_kind == "holdout"
        else build_terminal_receipt(evaluation, run_kind=run_kind)
    )
    _write_exclusive(args.output, receipt)
    if disposition == "inconclusive":
        raise CliFailure(stage="evaluator", code="evaluation_inconclusive", exit_code=12)
    if disposition == "evaluation_invalid":
        case_results = cast(list[dict[str, Any]], evaluation["case_results"])
        prohibited_mutation = any(
            result.get("reason_code") == "guardrail_veto" for result in case_results
        )
        raise CliFailure(
            stage="guardrail" if prohibited_mutation else "evaluator",
            code=("mutation_prohibited" if prohibited_mutation else "evaluation_invalid"),
            exit_code=14 if prohibited_mutation else 13,
        )
    return {
        "schema_version": "night-voyager.evidence-loop-evaluation-response.v2",
        "ok": True,
        "code": success_code,
        "terminal_disposition": evaluation["terminal_disposition"],
        "receipt": {
            "basename": args.output.name,
            "byte_length": len(receipt),
        },
    }


def main(argv: list[str] | None = None) -> int:
    if argv == ["--fresh-worker"] or (argv is None and sys.argv[1:] == ["--fresh-worker"]):
        return _fresh_worker()
    try:
        args = _parser().parse_args(argv)
        payload = _prepare(args)
    except CliFailure as error:
        return _emit_failure(error)
    except Exception:
        return _emit_failure(CliFailure(stage="internal", code="evaluation_failed", exit_code=13))
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
