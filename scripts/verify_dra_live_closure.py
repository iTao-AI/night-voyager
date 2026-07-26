#!/usr/bin/env python3
"""Bounded DRA live-capture controller and provider-free rehearsal."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import signal
import stat
import subprocess
import sys
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal, NoReturn, cast
from urllib.parse import urlsplit
from uuid import UUID

import httpx2
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from night_voyager.adapters.dra_readonly import (
    DraClientConfig,
    Httpx2DraTransport,
)
from night_voyager.dra.fixtures import load_live_closure_scenario
from night_voyager.dra.live_controller import (
    CaptureLiveCommand,
    DecideCommand,
    DraLiveCaptureController,
    DraLiveClosureController,
    PromoteCommand,
    ReconcileCreateCommand,
    ResumePollCommand,
    ReviewCommand,
    SelectAndImportCommand,
)
from night_voyager.dra.live_evaluation import (
    DraLiveEvaluationReportV1,
    DraLiveOutcomeExpectedV1,
    evaluate_full_closure,
)
from night_voyager.dra.live_fakes import (
    ScenarioCandidateGateway,
    ScenarioDraLiveTransport,
)
from night_voyager.dra.live_http import (
    EphemeralHttpAuthority,
    NightVoyagerAuthorityGateway,
)
from night_voyager.dra.live_models import (
    DraCandidateReadinessReceiptV1,
    DraCaptureInputV1,
    DraCaptureIntentV1,
    DraCaptureReceiptV1,
    DraControllerStopReceiptV1,
    DraDecisionInputV1,
    DraDecisionReceiptV1,
    DraFrozenRequestV1,
    DraInspectionRequiredReceiptV1,
    DraPollRecoveryReceiptV1,
    DraPreflightReceiptV1,
    DraPromotionInputV1,
    DraPromotionReceiptV1,
    DraReceiptIdentityV1,
    DraReconciliationRequiredReceiptV1,
    DraReviewInputV1,
    DraReviewReceiptV1,
    derive_identity_hash,
)
from night_voyager.dra.live_outcome import DraLiveOutcomeIntentV1
from night_voyager.dra.live_outcome_postgres import PostgresLiveOutcomeInspector
from night_voyager.dra.live_storage import (
    CleanupResultV1,
    LiveReceiptStore,
    LiveStorageError,
    LiveStorageInvalid,
)
from night_voyager.dra.models import DraCandidateImportV1
from night_voyager.dra.ports import DraCandidateViewV1
from night_voyager.identity.models import ActorContext, ActorRole

ONE_ATTEMPT_ACK = "separately-authorized-one-attempt"
CLEANUP_ACK = "delete-exact-live-artifact"
ALLOWED_RECOVERY_COMMAND = (
    "uv",
    "run",
    "pytest",
    "-q",
    "tests/integration/dra/test_live_closure_recovery.py",
    "tests/unit/dra/test_live_review_controller.py",
    "tests/unit/dra/test_live_decision_controller.py",
)
CANDIDATE_TASK_PROJECT = "night-voyager-dra-v0-1-6-live-acceptance"
DOCKER_VM_MINIMUM_KIB = 8_388_608
HOST_MINIMUM_KIB = 5_242_880
AUTHORITY_REVIEW_ACK = "independent_authority_review_attested"
DOCTOR_SEMANTIC_OUTPUT = (
    "PASSED CHECK: Docker daemon and Compose --wait are available\n"
    "PASSED CHECK: host project filesystem <available-kib> KiB available\n"
    "PASSED CHECK: Docker VM filesystem <available-kib> KiB available\n"
    "PASSED CHECK: port 127.0.0.1:3000 is free\n"
    "PASSED CHECK: port 127.0.0.1:8000 is free\n"
    "PASSED CHECK: port 127.0.0.1:55432 is free\n"
    "PASSED CHECK: contributor Python/uv/Node/npm toolchain is available\n"
    "doctor: dev preflight passed\n"
)
DOCTOR_OUTPUT_PATTERN = re.compile(
    r"PASSED CHECK: Docker daemon and Compose --wait are available\n"
    r"PASSED CHECK: host project filesystem ([0-9]+) KiB available\n"
    r"PASSED CHECK: Docker VM filesystem ([0-9]+) KiB available\n"
    r"PASSED CHECK: port 127\.0\.0\.1:3000 is free\n"
    r"PASSED CHECK: port 127\.0\.0\.1:8000 is free\n"
    r"PASSED CHECK: port 127\.0\.0\.1:55432 is free\n"
    r"PASSED CHECK: contributor Python/uv/Node/npm toolchain is available\n"
    r"doctor: dev preflight passed\n"
)
DOCKER_INVENTORY_COMMANDS = (
    ("compose", ("docker", "compose", "ls", "--all", "--format", "json")),
    ("containers", ("docker", "ps", "-a", "--no-trunc", "--format", "json")),
    (
        "images",
        (
            "docker",
            "image",
            "ls",
            "--digests",
            "--no-trunc",
            "--format",
            "json",
        ),
    ),
    ("build_cache", ("docker", "buildx", "du", "--format", "json")),
    ("networks", ("docker", "network", "ls", "--no-trunc", "--format", "json")),
    ("volumes", ("docker", "volume", "ls", "--format", "json")),
)
REHEARSAL_ORGANIZATION = UUID("10000000-0000-0000-0000-000000000001")
REHEARSAL_CASE = UUID("40000000-0000-0000-0000-000000000003")
REHEARSAL_ACTOR = UUID("20000000-0000-0000-0000-000000000001")
REHEARSAL_SESSION = UUID("30000000-0000-0000-0000-000000000001")
REHEARSAL_QUERY = b"bounded synthetic query"

ExitClass = Literal[
    "success",
    "safe_pause",
    "recoverable_incomplete",
    "terminal_failure",
    "cleanup_incomplete",
]
EXIT_CODES: dict[ExitClass, int] = {
    "success": 0,
    "safe_pause": 10,
    "recoverable_incomplete": 20,
    "terminal_failure": 30,
    "cleanup_incomplete": 40,
}


def _emit(payload: dict[str, object], *, as_json: bool) -> NoReturn:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    if len(encoded.encode("utf-8")) > 16_384:
        payload = {
            "schema_version": "night-voyager.dra-live-command-result.v1",
            "exit_class": "terminal_failure",
            "problem_code": "operator_output_limit",
            "permitted_next_command": "stop",
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if as_json:
        print(encoded)
    else:
        print(
            f"DRA live closure: {payload['exit_class']} "
            f"({payload.get('problem_code', 'none')})"
        )
    raise SystemExit(EXIT_CODES[payload["exit_class"]])  # type: ignore[index]


def _result_payload(
    exit_class: ExitClass,
    problem_code: str,
    permitted_next_command: str,
    *,
    receipt: DraReceiptIdentityV1 | None = None,
    **extra: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "night-voyager.dra-live-command-result.v1",
        "exit_class": exit_class,
        "problem_code": problem_code,
        "safe_interpretation": (
            "No provider or product authority is inferred beyond this receipt."
        ),
        "permitted_next_command": permitted_next_command,
    }
    if receipt is not None:
        payload["receipt"] = receipt.model_dump(mode="json")
    payload.update(extra)
    return payload


def _emit_mutation_preview(stage: str, payload: dict[str, object]) -> None:
    """Emit a bounded, content-free preview before any Stage 2-4 authority call."""
    preview = {
        "schema_version": "night-voyager.dra-live-mutation-preview.v1",
        "stage": stage,
        "input_sha256": hashlib.sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest(),
        "acknowledgement": "accepted",
    }
    print(
        json.dumps(preview, sort_keys=True, separators=(",", ":")),
        file=sys.stderr,
    )


def _open_root(path: Path, *, create: bool = False) -> LiveReceiptStore:
    if create:
        created = False
        try:
            os.mkdir(path, mode=0o700)
            created = True
        except FileExistsError:
            try:
                metadata = os.lstat(path)
            except OSError as error:
                raise LiveStorageInvalid("root_invalid") from error
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) != 0o700
            ):
                raise LiveStorageInvalid("root_invalid") from None
        if created:
            nofollow = getattr(os, "O_NOFOLLOW", 0)
            directory = getattr(os, "O_DIRECTORY", 0)
            if nofollow == 0 or directory == 0:
                raise LiveStorageInvalid("root_primitives_unavailable")
            descriptor = os.open(
                path, os.O_RDONLY | directory | nofollow
            )
            try:
                os.fchmod(descriptor, 0o700)
            finally:
                os.close(descriptor)
    return LiveReceiptStore.open(path)


def open_receipt_root(
    path: Path, *, create: bool = False
) -> LiveReceiptStore:
    """Open or safely create one exact private receipt root."""
    return _open_root(path, create=create)


def _read_intent(store: LiveReceiptStore) -> DraCaptureIntentV1:
    return store.read_receipt("intent.json", DraCaptureIntentV1)


def _preflight_receipt(store: LiveReceiptStore) -> DraPreflightReceiptV1:
    return store.read_receipt("preflight.json", DraPreflightReceiptV1)


def _ensure_no_orphaned_artifact(store: LiveReceiptStore) -> None:
    bundle = store.verify_recovery_bundle()
    receipt_names = {item.logical_name for item in bundle.receipts}
    if (
        bundle.artifact is not None
        and "inspection-required.json" not in receipt_names
    ):
        raise ValueError("cleanup_incomplete")


def _command_receipt(
    store: LiveReceiptStore, name: str, value: BaseModel
) -> DraReceiptIdentityV1:
    return store.write_receipt(name, value)


class _CaptureOnlyGateway:
    async def import_candidate(
        self,
        context: ActorContext,
        candidate_import: DraCandidateImportV1,
        idempotency_key: str,
    ) -> DraCandidateViewV1:
        del context, candidate_import, idempotency_key
        raise AssertionError("candidate import requires select-and-import")


class _NightVoyagerCandidateGateway:
    def __init__(self, environ: dict[str, str]) -> None:
        required = (
            "NIGHT_VOYAGER_LIVE_API_BASE_URL",
            "NIGHT_VOYAGER_LIVE_SESSION",
            "NIGHT_VOYAGER_LIVE_CSRF",
        )
        if any(not environ.get(name) for name in required):
            raise ValueError("candidate_environment_incomplete")
        self._base_url = environ[required[0]].rstrip("/")
        parsed = urlsplit(self._base_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("candidate_environment_invalid")
        self._session = environ[required[1]]
        self._csrf = environ[required[2]]
        self._origin = f"{parsed.scheme}://{parsed.netloc}"

    async def import_candidate(
        self,
        context: ActorContext,
        candidate_import: DraCandidateImportV1,
        idempotency_key: str,
    ) -> DraCandidateViewV1:
        payload = candidate_import.model_dump(
            mode="json", exclude_computed_fields=True
        )
        payload.pop("organization_id")
        payload.pop("case_id")
        try:
            async with httpx2.AsyncClient(
                trust_env=False,
                follow_redirects=False,
                timeout=30,
            ) as client:
                response = await client.post(
                    f"{self._base_url}/cases/{candidate_import.case_id}/"
                    f"dra-candidates",
                    json=payload,
                    headers={
                        "Origin": self._origin,
                        "X-CSRF-Token": self._csrf,
                        "Idempotency-Key": idempotency_key,
                    },
                    cookies={"night_voyager_session": self._session},
                )
            if response.status_code != 201:
                raise ValueError("candidate_import_failed")
            raw_response: object = response.json()
            if not isinstance(raw_response, dict):
                raise ValueError("candidate_import_failed")
            response_payload = cast(dict[str, object], raw_response)
            response_payload.pop("schema_version", None)
            return DraCandidateViewV1.model_validate(response_payload)
        except (httpx2.HTTPError, ValueError) as error:
            raise ValueError("candidate_import_failed") from error


def _actor_from_environment(intent: DraCaptureIntentV1) -> ActorContext:
    try:
        organization_id = UUID(
            os.environ["NIGHT_VOYAGER_LIVE_ORGANIZATION_ID"]
        )
        actor_id = UUID(os.environ["NIGHT_VOYAGER_LIVE_ACTOR_ID"])
        session_id = UUID(os.environ["NIGHT_VOYAGER_LIVE_SESSION_ID"])
    except (KeyError, ValueError) as error:
        raise ValueError("candidate_environment_incomplete") from error
    if organization_id != intent.capture.organization_id:
        raise ValueError("candidate_environment_invalid")
    return ActorContext(
        organization_id=organization_id,
        actor_id=actor_id,
        role=ActorRole.ADVISOR,
        session_id=session_id,
    )


def _live_transport(
    intent: DraCaptureIntentV1,
) -> Httpx2DraTransport:
    try:
        base_url = os.environ["DRA_BASE_URL"]
        declared_deadline = float(
            os.environ["DRA_POLL_DEADLINE_SECONDS"]
        )
    except (KeyError, ValueError) as error:
        raise ValueError("producer_environment_incomplete") from error
    if declared_deadline != intent.capture.deadline_seconds:
        raise ValueError("producer_environment_invalid")
    config = DraClientConfig(
        base_url=base_url,
        poll_seconds=intent.capture.poll_seconds,
        deadline_seconds=intent.capture.deadline_seconds,
    )
    return Httpx2DraTransport(config, environ=os.environ)


def freeze_intent(args: argparse.Namespace) -> NoReturn:
    if args.one_attempt_ack != ONE_ATTEMPT_ACK:
        _emit(
            _result_payload(
                "terminal_failure",
                "one_attempt_authorization_required",
                "stop",
            ),
            as_json=args.json,
        )
    query_path = Path(args.query_file)
    try:
        query = query_path.read_bytes()
        query.decode("utf-8", errors="strict")
    except (OSError, UnicodeDecodeError):
        _emit(
            _result_payload(
                "terminal_failure", "request_identity_invalid", "stop"
            ),
            as_json=args.json,
        )
    if not query or len(query) > 1_048_576:
        _emit(
            _result_payload(
                "terminal_failure", "request_identity_invalid", "stop"
            ),
            as_json=args.json,
        )
    scenario = load_live_closure_scenario()
    intent = DraCaptureIntentV1.freeze(
        DraCaptureInputV1(
            scenario_id=scenario.scenario_id,
            producer=scenario.producer,
            organization_id=UUID(args.organization_id),
            case_id=UUID(args.case_id),
            expected_case_revision=args.expected_case_revision,
            advisor_actor_identity_sha256=derive_identity_hash(
                "actor", args.advisor_actor_id
            ),
            tenant_identity_sha256=derive_identity_hash(
                "tenant", args.organization_id
            ),
            request=DraFrozenRequestV1(
                logical_name=query_path.name,
                encoding="utf-8",
                byte_length=len(query),
                sha256=hashlib.sha256(query).hexdigest(),
            ),
            deadline_seconds=args.deadline_seconds,
            poll_seconds=args.poll_seconds,
            receipt_root_id=Path(args.receipt_root).name,
            one_attempt_authorized=True,
        ),
        attempt_id_factory=lambda: f"attempt-{uuid.uuid4().hex}",
    )
    with _open_root(Path(args.receipt_root), create=True) as store:
        receipt = store.write_receipt("intent.json", intent)
    _emit(
        _result_payload(
            "success",
            "intent_frozen",
            "preflight-live",
            receipt=receipt,
            intent_sha256=intent.intent_sha256,
        ),
        as_json=args.json,
    )


def preflight_live(args: argparse.Namespace) -> NoReturn:
    try:
        with _open_root(Path(args.receipt_root)) as store:
            intent = _read_intent(store)
            controller = DraLiveCaptureController(
                ScenarioDraLiveTransport(load_live_closure_scenario()),
                _CaptureOnlyGateway(),
                store,
            )
            preflight = controller.preflight(intent)
            receipt = _command_receipt(store, "preflight.json", preflight)
    except (LiveStorageError, ValueError):
        _emit(
            _result_payload(
                "terminal_failure", "preflight_identity_invalid", "stop"
            ),
            as_json=args.json,
        )
    _emit(
        _result_payload(
            "success",
            "preflight_ready",
            "capture-live",
            receipt=receipt,
            provider_access="not_attempted",
        ),
        as_json=args.json,
    )


def _render_capture_result(
    result: object,
    store: LiveReceiptStore,
    *,
    as_json: bool,
    provider_create_calls: int | None = None,
) -> NoReturn:
    if isinstance(result, DraInspectionRequiredReceiptV1):
        receipt = _command_receipt(
            store, "inspection-required.json", result
        )
        _emit(
            _result_payload(
                "safe_pause",
                "operator_action_required",
                "select-and-import",
                receipt=receipt,
                run_id=result.run_id,
                artifact_present=store.artifact_path() is not None,
                provider_create_calls=provider_create_calls,
            ),
            as_json=as_json,
        )
    if isinstance(result, DraReconciliationRequiredReceiptV1):
        receipt = _command_receipt(
            store, "reconciliation-required.json", result
        )
        _emit(
            _result_payload(
                "recoverable_incomplete",
                "run_acceptance_ambiguous",
                "reconcile-create",
                receipt=receipt,
                provider_create_calls=provider_create_calls,
            ),
            as_json=as_json,
        )
    if isinstance(result, DraPollRecoveryReceiptV1):
        receipt = _command_receipt(store, "poll-recovery.json", result)
        _emit(
            _result_payload(
                "recoverable_incomplete",
                "poll_deadline_exhausted",
                "resume-poll",
                receipt=receipt,
                run_id=result.run_id,
                provider_create_calls=provider_create_calls,
            ),
            as_json=as_json,
        )
    if isinstance(result, DraControllerStopReceiptV1):
        receipt = _command_receipt(store, "failure.json", result)
        exit_class: ExitClass = (
            "cleanup_incomplete"
            if result.cleanup_status == "failed"
            else "terminal_failure"
        )
        _emit(
            _result_payload(
                exit_class,
                result.public_code,
                result.permitted_next_command,
                receipt=receipt,
                provider_create_calls=provider_create_calls,
            ),
            as_json=as_json,
        )
    raise AssertionError("dra_live_capture_result_unreachable")


def capture_live(args: argparse.Namespace) -> NoReturn:
    if args.one_attempt_ack != ONE_ATTEMPT_ACK:
        _emit(
            _result_payload(
                "terminal_failure",
                "one_attempt_authorization_required",
                "stop",
            ),
            as_json=args.json,
        )
    try:
        with _open_root(Path(args.receipt_root)) as store:
            intent = _read_intent(store)
            transport = _live_transport(intent)
            preflight = _preflight_receipt(store)
            _ensure_no_orphaned_artifact(store)
            _actor_from_environment(intent)
            controller = DraLiveCaptureController(
                transport, _CaptureOnlyGateway(), store
            )
            result = asyncio.run(
                controller.capture(
                    CaptureLiveCommand(
                        intent=intent,
                        preflight=preflight,
                        query_path=Path(args.query_file),
                    )
                )
            )
            _render_capture_result(result, store, as_json=args.json)
    except (LiveStorageError, ValueError):
        _emit(
            _result_payload(
                "terminal_failure", "capture_environment_invalid", "stop"
            ),
            as_json=args.json,
        )


def select_and_import(args: argparse.Namespace) -> NoReturn:
    try:
        with _open_root(Path(args.receipt_root)) as store:
            intent = _read_intent(store)
            inspection = store.read_receipt(
                "inspection-required.json",
                DraInspectionRequiredReceiptV1,
            )
            controller = DraLiveCaptureController(
                ScenarioDraLiveTransport(load_live_closure_scenario()),
                _NightVoyagerCandidateGateway(dict(os.environ)),
                store,
            )
            result = asyncio.run(
                controller.select_and_import(
                    SelectAndImportCommand(
                        intent=intent,
                        inspection=inspection,
                        declared_raw_url=args.declared_raw_url,
                        context=_actor_from_environment(intent),
                    )
                )
            )
            if isinstance(result, DraControllerStopReceiptV1):
                _render_capture_result(result, store, as_json=args.json)
            receipt = _command_receipt(store, "capture.json", result)
            _emit(
                _result_payload(
                    "success",
                    "candidate_imported",
                    "stop",
                    receipt=receipt,
                    candidate_authority=result.candidate_authority,
                    artifact_present=store.artifact_path() is not None,
                ),
                as_json=args.json,
            )
    except (LiveStorageError, ValueError):
        _emit(
            _result_payload(
                "terminal_failure", "candidate_environment_invalid", "stop"
            ),
            as_json=args.json,
        )


def reconcile_create(args: argparse.Namespace) -> NoReturn:
    if args.exact_replay_ack != ONE_ATTEMPT_ACK:
        _emit(
            _result_payload(
                "terminal_failure",
                "reconciliation_authorization_required",
                "stop",
            ),
            as_json=args.json,
        )
    try:
        with _open_root(Path(args.receipt_root)) as store:
            intent = _read_intent(store)
            transport = _live_transport(intent)
            _actor_from_environment(intent)
            controller = DraLiveCaptureController(
                transport, _CaptureOnlyGateway(), store
            )
            result = asyncio.run(
                controller.reconcile_create(
                    ReconcileCreateCommand(
                        intent=intent,
                        preflight=_preflight_receipt(store),
                        prior=store.read_receipt(
                            "reconciliation-required.json",
                            DraReconciliationRequiredReceiptV1,
                        ),
                        query_path=Path(args.query_file),
                        exact_replay_authorized=True,
                    )
                )
            )
            _render_capture_result(result, store, as_json=args.json)
    except (LiveStorageError, ValueError):
        _emit(
            _result_payload(
                "terminal_failure",
                "reconciliation_environment_invalid",
                "stop",
            ),
            as_json=args.json,
        )


def resume_poll(args: argparse.Namespace) -> NoReturn:
    try:
        with _open_root(Path(args.receipt_root)) as store:
            intent = _read_intent(store)
            transport = _live_transport(intent)
            _actor_from_environment(intent)
            controller = DraLiveCaptureController(
                transport, _CaptureOnlyGateway(), store
            )
            result = asyncio.run(
                controller.resume_poll(
                    ResumePollCommand(
                        intent=intent,
                        prior=store.read_receipt(
                            "poll-recovery.json", DraPollRecoveryReceiptV1
                        ),
                    )
                )
            )
            _render_capture_result(result, store, as_json=args.json)
    except (LiveStorageError, ValueError):
        _emit(
            _result_payload(
                "terminal_failure", "poll_recovery_invalid", "stop"
            ),
            as_json=args.json,
        )


def inspect_recovery(args: argparse.Namespace) -> NoReturn:
    try:
        with _open_root(Path(args.receipt_root)) as store:
            bundle = store.verify_recovery_bundle()
            intent = _read_intent(store)
            names = {item.logical_name for item in bundle.receipts}
            if bundle.artifact is not None and "inspection-required.json" not in names:
                next_command = "cleanup"
                stage = "cleanup-incomplete"
            elif "capture.json" in names:
                next_command = "stop"
                stage = "capture-live"
            elif "inspection-required.json" in names:
                next_command = "select-and-import"
                stage = "terminal-projection"
            elif "poll-recovery.json" in names:
                next_command = "resume-poll"
                stage = "run-accepted"
            elif "reconciliation-required.json" in names:
                next_command = "reconcile-create"
                stage = "provider-attempt"
            else:
                next_command = "capture-live"
                stage = "preflight"
            provider_attempt_consumed = False
            receipt_types = (
                ("capture.json", DraCaptureReceiptV1),
                (
                    "inspection-required.json",
                    DraInspectionRequiredReceiptV1,
                ),
                ("poll-recovery.json", DraPollRecoveryReceiptV1),
                (
                    "reconciliation-required.json",
                    DraReconciliationRequiredReceiptV1,
                ),
                ("failure.json", DraControllerStopReceiptV1),
            )
            for receipt_name, receipt_type in receipt_types:
                if receipt_name in names:
                    provider_attempt_consumed = store.read_receipt(
                        receipt_name, receipt_type
                    ).provider_attempt_consumed
                    break
    except (LiveStorageError, ValueError):
        _emit(
            _result_payload(
                "terminal_failure", "recovery_bundle_invalid", "stop"
            ),
            as_json=args.json,
        )
    exit_class: ExitClass = (
        "cleanup_incomplete" if next_command == "cleanup" else "success"
    )
    _emit(
        _result_payload(
            exit_class,
            (
                "cleanup_incomplete"
                if exit_class == "cleanup_incomplete"
                else "recovery_inspected"
            ),
            next_command,
            intent_sha256=intent.intent_sha256,
            attempt_id=intent.attempt_id,
            last_completed_stage=stage,
            provider_attempt_consumed=provider_attempt_consumed,
            required_external_inputs=(
                ["operator_declared_raw_url"]
                if next_command == "select-and-import"
                else []
            ),
            forbidden_next_actions=[
                "promotion",
                "planning",
                "review",
                "family-decision",
            ],
            artifact_present=bundle.artifact is not None,
            session_material_retained=False,
        ),
        as_json=args.json,
    )


def cleanup(args: argparse.Namespace) -> NoReturn:
    try:
        with _open_root(Path(args.receipt_root)) as store:
            artifact_present = store.artifact_path() is not None
            if args.delete_ack != CLEANUP_ACK:
                result = CleanupResultV1(
                    status="retained" if artifact_present else "absent",
                    artifact_present=artifact_present,
                )
            else:
                result = store.delete_artifact()
                store.write_receipt("cleanup.json", result)
    except LiveStorageError:
        _emit(
            _result_payload(
                "cleanup_incomplete", "cleanup_root_invalid", "cleanup"
            ),
            as_json=args.json,
        )
    exit_class: ExitClass = (
        "cleanup_incomplete" if result.status == "failed" else "success"
    )
    _emit(
        _result_payload(
            exit_class,
            f"cleanup_{result.status}",
            "cleanup" if result.status in {"retained", "failed"} else "stop",
            removed=["artifact"] if result.status == "removed" else [],
            absent=["artifact"] if result.status == "absent" else [],
            retained=["artifact"] if result.status == "retained" else [],
            failed=["artifact"] if result.status == "failed" else [],
        ),
        as_json=args.json,
    )


def _rehearsal_capture(root: Path, *, as_json: bool) -> NoReturn:
    root.mkdir(mode=0o700, exist_ok=False)
    query_path = root.parent / f"{root.name}.query.txt"
    query_path.write_bytes(REHEARSAL_QUERY)
    query_path.chmod(0o600)
    scenario = load_live_closure_scenario()
    intent = DraCaptureIntentV1.freeze(
        DraCaptureInputV1(
            scenario_id=scenario.scenario_id,
            producer=scenario.producer,
            organization_id=REHEARSAL_ORGANIZATION,
            case_id=REHEARSAL_CASE,
            expected_case_revision=1,
            advisor_actor_identity_sha256=derive_identity_hash(
                "actor", str(REHEARSAL_ACTOR)
            ),
            tenant_identity_sha256=derive_identity_hash(
                "tenant", str(REHEARSAL_ORGANIZATION)
            ),
            request=DraFrozenRequestV1(
                logical_name=query_path.name,
                encoding="utf-8",
                byte_length=len(REHEARSAL_QUERY),
                sha256=hashlib.sha256(REHEARSAL_QUERY).hexdigest(),
            ),
            receipt_root_id=root.name,
            one_attempt_authorized=True,
        ),
        attempt_id_factory=lambda: "attempt-rehearsal-00000001",
    )
    transport = ScenarioDraLiveTransport(scenario)
    try:
        with _open_root(root) as store:
            controller = DraLiveCaptureController(
                transport, ScenarioCandidateGateway(), store
            )
            preflight = controller.preflight(intent)
            result = asyncio.run(
                controller.capture(
                    CaptureLiveCommand(
                        intent=intent,
                        preflight=preflight,
                        query_path=query_path,
                    )
                )
            )
            store.verify_recovery_bundle()
            _render_capture_result(
                result,
                store,
                as_json=as_json,
                provider_create_calls=transport.create_calls,
            )
    finally:
        query_path.unlink(missing_ok=True)


def _rehearsal_resume(
    root: Path, declared_raw_url: str, *, as_json: bool
) -> NoReturn:
    transport = ScenarioDraLiveTransport(load_live_closure_scenario())
    with _open_root(root) as store:
        intent = _read_intent(store)
        inspection = store.read_receipt(
            "inspection-required.json", DraInspectionRequiredReceiptV1
        )
        controller = DraLiveCaptureController(
            transport, ScenarioCandidateGateway(), store
        )
        result = asyncio.run(
            controller.select_and_import(
                SelectAndImportCommand(
                    intent=intent,
                    inspection=inspection,
                    declared_raw_url=declared_raw_url,
                    context=ActorContext(
                        organization_id=REHEARSAL_ORGANIZATION,
                        actor_id=REHEARSAL_ACTOR,
                        role=ActorRole.ADVISOR,
                        session_id=REHEARSAL_SESSION,
                    ),
                )
            )
        )
        if not isinstance(result, DraCaptureReceiptV1):
            _render_capture_result(
                result,
                store,
                as_json=as_json,
                provider_create_calls=transport.create_calls,
            )
        receipt = _command_receipt(store, "capture.json", result)
        store.verify_recovery_bundle()
        _emit(
            _result_payload(
                "success",
                "rehearsal_candidate_imported",
                "stop",
                receipt=receipt,
                candidate_authority=result.candidate_authority,
                artifact_present=store.artifact_path() is not None,
                provider_create_calls=transport.create_calls,
            ),
            as_json=as_json,
        )


def rehearse_capture(args: argparse.Namespace) -> NoReturn:
    root = Path(args.receipt_root)
    if args.phase == "capture":
        _rehearsal_capture(root, as_json=args.json)
    if not args.declared_raw_url:
        _emit(
            _result_payload(
                "terminal_failure", "source_selection_required", "stop"
            ),
            as_json=args.json,
        )
    _rehearsal_resume(root, args.declared_raw_url, as_json=args.json)


def inspect_provider_free_stage(args: argparse.Namespace) -> NoReturn:
    """Run one provider-free Stage 2-4 mutation or final evaluation."""
    stage = str(args.command)
    if args.ack != f"acknowledge-{stage}":
        _emit(
            _result_payload(
                "terminal_failure",
                f"{stage}_acknowledgement_required",
                "stop",
            ),
            as_json=args.json,
        )
    if not getattr(args, "input_file", None):
        _emit(
            _result_payload(
                "terminal_failure",
                f"{stage if stage != 'promote' else 'promotion'}_input_required",
                "stop",
            ),
            as_json=args.json,
        )
    try:
        payload_value = json.loads(Path(args.input_file).read_text(encoding="utf-8"))
        if not isinstance(payload_value, dict):
            raise ValueError("stage_input_invalid")
        payload = cast(dict[str, object], payload_value)
        _emit_mutation_preview(stage, payload)
        result, identity = asyncio.run(_execute_provider_free_stage(args, payload))
    except (LiveStorageError, OSError, ValueError, httpx2.HTTPError):
        _emit(
            _result_payload(
                "terminal_failure",
                f"{stage}_authority_invalid",
                "stop",
            ),
            as_json=args.json,
        )
    _emit(
        _result_payload(
            "success",
            {
                "promote": "promotion_recorded",
                "review": "review_recorded",
                "decide": "decision_recorded",
                "evaluate": "closure_passed",
            }[stage],
            "cleanup" if stage == "evaluate" else (
                "review" if stage == "promote" else "decide" if stage == "review" else "evaluate"
            ),
            receipt=identity,
            preview={
                "stage": stage,
                "intent_sha256": str(result.intent_sha256),
                "attempt_id": (
                    str(result.attempt_id)
                    if not isinstance(result, DraLiveEvaluationReportV1)
                    else "evaluation"
                ),
            },
            mutation_performed=stage != "evaluate",
        ),
        as_json=args.json,
    )


def _ephemeral_context(role: ActorRole) -> tuple[ActorContext, EphemeralHttpAuthority, str]:
    required = (
        "NIGHT_VOYAGER_LIVE_API_BASE_URL",
        "NIGHT_VOYAGER_LIVE_SESSION",
        "NIGHT_VOYAGER_LIVE_CSRF",
        "NIGHT_VOYAGER_LIVE_ORGANIZATION_ID",
        "NIGHT_VOYAGER_LIVE_ACTOR_ID",
        "NIGHT_VOYAGER_LIVE_SESSION_ID",
    )
    if any(not os.environ.get(name) for name in required):
        raise ValueError("stage_environment_incomplete")
    base_url = os.environ[required[0]].rstrip("/")
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("stage_environment_invalid")
    context = ActorContext(
        organization_id=UUID(os.environ[required[3]]),
        actor_id=UUID(os.environ[required[4]]),
        role=role,
        session_id=UUID(os.environ[required[5]]),
    )
    return (
        context,
        EphemeralHttpAuthority(
            origin=f"{parsed.scheme}://{parsed.netloc}",
            session_value=os.environ[required[1]],
            csrf_value=os.environ[required[2]],
        ),
        base_url,
    )


async def _execute_provider_free_stage(
    args: argparse.Namespace, payload: dict[str, object]
) -> tuple[
    DraPromotionReceiptV1
    | DraReviewReceiptV1
    | DraDecisionReceiptV1
    | DraLiveEvaluationReportV1,
    DraReceiptIdentityV1,
]:
    stage = str(args.command)
    role = ActorRole.PARENT if stage == "decide" else ActorRole.ADVISOR
    context, authority, base_url = _ephemeral_context(role)
    with _open_root(Path(args.receipt_root)) as store:
        if stage == "evaluate":
            expected = DraLiveOutcomeExpectedV1.model_validate(payload)
            capture = store.read_receipt("capture.json", DraCaptureReceiptV1)
            promotion = store.read_receipt("promotion.json", DraPromotionReceiptV1)
            review = store.read_receipt("review.json", DraReviewReceiptV1)
            decision = store.read_receipt("decision.json", DraDecisionReceiptV1)
            database_url = os.environ.get("NIGHT_VOYAGER_DATABASE_URL")
            if not database_url:
                raise ValueError("stage_environment_incomplete")
            engine = create_async_engine(database_url)
            try:
                factory = async_sessionmaker(engine, expire_on_commit=False)
                async with factory() as session:
                    projection = await PostgresLiveOutcomeInspector(session).inspect(
                        context,
                        DraLiveOutcomeIntentV1(
                            intent_sha256=capture.intent_sha256,
                            organization_id=context.organization_id,
                            candidate_id=promotion.candidate_id,
                            advisor_actor_identity_sha256=derive_identity_hash(
                                "actor", str(context.actor_id)
                            ),
                            tenant_identity_sha256=derive_identity_hash(
                                "tenant", str(context.organization_id)
                            ),
                        ),
                    )
            finally:
                await engine.dispose()
            report = evaluate_full_closure(
                load_live_closure_scenario(),
                (capture, promotion, review, decision),
                expected,
                projection,
            )
            if report.status != "passed":
                raise ValueError("closure_evaluation_failed")
            return report, store.write_receipt("evaluation.json", report)
        async with httpx2.AsyncClient(
            base_url=base_url,
            trust_env=False,
            follow_redirects=False,
            timeout=30,
        ) as client:
            gateway = NightVoyagerAuthorityGateway(client, authority)
            controller = DraLiveClosureController(gateway, store)
            if stage == "promote":
                model = DraPromotionInputV1.model_validate(payload)
                snapshot_root = getattr(args, "snapshot_root", None)
                if not snapshot_root:
                    raise ValueError("promotion_snapshot_root_required")
                result = await controller.promote(
                    PromoteCommand(model, context, Path(snapshot_root))
                )
                return result, store.write_receipt("promotion.json", result)
            if stage == "review":
                model = DraReviewInputV1.model_validate(payload)
                result = await controller.review(ReviewCommand(model, context))
                return result, store.write_receipt("review.json", result)
            model = DraDecisionInputV1.model_validate(payload)
            result = await controller.decide(DecideCommand(model, context))
            return result, store.write_receipt("decision.json", result)


def rehearse_full(args: argparse.Namespace) -> NoReturn:
    """Run the existing real provider-free HTTP/worker/database closure."""
    command = [
        sys.executable,
        str(Path(__file__).with_name("verify_dra_governed_flow.py")),
        "--fixture",
    ]
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError:
        _emit(
            _result_payload(
                "terminal_failure",
                "full_rehearsal_failed",
                "stop",
            ),
            as_json=args.json,
        )
    _emit(
        _result_payload(
            "success",
            "closure_passed",
            "cleanup",
            provider_attempt_consumed=False,
            provider_accessed=False,
        ),
        as_json=args.json,
    )


def _read_candidate_evidence(
    path_value: str | None,
    *,
    kind: str,
    head: str,
    schema_version: str,
    exact_keys: frozenset[str],
) -> tuple[bytes, dict[str, object]]:
    if not path_value:
        raise ValueError(f"candidate_{kind}_evidence_missing")
    raw = Path(path_value).read_bytes()
    if not raw or len(raw) > 1_048_576:
        raise ValueError(f"candidate_{kind}_evidence_invalid")
    parsed_value = json.loads(raw)
    if not isinstance(parsed_value, dict):
        raise ValueError(f"candidate_{kind}_evidence_invalid")
    parsed = cast(dict[str, object], parsed_value)
    if (
        frozenset(parsed) != exact_keys
        or parsed.get("schema_version") != schema_version
        or parsed.get("head_sha") != head
    ):
        raise ValueError(f"candidate_{kind}_evidence_invalid")
    return raw, parsed


def _docker_inventory_invalid() -> NoReturn:
    raise ValueError("candidate_evidence_provenance_invalid")


def _docker_json_lines(raw: str) -> tuple[dict[str, object], ...]:
    values: list[dict[str, object]] = []
    for line in raw.splitlines():
        if not line:
            continue
        try:
            value: object = json.loads(line)
        except json.JSONDecodeError:
            _docker_inventory_invalid()
        if not isinstance(value, dict):
            _docker_inventory_invalid()
        values.append(cast(dict[str, object], value))
    return tuple(values)


def _docker_string(
    record: dict[str, object],
    key: str,
    *,
    allow_empty: bool = False,
) -> str:
    value = record.get(key)
    if not isinstance(value, str) or (not allow_empty and not value):
        _docker_inventory_invalid()
    return value


def _docker_boolean_string(record: dict[str, object], key: str) -> bool:
    value = _docker_string(record, key)
    if value not in {"true", "false"}:
        _docker_inventory_invalid()
    return value == "true"


def _docker_nonnegative_integer(value: object) -> int:
    if isinstance(value, bool):
        _docker_inventory_invalid()
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        result = int(value)
    else:
        _docker_inventory_invalid()
    if result < 0:
        _docker_inventory_invalid()
    return result


def _docker_labels(value: object) -> dict[str, str]:
    if not isinstance(value, str):
        _docker_inventory_invalid()
    labels: dict[str, str] = {}
    if not value:
        return labels
    for item in value.split(","):
        if "=" not in item:
            _docker_inventory_invalid()
        key, label_value = item.split("=", 1)
        if not key or key in labels:
            _docker_inventory_invalid()
        labels[key] = label_value
    return dict(sorted(labels.items()))


def _docker_string_set(value: object, *, nullable: bool = False) -> list[str]:
    if value is None and nullable:
        return []
    if isinstance(value, str):
        items = [] if not value else value.split(",")
    elif isinstance(value, list):
        items = cast(list[object], value)
    else:
        _docker_inventory_invalid()
    if not all(isinstance(item, str) and item for item in items):
        _docker_inventory_invalid()
    strings = cast(list[str], items)
    if len(set(strings)) != len(strings):
        _docker_inventory_invalid()
    return sorted(strings)


def _docker_size_bytes(record: dict[str, object]) -> int:
    value = _docker_string(record, "Size")
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([kMGTPE]?B)", value)
    if match is None:
        _docker_inventory_invalid()
    factors = {
        "B": 1,
        "kB": 1_000,
        "MB": 1_000_000,
        "GB": 1_000_000_000,
        "TB": 1_000_000_000_000,
        "PB": 1_000_000_000_000_000,
        "EB": 1_000_000_000_000_000_000,
    }
    try:
        size = Decimal(match.group(1)) * factors[match.group(2)]
    except InvalidOperation:
        _docker_inventory_invalid()
    if size != size.to_integral_value():
        _docker_inventory_invalid()
    return int(size)


def _canonical_docker_inventory(
    name: str,
    raw: str,
) -> tuple[dict[str, object], ...]:
    records: tuple[dict[str, object], ...]
    if name == "compose":
        try:
            value: object = json.loads(raw)
        except json.JSONDecodeError:
            _docker_inventory_invalid()
        if not isinstance(value, list):
            _docker_inventory_invalid()
        compose_items = cast(list[object], value)
        if not all(isinstance(item, dict) for item in compose_items):
            _docker_inventory_invalid()
        records = tuple(cast(dict[str, object], item) for item in compose_items)
    else:
        records = _docker_json_lines(raw)

    projected: list[dict[str, object]] = []
    identities: set[str] = set()
    for record in records:
        projection: dict[str, object]
        if name == "compose":
            projection = {
                "name": _docker_string(record, "Name"),
                "status": _docker_string(record, "Status"),
            }
            identity = _docker_string(record, "Name")
        elif name == "containers":
            projection = {
                "id": _docker_string(record, "ID"),
                "image": _docker_string(record, "Image"),
                "labels": _docker_labels(record.get("Labels")),
                "names": _docker_string(record, "Names"),
                "networks": _docker_string_set(record.get("Networks")),
                "state": _docker_string(record, "State"),
            }
            identity = cast(str, projection["id"])
        elif name == "images":
            projection = {
                "containers": _docker_nonnegative_integer(record.get("Containers")),
                "digest": _docker_string(record, "Digest"),
                "id": _docker_string(record, "ID"),
                "repository": _docker_string(record, "Repository"),
                "tag": _docker_string(record, "Tag"),
            }
            repository = cast(str, projection["repository"])
            tag = cast(str, projection["tag"])
            identity = (
                cast(str, projection["id"])
                if repository == "<none>" and tag == "<none>"
                else f"{repository}:{tag}"
            )
        elif name == "build_cache":
            mutable = record.get("Mutable")
            reclaimable = record.get("Reclaimable")
            shared = record.get("Shared")
            if not all(isinstance(value, bool) for value in (mutable, reclaimable, shared)):
                _docker_inventory_invalid()
            projection = {
                "id": _docker_string(record, "ID"),
                "mutable": mutable,
                "parents": _docker_string_set(
                    record.get("Parents"),
                    nullable=True,
                ),
                "reclaimable": reclaimable,
                "shared": shared,
                "size_bytes": _docker_size_bytes(record),
                "type": _docker_string(record, "Type"),
                "usage_count": _docker_nonnegative_integer(record.get("UsageCount")),
            }
            identity = cast(str, projection["id"])
        elif name == "networks":
            projection = {
                "driver": _docker_string(record, "Driver"),
                "id": _docker_string(record, "ID"),
                "internal": _docker_boolean_string(record, "Internal"),
                "ipv4": _docker_boolean_string(record, "IPv4"),
                "ipv6": _docker_boolean_string(record, "IPv6"),
                "labels": _docker_labels(record.get("Labels")),
                "name": _docker_string(record, "Name"),
                "scope": _docker_string(record, "Scope"),
            }
            identity = cast(str, projection["id"])
        elif name == "volumes":
            projection = {
                "availability": _docker_string(record, "Availability"),
                "driver": _docker_string(record, "Driver"),
                "labels": _docker_labels(record.get("Labels")),
                "name": _docker_string(record, "Name"),
                "scope": _docker_string(record, "Scope"),
                "status": _docker_string(record, "Status"),
            }
            identity = cast(str, projection["name"])
        else:
            _docker_inventory_invalid()
        if identity in identities:
            _docker_inventory_invalid()
        identities.add(identity)
        projected.append(projection)
    return tuple(
        sorted(
            projected,
            key=lambda item: json.dumps(
                item,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
        )
    )


def _canonical_docker_inventory_bytes(
    inventory: tuple[dict[str, object], ...],
) -> bytes:
    return json.dumps(
        inventory,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _doctor_semantic_result(output: str) -> tuple[int, int, str]:
    match = DOCTOR_OUTPUT_PATTERN.fullmatch(output)
    if match is None:
        raise ValueError("candidate_evidence_provenance_invalid")
    host_available_kib = int(match.group(1))
    docker_vm_available_kib = int(match.group(2))
    semantic_sha256 = hashlib.sha256(DOCTOR_SEMANTIC_OUTPUT.encode()).hexdigest()
    return host_available_kib, docker_vm_available_kib, semantic_sha256


def _recovery_passed_count(output: str) -> int:
    lines = output.splitlines()
    if not lines:
        raise ValueError("candidate_evidence_provenance_invalid")
    summary_match = re.fullmatch(
        r"([1-9][0-9]*) passed in [0-9]+(?:\.[0-9]+)?s",
        lines[-1],
    )
    if summary_match is None or any(
        re.fullmatch(r"\.+(?:\s+\[\s*[0-9]+%\])?", line) is None for line in lines[:-1]
    ):
        raise ValueError("candidate_evidence_provenance_invalid")
    return int(summary_match.group(1))


def _validated_candidate_evidence(
    args: argparse.Namespace,
    head: str,
) -> tuple[bytes, bytes, bytes, bytes]:
    inventory, inventory_evidence = _read_candidate_evidence(
        args.docker_inventory_file,
        kind="docker",
        head=head,
        schema_version="night-voyager.dra-live-docker-evidence.v3",
        exact_keys=frozenset(
            {
                "schema_version",
                "head_sha",
                "task_project",
                "minimum_host_kib",
                "minimum_docker_vm_kib",
                "host_available_kib",
                "docker_vm_available_kib",
                "doctor_semantic_sha256",
                "before_inventory_sha256",
                "after_inventory_sha256",
                "retained_resources",
            }
        ),
    )
    hosted, hosted_evidence = _read_candidate_evidence(
        args.hosted_check_evidence_file,
        kind="hosted_checks",
        head=head,
        schema_version="night-voyager.dra-live-hosted-checks-evidence.v1",
        exact_keys=frozenset(
            {
                "schema_version",
                "head_sha",
                "repository",
                "check_run_ids",
            }
        ),
    )
    recovery, recovery_evidence = _read_candidate_evidence(
        args.recovery_evidence_file,
        kind="recovery",
        head=head,
        schema_version="night-voyager.dra-live-recovery-evidence.v2",
        exact_keys=frozenset(
            {
                "schema_version",
                "head_sha",
                "command",
                "passed_count",
            }
        ),
    )
    review, review_evidence = _read_candidate_evidence(
        args.authority_review_evidence_file,
        kind="authority_review",
        head=head,
        schema_version="night-voyager.dra-live-authority-review-evidence.v2",
        exact_keys=frozenset(
            {
                "schema_version",
                "head_sha",
                "repository",
                "pull_request",
                "reviewed_head_sha",
                "verdict",
                "review_record_id",
                "review_record_sha256",
                "acknowledgement",
            }
        ),
    )

    command_value = recovery_evidence.get("command")
    if not isinstance(command_value, list):
        raise ValueError("candidate_evidence_provenance_invalid")
    command_items = cast(list[object], command_value)
    if not all(isinstance(item, str) for item in command_items):
        raise ValueError("candidate_evidence_provenance_invalid")
    recovery_command = tuple(cast(list[str], command_items))
    if recovery_command != ALLOWED_RECOVERY_COMMAND:
        raise ValueError("candidate_evidence_provenance_invalid")
    recorded_host_available_kib = inventory_evidence.get("host_available_kib")
    recorded_docker_vm_available_kib = inventory_evidence.get(
        "docker_vm_available_kib"
    )
    recovery_passed_count = recovery_evidence.get("passed_count")
    if (
        inventory_evidence.get("task_project") != CANDIDATE_TASK_PROJECT
        or inventory_evidence.get("minimum_host_kib") != HOST_MINIMUM_KIB
        or inventory_evidence.get("minimum_docker_vm_kib")
        != DOCKER_VM_MINIMUM_KIB
        or not isinstance(recorded_host_available_kib, int)
        or isinstance(recorded_host_available_kib, bool)
        or recorded_host_available_kib < HOST_MINIMUM_KIB
        or not isinstance(recorded_docker_vm_available_kib, int)
        or isinstance(recorded_docker_vm_available_kib, bool)
        or recorded_docker_vm_available_kib < DOCKER_VM_MINIMUM_KIB
        or not isinstance(recovery_passed_count, int)
        or isinstance(recovery_passed_count, bool)
        or recovery_passed_count <= 0
    ):
        raise ValueError("candidate_evidence_provenance_invalid")
    review_repository = review_evidence.get("repository")
    pull_request = review_evidence.get("pull_request")
    reviewed_head_sha = review_evidence.get("reviewed_head_sha")
    review_record_id = review_evidence.get("review_record_id")
    review_record_sha256 = review_evidence.get("review_record_sha256")
    if (
        not isinstance(review_repository, str)
        or review_repository != hosted_evidence.get("repository")
        or not isinstance(pull_request, int)
        or isinstance(pull_request, bool)
        or pull_request <= 0
        or not isinstance(reviewed_head_sha, str)
        or re.fullmatch(r"[0-9a-f]{40}", reviewed_head_sha) is None
        or review_evidence.get("verdict") != "CLEAN"
        or not isinstance(review_record_id, str)
        or re.fullmatch(r"[a-z0-9][a-z0-9._:-]{0,127}", review_record_id)
        is None
        or not isinstance(review_record_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", review_record_sha256) is None
        or review_evidence.get("acknowledgement") != AUTHORITY_REVIEW_ACK
    ):
        raise ValueError("candidate_evidence_provenance_invalid")

    def run(
        command: tuple[str, ...],
        *,
        environment: dict[str, str] | None = None,
    ) -> str:
        try:
            return subprocess.run(
                command,
                check=True,
                text=True,
                capture_output=True,
                env=environment,
            ).stdout
        except (OSError, subprocess.CalledProcessError) as error:
            raise ValueError("candidate_evidence_provenance_invalid") from error

    def capture_inventory() -> dict[str, tuple[dict[str, object], ...]]:
        return {
            name: _canonical_docker_inventory(name, run(command))
            for name, command in DOCKER_INVENTORY_COMMANDS
        }

    def inventory_hashes(
        observed: dict[str, tuple[dict[str, object], ...]],
    ) -> dict[str, str]:
        return {
            name: hashlib.sha256(_canonical_docker_inventory_bytes(value)).hexdigest()
            for name, value in observed.items()
        }

    def retained_resources(
        observed: dict[str, tuple[dict[str, object], ...]],
    ) -> dict[str, object]:
        images = tuple(
            sorted(
                f"{item['repository']}:{item['tag']}"
                for item in observed["images"]
                if item["repository"] != "<none>" and item["tag"] != "<none>"
            )
        )
        volumes = tuple(sorted(cast(str, item["name"]) for item in observed["volumes"]))
        return {
            "images": list(images),
            "volumes": list(volumes),
            "build_cache_sha256": hashlib.sha256(
                _canonical_docker_inventory_bytes(observed["build_cache"])
            ).hexdigest(),
        }

    before_inventory = capture_inventory()
    if any(
        CANDIDATE_TASK_PROJECT
        in _canonical_docker_inventory_bytes(value).decode()
        for value in before_inventory.values()
    ):
        raise ValueError("candidate_evidence_provenance_invalid")
    doctor_environment = os.environ.copy()
    doctor_environment.pop("NIGHT_VOYAGER_DOCKER_MINIMUM_KB", None)
    doctor_output = run(
        ("make", "doctor", "MODE=dev"),
        environment=doctor_environment,
    )
    host_available_kib, docker_vm_available_kib, doctor_semantic_sha256 = (
        _doctor_semantic_result(doctor_output)
    )
    after_inventory = capture_inventory()
    if any(
        CANDIDATE_TASK_PROJECT
        in _canonical_docker_inventory_bytes(value).decode()
        for value in after_inventory.values()
    ):
        raise ValueError("candidate_evidence_provenance_invalid")
    if (
        host_available_kib < HOST_MINIMUM_KIB
        or docker_vm_available_kib < DOCKER_VM_MINIMUM_KIB
        or inventory_evidence.get("doctor_semantic_sha256")
        != doctor_semantic_sha256
        or inventory_evidence.get("before_inventory_sha256")
        != inventory_hashes(before_inventory)
        or inventory_evidence.get("after_inventory_sha256")
        != inventory_hashes(after_inventory)
        or inventory_evidence.get("retained_resources")
        != retained_resources(after_inventory)
    ):
        raise ValueError("candidate_evidence_provenance_invalid")

    repository = hosted_evidence.get("repository")
    check_run_ids = hosted_evidence.get("check_run_ids")
    if not isinstance(repository, str) or not isinstance(check_run_ids, dict):
        raise ValueError("candidate_evidence_provenance_invalid")
    hosted_live_value: object = json.loads(
        run(
            (
                "gh",
                "api",
                f"repos/{repository}/commits/{head}/check-runs",
            )
        )
    )
    if not isinstance(hosted_live_value, dict):
        raise ValueError("candidate_evidence_provenance_invalid")
    hosted_live = cast(dict[str, object], hosted_live_value)
    live_runs_value = hosted_live.get("check_runs")
    if not isinstance(live_runs_value, list):
        raise ValueError("candidate_evidence_provenance_invalid")
    exact_checks: dict[str, int] = {}
    for item in cast(list[object], live_runs_value):
        if not isinstance(item, dict):
            continue
        run_item = cast(dict[str, object], item)
        name = run_item.get("name")
        identifier = run_item.get("id")
        if (
            isinstance(name, str)
            and isinstance(identifier, int)
            and name in {"python", "frontend", "compose"}
            and run_item.get("status") == "completed"
            and run_item.get("conclusion") == "success"
            and run_item.get("head_sha") == head
        ):
            exact_checks[name] = identifier
    supplied_checks: dict[str, int] = {}
    for name, identifier in cast(dict[object, object], check_run_ids).items():
        if not isinstance(name, str) or not isinstance(identifier, int):
            raise ValueError("candidate_evidence_provenance_invalid")
        supplied_checks[name] = identifier
    if exact_checks != supplied_checks or set(exact_checks) != {
        "python",
        "frontend",
        "compose",
    }:
        raise ValueError("candidate_evidence_provenance_invalid")

    recovery_output = run(recovery_command)
    if _recovery_passed_count(recovery_output) != recovery_passed_count:
        raise ValueError("candidate_evidence_provenance_invalid")

    pull_value: object = json.loads(
        run(("gh", "api", f"repos/{repository}/pulls/{pull_request}"))
    )
    if not isinstance(pull_value, dict):
        raise ValueError("candidate_evidence_provenance_invalid")
    pull = cast(dict[str, object], pull_value)
    pull_head_value = pull.get("head")
    if (
        pull.get("merged") is not True
        or pull.get("merge_commit_sha") != head
        or not isinstance(pull_head_value, dict)
        or cast(dict[str, object], pull_head_value).get("sha")
        != reviewed_head_sha
    ):
        raise ValueError("candidate_evidence_provenance_invalid")
    reviewed_commit_value: object = json.loads(
        run(
            (
                "gh",
                "api",
                f"repos/{repository}/git/commits/{reviewed_head_sha}",
            )
        )
    )
    merge_commit_value: object = json.loads(
        run(("gh", "api", f"repos/{repository}/git/commits/{head}"))
    )
    if (
        not isinstance(reviewed_commit_value, dict)
        or not isinstance(merge_commit_value, dict)
    ):
        raise ValueError("candidate_evidence_provenance_invalid")
    reviewed_tree = cast(dict[str, object], reviewed_commit_value).get("tree")
    merge_tree = cast(dict[str, object], merge_commit_value).get("tree")
    reviewed_tree_sha = (
        cast(dict[str, object], reviewed_tree).get("sha")
        if isinstance(reviewed_tree, dict)
        else None
    )
    merge_tree_sha = (
        cast(dict[str, object], merge_tree).get("sha")
        if isinstance(merge_tree, dict)
        else None
    )
    if (
        not isinstance(reviewed_tree_sha, str)
        or re.fullmatch(r"[0-9a-f]{40}", reviewed_tree_sha) is None
        or reviewed_tree_sha != merge_tree_sha
    ):
        raise ValueError("candidate_evidence_provenance_invalid")
    return inventory, hosted, recovery, review


def freeze_candidate(args: argparse.Namespace) -> NoReturn:
    """Write a provider-free, executable post-merge readiness identity."""
    required_hosted_checks = tuple(sorted(set(args.hosted_check)))
    authorization_placeholder = args.authorization_placeholder
    try:
        if required_hosted_checks != ("compose", "frontend", "python"):
            raise ValueError("candidate_hosted_check_names_invalid")
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout
        local_main = subprocess.run(
            ["git", "rev-parse", "main"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        origin_main = subprocess.run(
            ["git", "rev-parse", "origin/main"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        if (
            head != args.merged_main_sha
            or branch != "main"
            or status
            or local_main != head
            or origin_main != head
        ):
            raise ValueError("candidate_main_identity_invalid")
        live_main = subprocess.run(
            ["git", "ls-remote", "origin", "refs/heads/main"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.split()[0]
        if live_main != head:
            raise ValueError("candidate_main_identity_invalid")

        inventory, hosted, recovery, review = _validated_candidate_evidence(
            args, head
        )
        repository = Path(__file__).resolve().parents[1]

        def digest(relative: str) -> str:
            return hashlib.sha256(
                (repository / relative).read_bytes()
            ).hexdigest()

        receipt = DraCandidateReadinessReceiptV1(
            merged_main_sha=head,
            spec_sha256=digest(
                "docs/superpowers/specs/"
                "2026-07-25-dra-v0-1-6-governed-live-closure-design.md"
            ),
            plan_sha256=digest(
                "docs/superpowers/plans/"
                "2026-07-25-dra-v0-1-6-live-closure-pr-c-implementation-plan.md"
            ),
            scenario_sha256=digest(
                "fixtures/dra/live-closure-scenario-v1.json"
            ),
            intent_schema_sha256=digest(
                "src/night_voyager/dra/live_models.py"
            ),
            receipt_schema_sha256=digest(
                "src/night_voyager/dra/live_storage.py"
            ),
            cli_sha256=digest("scripts/verify_dra_live_closure.py"),
            producer=load_live_closure_scenario().producer,
            required_hosted_checks=required_hosted_checks,
            recovery_matrix_status="passed",
            docker_preflight_status="passed",
            docker_inventory_sha256=hashlib.sha256(inventory).hexdigest(),
            hosted_checks_evidence_sha256=hashlib.sha256(hosted).hexdigest(),
            recovery_matrix_evidence_sha256=hashlib.sha256(recovery).hexdigest(),
            authority_review_evidence_sha256=hashlib.sha256(review).hexdigest(),
            cleanup_state="clean",
            authorization_placeholder=authorization_placeholder,
        )
        with _open_root(Path(args.receipt_root), create=True) as store:
            identity = store.write_receipt("readiness.json", receipt)
    except (
        LiveStorageError,
        OSError,
        subprocess.CalledProcessError,
        ValueError,
    ):
        _emit(
            _result_payload(
                "terminal_failure",
                "candidate_readiness_invalid",
                "stop",
            ),
            as_json=args.json,
        )
    _emit(
        _result_payload(
            "success",
            "candidate_readiness_frozen",
            "await-separate-live-authorization",
            receipt=identity,
            required_hosted_checks=required_hosted_checks,
            docker_inventory_sha256=receipt.docker_inventory_sha256,
            authorization_placeholder=authorization_placeholder,
            capability_status="INCOMPLETE_PENDING_LIVE_ACCEPTANCE",
        ),
        as_json=args.json,
    )


def _root_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--receipt-root", required=True)
    parser.add_argument("--json", action="store_true")


def _raise_interrupt(_signum: int, _frame: object) -> NoReturn:
    raise KeyboardInterrupt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Governed DRA live closure command surface"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    freeze = commands.add_parser(
        "freeze-intent", help="provider-free mutating intent freeze"
    )
    _root_argument(freeze)
    freeze.add_argument("--query-file", required=True)
    freeze.add_argument("--organization-id", required=True)
    freeze.add_argument("--case-id", required=True)
    freeze.add_argument("--expected-case-revision", type=int, required=True)
    freeze.add_argument("--advisor-actor-id", required=True)
    freeze.add_argument("--one-attempt-ack", required=True)
    freeze.add_argument("--deadline-seconds", type=int, default=900)
    freeze.add_argument("--poll-seconds", type=float, default=2.0)

    preflight = commands.add_parser(
        "preflight-live", help="provider-free mutating readiness receipt"
    )
    _root_argument(preflight)

    capture = commands.add_parser(
        "capture-live", help="provider-consuming mutating one-attempt capture"
    )
    _root_argument(capture)
    capture.add_argument("--query-file", required=True)
    capture.add_argument("--one-attempt-ack", required=True)

    select = commands.add_parser(
        "select-and-import",
        help="provider-free mutating operator selection and candidate import",
    )
    _root_argument(select)
    select.add_argument("--declared-raw-url", required=True)

    reconcile = commands.add_parser(
        "reconcile-create",
        help="provider-consuming mutating exact create replay",
    )
    _root_argument(reconcile)
    reconcile.add_argument("--query-file", required=True)
    reconcile.add_argument("--exact-replay-ack", required=True)

    resume = commands.add_parser(
        "resume-poll", help="provider-consuming read-only same-run poll"
    )
    _root_argument(resume)

    inspect = commands.add_parser(
        "inspect-recovery", help="provider-free read-only recovery inspection"
    )
    _root_argument(inspect)

    rehearsal = commands.add_parser(
        "rehearse-capture", help="provider-free mutating fake rehearsal"
    )
    _root_argument(rehearsal)
    rehearsal.add_argument("--phase", choices=("capture", "resume"), required=True)
    rehearsal.add_argument("--declared-raw-url")

    for stage in ("promote", "review", "decide", "evaluate"):
        stage_parser = commands.add_parser(
            stage,
            help=f"provider-free {stage} predecessor and authority preflight",
        )
        _root_argument(stage_parser)
        stage_parser.add_argument("--ack", required=True)
        stage_parser.add_argument("--input-file")
        if stage == "promote":
            stage_parser.add_argument("--snapshot-root")

    full_rehearsal = commands.add_parser(
        "rehearse-full",
        help="provider-free full HTTP/worker/database closure rehearsal",
    )
    full_rehearsal.add_argument("--json", action="store_true")

    candidate = commands.add_parser(
        "freeze-candidate",
        help="provider-free post-merge live-acceptance candidate freeze",
    )
    _root_argument(candidate)
    candidate.add_argument("--merged-main-sha", required=True)
    candidate.add_argument("--docker-inventory-file", required=True)
    candidate.add_argument("--hosted-check-evidence-file")
    candidate.add_argument("--recovery-evidence-file")
    candidate.add_argument("--authority-review-evidence-file")
    candidate.add_argument(
        "--hosted-check",
        action="append",
        choices=("python", "frontend", "compose"),
        required=True,
    )
    candidate.add_argument(
        "--authorization-placeholder",
        required=True,
        choices=("PENDING_SEPARATE_LIVE_ACCEPTANCE_AUTHORIZATION",),
    )

    clean = commands.add_parser(
        "cleanup", help="provider-free mutating exact-root cleanup (dry-run default)"
    )
    _root_argument(clean)
    clean.add_argument("--delete-ack")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    signal.signal(signal.SIGTERM, _raise_interrupt)
    handlers = {
        "freeze-intent": freeze_intent,
        "preflight-live": preflight_live,
        "capture-live": capture_live,
        "select-and-import": select_and_import,
        "reconcile-create": reconcile_create,
        "resume-poll": resume_poll,
        "inspect-recovery": inspect_recovery,
        "rehearse-capture": rehearse_capture,
        "promote": inspect_provider_free_stage,
        "review": inspect_provider_free_stage,
        "decide": inspect_provider_free_stage,
        "evaluate": inspect_provider_free_stage,
        "rehearse-full": rehearse_full,
        "freeze-candidate": freeze_candidate,
        "cleanup": cleanup,
    }
    try:
        handlers[args.command](args)
    except SystemExit:
        raise
    except KeyboardInterrupt:
        root_value = getattr(args, "receipt_root", None)
        cleanup_status = "absent"
        if root_value:
            try:
                with _open_root(Path(root_value)) as store:
                    cleanup_status = store.delete_artifact().status
            except LiveStorageError:
                cleanup_status = "failed"
        exit_class: ExitClass = (
            "cleanup_incomplete"
            if cleanup_status in {"failed", "retained"}
            else "terminal_failure"
        )
        _emit(
            _result_payload(
                exit_class,
                "operator_interrupt",
                "cleanup" if exit_class == "cleanup_incomplete" else "stop",
            ),
            as_json=getattr(args, "json", False),
        )
    except Exception:
        _emit(
            _result_payload(
                "terminal_failure", "dra_live_command_failed", "stop"
            ),
            as_json=getattr(args, "json", False),
        )


if __name__ == "__main__":
    main()
