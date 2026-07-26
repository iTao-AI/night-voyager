#!/usr/bin/env python3
"""Verify the offline governed DRA-to-decision closure through public HTTP."""

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
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from night_voyager.dra.fixtures import (
    build_v0_1_6_scenario_candidate_import,
    load_live_closure_scenario,
)
from night_voyager.dra.live_controller import (
    CaptureLiveCommand,
    DecideCommand,
    DraLiveCaptureController,
    DraLiveClosureController,
    PromoteCommand,
    ReviewCommand,
    SelectAndImportCommand,
)
from night_voyager.dra.live_evaluation import (
    DraLiveEvaluationReportV1,
    DraLiveOutcomeExpectedV1,
    evaluate_full_closure,
)
from night_voyager.dra.live_fakes import ScenarioDraLiveTransport
from night_voyager.dra.live_http import (
    EphemeralHttpAuthority,
    NightVoyagerAuthorityGateway,
)
from night_voyager.dra.live_models import (
    DraCandidateReadinessReceiptV2,
    DraCaptureInputV2,
    DraCaptureIntentV2,
    DraCaptureReceiptV1,
    DraDecisionInputV1,
    DraDecisionReceiptV1,
    DraInspectionRequiredReceiptV1,
    DraPromotionInputV1,
    DraPromotionReceiptV1,
    DraReviewInputV1,
    DraReviewReceiptV1,
    compose_effective_query_v2,
    derive_identity_hash,
)
from night_voyager.dra.live_outcome import DraLiveOutcomeIntentV1
from night_voyager.dra.live_outcome_postgres import (
    PostgresLiveOutcomeInspector,
)
from night_voyager.dra.live_storage import LiveReceiptStore, LiveStorageError
from night_voyager.dra.models import SourceAttestationV1
from night_voyager.identity.demo_seed import DRA_PROOF_CASE_ID
from night_voyager.identity.models import ActorContext, ActorRole

ORIGIN = "http://127.0.0.1:3000"
API = "http://127.0.0.1:8000/api/v1"
ORGANIZATION = "10000000-0000-0000-0000-000000000001"
PACK = "50000000-0000-0000-0000-000000000001"
AUSTRALIA = "71000000-0000-0000-0000-000000000001"
SOURCE_ROOT = Path(__file__).resolve().parents[1] / "fixtures/dra"
SOURCE_LOGICAL_PATH = "sources/australia-program-fit.html"
SOURCE_SHA256 = "87e314e801dca1aeaf9b751c149c53629a4cf23ee04698939fdc87def5a90a13"
MAX_RESPONSE_BYTES = 1_048_576
LIVE_STAGES = ("promote", "review", "decide", "evaluate")


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        del req, fp, code, msg, headers, newurl
        return None


class _StdlibHttpResponse:
    def __init__(self, status_code: int, body: bytes) -> None:
        self.status_code = status_code
        self._body = body

    def json(self) -> object:
        return json.loads(self._body)

    def raise_for_status(self) -> None:
        if not 200 <= self.status_code < 300:
            raise RuntimeError(f"night_voyager_http_status_{self.status_code}")


