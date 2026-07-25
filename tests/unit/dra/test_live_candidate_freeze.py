# pyright: reportPrivateUsage=false

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.verify_dra_live_closure import _validated_candidate_evidence

HEAD = "a" * 40


def _write(path: Path, value: dict[str, object]) -> str:
    path.write_text(json.dumps(value), encoding="utf-8")
    return str(path)


def _args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        docker_inventory_file=_write(
            tmp_path / "docker.json",
            {
                "schema_version": "night-voyager.dra-live-docker-evidence.v1",
                "head_sha": HEAD,
                "docker_preflight_status": "passed",
                "teardown_status": "passed",
                "cleanup_state": "clean",
                "compose_projects_after": [],
            },
        ),
        hosted_check_evidence_file=_write(
            tmp_path / "checks.json",
            {
                "schema_version": (
                    "night-voyager.dra-live-hosted-checks-evidence.v1"
                ),
                "head_sha": HEAD,
                "checks": {
                    "python": "SUCCESS",
                    "frontend": "SUCCESS",
                    "compose": "SUCCESS",
                },
            },
        ),
        recovery_evidence_file=_write(
            tmp_path / "recovery.json",
            {
                "schema_version": "night-voyager.dra-live-recovery-evidence.v1",
                "head_sha": HEAD,
                "recovery_matrix_status": "passed",
            },
        ),
        authority_review_evidence_file=_write(
            tmp_path / "review.json",
            {
                "schema_version": (
                    "night-voyager.dra-live-authority-review-evidence.v1"
                ),
                "head_sha": HEAD,
                "authority_review_status": "CLEAN",
            },
        ),
    )


def test_candidate_evidence_requires_all_exact_success_receipts(
    tmp_path: Path,
) -> None:
    args = _args(tmp_path)
    with pytest.raises(ValueError):
        _validated_candidate_evidence(args, HEAD)


def test_candidate_evidence_is_independently_reverified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compose_ls = "[]"
    recovery_output = "47 passed\n"
    repository = "example/night-voyager"
    reviewed_head = "b" * 40
    args = argparse.Namespace(
        docker_inventory_file=_write(
            tmp_path / "docker.json",
            {
                "schema_version": "night-voyager.dra-live-docker-evidence.v1",
                "head_sha": HEAD,
                "server_version": "27.0",
                "compose_version": "2.0",
                "compose_ls_sha256": hashlib.sha256(compose_ls.encode()).hexdigest(),
                "task_project": "night-voyager-dra-live-closure",
            },
        ),
        hosted_check_evidence_file=_write(
            tmp_path / "checks.json",
            {
                "schema_version": "night-voyager.dra-live-hosted-checks-evidence.v1",
                "head_sha": HEAD,
                "repository": repository,
                "check_run_ids": {"python": 1, "frontend": 2, "compose": 3},
            },
        ),
        recovery_evidence_file=_write(
            tmp_path / "recovery.json",
            {
                "schema_version": "night-voyager.dra-live-recovery-evidence.v1",
                "head_sha": HEAD,
                "command": [
                    "uv",
                    "run",
                    "pytest",
                    "-q",
                    "tests/integration/dra/test_live_closure_recovery.py",
                    "tests/unit/dra/test_live_review_controller.py",
                    "tests/unit/dra/test_live_decision_controller.py",
                ],
                "stdout_sha256": hashlib.sha256(recovery_output.encode()).hexdigest(),
            },
        ),
        authority_review_evidence_file=_write(
            tmp_path / "review.json",
            {
                "schema_version": (
                    "night-voyager.dra-live-authority-review-evidence.v1"
                ),
                "head_sha": HEAD,
                "repository": repository,
                "pull_request": 70,
                "review_id": 9,
                "reviewed_head_sha": reviewed_head,
            },
        ),
    )

    def run(command: tuple[str, ...], **kwargs: object) -> SimpleNamespace:
        del kwargs
        if command[:2] == ("docker", "version"):
            output = "27.0\n"
        elif command[:3] == ("docker", "compose", "version"):
            output = "2.0\n"
        elif command[:3] == ("docker", "compose", "ls"):
            output = compose_ls
        elif command[-1].endswith("/check-runs"):
            output = json.dumps(
                {
                    "check_runs": [
                        {
                            "id": identifier,
                            "name": name,
                            "status": "completed",
                            "conclusion": "success",
                            "head_sha": HEAD,
                        }
                        for name, identifier in (
                            ("python", 1),
                            ("frontend", 2),
                            ("compose", 3),
                        )
                    ]
                }
            )
        elif command[:4] == ("uv", "run", "pytest", "-q"):
            output = recovery_output
        elif command[-1].endswith("/reviews/9"):
            output = json.dumps(
                {"id": 9, "state": "APPROVED", "commit_id": reviewed_head}
            )
        else:
            output = json.dumps({"merged": True, "merge_commit_sha": HEAD})
        return SimpleNamespace(stdout=output)

    monkeypatch.setattr("scripts.verify_dra_live_closure.subprocess.run", run)
    assert all(_validated_candidate_evidence(args, HEAD))

    Path(args.authority_review_evidence_file).write_text(
        Path(args.authority_review_evidence_file)
        .read_text(encoding="utf-8")
        .replace('"review_id": 9', '"review_id": 10'),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="candidate_evidence_provenance_invalid"):
        _validated_candidate_evidence(args, HEAD)

@pytest.mark.parametrize("mutation", ("failed", "stale", "arbitrary"))
def test_candidate_evidence_rejects_failed_stale_or_arbitrary_receipts(
    tmp_path: Path,
    mutation: str,
) -> None:
    args = _args(tmp_path)
    review = Path(args.authority_review_evidence_file)
    value = json.loads(review.read_text(encoding="utf-8"))
    if mutation == "failed":
        value["authority_review_status"] = "BLOCKED"
    elif mutation == "stale":
        value["head_sha"] = "b" * 40
    else:
        value["unexpected"] = "self-asserted"
    review.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValueError):
        _validated_candidate_evidence(args, HEAD)
