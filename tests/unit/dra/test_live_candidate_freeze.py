# pyright: reportPrivateUsage=false

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from scripts.verify_dra_live_closure import (
    _canonical_docker_inventory,
    _canonical_docker_inventory_bytes,
    _validated_candidate_evidence,
)

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
    "PASSED CHECK: Docker daemon and Compose --wait are available\n"
    "PASSED CHECK: host project filesystem 44040192 KiB available\n"
    "PASSED CHECK: Docker VM filesystem 12582912 KiB available\n"
    "PASSED CHECK: port 127.0.0.1:3000 is free\n"
    "PASSED CHECK: port 127.0.0.1:8000 is free\n"
    "PASSED CHECK: port 127.0.0.1:55432 is free\n"
    "PASSED CHECK: contributor Python/uv/Node/npm toolchain is available\n"
    "doctor: dev preflight passed\n"
)
DOCTOR_SEMANTIC_OUTPUT = (
    "PASSED CHECK: Docker daemon and Compose --wait are available\n"
    "PASSED CHECK: host project filesystem <available-kib> KiB available\n"
    "PASSED CHECK: Docker VM filesystem <available-kib> KiB available\n"
    "PASSED CHECK: port 127.0.0.1:3000 is free\n"
    "PASSED CHECK: port 127.0.0.1:8000 is free\n"
    "PASSED CHECK: port 127.0.0.1:55432 is free\n"
    "PASSED CHECK: contributor Python/uv/Node/npm toolchain is available\n"
    "doctor: dev preflight passed\n"
)
INVENTORY_OUTPUTS: dict[tuple[str, ...], str] = {
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
    ): (
        '{"Containers":"0","CreatedAt":"2026-07-14 10:18:56 +0800 CST",'
        '"CreatedSince":"12 days ago",'
        '"Digest":"sha256:57cd7c3a7a273101a6485ba99423ee568157882804b'
        '1124b4dd04266317710de","ID":"sha256:57cd7c3a7a273101a6485ba'
        '99423ee568157882804b1124b4dd04266317710de","Repository":"python",'
        '"SharedSize":"N/A","Size":"205MB","Tag":"3.12.13-slim",'
        '"UniqueSize":"N/A"}\n'
    ),
    ("docker", "buildx", "du", "--format", "json"): (
        '{"CreatedAt":"2026-07-17 05:40:51 +0000 UTC","Description":"",'
        '"ID":"cache-b","LastUsedAt":"7 days ago","Mutable":false,'
        '"Parents":["parent-b","parent-a"],"Reclaimable":true,'
        '"Shared":true,"Size":"248B","Type":"regular","UsageCount":7}\n'
        '{"CreatedAt":"2026-07-18 05:40:51 +0000 UTC",'
        '"Description":"[proof 1/1] RUN true","ID":"cache-a",'
        '"LastUsedAt":"6 days ago","Mutable":false,"Parents":null,'
        '"Reclaimable":false,"Shared":false,"Size":"4.128kB",'
        '"Type":"regular","UsageCount":1}\n'
    ),
    ("docker", "network", "ls", "--no-trunc", "--format", "json"): (
        '{"CreatedAt":"2026-07-13 08:57:30 +0000 UTC",'
        '"Driver":"bridge","ID":"network-bridge","IPv4":"true",'
        '"IPv6":"false","Internal":"false","Labels":"","Name":"bridge",'
        '"Scope":"local"}\n'
    ),
    ("docker", "volume", "ls", "--format", "json"): (
        '{"Availability":"N/A","Driver":"local","Group":"N/A",'
        '"Labels":"com.docker.compose.project=night-voyager,'
        'com.docker.compose.volume=postgres-data","Links":"N/A",'
        '"Mountpoint":"/var/lib/docker/volumes/'
        'night-voyager_postgres-data/_data",'
        '"Name":"night-voyager_postgres-data","Scope":"local",'
        '"Size":"N/A","Status":"N/A"}\n'
    ),
}
DOCKER_COMMANDS_BY_NAME: dict[str, tuple[str, ...]] = dict(
    zip(
        ("compose", "containers", "images", "build_cache", "networks", "volumes"),
        INVENTORY_OUTPUTS,
        strict=True,
    )
)


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
                "schema_version": ("night-voyager.dra-live-hosted-checks-evidence.v1"),
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
                "schema_version": "night-voyager.dra-live-recovery-evidence.v2",
                "head_sha": HEAD,
                "recovery_matrix_status": "passed",
            },
        ),
        authority_review_evidence_file=_write(
            tmp_path / "review.json",
            {
                "schema_version": ("night-voyager.dra-live-authority-review-evidence.v1"),
                "head_sha": HEAD,
                "authority_review_status": "CLEAN",
            },
        ),
    )


