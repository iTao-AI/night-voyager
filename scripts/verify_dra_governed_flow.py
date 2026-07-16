#!/usr/bin/env python3
"""Verify the offline governed DRA-to-decision closure through public HTTP."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import time
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from night_voyager.dra.fixtures import build_fixture_candidate_import
from night_voyager.identity.demo_seed import DRA_PROOF_CASE_ID

ORIGIN = "http://127.0.0.1:3000"
API = "http://127.0.0.1:8000/api/v1"
ORGANIZATION = "10000000-0000-0000-0000-000000000001"
PACK = "50000000-0000-0000-0000-000000000001"
AUSTRALIA = "71000000-0000-0000-0000-000000000001"
SOURCE_ROOT = Path(__file__).resolve().parents[1] / "fixtures/dra"
SOURCE_LOGICAL_PATH = "sources/australia-program-fit.html"
SOURCE_SHA256 = "87e314e801dca1aeaf9b751c149c53629a4cf23ee04698939fdc87def5a90a13"


def session(role: str) -> tuple[urllib.request.OpenerDirector, str]:
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
    return opener, str(minted["csrf_token"])


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
    candidate = build_fixture_candidate_import()
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
    parent, parent_csrf = session("parent")
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


async def inspect(promoted_version: int) -> None:
    database_url = os.environ.get("NIGHT_VOYAGER_DATABASE_URL")
    if not database_url:
        raise SystemExit("NIGHT_VOYAGER_DATABASE_URL is required")
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            for name, value in (
                ("night_voyager.organization_id", ORGANIZATION),
                ("night_voyager.actor_id", "20000000-0000-0000-0000-000000000001"),
                ("night_voyager.role", "advisor"),
            ):
                await connection.execute(
                    text("SELECT set_config(:name,:value,true)"),
                    {"name": name, "value": value},
                )
            row = (
                await connection.execute(
                    text(
                        "SELECT count(*) FILTER (WHERE authority='externally_verified') external,"
                        "count(*) FILTER (WHERE claim='australia_program_fit' AND "
                        "authority='externally_verified') bounded,count(*) total "
                        "FROM app.evidence_refs WHERE organization_id=:org "
                        "AND source_pack_id=:pack AND source_pack_version=:version"
                    ),
                    {"org": ORGANIZATION, "pack": PACK, "version": promoted_version},
                )
            ).mappings().one()
            if dict(row) != {"external": 1, "bounded": 1, "total": 6}:
                raise SystemExit("dra_governed_authority_invalid")
    finally:
        await engine.dispose()


def verify_fixture_flow() -> None:
    advisor, advisor_csrf = session("advisor")
    candidate_id, promoted_version = import_and_promote(advisor, advisor_csrf)
    task_id, run_id = create_and_wait_for_task(
        advisor, advisor_csrf, promoted_version
    )
    brief_id, receipt_id, timeline_id = close_human_decision(
        advisor, advisor_csrf, run_id
    )
    asyncio.run(inspect(promoted_version))
    print(
        "compose-proof: governed DRA fixture-to-decision closure passed "
        f"candidate={candidate_id} task={task_id} run={run_id} brief={brief_id} "
        f"receipt={receipt_id} timeline={timeline_id}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", action="store_true", required=True)
    parser.parse_args()
    verify_fixture_flow()


if __name__ == "__main__":
    main()
