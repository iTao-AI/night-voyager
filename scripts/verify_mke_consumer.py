#!/usr/bin/env python3
"""Bounded M4B candidate identity checks and proof controller entry point."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Literal, cast

from night_voyager.evidence.candidate_lock import (
    build_candidate_lock,
    canonical_sha256,
    verify_candidate_artifact,
)
from night_voyager.evidence.mke_contract import (
    AskLibrarySuccessV1,
    ListLibrariesSuccessV1,
    SearchLibrarySuccessV1,
)
from night_voyager.evidence.mke_models import (
    CandidateEvidence,
    CandidateStoreNoMatch,
    EvidenceQuery,
    M4BManifestV1,
    MkeConsumerError,
    MkeFailureCode,
)
from night_voyager.evidence.mke_projection import (
    project_ask_candidate,
    project_search_candidate,
    require_paired_candidate,
)

REPOSITORY = Path(__file__).resolve().parents[1]
LOCK_PATH = REPOSITORY / "fixtures" / "m4b" / "candidate-artifact-lock.json"
MANIFEST_PATH = REPOSITORY / "fixtures" / "m4b" / "manifest.json"
ASSERTIONS_PATH = REPOSITORY / "fixtures" / "m4b" / "smoke-assertions.json"
SOURCE_PATH = REPOSITORY / "fixtures" / "m4b" / "sources" / "australia-program-fit.pdf"
PROOF_STAGES = (
    "artifact_verify",
    "env_create",
    "wheel_install",
    "store_setup",
    "initialize",
    "discover",
    "search",
    "ask",
    "cleanup",
)
ProofStage = Literal[
    "artifact_verify",
    "env_create",
    "wheel_install",
    "store_setup",
    "initialize",
    "discover",
    "search",
    "ask",
    "cleanup",
]


def render(value: Mapping[str, object]) -> None:
    print(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")))


def proof_failure_payload(code: str) -> dict[str, str]:
    return {
        "schema_version": "night_voyager.m4b_proof.v1",
        "status": "failed",
        "code": code,
    }


class ProofFailure(RuntimeError):
    def __init__(self, code: MkeFailureCode, stage: ProofStage) -> None:
        self.code = code
        self.stage = stage
        super().__init__(code)


def _run_stage(command: list[str], *, stage: ProofStage, code: MkeFailureCode) -> None:
    try:
        completed = subprocess.run(
            command,
            cwd=REPOSITORY,
            env={
                key: value
                for key in ("HOME", "PATH", "TMPDIR")
                if (value := os.environ.get(key)) is not None
            },
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ProofFailure(code, stage) from error
    if (
        completed.returncode != 0
        or len(completed.stdout) > 1_048_576
        or len(completed.stderr) > 65_536
    ):
        raise ProofFailure(code, stage)


def _query(manifest: M4BManifestV1, text: str) -> EvidenceQuery:
    source = manifest.sources[0]
    return EvidenceQuery(
        schema_version=1,
        organization_id=manifest.organization_id,
        source_pack_id=manifest.source_pack_id,
        source_pack_version=manifest.source_pack_version,
        claim=source.claim,
        evidence_role=source.evidence_role,
        query=text,
        allowed_locator_kinds=("page",),
        limit=1,
    )


async def _run_reads(
    executable: Path,
    database: Path,
    allowed_root: Path,
    manifest: M4BManifestV1,
    assertions: dict[str, object],
) -> dict[str, object]:
    from night_voyager.adapters.mke_readonly import MkeReadOnlyConfig, MkeReadOnlyConsumer

    config = MkeReadOnlyConfig(
        executable=executable,
        database=database,
        allowed_root=allowed_root,
        cwd=allowed_root,
        child_environment={
            "HOME": str(allowed_root / "home"),
            "PATH": str(executable.parent),
        },
        startup_timeout_seconds=60.0,
        tool_timeout_seconds=60.0,
        parsed_response_bytes=1_048_576,
        selected_text_bytes=65_536,
        stderr_bytes=65_536,
    )
    consumer = MkeReadOnlyConsumer(config)
    stage: ProofStage = "initialize"
    try:
        listed = await consumer.initialize()
        stage = "discover"
        if not isinstance(listed.root, ListLibrariesSuccessV1):
            raise ProofFailure("mke_contract_incompatible", stage)
        if listed.root.observation.state != "active":
            raise ProofFailure("mke_contract_incompatible", stage)
        observation = listed.root.observation
        if (
            observation.source_count != 1
            or observation.active_publication_count != 1
            or observation.active_evidence_count != 1
        ):
            raise ProofFailure("mke_source_snapshot_changed", stage)

        raw_positive = assertions.get("positive")
        raw_no_match = assertions.get("no_match")
        if not isinstance(raw_positive, dict) or not isinstance(raw_no_match, dict):
            raise ProofFailure("mke_consumer_failed", stage)
        positive = cast(dict[str, object], raw_positive)
        no_match = cast(dict[str, object], raw_no_match)
        positive_text = positive.get("query")
        absent_text = no_match.get("query")
        if not isinstance(positive_text, str) or not isinstance(absent_text, str):
            raise ProofFailure("mke_consumer_failed", stage)

        stage = "search"
        positive_query = _query(manifest, positive_text)
        searched = await consumer.search(positive_query)
        if not isinstance(searched.root, SearchLibrarySuccessV1):
            raise ProofFailure("mke_response_invalid", stage)
        search_candidate = project_search_candidate(positive_query, manifest, searched.root)
        if not isinstance(search_candidate, CandidateEvidence):
            raise ProofFailure("mke_active_store_no_match", stage)

        stage = "ask"
        asked = await consumer.ask(positive_query)
        if not isinstance(asked.root, AskLibrarySuccessV1):
            raise ProofFailure("mke_response_invalid", stage)
        ask_candidate = project_ask_candidate(positive_query, manifest, asked.root)
        if not isinstance(ask_candidate, CandidateEvidence):
            raise ProofFailure("mke_active_store_no_match", stage)
        require_paired_candidate(search_candidate, ask_candidate)

        absent_query = _query(manifest, absent_text)
        absent_search = await consumer.search(absent_query)
        absent_ask = await consumer.ask(absent_query)
        if not isinstance(absent_search.root, SearchLibrarySuccessV1) or not isinstance(
            absent_ask.root, AskLibrarySuccessV1
        ):
            raise ProofFailure("mke_response_invalid", stage)
        search_no_match = project_search_candidate(absent_query, manifest, absent_search.root)
        ask_no_match = project_ask_candidate(absent_query, manifest, absent_ask.root)
        if not isinstance(search_no_match, CandidateStoreNoMatch) or not isinstance(
            ask_no_match, CandidateStoreNoMatch
        ):
            raise ProofFailure("mke_consumer_failed", stage)
        return {
            "source_count": observation.source_count,
            "active_publication_count": observation.active_publication_count,
            "active_evidence_count": observation.active_evidence_count,
            "observation_state": observation.state,
            "identity_verified": True,
            "contracts_verified": True,
            "mapping_verified": True,
            "pairing_verified": True,
            "proof_pack_no_match": True,
            "redaction_verified": True,
        }
    except ProofFailure:
        raise
    except MkeConsumerError as error:
        raise ProofFailure(error.failure.code, stage) from error
    except Exception as error:
        raise ProofFailure("mke_consumer_failed", stage) from error
    finally:
        try:
            await consumer.aclose()
        except MkeConsumerError as error:
            raise ProofFailure("mke_cleanup_failed", "cleanup") from error


def run_proof(args: argparse.Namespace) -> dict[str, object]:
    started = time.monotonic()
    stage: ProofStage = "artifact_verify"
    try:
        verified = verify_candidate_artifact(
            args.wheel, args.candidate_receipt, LOCK_PATH
        )
    except MkeConsumerError as error:
        raise ProofFailure(error.failure.code, stage) from error
    manifest = M4BManifestV1.model_validate_json(MANIFEST_PATH.read_text(encoding="utf-8"))
    raw_assertions = json.loads(ASSERTIONS_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw_assertions, dict):
        raise ProofFailure("mke_consumer_failed", stage)
    assertions = cast(dict[str, object], raw_assertions)
    if hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest() != manifest.sources[0].sha256:
        raise ProofFailure("mke_source_snapshot_changed", stage)

    try:
        with tempfile.TemporaryDirectory(prefix="night-voyager-m4b-proof-") as directory:
            root = Path(directory)
            environment = root / "mke-env"
            source_root = root / "source"
            source_root.mkdir()
            copied_source = source_root / SOURCE_PATH.name
            shutil.copyfile(SOURCE_PATH, copied_source)
            database = root / "mke.sqlite"
            stage = "env_create"
            _run_stage(
                ["uv", "venv", str(environment), "--python", "3.12"],
                stage=stage,
                code="mke_environment_failed",
            )
            python = environment / "bin" / "python"
            executable = environment / "bin" / "mke"
            stage = "wheel_install"
            _run_stage(
                ["uv", "pip", "install", "--python", str(python), str(verified.wheel)],
                stage=stage,
                code="mke_install_failed",
            )
            stage = "store_setup"
            _run_stage(
                [
                    str(executable),
                    "--db",
                    str(database),
                    "ingest",
                    str(copied_source),
                    "--json",
                ],
                stage=stage,
                code="mke_store_setup_failed",
            )
            reads = asyncio.run(
                asyncio.wait_for(
                    _run_reads(
                        executable, database, source_root, manifest, assertions
                    ),
                    timeout=max(1.0, 300.0 - (time.monotonic() - started)),
                )
            )
    except ProofFailure:
        raise
    except TimeoutError as error:
        raise ProofFailure("mke_tool_timeout", stage) from error
    except Exception as error:
        raise ProofFailure("mke_consumer_failed", stage) from error

    receipt: dict[str, object] = {
        "schema_version": "night_voyager.m4b_proof.v1",
        "status": "passed",
        "source_pack_id": str(manifest.source_pack_id),
        "source_pack_version": manifest.source_pack_version,
        "mke_package_version": verified.package_version,
        "mke_source_commit": verified.source_commit,
        "mke_wheel_sha256": verified.wheel_sha256,
        "required_tools": ["list_libraries_v1", "search_library_v1", "ask_library_v1"],
        "response_schemas": [
            "mke.list_libraries_response.v1",
            "mke.search_library_response.v1",
            "mke.ask_library_response.v1",
        ],
        **reads,
        "cleanup_verified": True,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def run_proof_command(args: argparse.Namespace) -> int:
    started = time.monotonic()
    try:
        render(run_proof(args))
        return 0
    except ProofFailure as error:
        render(proof_failure_payload(error.code))
        elapsed_ms = min(int((time.monotonic() - started) * 1000), 300_000)
        print(
            "FAILED CHECK "
            f"stage={error.stage} code={error.code} expected=passed observed=failed "
            f"recovery=retry elapsed_ms={elapsed_ms}",
            file=sys.stderr,
        )
        return 1


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
    proof = commands.add_parser("proof")
    proof.add_argument("--wheel", required=True, type=Path)
    proof.add_argument("--candidate-receipt", required=True, type=Path)
    proof.add_argument("--json", action="store_true")
    return root


def main() -> int:
    args = parser().parse_args()
    if args.command == "proof":
        return run_proof_command(args)
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