def _inventory_hashes(
    outputs: Mapping[tuple[str, ...], str] = INVENTORY_OUTPUTS,
) -> dict[str, str]:
    return {
        name: hashlib.sha256(
            _canonical_docker_inventory_bytes(
                _canonical_docker_inventory(name, outputs[command])
            )
        ).hexdigest()
        for name, command in DOCKER_COMMANDS_BY_NAME.items()
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
                "schema_version": "night-voyager.dra-live-docker-evidence.v3",
                "head_sha": HEAD,
                "task_project": TASK_PROJECT,
                "minimum_host_kib": 5_242_880,
                "minimum_docker_vm_kib": 8_388_608,
                "host_available_kib": 44_040_192,
                "docker_vm_available_kib": 12_582_912,
                "doctor_semantic_sha256": hashlib.sha256(
                    DOCTOR_SEMANTIC_OUTPUT.encode()
                ).hexdigest(),
                "before_inventory_sha256": inventory_hashes,
                "after_inventory_sha256": inventory_hashes,
                "retained_resources": retained,
            },
        ),
        hosted_check_evidence_file=_write(
            tmp_path / "checks.json",
            {
                "schema_version": ("night-voyager.dra-live-hosted-checks-evidence.v1"),
                "head_sha": HEAD,
                "repository": repository,
                "check_run_ids": {"python": 1, "frontend": 2, "compose": 3},
            },
        ),
        recovery_evidence_file=_write(
            tmp_path / "recovery.json",
            {
                "schema_version": "night-voyager.dra-live-recovery-evidence.v2",
                "head_sha": HEAD,
                "command": RECOVERY_COMMAND,
                "passed_count": 47,
            },
        ),
        authority_review_evidence_file=_write(
            tmp_path / "review.json",
            {
                "schema_version": ("night-voyager.dra-live-authority-review-evidence.v2"),
                "head_sha": HEAD,
                "repository": repository,
                "pull_request": 70,
                "reviewed_head_sha": REVIEWED_HEAD,
                "verdict": "CLEAN",
                "review_record_id": "independent-review-2026-07-25",
                "review_record_sha256": "d" * 64,
                "acknowledgement": "independent_authority_review_attested",
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
    recovery_output: str = "47 passed in 1.23s\n",
    recovery_stderr: str = "",
    inventory_outputs: Mapping[tuple[str, ...], str | tuple[str, str]] = INVENTORY_OUTPUTS,
    environments: list[dict[str, str] | None] | None = None,
):
    inventory_calls: dict[tuple[str, ...], int] = {}

    def run(command: tuple[str, ...], **kwargs: object) -> SimpleNamespace:
        normalized = tuple(command)
        calls.append(normalized)
        if environments is not None:
            environment = kwargs.get("env")
            environments.append(
                cast(dict[str, str], environment)
                if isinstance(environment, dict)
                else None
            )
        if normalized in inventory_outputs:
            configured = inventory_outputs[normalized]
            if isinstance(configured, tuple):
                index = min(inventory_calls.get(normalized, 0), 1)
                inventory_calls[normalized] = index + 1
                output = configured[index]
            else:
                output = configured
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
            output = recovery_output
        elif normalized[-1].endswith("/reviews"):
            output = "[]"
        elif "/reviews/" in normalized[-1]:
            raise AssertionError("GitHub review authority must not be queried")
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
        stderr = recovery_stderr if normalized == tuple(RECOVERY_COMMAND) else ""
        return SimpleNamespace(stdout=output, stderr=stderr)

    return run


def test_candidate_evidence_requires_all_exact_success_receipts(
    tmp_path: Path,
) -> None:
    args = _args(tmp_path)
    with pytest.raises(ValueError):
        _validated_candidate_evidence(args, HEAD)


def test_candidate_evidence_accepts_independent_review_when_github_reviews_empty(
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
    assert not any("/reviews" in item[-1] for item in calls)


def test_candidate_evidence_accepts_above_threshold_doctor_capacity_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = _valid_args(tmp_path)
    live_output = DOCTOR_OUTPUT.replace("44040192", "46006528").replace(
        "12582912", "18698240"
    )
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "scripts.verify_dra_live_closure.subprocess.run",
        _live_runner(calls, doctor_output=live_output),
    )

    assert all(_validated_candidate_evidence(args, HEAD))


def test_candidate_evidence_accepts_recovery_elapsed_time_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = _valid_args(tmp_path)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "scripts.verify_dra_live_closure.subprocess.run",
        _live_runner(calls, recovery_output="47 passed in 9.87s\n"),
    )

    assert all(_validated_candidate_evidence(args, HEAD))