class _StdlibAsyncHttpClient:
    """Core-runtime HTTP client for the loopback-only Compose proof."""

    def __init__(self, *, base_url: str, timeout: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            _NoRedirectHandler(),
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        del args

    async def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str] | None = None,
    ) -> _StdlibHttpResponse:
        return await self._request("GET", url, headers=headers, params=params)

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: object,
    ) -> _StdlibHttpResponse:
        body = _canonical_json_bytes(json)
        return await self._request("POST", url, headers=headers, body=body)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str],
        params: dict[str, str] | None = None,
        body: bytes | None = None,
    ) -> _StdlibHttpResponse:
        url = f"{self._base_url}/{path.lstrip('/')}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        request_headers = dict(headers)
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            url,
            data=body,
            headers=request_headers,
            method=method,
        )
        return await asyncio.to_thread(self._open, request)

    def _open(self, request: urllib.request.Request) -> _StdlibHttpResponse:
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                status = response.status
                body = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as error:
            status = error.code
            body = error.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ValueError("night_voyager_http_response_too_large")
        return _StdlibHttpResponse(status, body)


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def session(role: str) -> tuple[urllib.request.OpenerDirector, str, str]:
    cookies = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
    with opener.open(
        urllib.request.Request(f"{API}/demo/session-bootstrap", headers={"Origin": ORIGIN})
    ) as response:
        bootstrap = json.load(response)
    request = urllib.request.Request(
        f"{API}/demo/sessions",
        data=json.dumps({"demo_actor": role}).encode(),
        headers={
            "Content-Type": "application/json",
            "Origin": ORIGIN,
            "X-CSRF-Token": bootstrap["csrf_token"],
        },
        method="POST",
    )
    with opener.open(request) as response:
        minted = json.load(response)
    session_value = next(
        cookie.value
        for cookie in cookies
        if cookie.name == "night_voyager_session"
    )
    if session_value is None:
        raise SystemExit("demo_session_missing")
    return opener, str(minted["csrf_token"]), session_value


def post(
    opener: urllib.request.OpenerDirector,
    path: str,
    csrf: str,
    key: str,
    payload: dict[str, object],
) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Origin": ORIGIN,
            "X-CSRF-Token": csrf,
            "Idempotency-Key": key,
        },
        method="POST",
    )
    with opener.open(request) as response:
        return json.load(response)


def validate_source_snapshot(
    root: Path, logical_path: str, expected_sha256: str
) -> tuple[int, str]:
    declared_root = root.resolve(strict=True)
    requested = root / logical_path
    if requested.is_symlink():
        raise SystemExit("dra_governed_source_invalid")
    resolved = requested.resolve(strict=True)
    if not resolved.is_relative_to(declared_root):
        raise SystemExit("dra_governed_source_invalid")
    content = resolved.read_bytes()
    actual = hashlib.sha256(content).hexdigest()
    if actual != expected_sha256:
        raise SystemExit("dra_governed_source_invalid")
    return len(content), actual


def import_and_promote(
    opener: urllib.request.OpenerDirector, csrf: str
) -> tuple[str, int]:
    candidate = build_v0_1_6_scenario_candidate_import()
    payload = candidate.model_dump(mode="json", exclude_computed_fields=True)
    payload.pop("organization_id")
    payload.pop("case_id")
    imported = post(
        opener,
        f"/cases/{DRA_PROOF_CASE_ID}/dra-candidates",
        csrf,
        "compose-governed-import",
        payload,
    )
    evidence = next(item for item in candidate.evidence if item.is_promotable)
    byte_length, source_sha256 = validate_source_snapshot(
        SOURCE_ROOT, SOURCE_LOGICAL_PATH, SOURCE_SHA256
    )
    approved = post(
        opener,
        f"/cases/{DRA_PROOF_CASE_ID}/dra-candidates/"
        f"{imported['candidate_id']}/verification-decisions",
        csrf,
        "compose-governed-approval",
        {
            "schema_version": 1,
            "expected_case_revision": 1,
            "dra_evidence_id": evidence.evidence_id,
            "decision": "approve",
            "reason": "Exact bounded fixture source inspected.",
            "source_attestation": {
                "canonical_url": str(evidence.source_url),
                "publisher": "Synthetic Public Source Publisher",
                "institution": "Synthetic Australia Institution",
                "snapshot_date": "2026-07-11",
                "freshness_days": 365,
                "redistribution_class": "link_only",
                "evidence_class": "institutional",
                "logical_path": SOURCE_LOGICAL_PATH,
                "snapshot_byte_length": byte_length,
                "snapshot_sha256": source_sha256,
                "known_gaps": ["applicant_eligibility", "intake_availability"],
            },
        },
    )
    return str(imported["candidate_id"]), int(approved["promoted_source_pack_version"])


