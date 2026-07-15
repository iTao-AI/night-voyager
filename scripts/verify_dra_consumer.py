#!/usr/bin/env python3
"""Offline DRA fixture verification and separately authorized live proof."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import cast

from night_voyager.dra.fixtures import build_fixture_candidate_import, load_dra_fixture
from night_voyager.dra.models import DraCanonicalArtifactInputV1, DraRunProjectionV1

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "fixtures/dra/sources/australia-program-fit.html"
EXPECTED_SOURCE_SHA256 = "87e314e801dca1aeaf9b751c149c53629a4cf23ee04698939fdc87def5a90a13"
LIVE_ACK = "separately-authorized-one-attempt"
MAX_QUERY_BYTES = 65_536


def render(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    else:
        print(f"DRA {payload['mode']} proof: {payload['status']}")


def verify_fixture() -> dict[str, object]:
    os.chdir(ROOT)
    fixture = load_dra_fixture()
    candidate = build_fixture_candidate_import()
    source_sha256 = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if source_sha256 != EXPECTED_SOURCE_SHA256:
        raise SystemExit("dra_source_snapshot_changed")
    if len(candidate.evidence) == 0 or candidate.artifact.byte_length > 1_048_576:
        raise SystemExit("dra_candidate_contract_invalid")
    return {
        "schema_version": "night-voyager.dra-consumer-proof.v1",
        "mode": "fixture",
        "status": "verified",
        "release": candidate.producer.release,
        "commit": candidate.producer.commit,
        "contract_schema": fixture.schema_version,
        "fixture_sha256": candidate.producer.fixture_sha256,
        "source_sha256": source_sha256,
        "artifact_sha256": candidate.artifact.content_hash,
        "evidence_count": len(candidate.evidence),
    }


def required_environment() -> tuple[str, str, str, Path, int]:
    if os.environ.get("DRA_LIVE_PROOF_ACK") != LIVE_ACK:
        raise SystemExit("dra_live_proof_not_authorized")
    names = (
        "DECISION_RESEARCH_AGENT_API_KEY",
        "DRA_IDEMPOTENCY_KEY",
        "DRA_BASE_URL",
        "DRA_QUERY_FILE",
        "DRA_POLL_DEADLINE_SECONDS",
    )
    if any(not os.environ.get(name) for name in names):
        raise SystemExit("dra_live_proof_environment_incomplete")
    query_path = Path(os.environ["DRA_QUERY_FILE"]).resolve()
    try:
        query_bytes = query_path.read_bytes()
    except OSError as error:
        raise SystemExit("dra_query_file_unreadable") from error
    if not query_bytes or len(query_bytes) > MAX_QUERY_BYTES:
        raise SystemExit("dra_query_file_invalid")
    try:
        query_bytes.decode("utf-8")
        deadline = int(os.environ["DRA_POLL_DEADLINE_SECONDS"])
    except (UnicodeDecodeError, ValueError) as error:
        raise SystemExit("dra_live_proof_environment_invalid") from error
    if not 1 <= deadline <= 3600:
        raise SystemExit("dra_live_proof_environment_invalid")
    return (
        os.environ["DRA_BASE_URL"],
        os.environ["DRA_IDEMPOTENCY_KEY"],
        query_bytes.decode("utf-8"),
        query_path,
        deadline,
    )


async def verify_live() -> dict[str, object]:
    base_url, key, query, _query_path, deadline = required_environment()
    from night_voyager.adapters.dra_readonly import DraClientConfig, Httpx2DraTransport
    from night_voyager.dra.reconciliation import DraRunReconciler

    config = DraClientConfig(
        base_url=base_url, poll_seconds=1, deadline_seconds=deadline
    )
    transport = Httpx2DraTransport(config, environ=os.environ)
    await transport.health()
    acceptance = await DraRunReconciler(transport).create(
        {"query": query, "profile_id": "generic"}, key
    )
    stop_at = time.monotonic() + deadline
    run: DraRunProjectionV1 | None = None
    while time.monotonic() < stop_at:
        status_payload = await transport._request_json(  # pyright: ignore[reportPrivateUsage]
            "GET", f"/api/runs/{acceptance.run_id}"
        )
        try:
            run = DraRunProjectionV1.model_validate(status_payload)
        except ValueError:
            await asyncio.sleep(config.poll_seconds)
            continue
        break
    if run is None:
        raise SystemExit("dra_poll_deadline_exceeded")
    result = await transport._request_json(  # pyright: ignore[reportPrivateUsage]
        "GET", f"/api/runs/{acceptance.run_id}/result"
    )
    artifact_payload = result.get("artifact")
    if not isinstance(artifact_payload, dict):
        raise SystemExit("dra_live_artifact_invalid")
    artifact = DraCanonicalArtifactInputV1.model_validate(
        cast(dict[str, object], artifact_payload)
    )
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".md", prefix="dra-proof-", delete=True
    ) as output:
        output.write(artifact.content)
        output.flush()
    return {
        "schema_version": "night-voyager.dra-consumer-proof.v1",
        "mode": "live",
        "status": "verified",
        "thread_id": acceptance.thread_id,
        "run_id": acceptance.run_id,
        "segment_id": acceptance.segment_id,
        "artifact_sha256": artifact.content_hash,
        "artifact_byte_length": artifact.byte_length,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("fixture", "live"))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        payload = verify_fixture() if args.mode == "fixture" else asyncio.run(verify_live())
    except SystemExit as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from None
    render(payload, args.json)


if __name__ == "__main__":
    main()