def test_candidate_evidence_rejects_recovery_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = _valid_args(tmp_path)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "scripts.verify_dra_live_closure.subprocess.run",
        _live_runner(calls, recovery_stderr="WARNING: degraded recovery proof\n"),
    )

    with pytest.raises(ValueError, match="candidate_evidence_provenance_invalid"):
        _validated_candidate_evidence(args, HEAD)


@pytest.mark.parametrize(
    "legacy_schema",
    (
        "night-voyager.dra-live-docker-evidence.v1",
        "night-voyager.dra-live-docker-evidence.v2",
    ),
)
def test_candidate_evidence_rejects_legacy_docker_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    legacy_schema: str,
) -> None:
    args = _valid_args(tmp_path)
    docker = Path(args.docker_inventory_file)
    value = json.loads(docker.read_text(encoding="utf-8"))
    value["schema_version"] = legacy_schema
    raw_hashes = {
        name: hashlib.sha256(output.encode()).hexdigest()
        for name, output in zip(
            (
                "compose",
                "containers",
                "images",
                "build_cache",
                "networks",
                "volumes",
            ),
            INVENTORY_OUTPUTS.values(),
            strict=True,
        )
    }
    value["before_inventory_sha256"] = raw_hashes
    value["after_inventory_sha256"] = raw_hashes
    value["retained_resources"]["build_cache_sha256"] = raw_hashes["build_cache"]
    docker.write_text(json.dumps(value), encoding="utf-8")
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "scripts.verify_dra_live_closure.subprocess.run",
        _live_runner(calls),
    )

    with pytest.raises(ValueError, match="candidate_docker_evidence_invalid"):
        _validated_candidate_evidence(args, HEAD)


def test_candidate_evidence_rejects_legacy_recovery_evidence_before_subprocess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = _valid_args(tmp_path)
    recovery = Path(args.recovery_evidence_file)
    value = json.loads(recovery.read_text(encoding="utf-8"))
    value["schema_version"] = "night-voyager.dra-live-recovery-evidence.v1"
    recovery.write_text(json.dumps(value), encoding="utf-8")
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "scripts.verify_dra_live_closure.subprocess.run",
        _live_runner(calls),
    )

    with pytest.raises(ValueError, match="candidate_recovery_evidence_invalid"):
        _validated_candidate_evidence(args, HEAD)

    assert calls == []


