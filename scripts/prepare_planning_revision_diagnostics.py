"""Export the closed, credential-free planning-revision failure projection."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
import zlib
from pathlib import Path
from typing import Any, cast

STAGES = {
    "started",
    "request-revision",
    "fact-confirmation",
    "create-task",
    "lost-ack-intercepted",
    "lost-ack-committed",
    "lost-ack-aborted",
    "replay-action",
    "replay-post-observed",
    "helper-unrouted",
    "student-handoff-assertion",
    "student-handoff-observed",
}
PHASES = {
    "task_ready",
    "active_task",
    "review_required",
    "revision_requested",
    "revision_fact_pending",
    "replan_required",
    "revision_task_active",
    "revision_review_required",
    "revision_blocked",
    "family_review",
    "plan_ready",
    "terminal_task_failure",
}
CODES = {
    "bff_upstream_unavailable",
    "bff_session_recovery_required",
    "authentication_failed",
    "resource_unavailable",
    "request_validation_failed",
    "stale_revision",
    "intake_evidence_unavailable",
}
PATHS = {
    "/api/demo/session-bootstrap",
    "/api/demo/sessions",
    "/api/demo/session",
    *(
        f"/api/demo/cases/:case/{name}"
        for name in (
            "advisor-reviews",
            "journey-status",
            "advisor-ledger",
            "confirmed-facts",
            "collaboration-thread",
            "memory-candidates",
            "agent-tasks",
        )
    ),
}
VISIBLE = {
    "request_revision",
    "reconnect",
    "continue_student",
    "continue_advisor",
    "continue_parent",
}
ACTIONS = {f"{action}-{locale}" for action in VISIBLE for locale in ("en", "zh-CN")}


def require(condition: bool) -> None:
    if not condition:
        raise ValueError("unsafe diagnostic projection")


def exact(value: Any, keys: set[str]) -> dict[str, Any]:
    require(isinstance(value, dict))
    projected = cast(dict[str, Any], value)
    require(set(projected) == keys)
    return projected


def bounded_integer(value: Any, maximum: int = 3_600_000) -> bool:
    return type(value) is int and 0 <= value <= maximum


def safe_file(path: Path, maximum: int) -> bytes:
    require(not path.is_symlink() and path.is_file() and path.stat().st_size <= maximum)
    return path.read_bytes()


def bounded_png(data: bytes) -> None:
    require(data.startswith(b"\x89PNG\r\n\x1a\n"))
    offset = 8
    kinds: list[bytes] = []
    while offset < len(data):
        require(offset + 12 <= len(data))
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        require(kind in {b"IHDR", b"IDAT", b"IEND"} and offset + 12 + length <= len(data))
        body = data[offset + 8 : offset + 8 + length]
        crc = struct.unpack(">I", data[offset + 8 + length : offset + 12 + length])[0]
        require(zlib.crc32(kind + body) == crc)
        if kind == b"IHDR":
            require(length == 13)
            width, height = struct.unpack(">II", body[:8])
            require(0 < width <= 900 and 0 < height <= 180)
        kinds.append(kind)
        offset += 12 + length
    require(
        bool(kinds) and kinds[0] == b"IHDR" and kinds[-1] == b"IEND" and kinds.count(b"IHDR") == 1
    )
    require(b"IDAT" in kinds and kinds.count(b"IEND") == 1)


def validate(value: Any, locale: str, candidate: str) -> dict[str, Any]:
    value = exact(
        value,
        {
            "schema_version",
            "proof_mode",
            "candidate_head",
            "locale",
            "stage",
            "stages",
            "http",
            "document_lang",
            "visible",
            "replay",
            "screenshot",
        },
    )
    require(
        type(value["schema_version"]) is int
        and value["schema_version"] == 1
        and value["proof_mode"] == "synthetic-demo"
    )
    require(value["candidate_head"] == candidate and value["locale"] == locale)
    require(value["stage"] in STAGES and value["document_lang"] in {"en", "zh-CN", "unknown"})
    for field in ("stages", "http"):
        require(isinstance(value[field], list) and len(value[field]) <= 128)
    for stage in value["stages"]:
        stage = exact(stage, {"name", "elapsed_ms"})
        require(stage["name"] in STAGES and bounded_integer(stage["elapsed_ms"]))
    for event in value["http"]:
        event = exact(
            event, {"method", "path", "status", "elapsed_ms", "outcome", "phase", "role", "code"}
        )
        require(event["method"] in {"GET", "POST", "DELETE"} and event["path"] in PATHS)
        require(bounded_integer(event["elapsed_ms"]))
        require(event["phase"] is None or event["phase"] in PHASES)
        require(event["role"] in {None, "advisor", "student", "parent"})
        require(event["code"] is None or event["code"] in CODES)
        require(
            (event["outcome"] in {"pending", "failed"} and event["status"] is None)
            or (
                event["outcome"] == "response"
                and type(event["status"]) is int
                and 100 <= event["status"] <= 599
            )
        )
    visible = exact(value["visible"], VISIBLE)
    require(all(flag is None or type(flag) is bool for flag in visible.values()))
    replay = exact(value["replay"], {"observed_posts", "same_key"})
    require(bounded_integer(replay["observed_posts"], 100))
    require(replay["same_key"] is None or type(replay["same_key"]) is bool)
    if value["screenshot"] is not None:
        image = exact(value["screenshot"], {"file", "action", "text_matches", "sha256"})
        require(image["file"] == "visible-action.png" and image["action"] in ACTIONS)
        require(image["text_matches"] is True)
        require(
            isinstance(image["sha256"], str)
            and re.fullmatch(r"[0-9a-f]{64}", image["sha256"]) is not None
        )
    return value


def prepare(review: Path, output: Path, candidate: str) -> bool:
    require(re.fullmatch(r"[0-9a-f]{40}", candidate) is not None and candidate != "0" * 40)
    require(not review.is_symlink() and not output.exists() and not output.is_symlink())
    prepared: dict[str, bytes] = {}
    for locale in ("en", "zh-CN"):
        source = review / f"diagnostics-{locale}"
        require(not source.is_symlink())
        report = source / "diagnostics.json"
        if not report.exists() and not report.is_symlink():
            report = source / "progress.json"
            if not report.exists() and not report.is_symlink():
                continue
        value = validate(json.loads(safe_file(report, 65_536)), locale, candidate)
        image = value["screenshot"]
        if image is not None:
            data = safe_file(source / "visible-action.png", 1_048_576)
            bounded_png(data)
            require(hashlib.sha256(data).hexdigest() == image["sha256"])
            prepared[f"{locale}/visible-action.png"] = data
        prepared[f"{locale}/diagnostics.json"] = (json.dumps(value, indent=2) + "\n").encode()
        lines = [
            "# Planning revision failure projection",
            "",
            f"Candidate: `{candidate}`",
            f"Locale: `{locale}`; document language: `{value['document_lang']}`",
            f"Observed stage: `{value['stage']}`",
            "",
            "Visible approved actions:",
        ]
        lines.extend(f"- `{name}`: `{flag}`" for name, flag in sorted(value["visible"].items()))
        lines.extend(
            [
                "",
                "HTTP body/headers, storage, idempotency values and raw trace are excluded.",
                "The optional screenshot crops one exact static action label; "
                "it is not a whole-page image.",
                "",
            ]
        )
        prepared[f"{locale}/context.md"] = "\n".join(lines).encode()
    if not prepared:
        return False
    manifest = {
        "schema_version": 1,
        "candidate_head": candidate,
        "proof_mode": "synthetic-demo",
        "raw_trace_included": False,
        "files": [
            {"path": path, "sha256": hashlib.sha256(data).hexdigest()}
            for path, data in sorted(prepared.items())
        ],
    }
    prepared["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    # Validate every input before writing any publishable output.
    for path, data in prepared.items():
        target = output / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    try:
        ready = prepare(args.review_root, args.output, args.candidate_sha)
    except (ValueError, TypeError, KeyError, OSError, struct.error):
        print("planning-revision diagnostics rejected; no safe artifact prepared", file=sys.stderr)
        return 1
    if args.github_output is not None:
        with args.github_output.open("a") as stream:
            stream.write(f"ready={'true' if ready else 'false'}\n")
    print(
        "planning-revision safe diagnostics prepared"
        if ready
        else "no planning-revision diagnostic available"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
