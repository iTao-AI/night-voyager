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
REVIEWED_HEAD = "b" * 40
TASK_PROJECT = "night-voyager-dra-v0-1-6-live-acceptance"
RECOVERY_COMMAND = [
    "uv",
    "run",
    "pytest",
    "-q",
    "tests/integration/dra/test_live_closure_recovery.py",
    "tests/unit/dra/test_live_review_controller.py",
    "tests/unit/dra/test_live_decision_controller.py",
]
DOCTOR_OUTPUT = (
    "PASSED CHECK: host project filesystem 44040192 KiB available\n"
    "PASSED CHECK: Docker VM filesystem 12582912 KiB available\n"
    "doctor: dev preflight passed\n"
)
INVENTORY_OUTPUTS = {
    ("docker", "compose", "ls", "--all", "--format", "json"): "[]\n",
    ("docker", "ps", "-a", "--no-trunc", "--format", "json"): "",
    (
        "docker",
        "image",
        "ls",
        "--digests",
        "--no-trunc",
        "--format",
        "json",
    ): '{"Repository":"python","Tag":"3.12.13-slim"}\n',
    ("docker", "buildx", "du", "--verbose"): "ID RECLAIMABLE SIZE\n",
    ("docker", "network", "ls", "--no-trunc", "--format", "json"): (
        '{"Name":"bridge"}\n'
    ),
    ("docker", "volume", "ls", "--format", "json"): (
        '{"Name":"night-voyager_postgres-data"}\n'
    ),
}


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


def _inventory_hashes(
    outputs: dict[tuple[str, ...], str] = INVENTORY_OUTPUTS,
) -> dict[str, str]:
    names = ("compose", "containers", "images", "build_cache", "networks", "volumes")
    return {
        name: hashlib.sha256(output.encode()).hexdigest()
        for name, output in zip(names, outputs.values(), strict=True)
    }


def _valid_args(tmp_path: Path) -> argparse.Namespace:
    repository = "example/night-voyager"
    inventory_hashes = _inventory_hashes()
    retained = {
        "images": ["python:3.12.13-slim"],
        "volumes": ["night-voyager_postgres-data"],
        "build_cache_sha256": inventory_hashes["build_cache"],
    }
    return argparse.Namespace(
        docker_inventory_file=_write(
            tmp_path / "docker.json",
            {
                "schema_version": "night-voyager.dra-live-docker-evidence.v1",
                "head_sha": HEAD,
                "task_project": TASK_PROJECT,
                "minimum_docker_vm_kib": 8_388_608,
                "host_available_kib": 44_040_192,
                "docker_vm_available_kib": 12_582_912,
                "doctor_stdout_sha256": hashlib.sha256(
                    DOCTOR_OUTPUT.encode()
                ).hexdigest(),
                "before_inventory_sha256": inventory_hashes,
                "after_inventory_sha256": inventory_hashes,
                "retained_resources": retained,
            },
        ),
        hosted_check_evidence_file=_write(
            tmp_path / "checks.json",
            {
                "schema_version": (
                    "night-voyager.dra-live-hosted-checks-evidence.v1"
                ),
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
                "command": RECOVERY_COMMAND,
                "stdout_sha256": hashlib.sha256(b"47 passed\n").hexdigest(),
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
                "reviewed_head_sha": REVIEWED_HEAD,
            },
        ),
    )