def create_and_wait_for_task(
    opener: urllib.request.OpenerDirector, csrf: str, promoted_version: int
) -> tuple[str, str]:
    created = post(
        opener,
        f"/cases/{DRA_PROOF_CASE_ID}/agent-tasks",
        csrf,
        "compose-governed-mixed-task",
        {
            "schema_version": 1,
            "operation": "generate_governed_mixed_planning_run_v1",
            "expected_case_revision": 1,
            "source_pack_id": PACK,
            "source_pack_version": promoted_version,
            "policy_version": "m3a-policy-v1",
        },
    )
    task_id = str(created["task_id"])
    for _ in range(30):
        with opener.open(f"{API}/tasks/{task_id}") as response:
            task = json.load(response)
        if task["status"] == "needs_advisor_review":
            run_id = task.get("planning_run_id")
            if not run_id:
                raise SystemExit("dra_governed_task_invalid")
            with opener.open(f"{API}/tasks/{task_id}/events") as response:
                events = response.read().decode()
            if "event: waiting_review" not in events:
                raise SystemExit("dra_governed_sse_invalid")
            return task_id, str(run_id)
        if task["status"] != "preparing":
            raise SystemExit("dra_governed_task_invalid")
        time.sleep(1)
    raise SystemExit("dra_governed_task_timeout")


def close_human_decision(
    advisor: urllib.request.OpenerDirector,
    advisor_csrf: str,
    run_id: str,
) -> tuple[str, str, str]:
    review = post(
        advisor,
        f"/cases/{DRA_PROOF_CASE_ID}/advisor-reviews",
        advisor_csrf,
        "compose-governed-advisor-review",
        {
            "schema_version": 1,
            "planning_run_id": run_id,
            "expected_case_revision": 1,
            "action": "approve_for_consultation",
            "eligible_route_ids": [AUSTRALIA],
            "risk_acceptances": [],
        },
    )
    brief_id = str(review["brief_id"])
    parent, parent_csrf, _ = session("parent")
    decision = post(
        parent,
        f"/decision-briefs/{brief_id}/family-decisions",
        parent_csrf,
        "compose-governed-family-decision",
        {
            "schema_version": 1,
            "expected_brief_version": 1,
            "selected_route_id": AUSTRALIA,
            "accepted_budget_min_minor": 30_000_000,
            "accepted_budget_max_minor": 40_000_000,
            "currency": "CNY",
            "accepted_trade_offs": ["budget_elasticity"],
        },
    )
    with parent.open(f"{API}/decision-briefs/{brief_id}") as response:
        persisted = json.load(response)
    if (
        persisted.get("receipt_id") != decision.get("receipt_id")
        or persisted.get("timeline_id") != decision.get("timeline_id")
    ):
        raise SystemExit("dra_governed_decision_invalid")
    return brief_id, str(decision["receipt_id"]), str(decision["timeline_id"])


async def inspect(
    candidate_id: str,
    promoted_version: int,
    task_id: str,
    run_id: str,
) -> None:
    database_url = os.environ.get("NIGHT_VOYAGER_DATABASE_URL")
    if not database_url:
        raise SystemExit("NIGHT_VOYAGER_DATABASE_URL is required")
    engine = create_async_engine(database_url)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        context = ActorContext(
            organization_id=UUID(ORGANIZATION),
            actor_id=UUID("20000000-0000-0000-0000-000000000001"),
            role=ActorRole.ADVISOR,
            session_id=UUID("30000000-0000-0000-0000-000000000001"),
        )
        intent = DraLiveOutcomeIntentV1(
            intent_sha256="0" * 64,
            organization_id=context.organization_id,
            candidate_id=UUID(candidate_id),
            advisor_actor_identity_sha256=derive_identity_hash(
                "actor", str(context.actor_id)
            ),
            tenant_identity_sha256=derive_identity_hash(
                "tenant", str(context.organization_id)
            ),
        )
        async with factory() as session:
            projection = await PostgresLiveOutcomeInspector(
                session
            ).inspect(context, intent)
        expected = {
            "candidate_id": candidate_id,
            "promoted_source_pack_id": PACK,
            "promoted_source_pack_version": promoted_version,
            "task_id": task_id,
            "planning_run_id": run_id,
            "external_claim": "australia_program_fit",
            "evidence_role": "program_fit",
            "external_authority": "externally_verified",
            "verification_count": 1,
            "governed_task_count": 1,
            "advisor_review_count": 1,
            "family_decision_count": 1,
            "decision_receipt_count": 1,
            "timeline_plan_count": 1,
        }
        observed = projection.model_dump(mode="json")
        if any(observed[key] != value for key, value in expected.items()):
            raise SystemExit("dra_governed_authority_invalid")
    finally:
        await engine.dispose()


