from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import sys
import zlib
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
HEAD = "b9e37518bcee783328edf06e403cdb87b9e21020"


def diagnostic() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "proof_mode": "synthetic-demo",
        "candidate_head": HEAD,
        "locale": "en",
        "stage": "student-handoff-assertion",
        "stages": [{"name": "helper-unrouted", "elapsed_ms": 31}],
        "http": [
            {
                "method": "POST",
                "path": "/api/demo/cases/:case/advisor-reviews",
                "status": 200,
                "elapsed_ms": 21,
                "outcome": "response",
                "phase": None,
                "role": None,
                "code": None,
            }
        ],
        "document_lang": "en",
        "visible": {
            "request_revision": False,
            "reconnect": True,
            "continue_student": False,
            "continue_advisor": False,
            "continue_parent": False,
        },
        "replay": {"observed_posts": 2, "same_key": True},
        "screenshot": None,
    }


def invoke(
    tmp_path: Path, value: dict[str, Any] | None, candidate: str = HEAD
) -> subprocess.CompletedProcess[str]:
    source = tmp_path / "review" / "diagnostics-en"
    source.mkdir(parents=True, exist_ok=True)
    if value is not None:
        (source / "diagnostics.json").write_text(json.dumps(value))
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/prepare_planning_revision_diagnostics.py"),
            "--review-root",
            str(tmp_path / "review"),
            "--output",
            str(tmp_path / "safe"),
            "--candidate-sha",
            candidate,
            "--github-output",
            str(tmp_path / "github-output"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def png_with_chunks(*extra: tuple[bytes, bytes]) -> bytes:
    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + b"".join(chunk(kind, body) for kind, body in extra)
        + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
        + chunk(b"IEND", b"")
    )


def test_safe_bundle_copies_only_validated_projection_and_manifest(tmp_path: Path) -> None:
    source = tmp_path / "review" / "diagnostics-en"
    source.mkdir(parents=True)
    (source / "trace.zip").write_text("unit-secret-cookie")
    (source / "error-context.md").write_text("unit-secret-csrf")
    result = invoke(tmp_path, diagnostic())
    assert result.returncode == 0, result.stderr
    files = {
        str(path.relative_to(tmp_path / "safe"))
        for path in (tmp_path / "safe").rglob("*")
        if path.is_file()
    }
    assert files == {"manifest.json", "en/diagnostics.json", "en/context.md"}
    output = "\n".join(
        path.read_text() for path in (tmp_path / "safe").rglob("*") if path.is_file()
    )
    assert "unit-secret" not in output
    assert HEAD in output and "student-handoff-assertion" in output
    manifest = json.loads((tmp_path / "safe/manifest.json").read_text())
    for entry in manifest["files"]:
        assert (
            entry["sha256"]
            == hashlib.sha256((tmp_path / "safe" / entry["path"]).read_bytes()).hexdigest()
        )


def test_no_diagnostic_does_not_invent_failure_evidence(tmp_path: Path) -> None:
    result = invoke(tmp_path, None)
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "safe").exists()
    assert (tmp_path / "github-output").read_text() == "ready=false\n"


def test_unknown_candidate_cannot_publish_a_projection(tmp_path: Path) -> None:
    value = diagnostic()
    value["candidate_head"] = "0" * 40
    result = invoke(tmp_path, value, "0" * 40)
    assert result.returncode == 1
    assert not (tmp_path / "safe").exists()
    assert not (tmp_path / "github-output").exists()


def test_second_locale_rejection_writes_no_partial_public_bundle(tmp_path: Path) -> None:
    source = tmp_path / "review" / "diagnostics-zh-CN"
    source.mkdir(parents=True)
    unsafe = diagnostic()
    unsafe.update(locale="zh-CN", storage="unit-secret-cookie")
    (source / "diagnostics.json").write_text(json.dumps(unsafe))
    result = invoke(tmp_path, diagnostic())
    assert result.returncode == 1
    assert not (tmp_path / "safe").exists()
    assert "unit-secret" not in result.stdout + result.stderr


def test_abrupt_exit_keeps_only_observed_progress_and_pending_http(tmp_path: Path) -> None:
    source = tmp_path / "review" / "diagnostics-en"
    source.mkdir(parents=True)
    value = diagnostic()
    value["document_lang"] = "unknown"
    value["visible"] = dict.fromkeys(value["visible"])
    value["http"][0].update(status=None, outcome="pending")
    (source / "progress.json").write_text(json.dumps(value))
    result = invoke(tmp_path, None)
    assert result.returncode == 0, result.stderr
    exported = json.loads((tmp_path / "safe/en/diagnostics.json").read_text())
    assert exported["stage"] == "student-handoff-assertion"
    assert exported["http"][0]["outcome"] == "pending"
    assert exported["document_lang"] == "unknown"
    assert all(flag is None for flag in exported["visible"].values())


def test_observed_language_mismatch_is_preserved_without_raw_context(tmp_path: Path) -> None:
    source = tmp_path / "review" / "diagnostics-en"
    source.mkdir(parents=True)
    image = png_with_chunks()
    (source / "visible-action.png").write_bytes(image)
    value = diagnostic()
    value["document_lang"] = "zh-CN"
    value["screenshot"] = {
        "file": "visible-action.png",
        "action": "reconnect-zh-CN",
        "text_matches": True,
        "sha256": hashlib.sha256(image).hexdigest(),
    }
    result = invoke(tmp_path, value)
    assert result.returncode == 0, result.stderr
    exported = json.loads((tmp_path / "safe/en/diagnostics.json").read_text())
    assert exported["locale"] == "en" and exported["document_lang"] == "zh-CN"