def _live_runner(
    calls: list[tuple[str, ...]],
    *,
    pull_head: str = REVIEWED_HEAD,
    reviewed_tree: str = "c" * 40,
    merge_tree: str = "c" * 40,
    doctor_output: str = DOCTOR_OUTPUT,
    inventory_outputs: dict[tuple[str, ...], str] = INVENTORY_OUTPUTS,
):
    def run(command: tuple[str, ...], **kwargs: object) -> SimpleNamespace:
        del kwargs
        normalized = tuple(command)
        calls.append(normalized)
        if normalized in inventory_outputs:
            output = inventory_outputs[normalized]
        elif normalized[:2] == ("docker", "version"):
            output = "27.0\n"
        elif normalized == ("docker", "compose", "version", "--short"):
            output = "2.0\n"
        elif normalized == ("docker", "compose", "ls", "--format", "json"):
            output = "[]\n"
        elif normalized == ("make", "doctor", "MODE=dev"):
            output = doctor_output
        elif normalized[-1].endswith("/check-runs"):
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
        elif normalized == tuple(RECOVERY_COMMAND):
            output = "47 passed\n"
        elif normalized[-1].endswith("/reviews/9"):
            output = json.dumps(
                {"id": 9, "state": "APPROVED", "commit_id": REVIEWED_HEAD}
            )
        elif normalized[-1].endswith(f"/git/commits/{REVIEWED_HEAD}"):
            output = json.dumps({"tree": {"sha": reviewed_tree}})
        elif normalized[-1].endswith(f"/git/commits/{HEAD}"):
            output = json.dumps({"tree": {"sha": merge_tree}})
        else:
            output = json.dumps(
                {
                    "merged": True,
                    "merge_commit_sha": HEAD,
                    "head": {"sha": pull_head},
                }
            )
        return SimpleNamespace(stdout=output)

    return run


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
    args = _valid_args(tmp_path)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "scripts.verify_dra_live_closure.subprocess.run",
        _live_runner(calls),
    )
    assert all(_validated_candidate_evidence(args, HEAD))

    Path(args.authority_review_evidence_file).write_text(
        Path(args.authority_review_evidence_file)
        .read_text(encoding="utf-8")
        .replace('"review_id": 9', '"review_id": 10'),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="candidate_evidence_provenance_invalid"):
        _validated_candidate_evidence(args, HEAD)


def test_candidate_evidence_rejects_unapproved_recovery_before_any_subprocess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = _valid_args(tmp_path)
    recovery = Path(args.recovery_evidence_file)
    value = json.loads(recovery.read_text(encoding="utf-8"))
    value["command"] = ["python", "-c", "raise SystemExit('must never execute')"]
    recovery.write_text(json.dumps(value), encoding="utf-8")
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "scripts.verify_dra_live_closure.subprocess.run",
        _live_runner(calls),
    )

    with pytest.raises(ValueError, match="candidate_evidence_provenance_invalid"):
        _validated_candidate_evidence(args, HEAD)

    assert calls == []


def test_candidate_evidence_rejects_review_of_stale_pr_head(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = _valid_args(tmp_path)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "scripts.verify_dra_live_closure.subprocess.run",
        _live_runner(calls, pull_head="d" * 40),
    )

    with pytest.raises(ValueError, match="candidate_evidence_provenance_invalid"):
        _validated_candidate_evidence(args, HEAD)


def test_candidate_evidence_rejects_reviewed_tree_that_differs_from_merge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = _valid_args(tmp_path)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "scripts.verify_dra_live_closure.subprocess.run",
        _live_runner(calls, merge_tree="d" * 40),
    )

    with pytest.raises(ValueError, match="candidate_evidence_provenance_invalid"):
        _validated_candidate_evidence(args, HEAD)


@pytest.mark.parametrize(
    ("mutation", "observed"),
    (
        ("low-space", None),
        ("wrong-project", None),
        (
            "residual-resource",
            {
                **INVENTORY_OUTPUTS,
                ("docker", "ps", "-a", "--no-trunc", "--format", "json"): (
                    f'{{"Names":"{TASK_PROJECT}-api-1"}}\n'
                ),
            },
        ),
    ),
)
def test_candidate_evidence_rejects_invalid_docker_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    observed: dict[tuple[str, ...], str] | None,
) -> None:
    args = _valid_args(tmp_path)
    doctor_output = DOCTOR_OUTPUT
    docker = Path(args.docker_inventory_file)
    docker_value = json.loads(docker.read_text(encoding="utf-8"))
    if mutation == "low-space":
        doctor_output = DOCTOR_OUTPUT.replace("12582912", "8388607")
        docker_value["docker_vm_available_kib"] = 8_388_607
        docker_value["doctor_stdout_sha256"] = hashlib.sha256(
            doctor_output.encode()
        ).hexdigest()
    elif mutation == "wrong-project":
        docker_value["task_project"] = "arbitrary-absent-project"
    elif observed is not None:
        docker_value["before_inventory_sha256"] = _inventory_hashes(observed)
        docker_value["after_inventory_sha256"] = _inventory_hashes(observed)
    docker.write_text(json.dumps(docker_value), encoding="utf-8")
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "scripts.verify_dra_live_closure.subprocess.run",
        _live_runner(
            calls,
            doctor_output=doctor_output,
            inventory_outputs=observed or INVENTORY_OUTPUTS,
        ),
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