def _stage_environment(
    context: ActorContext,
    *,
    session_value: str,
    csrf_value: str,
) -> dict[str, str]:
    return {
        **os.environ,
        "NIGHT_VOYAGER_DRA_STAGE_ORGANIZATION_ID": str(context.organization_id),
        "NIGHT_VOYAGER_DRA_STAGE_ACTOR_ID": str(context.actor_id),
        "NIGHT_VOYAGER_DRA_STAGE_SESSION_ID": str(context.session_id),
        "NIGHT_VOYAGER_DRA_STAGE_ROLE": context.role.value,
        "NIGHT_VOYAGER_DRA_STAGE_SESSION": session_value,
        "NIGHT_VOYAGER_DRA_STAGE_CSRF": csrf_value,
    }


async def _execute_live_stage_child(
    stage: str,
    receipt_root: Path,
    input_file: Path,
    snapshot_root: Path | None,
) -> None:
    context = ActorContext(
        organization_id=UUID(os.environ["NIGHT_VOYAGER_DRA_STAGE_ORGANIZATION_ID"]),
        actor_id=UUID(os.environ["NIGHT_VOYAGER_DRA_STAGE_ACTOR_ID"]),
        role=ActorRole(os.environ["NIGHT_VOYAGER_DRA_STAGE_ROLE"]),
        session_id=UUID(os.environ["NIGHT_VOYAGER_DRA_STAGE_SESSION_ID"]),
    )
    authority = EphemeralHttpAuthority(
        origin=ORIGIN,
        session_value=os.environ["NIGHT_VOYAGER_DRA_STAGE_SESSION"],
        csrf_value=os.environ["NIGHT_VOYAGER_DRA_STAGE_CSRF"],
    )
    payload_json = input_file.read_text(encoding="utf-8")
    async with _StdlibAsyncHttpClient(
        base_url="http://127.0.0.1:8000",
        timeout=30,
    ) as client:
        with LiveReceiptStore.open(receipt_root) as store:
            controller = DraLiveClosureController(
                NightVoyagerAuthorityGateway(client, authority),
                store,
            )
            if stage == "promote":
                if snapshot_root is None:
                    raise ValueError("dra_live_stage_snapshot_missing")
                await controller.promote(
                    PromoteCommand(
                        DraPromotionInputV1.model_validate_json(payload_json),
                        context,
                        snapshot_root,
                    )
                )
                return
            if stage == "review":
                await controller.review(
                    ReviewCommand(
                        DraReviewInputV1.model_validate_json(payload_json),
                        context,
                    )
                )
                return
            if stage == "decide":
                await controller.decide(
                    DecideCommand(
                        DraDecisionInputV1.model_validate_json(payload_json),
                        context,
                    )
                )
                return
            if stage != "evaluate":
                raise ValueError("dra_live_stage_invalid")
            capture = store.read_receipt("capture.json", DraCaptureReceiptV1)
            promotion = store.read_receipt("promotion.json", DraPromotionReceiptV1)
            review = store.read_receipt("review.json", DraReviewReceiptV1)
            decision = store.read_receipt("decision.json", DraDecisionReceiptV1)
            database_url = os.environ.get("NIGHT_VOYAGER_DATABASE_URL")
            if not database_url:
                raise ValueError("dra_live_stage_database_missing")
            engine = create_async_engine(database_url)
            try:
                factory = async_sessionmaker(engine, expire_on_commit=False)
                async with factory() as database_session:
                    projection = await PostgresLiveOutcomeInspector(
                        database_session
                    ).inspect(
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
                DraLiveOutcomeExpectedV1.model_validate_json(payload_json),
                projection,
            )
            if report.status != "passed":
                raise ValueError("dra_live_rehearsal_evaluation_failed")
            store.write_receipt("evaluation.json", report)