def test_candidate_evidence_canonicalizes_inventory_presentation_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = _valid_args(tmp_path)
    image_command = next(
        command
        for command in INVENTORY_OUTPUTS
        if command[:3]
        == (
            "docker",
            "image",
            "ls",
        )
    )
    cache_command = ("docker", "buildx", "du", "--format", "json")
    volume_command = ("docker", "volume", "ls", "--format", "json")
    image_after = INVENTORY_OUTPUTS[image_command].replace(
        '"CreatedSince":"12 days ago"',
        '"CreatedSince":"13 days ago"',
    )
    cache_lines = INVENTORY_OUTPUTS[cache_command].splitlines()
    cache_after = (
        cache_lines[1].replace(
            '"LastUsedAt":"6 days ago"',
            '"LastUsedAt":"7 days ago"',
        )
        + "\n"
        + cache_lines[0]
        .replace(
            '"LastUsedAt":"7 days ago"',
            '"LastUsedAt":"8 days ago"',
        )
        .replace(
            '"Parents":["parent-b","parent-a"]',
            '"Parents":["parent-a","parent-b"]',
        )
        + "\n"
    )
    volume_after = INVENTORY_OUTPUTS[volume_command].replace(
        (
            '"Labels":"com.docker.compose.project=night-voyager,'
            'com.docker.compose.volume=postgres-data"'
        ),
        (
            '"Labels":"com.docker.compose.volume=postgres-data,'
            'com.docker.compose.project=night-voyager"'
        ),
    )
    observed: dict[tuple[str, ...], str | tuple[str, str]] = {
        **INVENTORY_OUTPUTS,
        image_command: (INVENTORY_OUTPUTS[image_command], image_after),
        cache_command: (INVENTORY_OUTPUTS[cache_command], cache_after),
        volume_command: (INVENTORY_OUTPUTS[volume_command], volume_after),
    }
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "scripts.verify_dra_live_closure.subprocess.run",
        _live_runner(calls, inventory_outputs=observed),
    )

    assert all(_validated_candidate_evidence(args, HEAD))


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


def test_candidate_evidence_removes_doctor_threshold_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = _valid_args(tmp_path)
    calls: list[tuple[str, ...]] = []
    environments: list[dict[str, str] | None] = []
    monkeypatch.setenv("NIGHT_VOYAGER_DOCKER_MINIMUM_KB", "1")
    monkeypatch.setattr(
        "scripts.verify_dra_live_closure.subprocess.run",
        _live_runner(calls, environments=environments),
    )

    assert all(_validated_candidate_evidence(args, HEAD))
    doctor_index = calls.index(("make", "doctor", "MODE=dev"))
    doctor_environment = environments[doctor_index]
    assert doctor_environment is not None
    assert "NIGHT_VOYAGER_DOCKER_MINIMUM_KB" not in doctor_environment


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
    ("mutation", "value"),
    (
        ("missing-record-id", None),
        ("malformed-record-hash", "not-a-sha256"),
        ("non-clean", "BLOCKED"),
        ("cross-head", "e" * 40),
        ("wrong-acknowledgement", "automated_check_completed"),
        ("extra-field", "self-asserted"),
    ),
)
def test_candidate_evidence_rejects_invalid_human_review_attestation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    value: object,
) -> None:
    args = _valid_args(tmp_path)
    review = Path(args.authority_review_evidence_file)
    review_value = json.loads(review.read_text(encoding="utf-8"))
    if mutation == "missing-record-id":
        review_value.pop("review_record_id")
    elif mutation == "malformed-record-hash":
        review_value["review_record_sha256"] = value
    elif mutation == "non-clean":
        review_value["verdict"] = value
    elif mutation == "cross-head":
        review_value["reviewed_head_sha"] = value
    elif mutation == "wrong-acknowledgement":
        review_value["acknowledgement"] = value
    else:
        review_value["unexpected"] = value
    review.write_text(json.dumps(review_value), encoding="utf-8")
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "scripts.verify_dra_live_closure.subprocess.run",
        _live_runner(calls),
    )

    with pytest.raises(ValueError, match=r"candidate_.*evidence"):
        _validated_candidate_evidence(args, HEAD)


