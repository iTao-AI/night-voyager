# pyright: reportPrivateUsage=false

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
from collections.abc import Generator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import httpx2
import pytest

from night_voyager.dra.fixtures import (
    build_v0_1_6_scenario_candidate_import,
    load_live_closure_scenario,
)
from night_voyager.dra.live_evaluation import DraLiveCandidateReadinessV3
from night_voyager.dra.live_http import (
    EphemeralHttpAuthority,
    NightVoyagerAuthorityGateway,
)
from night_voyager.dra.live_models import (
    DraCandidateReadinessReceiptV2,
    compose_effective_query_v2,
)
from night_voyager.dra.live_storage import LiveReceiptStore
from night_voyager.dra.ports import VerifyDraCandidateCommand
from night_voyager.dra.reconciliation import DraAmbiguousOutcome
from night_voyager.identity.models import ActorContext, ActorRole
from scripts import verify_dra_governed_flow as governed_flow
from scripts import verify_dra_live_closure as live_cli

from .test_live_promotion_controller import (  # pyright: ignore[reportPrivateUsage]
    _capture,
    _command,
    _private_roots,
)

ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / "scripts/verify_dra_live_closure.py"
GOVERNED_PROOF = ROOT / "scripts/verify_dra_governed_flow.py"


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("uv", "run", "python", str(CLI), *arguments),
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_promote_is_a_real_stage_command_not_a_preflight_stub(
    tmp_path: Path,
) -> None:
    receipts = tmp_path / "receipts"
    receipts.mkdir(mode=0o700)
    with LiveReceiptStore.open(receipts) as store:
        store.write_receipt("capture.json", _capture())

    result = _run(
        "promote",
        "--receipt-root",
        str(receipts),
        "--ack",
        "acknowledge-promote",
        "--json",
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 30
    assert payload["problem_code"] == "promotion_input_required"
    assert "mutation_performed" not in payload


def test_promote_emits_bounded_preview_before_authority_access(
    tmp_path: Path,
) -> None:
    receipts, snapshot_root = _private_roots(tmp_path)
    with LiveReceiptStore.open(receipts) as store:
        store.write_receipt("capture.json", _capture())
    stage_input = tmp_path / "promotion.json"
    stage_input.write_text(
        _command(snapshot_root).promotion.model_dump_json(),
        encoding="utf-8",
    )

    result = _run(
        "promote",
        "--receipt-root",
        str(receipts),
        "--snapshot-root",
        str(snapshot_root),
        "--input-file",
        str(stage_input),
        "--ack",
        "acknowledge-promote",
        "--json",
    )

    preview = json.loads(result.stderr)
    assert result.returncode == 30
    assert preview == {
        "schema_version": "night-voyager.dra-live-mutation-preview.v1",
        "stage": "promote",
        "input_sha256": preview["input_sha256"],
        "acknowledgement": "accepted",
    }
    assert len(preview["input_sha256"]) == 64
    assert "session" not in result.stderr


def test_freeze_candidate_rejects_feature_head_and_arbitrary_inventory(
    tmp_path: Path,
) -> None:
    receipts = tmp_path / "readiness"
    inventory = tmp_path / "inventory.txt"
    inventory.write_text("not a verified Docker evidence receipt\n", encoding="utf-8")
    query = tmp_path / "query.txt"
    query.write_text("bounded synthetic query", encoding="utf-8")
    head = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()

    result = _run(
        "freeze-candidate",
        "--receipt-root",
        str(receipts),
        "--merged-main-sha",
        head,
        "--query-file",
        str(query),
        "--docker-inventory-file",
        str(inventory),
        "--hosted-check",
        "python",
        "--hosted-check",
        "frontend",
        "--hosted-check",
        "compose",
        "--authorization-placeholder",
        "PENDING_SEPARATE_LIVE_ACCEPTANCE_AUTHORIZATION",
        "--json",
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 30
    assert payload["problem_code"] == "candidate_readiness_invalid"
    assert not receipts.exists()


def test_strict_freeze_rejects_legacy_readiness_before_provider_construction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    legacy = tmp_path / "legacy-v2.json"
    legacy.write_text(
        DraCandidateReadinessReceiptV2(
            merged_main_sha="0" * 40,
            request=compose_effective_query_v2(
                b"bounded synthetic query",
                logical_name="query.txt",
            )[1],
            spec_sha256="1" * 64,
            plan_sha256="2" * 64,
            scenario_sha256="3" * 64,
            intent_schema_sha256="4" * 64,
            receipt_schema_sha256="5" * 64,
            cli_sha256="6" * 64,
            producer=load_live_closure_scenario().producer,
            required_hosted_checks=("compose", "frontend", "python"),
            recovery_matrix_status="passed",
            docker_preflight_status="passed",
            docker_inventory_sha256="7" * 64,
            hosted_checks_evidence_sha256="8" * 64,
            recovery_matrix_evidence_sha256="9" * 64,
            authority_review_evidence_sha256="a" * 64,
            cleanup_state="clean",
            authorization_placeholder=(
                "PENDING_SEPARATE_LIVE_ACCEPTANCE_AUTHORIZATION"
            ),
        ).model_dump_json(),
        encoding="utf-8",
    )
    provider_create_calls = 0

    def forbidden_provider(*_args: object, **_kwargs: object) -> object:
        nonlocal provider_create_calls
        provider_create_calls += 1
        raise AssertionError("provider construction must not occur")

    monkeypatch.setattr(live_cli, "_live_transport", forbidden_provider)

    with pytest.raises(SystemExit) as stopped:
        live_cli.main(["freeze-candidate", "--readiness", str(legacy)])

    assert stopped.value.code == 30
    assert "candidate_readiness_invalid" in capsys.readouterr().out
    assert provider_create_calls == 0


def test_freeze_candidate_writes_canonical_v3_strict_readiness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    head = "e" * 40
    query_bytes = b"Compare one bounded synthetic source."
    exact_clause = (
        b"[NIGHT_VOYAGER_DRA_LIVE_CITATION_CONTRACT_V2]\n"
        b"Use internet_search. The final canonical report must include the exact raw "
        b"URL of at least one public HTTPS source that internet_search actually returned "
        b"and that passes the current source-admission contract. Do not invent, alter, "
        b"normalize, or guess any URL."
    )
    effective_bytes = query_bytes + b"\n\n" + exact_clause
    query = tmp_path / "query.txt"
    query.write_bytes(query_bytes)
    receipts = tmp_path / "readiness"
    git_outputs: dict[tuple[str, ...], str] = {
        ("git", "rev-parse", "HEAD"): f"{head}\n",
        ("git", "branch", "--show-current"): "main\n",
        ("git", "status", "--porcelain"): "",
        ("git", "rev-parse", "main"): f"{head}\n",
        ("git", "rev-parse", "origin/main"): f"{head}\n",
        (
            "git",
            "ls-remote",
            "origin",
            "refs/heads/main",
        ): f"{head}\trefs/heads/main\n",
    }

    def completed_git(
        command: list[str],
        **_: object,
    ) -> subprocess.CompletedProcess[str]:
        output = git_outputs.get(tuple(command))
        if output is None:
            raise AssertionError(f"unexpected subprocess: {command!r}")
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

    def validated_evidence(
        _args: argparse.Namespace,
        _head: str,
    ) -> tuple[bytes, bytes, bytes, bytes]:
        return (
            b"validated-docker-evidence",
            b"validated-hosted-evidence",
            b"validated-recovery-evidence",
            b"validated-review-evidence",
        )

    monkeypatch.setattr(live_cli.subprocess, "run", completed_git)
    monkeypatch.setattr(
        live_cli,
        "_validated_candidate_evidence",
        validated_evidence,
    )
    args = argparse.Namespace(
        hosted_check=["python", "frontend", "compose"],
        authorization_placeholder=(
            "PENDING_SEPARATE_LIVE_ACCEPTANCE_AUTHORIZATION"
        ),
        merged_main_sha=head,
        query_file=str(query),
        receipt_root=str(receipts),
        json=True,
    )

    with pytest.raises(SystemExit) as stopped:
        live_cli.freeze_candidate(args)

    assert stopped.value.code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["problem_code"] == "candidate_readiness_frozen"
    readiness_bytes = (receipts / "readiness.json").read_bytes()
    readiness = DraLiveCandidateReadinessV3.model_validate_json(
        readiness_bytes
    )
    assert readiness.schema_version == (
        "night-voyager.dra-live-candidate-readiness.v3"
    )
    assert readiness.status == "INCOMPLETE_PENDING_LIVE_ACCEPTANCE"
    assert readiness.producer.ref_kind == "commit"
    assert readiness.producer.profile_id == "generic-strict-citation"
    assert readiness.request_identity.schema_version == (
        "night-voyager.dra-run-request-identity.v2"
    )
    assert readiness.request_identity.profile_id == "generic-strict-citation"
    assert readiness.request_identity.request_sha256 == hashlib.sha256(
        effective_bytes
    ).hexdigest()
    assert readiness.observed_profile.profile_version == "1"
    assert readiness.authorization == (
        "PENDING_SEPARATE_LIVE_ACCEPTANCE_AUTHORIZATION"
    )
    canonical_round_trip = json.dumps(
        readiness.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    assert canonical_round_trip == readiness_bytes
    assert result["receipt"]["sha256"] == hashlib.sha256(
        readiness_bytes
    ).hexdigest()


@pytest.mark.asyncio
async def test_production_gateway_translates_commit_then_timeout_and_rereads_task() -> None:
    case_id = UUID("10000000-0000-0000-0000-000000000101")
    task_id = UUID("10000000-0000-0000-0000-000000000102")
    source_pack_id = UUID("10000000-0000-0000-0000-000000000103")
    planning_run_id = UUID("10000000-0000-0000-0000-000000000104")
    execution_id = UUID("10000000-0000-0000-0000-000000000105")
    observed: list[tuple[str, str]] = []

    class _Response:
        status_code = 200

        def json(self) -> object:
            return {
                "schema_version": 1,
                "task_id": str(task_id),
                "case_id": str(case_id),
                "case_revision": 7,
                "operation": "generate_governed_mixed_planning_run_v1",
                "source_pack_id": str(source_pack_id),
                "source_pack_version": 3,
                "status": "needs_advisor_review",
                "planning_run_id": str(planning_run_id),
                "execution_id": str(execution_id),
                "terminal_event_id": 11,
                "skill_pin": {
                    "skill_definition_id": "81000000-0000-0000-0000-000000000002",
                    "skill_version_id": "82000000-0000-0000-0000-000000000002",
                    "skill_activation_event_id": "84000000-0000-0000-0000-000000000001",
                    "skill_activation_sequence": 1,
                    "runtime_binding_sha256": "d" * 64,
                },
                "request_sha256": "e" * 64,
            }

        def raise_for_status(self) -> None:
            return None

    class _Client:
        async def post(self, url: str, **kwargs: object) -> _Response:
            del kwargs
            observed.append(("POST", url))
            raise httpx2.ReadTimeout("committed response lost")

        async def get(self, url: str, **kwargs: object) -> _Response:
            del kwargs
            observed.append(("GET", url))
            return _Response()

    context = ActorContext(
        organization_id=UUID("10000000-0000-0000-0000-000000000106"),
        actor_id=UUID("10000000-0000-0000-0000-000000000107"),
        role=ActorRole.ADVISOR,
        session_id=UUID("10000000-0000-0000-0000-000000000108"),
    )
    gateway = NightVoyagerAuthorityGateway(
        _Client(),
        EphemeralHttpAuthority(
            origin="http://127.0.0.1:3000",
            session_value="bounded-session",
            csrf_value="bounded-csrf",
        ),
    )

    with pytest.raises(DraAmbiguousOutcome):
        await gateway.create_task(
            context,
            case_id,
            7,
            source_pack_id,
            3,
            "bounded-idempotency-key",
        )
    recovered = await NightVoyagerAuthorityGateway(
        _Client(),
        gateway._authority,  # pyright: ignore[reportPrivateUsage]
    ).get_task(context, "bounded-idempotency-key")

    assert recovered is not None
    assert recovered.task_id == task_id
    assert observed[-1] == ("GET", "/api/v1/agent-tasks/recovery")


def test_governed_rehearsal_stage_probe_runs_in_a_fresh_process() -> None:
    child_pid = governed_flow._run_live_stage_probe()  # pyright: ignore[reportPrivateUsage]
    assert child_pid != os.getpid()


@pytest.mark.asyncio
async def test_all_production_mutations_translate_transport_lost_ack(
    tmp_path: Path,
) -> None:
    observed: list[str] = []

    class _Client:
        async def post(self, url: str, **kwargs: object) -> object:
            del kwargs
            observed.append(url)
            raise httpx2.ReadTimeout("committed response lost")

    command = _command(_private_roots(tmp_path)[1]).promotion
    context = ActorContext(
        organization_id=command.organization_id,
        actor_id=UUID("20000000-0000-4000-8000-000000000002"),
        role=ActorRole.ADVISOR,
        session_id=UUID("30000000-0000-4000-8000-000000000002"),
    )
    gateway = NightVoyagerAuthorityGateway(
        _Client(),
        EphemeralHttpAuthority(
            origin="http://127.0.0.1:3000",
            session_value="bounded-session",
            csrf_value="bounded-csrf",
        ),
    )
    assert command.source_attestation is not None
    calls = (
        gateway.promote_candidate(
            context,
            VerifyDraCandidateCommand(
                case_id=command.case_id,
                candidate_id=command.candidate_id,
                expected_case_revision=command.expected_case_revision,
                dra_evidence_id=command.dra_evidence_id,
                decision="approve",
                reason=command.reason,
                source_attestation=command.source_attestation,
            ),
            "promotion-key",
        ),
        gateway.record_review(
            context,
            command.case_id,
            command.expected_case_revision,
            UUID("10000000-0000-4000-8000-000000000201"),
            (UUID("10000000-0000-4000-8000-000000000202"),),
            "review-key",
        ),
        gateway.record_decision(
            context,
            UUID("10000000-0000-4000-8000-000000000203"),
            1,
            UUID("10000000-0000-4000-8000-000000000202"),
            100,
            200,
            ("bounded",),
            "decision-key",
        ),
    )
    for call in calls:
        with pytest.raises(DraAmbiguousOutcome):
            await call

    assert len(observed) == 3


def test_governed_proof_imports_with_exact_core_runtime_export() -> None:
    exported = subprocess.run(
        ("uv", "export", "--frozen", "--no-dev", "--no-emit-project"),
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert "\nhttpx2==" not in f"\n{exported}"

    code = f"""
import builtins
import runpy

original_import = builtins.__import__

def core_runtime_import(name, *args, **kwargs):
    if name == "httpx2" or name.startswith("httpx2."):
        raise ModuleNotFoundError("core runtime excludes optional dra dependencies")
    return original_import(name, *args, **kwargs)

builtins.__import__ = core_runtime_import
runpy.run_path({str(GOVERNED_PROOF)!r}, run_name="core_runtime_proof")
"""
    imported = subprocess.run(
        (sys.executable, "-c", code),
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert imported.returncode == 0, imported.stderr


class _ProofHandler(BaseHTTPRequestHandler):
    response_status = 200
    response_body = b'{"status":"ok"}'
    requests: list[dict[str, object]] = []

    def do_GET(self) -> None:  # noqa: N802
        self._handle()

    def do_POST(self) -> None:  # noqa: N802
        self._handle()

    def _handle(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        type(self).requests.append(
            {
                "method": self.command,
                "path": self.path,
                "headers": dict(self.headers.items()),
                "body": body,
            }
        )
        self.send_response(type(self).response_status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(type(self).response_body)

    def log_message(self, format: str, *args: Any) -> None:
        del format, args


@contextmanager
def _proof_server(
    *,
    status: int = 200,
    body: bytes = b'{"status":"ok"}',
) -> Generator[tuple[str, list[dict[str, object]]]]:
    handler = type(
        "ProofHandler",
        (_ProofHandler,),
        {"response_status": status, "response_body": body, "requests": []},
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host = str(server.server_address[0])
        port = int(server.server_address[1])
        yield f"http://{host}:{port}", handler.requests
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


@pytest.mark.asyncio
async def test_stdlib_async_client_preserves_authority_and_json_request() -> None:
    client_type = getattr(governed_flow, "_StdlibAsyncHttpClient", None)
    assert client_type is not None
    with _proof_server() as (base_url, requests):
        async with client_type(base_url=base_url, timeout=1) as client:
            response = await client.post(
                "/api/v1/mutate",
                headers={
                    "Origin": "http://127.0.0.1:3000",
                    "X-CSRF-Token": "bounded-csrf",
                    "Cookie": "night_voyager_session=bounded-session",
                    "Idempotency-Key": "bounded-idempotency-key",
                },
                json={"schema_version": 1},
            )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    response.raise_for_status()
    assert len(requests) == 1
    request = requests[0]
    assert request["method"] == "POST"
    assert request["path"] == "/api/v1/mutate"
    assert request["body"] == b'{"schema_version":1}'
    headers = request["headers"]
    assert isinstance(headers, dict)
    observed_headers = {
        key.lower(): value
        for key, value in cast(dict[str, str], headers).items()
    }
    assert observed_headers["content-type"] == "application/json"
    assert observed_headers["origin"] == "http://127.0.0.1:3000"
    assert observed_headers["x-csrf-token"] == "bounded-csrf"
    assert observed_headers["cookie"] == "night_voyager_session=bounded-session"
    assert observed_headers["idempotency-key"] == "bounded-idempotency-key"


@pytest.mark.asyncio
async def test_stdlib_async_client_preserves_404_for_gateway_handling() -> None:
    client_type = getattr(governed_flow, "_StdlibAsyncHttpClient", None)
    assert client_type is not None
    with _proof_server(status=404, body=b'{"code":"resource_unavailable"}') as (
        base_url,
        requests,
    ):
        async with client_type(base_url=base_url, timeout=1) as client:
            response = await client.get(
                "/api/v1/missing",
                headers={"Origin": "http://127.0.0.1:3000"},
            )

    assert requests[0]["path"] == "/api/v1/missing"
    assert response.status_code == 404
    assert response.json() == {"code": "resource_unavailable"}


@pytest.mark.asyncio
async def test_stdlib_async_client_rejects_non_success_and_invalid_json() -> None:
    client_type = getattr(governed_flow, "_StdlibAsyncHttpClient", None)
    assert client_type is not None
    with _proof_server(status=503, body=b'{"code":"temporarily_unavailable"}') as (
        base_url,
        _,
    ):
        async with client_type(base_url=base_url, timeout=1) as client:
            unavailable = await client.get("/api/v1/status", headers={})
    with pytest.raises(RuntimeError, match="night_voyager_http_status_503"):
        unavailable.raise_for_status()

    with _proof_server(body=b"not-json") as (base_url, _):
        async with client_type(base_url=base_url, timeout=1) as client:
            invalid = await client.get("/api/v1/status", headers={})
    with pytest.raises(json.JSONDecodeError):
        invalid.json()


@pytest.mark.asyncio
async def test_core_proof_gateway_accepts_versioned_candidate_http_envelope() -> None:
    candidate_id = UUID("00000000-0000-4000-8000-000000000099")
    body = json.dumps(
        {
            "schema_version": 1,
            "candidate_id": str(candidate_id),
            "verification": None,
            "replayed": False,
        }
    ).encode()
    candidate_import = build_v0_1_6_scenario_candidate_import()
    context = ActorContext(
        organization_id=candidate_import.organization_id,
        actor_id=UUID("20000000-0000-0000-0000-000000000001"),
        role=ActorRole.ADVISOR,
        session_id=UUID("30000000-0000-0000-0000-000000000001"),
    )

    client_type = getattr(governed_flow, "_StdlibAsyncHttpClient", None)
    assert client_type is not None
    with _proof_server(status=201, body=body) as (base_url, _):
        async with client_type(base_url=base_url, timeout=1) as client:
            imported = await NightVoyagerAuthorityGateway(
                client,
                EphemeralHttpAuthority(
                    origin="http://127.0.0.1:3000",
                    session_value="bounded-session",
                    csrf_value="bounded-csrf",
                ),
            ).import_candidate(
                context,
                candidate_import,
                "bounded-idempotency-key",
            )

    assert imported.candidate_id == candidate_id
    assert imported.verification is None


@pytest.mark.asyncio
async def test_core_proof_gateway_parses_task_skill_pin_from_http_json() -> None:
    case_id = UUID("10000000-0000-0000-0000-000000000001")
    task_id = UUID("10000000-0000-0000-0000-000000000002")
    source_pack_id = UUID("10000000-0000-0000-0000-000000000003")
    planning_run_id = UUID("10000000-0000-0000-0000-000000000004")
    execution_id = UUID("10000000-0000-0000-0000-000000000005")

    class _Response:
        status_code = 200

        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = payload

        def json(self) -> object:
            return self._payload

        def raise_for_status(self) -> None:
            return None

    class _Client:
        async def post(self, *args: object, **kwargs: object) -> _Response:
            del args, kwargs
            return _Response({"schema_version": 1, "task_id": str(task_id)})

        async def get(self, *args: object, **kwargs: object) -> _Response:
            del args, kwargs
            return _Response(
                {
                    "schema_version": 1,
                    "task_id": str(task_id),
                    "case_id": str(case_id),
                    "case_revision": 7,
                    "source_pack_id": str(source_pack_id),
                    "source_pack_version": 3,
                    "status": "needs_advisor_review",
                    "planning_run_id": str(planning_run_id),
                    "execution_id": str(execution_id),
                    "terminal_event_id": 11,
                    "skill_pin": {
                        "skill_definition_id": (
                            "81000000-0000-0000-0000-000000000002"
                        ),
                        "skill_version_id": "82000000-0000-0000-0000-000000000002",
                        "skill_activation_event_id": (
                            "84000000-0000-0000-0000-000000000001"
                        ),
                        "skill_activation_sequence": 1,
                        "runtime_binding_sha256": "d" * 64,
                    },
                    "request_sha256": "e" * 64,
                }
            )

    context = ActorContext(
        organization_id=UUID("10000000-0000-0000-0000-000000000006"),
        actor_id=UUID("10000000-0000-0000-0000-000000000007"),
        role=ActorRole.ADVISOR,
        session_id=UUID("10000000-0000-0000-0000-000000000008"),
    )
    task = await NightVoyagerAuthorityGateway(
        _Client(),
        EphemeralHttpAuthority(
            origin="http://127.0.0.1:3000",
            session_value="bounded-session",
            csrf_value="bounded-csrf",
        ),
    ).create_task(
        context,
        case_id,
        7,
        source_pack_id,
        3,
        "bounded-idempotency-key",
    )

    assert task.task_id == task_id
    assert task.skill_pin.skill_definition_id == UUID(
        "81000000-0000-0000-0000-000000000002"
    )
