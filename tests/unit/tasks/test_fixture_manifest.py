from __future__ import annotations

import hashlib
import json
from pathlib import Path

M3A = Path("fixtures/m3a/manifest.json")
M4A = Path("fixtures/m4a/manifest.json")


def test_m4a_manifest_references_exact_m3a_fixture_without_duplication() -> None:
    payload = json.loads(M4A.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["eval_id"] == "sse_idempotency_retry"
    assert payload["operation"] == "generate_planning_run_v1"
    assert payload["policy_version"] == "m3a-policy-v1"
    assert payload["planning_fixture"] == {
        "path": "../m3a/manifest.json",
        "sha256": hashlib.sha256(M3A.read_bytes()).hexdigest(),
    }
    assert "case" not in payload
    assert "evidence" not in payload
    assert payload["runtime"] == {
        "lease_seconds": 60,
        "heartbeat_seconds": 15,
        "poll_seconds": 1,
        "sse_heartbeat_seconds": 15,
        "max_attempts": 3,
        "sse_page_size": 100,
    }
    assert payload["assertions"] == [
        "same_key_same_request_replays",
        "same_key_different_request_conflicts",
        "lease_generation_fences_writes",
        "sse_reconnect_has_no_duplicates",
        "sse_comments_are_not_durable_events",
    ]