@pytest.mark.parametrize(
    ("mutation", "observed"),
    (
        ("recorded-host-low", None),
        ("recorded-vm-low", None),
        ("live-host-low", None),
        ("live-vm-low", None),
        ("doctor-semantic-hash", None),
        ("docker-extra-field", None),
        ("wrong-project", None),
        (
            "residual-resource",
            {
                **INVENTORY_OUTPUTS,
                ("docker", "ps", "-a", "--no-trunc", "--format", "json"): (
                    '{"Command":"python","CreatedAt":"2026-07-26",'
                    f'"ID":"container-task","Image":"night-voyager-api",'
                    f'"Labels":"com.docker.compose.project={TASK_PROJECT}",'
                    f'"LocalVolumes":"0","Mounts":"","Names":"{TASK_PROJECT}-api-1",'
                    f'"Networks":"{TASK_PROJECT}_default","Ports":"",'
                    '"RunningFor":"1 minute","Size":"0B","State":"running",'
                    '"Status":"Up 1 minute"}\n'
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
    if mutation == "recorded-host-low":
        docker_value["host_available_kib"] = 5_242_879
    elif mutation == "recorded-vm-low":
        docker_value["docker_vm_available_kib"] = 8_388_607
    elif mutation == "live-host-low":
        doctor_output = DOCTOR_OUTPUT.replace("44040192", "5242879")
    elif mutation == "live-vm-low":
        doctor_output = DOCTOR_OUTPUT.replace("12582912", "8388607")
    elif mutation == "doctor-semantic-hash":
        docker_value["doctor_semantic_sha256"] = "f" * 64
    elif mutation == "docker-extra-field":
        docker_value["unexpected"] = "self-attested"
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

    expected_error = (
        "candidate_docker_evidence_invalid"
        if mutation == "docker-extra-field"
        else "candidate_evidence_provenance_invalid"
    )
    with pytest.raises(ValueError, match=expected_error):
        _validated_candidate_evidence(args, HEAD)


@pytest.mark.parametrize(
    "doctor_output",
    (
        DOCTOR_OUTPUT.replace("PASSED CHECK: Docker daemon and Compose --wait are available\n", ""),
        DOCTOR_OUTPUT.replace(
            "PASSED CHECK: contributor Python/uv/Node/npm toolchain is available",
            "PASSED CHECK: contributor toolchain is available",
        ),
        DOCTOR_OUTPUT.replace(
            "doctor: dev preflight passed\n",
            "PASSED CHECK: unexpected doctor extension\ndoctor: dev preflight passed\n",
        ),
        DOCTOR_OUTPUT.replace(
            "PASSED CHECK: host project filesystem 44040192 KiB available",
            "PASSED CHECK: host project filesystem unknown KiB available",
        ),
    ),
)
def test_candidate_evidence_rejects_doctor_contract_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    doctor_output: str,
) -> None:
    args = _valid_args(tmp_path)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "scripts.verify_dra_live_closure.subprocess.run",
        _live_runner(calls, doctor_output=doctor_output),
    )

    with pytest.raises(ValueError, match="candidate_evidence_provenance_invalid"):
        _validated_candidate_evidence(args, HEAD)


@pytest.mark.parametrize(
    ("evidence_count", "recovery_output"),
    (
        (47, "48 passed in 1.23s\n"),
        (47, "46 passed, 1 skipped in 1.23s\n"),
        (47, "46 passed, 1 xfailed in 1.23s\n"),
        (47, "46 passed, 1 warning in 1.23s\n"),
        (47, "1 failed, 46 passed in 1.23s\n"),
        (47, "47 passed\n"),
        (47, "arbitrary output\n47 passed in 1.23s\n"),
        (0, "47 passed in 1.23s\n"),
    ),
)
def test_candidate_evidence_rejects_recovery_result_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    evidence_count: int,
    recovery_output: str,
) -> None:
    args = _valid_args(tmp_path)
    recovery = Path(args.recovery_evidence_file)
    value = json.loads(recovery.read_text(encoding="utf-8"))
    value["passed_count"] = evidence_count
    recovery.write_text(json.dumps(value), encoding="utf-8")
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "scripts.verify_dra_live_closure.subprocess.run",
        _live_runner(calls, recovery_output=recovery_output),
    )

    with pytest.raises(ValueError, match="candidate_evidence_provenance_invalid"):
        _validated_candidate_evidence(args, HEAD)


def test_candidate_evidence_rejects_recovery_extra_field(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = _valid_args(tmp_path)
    recovery = Path(args.recovery_evidence_file)
    value = json.loads(recovery.read_text(encoding="utf-8"))
    value["stdout_sha256"] = "f" * 64
    recovery.write_text(json.dumps(value), encoding="utf-8")
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "scripts.verify_dra_live_closure.subprocess.run",
        _live_runner(calls),
    )

    with pytest.raises(ValueError, match="candidate_recovery_evidence_invalid"):
        _validated_candidate_evidence(args, HEAD)


@pytest.mark.parametrize(
    ("kind", "after"),
    (
        (
            "images",
            INVENTORY_OUTPUTS[
                (
                    "docker",
                    "image",
                    "ls",
                    "--digests",
                    "--no-trunc",
                    "--format",
                    "json",
                )
            ].replace('"Containers":"0"', '"Containers":"1"'),
        ),
        (
            "build_cache",
            INVENTORY_OUTPUTS[("docker", "buildx", "du", "--format", "json")].replace(
                '"Reclaimable":true', '"Reclaimable":false', 1
            ),
        ),
        (
            "volumes",
            INVENTORY_OUTPUTS[("docker", "volume", "ls", "--format", "json")].replace(
                '"Name":"night-voyager_postgres-data"',
                '"Name":"night-voyager-other-data"',
            ),
        ),
    ),
)
def test_candidate_evidence_rejects_semantic_inventory_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    after: str,
) -> None:
    args = _valid_args(tmp_path)
    command = dict(DOCKER_COMMANDS_BY_NAME)[kind]
    observed: dict[tuple[str, ...], str | tuple[str, str]] = {
        **INVENTORY_OUTPUTS,
        command: (INVENTORY_OUTPUTS[command], after),
    }
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "scripts.verify_dra_live_closure.subprocess.run",
        _live_runner(calls, inventory_outputs=observed),
    )

    with pytest.raises(ValueError, match="candidate_evidence_provenance_invalid"):
        _validated_candidate_evidence(args, HEAD)


@pytest.mark.parametrize(
    ("kind", "after"),
    (
        ("volumes", "not-json\n"),
        (
            "volumes",
            INVENTORY_OUTPUTS[("docker", "volume", "ls", "--format", "json")] * 2,
        ),
        (
            "build_cache",
            INVENTORY_OUTPUTS[("docker", "buildx", "du", "--format", "json")].replace(
                '"Parents":["parent-b","parent-a"]', '"Parents":"parent-a"'
            ),
        ),
    ),
)
def test_candidate_evidence_rejects_malformed_or_duplicate_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    after: str,
) -> None:
    args = _valid_args(tmp_path)
    command = dict(DOCKER_COMMANDS_BY_NAME)[kind]
    observed: dict[tuple[str, ...], str | tuple[str, str]] = {
        **INVENTORY_OUTPUTS,
        command: (INVENTORY_OUTPUTS[command], after),
    }
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "scripts.verify_dra_live_closure.subprocess.run",
        _live_runner(calls, inventory_outputs=observed),
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