def _run_live_stage(
    stage: str,
    *,
    receipt_root: Path,
    input_file: Path,
    environment: dict[str, str],
    snapshot_root: Path | None = None,
    expect_success: bool = True,
) -> int:
    command: list[str] = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--live-stage",
        stage,
        "--receipt-root",
        str(receipt_root),
        "--input-file",
        str(input_file),
    ]
    if snapshot_root is not None:
        command.extend(("--snapshot-root", str(snapshot_root)))
    completed = subprocess.run(
        command,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != (0 if expect_success else 1):
        raise RuntimeError(
            f"dra_live_stage_{stage}_unexpected_exit_{completed.returncode}"
        )
    if not expect_success:
        result = json.loads(completed.stdout)
        if (
            result.get("stage") != stage
            or result.get("problem") != "stage_authority_invalid"
        ):
            raise RuntimeError("dra_live_stage_rejection_invalid")
        return -1
    result = json.loads(completed.stdout)
    if result.get("stage") != stage or not isinstance(result.get("pid"), int):
        raise RuntimeError("dra_live_stage_identity_invalid")
    return int(result["pid"])


def _write_stage_input(path: Path, model: BaseModel) -> None:
    path.write_text(model.model_dump_json(), encoding="utf-8")
    path.chmod(0o600)


async def _real_live_closure_rehearsal() -> tuple[str, str, str]:
    scenario = load_live_closure_scenario()
    advisor_context = ActorContext(
        organization_id=UUID(ORGANIZATION),
        actor_id=UUID("20000000-0000-0000-0000-000000000001"),
        role=ActorRole.ADVISOR,
        session_id=UUID("30000000-0000-0000-0000-000000000001"),
    )
    _, advisor_csrf, advisor_session = session("advisor")
    parent_context = ActorContext(
        organization_id=UUID(ORGANIZATION),
        actor_id=UUID("20000000-0000-0000-0000-000000000003"),
        role=ActorRole.PARENT,
        session_id=UUID("30000000-0000-0000-0000-000000000003"),
    )
    _, parent_csrf, parent_session = session("parent")
    query = b"bounded synthetic query"
    with tempfile.TemporaryDirectory(prefix="night-voyager-dra-live-") as temporary:
        task_root = Path(temporary)
        task_root.chmod(0o700)
        receipt_root = task_root / "receipts"
        receipt_root.mkdir(mode=0o700)
        query_path = task_root / "query.txt"
        query_path.write_bytes(query)
        query_path.chmod(0o600)
        _, request = compose_effective_query_v2(
            query,
            logical_name=query_path.name,
        )
        readiness = DraCandidateReadinessReceiptV2(
            merged_main_sha="0" * 40,
            request=request,
            spec_sha256="1" * 64,
            plan_sha256="2" * 64,
            scenario_sha256="3" * 64,
            intent_schema_sha256="4" * 64,
            receipt_schema_sha256="5" * 64,
            cli_sha256="6" * 64,
            producer=scenario.producer,
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
        )
        with LiveReceiptStore.open(receipt_root) as store:
            readiness_identity = store.write_receipt(
                "readiness.json",
                readiness,
            )
        intent = DraCaptureIntentV2.freeze(
            DraCaptureInputV2(
                scenario_id=scenario.scenario_id,
                producer=scenario.producer,
                organization_id=advisor_context.organization_id,
                case_id=DRA_PROOF_CASE_ID,
                expected_case_revision=1,
                advisor_actor_identity_sha256=derive_identity_hash(
                    "actor", str(advisor_context.actor_id)
                ),
                tenant_identity_sha256=derive_identity_hash(
                    "tenant", str(advisor_context.organization_id)
                ),
                request=request,
                candidate_readiness_sha256=readiness_identity.sha256,
                receipt_root_id=receipt_root.name,
                one_attempt_authorized=True,
            ),
            attempt_id_factory=lambda: "compose-rehearsal-attempt-1",
        )
        async with _StdlibAsyncHttpClient(
            base_url="http://127.0.0.1:8000",
            timeout=30,
        ) as advisor_client:
            advisor_gateway = NightVoyagerAuthorityGateway(
                advisor_client,
                EphemeralHttpAuthority(
                    origin=ORIGIN,
                    session_value=advisor_session,
                    csrf_value=advisor_csrf,
                ),
            )
            with LiveReceiptStore.open(receipt_root) as store:
                capture_controller = DraLiveCaptureController(
                    ScenarioDraLiveTransport(scenario),
                    advisor_gateway,
                    store,
                )
                preflight = capture_controller.preflight(intent)
                inspection = await capture_controller.capture(
                    CaptureLiveCommand(intent, preflight, query_path)
                )
            if not isinstance(inspection, DraInspectionRequiredReceiptV1):
                raise SystemExit("dra_live_rehearsal_capture_invalid")
            selected_url = next(
                item.source_url
                for item in inspection.evidence
                if item.citation_status == "cited"
            )
            if selected_url is None:
                raise SystemExit("dra_live_rehearsal_selection_invalid")
            with LiveReceiptStore.open(receipt_root) as store:
                capture = await DraLiveCaptureController(
                    ScenarioDraLiveTransport(scenario),
                    advisor_gateway,
                    store,
                ).select_and_import(
                    SelectAndImportCommand(
                        intent,
                        store.read_receipt(
                            "inspection-required.json",
                            DraInspectionRequiredReceiptV1,
                        ),
                        selected_url,
                        advisor_context,
                    )
                )
            if not isinstance(capture, DraCaptureReceiptV1):
                raise SystemExit("dra_live_rehearsal_import_invalid")
            if capture.candidate_id is None or capture.selected_evidence is None:
                raise SystemExit("dra_live_rehearsal_import_invalid")
            snapshot_root = task_root / "snapshot"
            snapshot_root.mkdir(mode=0o700)
            source_parent = snapshot_root / "sources"
            source_parent.mkdir(mode=0o700)
            snapshot_path = source_parent / "australia-program-fit.html"
            shutil.copyfile(SOURCE_ROOT / SOURCE_LOGICAL_PATH, snapshot_path)
            snapshot_path.chmod(0o600)
            attestation = SourceAttestationV1(
                canonical_url=selected_url,
                publisher="Synthetic Public Source Publisher",
                institution="Synthetic Australia Institution",
                snapshot_date=date(2026, 7, 11),
                freshness_days=365,
                redistribution_class="link_only",
                evidence_class="institutional",
                logical_path=SOURCE_LOGICAL_PATH,
                snapshot_byte_length=snapshot_path.stat().st_size,
                snapshot_sha256=hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
                known_gaps=("applicant_eligibility", "intake_availability"),
            )
            promotion_input = DraPromotionInputV1(
                intent_sha256=intent.intent_sha256,
                capture=capture,
                organization_id=advisor_context.organization_id,
                case_id=DRA_PROOF_CASE_ID,
                expected_case_revision=1,
                candidate_id=capture.candidate_id,
                dra_evidence_id=capture.selected_evidence.evidence_id,
                selected_raw_url=selected_url,
                advisor_actor_identity_sha256=derive_identity_hash(
                    "actor", str(advisor_context.actor_id)
                ),
                tenant_identity_sha256=derive_identity_hash(
                    "tenant", str(advisor_context.organization_id)
                ),
                reason="Exact bounded fixture source inspected.",
                source_attestation=attestation,
            )
            promotion_input_path = task_root / "promotion-input.json"
            _write_stage_input(promotion_input_path, promotion_input)
            missing_root = task_root / "missing-predecessor"
            missing_root.mkdir(mode=0o700)
            _run_live_stage(
                "promote",
                receipt_root=missing_root,
                input_file=promotion_input_path,
                snapshot_root=snapshot_root,
                environment=_stage_environment(
                    advisor_context,
                    session_value=advisor_session,
                    csrf_value=advisor_csrf,
                ),
                expect_success=False,
            )
            stage_pids = {
                _run_live_stage(
                    "promote",
                    receipt_root=receipt_root,
                    input_file=promotion_input_path,
                    snapshot_root=snapshot_root,
                    environment=_stage_environment(
                        advisor_context,
                        session_value=advisor_session,
                        csrf_value=advisor_csrf,
                    ),
                )
            }
            with LiveReceiptStore.open(receipt_root) as store:
                promotion = store.read_receipt(
                    "promotion.json", DraPromotionReceiptV1
                )
            review_input = DraReviewInputV1(
                intent_sha256=intent.intent_sha256,
                promotion=promotion,
                organization_id=advisor_context.organization_id,
                case_id=DRA_PROOF_CASE_ID,
                expected_case_revision=1,
                candidate_id=promotion.candidate_id,
                promoted_source_pack_id=UUID(PACK),
                promoted_source_pack_version=promotion.promoted_source_pack_version,
                advisor_actor_identity_sha256=derive_identity_hash(
                    "actor", str(advisor_context.actor_id)
                ),
                tenant_identity_sha256=derive_identity_hash(
                    "tenant", str(advisor_context.organization_id)
                ),
                eligible_route_ids=(UUID(AUSTRALIA),),
            )
            review_input_path = task_root / "review-input.json"
            _write_stage_input(review_input_path, review_input)
            forged_payload = review_input.model_dump(mode="json")
            forged_payload["promotion"]["verification_id"] = str(UUID(int=999))
            forged_input_path = task_root / "forged-review-input.json"
            forged_input_path.write_text(
                json.dumps(forged_payload, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            forged_input_path.chmod(0o600)
            _run_live_stage(
                "review",
                receipt_root=receipt_root,
                input_file=forged_input_path,
                environment=_stage_environment(
                    advisor_context,
                    session_value=advisor_session,
                    csrf_value=advisor_csrf,
                ),
                expect_success=False,
            )
            stage_pids.add(
                _run_live_stage(
                    "review",
                    receipt_root=receipt_root,
                    input_file=review_input_path,
                    environment=_stage_environment(
                        advisor_context,
                        session_value=advisor_session,
                        csrf_value=advisor_csrf,
                    ),
                )
            )
            with LiveReceiptStore.open(receipt_root) as store:
                review = store.read_receipt("review.json", DraReviewReceiptV1)
            decision_input = DraDecisionInputV1(
                intent_sha256=intent.intent_sha256,
                review=review,
                organization_id=parent_context.organization_id,
                case_id=DRA_PROOF_CASE_ID,
                brief_id=review.review.brief_id,
                expected_brief_version=1,
                selected_route_id=UUID(AUSTRALIA),
                accepted_budget_min_minor=30_000_000,
                accepted_budget_max_minor=40_000_000,
                accepted_trade_offs=("budget_elasticity",),
                family_actor_identity_sha256=derive_identity_hash(
                    "actor", str(parent_context.actor_id)
                ),
                tenant_identity_sha256=derive_identity_hash(
                    "tenant", str(parent_context.organization_id)
                ),
            )
            decision_input_path = task_root / "decision-input.json"
            _write_stage_input(decision_input_path, decision_input)
            stage_pids.add(
                _run_live_stage(
                    "decide",
                    receipt_root=receipt_root,
                    input_file=decision_input_path,
                    environment=_stage_environment(
                        parent_context,
                        session_value=parent_session,
                        csrf_value=parent_csrf,
                    ),
                )
            )
            with LiveReceiptStore.open(receipt_root) as store:
                decision = store.read_receipt(
                    "decision.json", DraDecisionReceiptV1
                )
        expected = DraLiveOutcomeExpectedV1(
            candidate_id=str(promotion.candidate_id),
            source_pack_id=str(review.source_pack_id),
            source_pack_version=review.source_pack_version,
            source_entry_id=str(promotion.promoted_source_entry_id),
            evidence_id=str(promotion.promoted_evidence_id),
            task_id=str(review.task.task_id),
            task_state="waiting_review",
            planning_run_id=str(review.task.planning_run_id),
            planning_run_state="review_required",
            verification_id=str(promotion.verification_id),
            execution_id=str(review.task.execution_id),
            terminal_event_id=review.task.terminal_event_id,
            skill_definition_id=str(review.task.skill_pin.skill_definition_id),
            skill_version_id=str(review.task.skill_pin.skill_version_id),
            skill_activation_event_id=str(
                review.task.skill_pin.skill_activation_event_id
            ),
            skill_activation_sequence=review.task.skill_pin.skill_activation_sequence,
            runtime_binding_sha256=review.task.skill_pin.runtime_binding_sha256,
            review_id=str(review.review.review_id),
            brief_id=str(review.review.brief_id),
            decision_id=str(decision.decision.decision_id),
            decision_receipt_id=str(decision.decision.decision_receipt_id),
            timeline_plan_id=str(decision.decision.timeline_plan_id),
        )
        expected_path = task_root / "evaluation-input.json"
        _write_stage_input(expected_path, expected)
        stage_pids.add(
            _run_live_stage(
                "evaluate",
                receipt_root=receipt_root,
                input_file=expected_path,
                environment=_stage_environment(
                    advisor_context,
                    session_value=advisor_session,
                    csrf_value=advisor_csrf,
                ),
            )
        )
        if len(stage_pids) != len(LIVE_STAGES) or os.getpid() in stage_pids:
            raise SystemExit("dra_live_rehearsal_process_boundary_invalid")
        with LiveReceiptStore.open(receipt_root) as store:
            report = store.read_receipt(
                "evaluation.json", DraLiveEvaluationReportV1
            )
        if report.status != "passed":
            raise SystemExit("dra_live_rehearsal_evaluation_failed")
        return str(promotion.candidate_id), str(review.task.task_id), str(
            decision.decision.decision_receipt_id
        )


def verify_fixture_flow() -> None:
    candidate_id, task_id, receipt_id = asyncio.run(
        _real_live_closure_rehearsal()
    )
    print(
        "compose-proof: governed DRA live-controller closure passed "
        f"candidate={candidate_id} task={task_id} receipt={receipt_id}"
    )


def _run_live_stage_probe() -> int:  # pyright: ignore[reportUnusedFunction]
    completed = subprocess.run(
        (sys.executable, str(Path(__file__).resolve()), "--live-stage-probe"),
        check=True,
        text=True,
        capture_output=True,
    )
    return int(completed.stdout.strip())


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fixture", action="store_true")
    mode.add_argument("--live-stage-probe", action="store_true")
    mode.add_argument("--live-stage", choices=LIVE_STAGES)
    parser.add_argument("--receipt-root")
    parser.add_argument("--input-file")
    parser.add_argument("--snapshot-root")
    args = parser.parse_args()
    if args.live_stage_probe:
        print(os.getpid())
        return
    if args.live_stage:
        if not args.receipt_root or not args.input_file:
            raise SystemExit(1)
        try:
            asyncio.run(
                _execute_live_stage_child(
                    args.live_stage,
                    Path(args.receipt_root),
                    Path(args.input_file),
                    Path(args.snapshot_root) if args.snapshot_root else None,
                )
            )
        except (KeyError, LiveStorageError, OSError, ValueError):
            print(
                json.dumps(
                    {
                        "stage": args.live_stage,
                        "problem": "stage_authority_invalid",
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            raise SystemExit(1) from None
        print(
            json.dumps(
                {"stage": args.live_stage, "pid": os.getpid()},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return
    verify_fixture_flow()


if __name__ == "__main__":
    main()
