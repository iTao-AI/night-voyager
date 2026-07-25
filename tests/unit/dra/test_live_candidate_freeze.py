# pyright: reportPrivateUsage=false

from __future__ import annotations

import argparse
import json
from pathlib import Path

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
    evidence = _validated_candidate_evidence(args, HEAD)
    assert all(evidence)

    Path(args.hosted_check_evidence_file).write_text(
        json.dumps(
            {
                "schema_version": (
                    "night-voyager.dra-live-hosted-checks-evidence.v1"
                ),
                "head_sha": HEAD,
                "checks": {"python": "SUCCESS", "frontend": "SUCCESS"},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="candidate_hosted_checks_invalid"):
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