def test_invalid_final_report_does_not_fall_back_to_progress(tmp_path: Path) -> None:
    source = tmp_path / "review" / "diagnostics-en"
    source.mkdir(parents=True)
    (source / "progress.json").write_text(json.dumps(diagnostic()))
    value = diagnostic()
    value["headers"] = {"Cookie": "unit-secret-cookie"}
    result = invoke(tmp_path, value)
    assert result.returncode == 1
    assert not (tmp_path / "safe").exists()


@pytest.mark.parametrize(
    "mutation",
    (
        "extra_storage",
        "unsafe_path",
        "unknown_code",
        "different_head",
        "false_outcome",
        "unknown_language",
    ),
)
def test_unsafe_or_misbound_projection_fails_closed(tmp_path: Path, mutation: str) -> None:
    value = diagnostic()
    if mutation == "extra_storage":
        value["sessionStorage"] = "unit-secret-token"
    elif mutation == "unsafe_path":
        value["http"][0]["path"] = "/api/demo/sessions?csrf=unit-secret-token"
    elif mutation == "unknown_code":
        value["http"][0]["code"] = "unit-secret-token"
    elif mutation == "different_head":
        value["candidate_head"] = "0" * 40
    elif mutation == "false_outcome":
        value["http"][0]["outcome"] = "failed"
    else:
        value["document_lang"] = "unit-secret-token"
    result = invoke(tmp_path, value)
    assert result.returncode == 1
    assert "unit-secret" not in result.stdout + result.stderr
    assert not (tmp_path / "safe").exists()


@pytest.mark.parametrize("unsafe", (False, True))
def test_only_bounded_png_without_metadata_is_exported(tmp_path: Path, unsafe: bool) -> None:
    source = tmp_path / "review" / "diagnostics-en"
    source.mkdir(parents=True)
    image = (
        png_with_chunks((b"tEXt", b"secret\x00unit-secret-cookie")) if unsafe else png_with_chunks()
    )
    (source / "visible-action.png").write_bytes(image)
    value = diagnostic()
    value["screenshot"] = {
        "file": "visible-action.png",
        "action": "reconnect-en",
        "text_matches": True,
        "sha256": hashlib.sha256(image).hexdigest(),
    }
    result = invoke(tmp_path, value)
    assert result.returncode == (1 if unsafe else 0)
    if unsafe:
        assert not (tmp_path / "safe").exists()
    else:
        assert (tmp_path / "safe/en/visible-action.png").read_bytes() == image


def test_diagnostic_symlinks_are_not_followed(tmp_path: Path) -> None:
    source = tmp_path / "review" / "diagnostics-en"
    source.mkdir(parents=True)
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps(diagnostic()))
    (source / "diagnostics.json").symlink_to(outside)
    result = invoke(tmp_path, None)
    assert result.returncode == 1
    assert not (tmp_path / "safe").exists()


@pytest.mark.parametrize("browser_status,expected", ((37, 37), (0, 1)))
def test_shell_retains_browser_failure_instead_of_kill_status(
    tmp_path: Path, browser_status: int, expected: int
) -> None:
    source = (ROOT / "scripts/verify_compose.sh").read_text()
    assert "require_planning_revision_browser() {" in source
    function = source.split("require_planning_revision_browser() {", 1)[1].split("\n}", 1)[0]
    harness = tmp_path / "browser-status.sh"
    harness.write_text(
        "set -eu\nplanning_revision_browser_pid=42\nkill() { return 1; }\n"
        f"wait() {{ return {browser_status}; }}\n"
        f"require_planning_revision_browser() {{{function}\n}}\n"
        "require_planning_revision_browser\n"
    )
    result = subprocess.run(["sh", str(harness)], capture_output=True, text=True, check=False)
    assert result.returncode == expected


def test_failure_upload_uses_explicit_safe_paths_and_preserves_existing_gate() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    steps = workflow["jobs"]["compose_proof"]["steps"]
    prepare = next(step for step in steps if step.get("id") == "planning_revision_diagnostics")
    upload = next(step for step in steps if "actions/upload-artifact@" in step.get("uses", ""))
    assert prepare["if"] == "failure()"
    assert "prepare_planning_revision_diagnostics.py" in prepare["run"]
    assert "failure()" in upload["if"] and "outputs.ready == 'true'" in upload["if"]
    assert upload["with"]["include-hidden-files"] is False
    paths = upload["with"]["path"].splitlines()
    assert set(paths) == {
        "tmp/planning-revision-ci-artifacts/manifest.json",
        *(
            f"tmp/planning-revision-ci-artifacts/{locale}/{name}"
            for locale in ("en", "zh-CN")
            for name in ("diagnostics.json", "context.md", "visible-action.png")
        ),
    }
    assert len(paths) == 7
    assert upload["uses"] == "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
    assert upload["with"]["retention-days"] == 7
    assert [step["run"] for step in steps if step.get("run") == "make compose-proof"] == [
        "make compose-proof"
    ]
    assert steps[-1] == {"if": "always()", "run": "make down"}
    assert not any(step.get("continue-on-error") for step in steps)
