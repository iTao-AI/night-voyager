from __future__ import annotations

import json
import multiprocessing
import os
from pathlib import Path

import pytest

from night_voyager.dra.fixtures import (
    build_v0_1_6_scenario_candidate_import,
    load_live_closure_scenario,
)
from night_voyager.dra.live_models import DraReceiptIdentityV1
from night_voyager.dra.live_storage import (
    LiveReceiptStore,
    LiveStorageConflict,
    LiveStorageInvalid,
)


def private_root(tmp_path: Path, name: str = "receipts") -> Path:
    root = tmp_path / name
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    return root


def receipt(value: str = "a" * 64) -> DraReceiptIdentityV1:
    return DraReceiptIdentityV1(
        logical_name="intent.json",
        byte_length=64,
        sha256=value,
    )


def race_writer(root: str, value: str, queue: multiprocessing.Queue[str]) -> None:
    try:
        with LiveReceiptStore.open(Path(root)) as store:
            store.write_receipt("intent.json", receipt(value))
        queue.put("ok")
    except LiveStorageConflict:
        queue.put("conflict")


def test_root_must_be_private_owned_directory(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    with pytest.raises(LiveStorageInvalid, match="root_invalid"):
        LiveReceiptStore.open(missing)

    public = private_root(tmp_path, "public")
    public.chmod(0o755)
    with pytest.raises(LiveStorageInvalid, match="root_invalid"):
        LiveReceiptStore.open(public)

    target = private_root(tmp_path, "target")
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(LiveStorageInvalid, match="root_invalid"):
        LiveReceiptStore.open(link)


def test_receipt_write_is_atomic_private_and_create_once(tmp_path: Path) -> None:
    root = private_root(tmp_path)
    with LiveReceiptStore.open(root) as store:
        first = store.write_receipt("intent.json", receipt())
        replay = store.write_receipt("intent.json", receipt())
        assert first == replay
        assert (root / "intent.json").stat().st_mode & 0o777 == 0o600
        assert store.read_receipt("intent.json", DraReceiptIdentityV1) == receipt()
        with pytest.raises(LiveStorageConflict, match="receipt_conflict"):
            store.write_receipt("intent.json", receipt("b" * 64))
    assert not list(root.glob(".tmp-*"))


@pytest.mark.parametrize(
    "name",
    ("../intent.json", "nested/intent.json", "/tmp/intent.json", "unknown.json"),
)
def test_receipt_names_are_closed_and_traversal_free(
    tmp_path: Path, name: str
) -> None:
    with (
        LiveReceiptStore.open(private_root(tmp_path)) as store,
        pytest.raises(LiveStorageInvalid, match="receipt_name_invalid"),
    ):
        store.write_receipt(name, receipt())


def test_artifact_is_exact_private_and_persists_until_explicit_cleanup(
    tmp_path: Path,
) -> None:
    root = private_root(tmp_path)
    scenario = load_live_closure_scenario()
    artifact = build_v0_1_6_scenario_candidate_import().artifact
    with LiveReceiptStore.open(root) as store:
        path = store.write_artifact_for_inspection(
            scenario.result.artifact, artifact.content.encode("utf-8")
        )
        assert path.read_bytes() == artifact.content.encode("utf-8")
        assert path.stat().st_mode & 0o777 == 0o600
        assert store.artifact_path() == path
        cleanup = store.delete_artifact()
        assert cleanup.status == "removed"
        assert not path.exists()
        assert store.delete_artifact().status == "absent"

        with pytest.raises(LiveStorageInvalid, match="artifact_hash_invalid"):
            store.write_artifact_for_inspection(
                scenario.result.artifact, b"forged"
            )


def test_root_descriptor_survives_path_rename_without_escape(tmp_path: Path) -> None:
    root = private_root(tmp_path)
    moved = tmp_path / "moved"
    with LiveReceiptStore.open(root) as store:
        root.rename(moved)
        replacement = private_root(tmp_path)
        store.write_receipt("intent.json", receipt())
        assert (moved / "intent.json").exists()
        assert not (replacement / "intent.json").exists()


def test_operator_artifact_path_fails_closed_after_root_path_replacement(
    tmp_path: Path,
) -> None:
    root = private_root(tmp_path)
    moved = tmp_path / "moved"
    scenario = load_live_closure_scenario()
    artifact = build_v0_1_6_scenario_candidate_import().artifact
    attacker_bytes = b"attacker-controlled replacement"
    with LiveReceiptStore.open(root) as store:
        root.rename(moved)
        replacement = private_root(tmp_path)
        replacement_artifact = replacement / "artifact.research-report.md"
        replacement_artifact.write_bytes(attacker_bytes)
        replacement_artifact.chmod(0o600)

        with pytest.raises(LiveStorageInvalid, match="artifact_path_invalid"):
            store.write_artifact_for_inspection(
                scenario.result.artifact, artifact.content.encode("utf-8")
            )

        assert store.read_artifact(scenario.result.artifact) == (
            artifact.content.encode("utf-8")
        )
        assert replacement_artifact.read_bytes() == attacker_bytes


def test_symlink_swap_and_malformed_json_fail_closed(tmp_path: Path) -> None:
    root = private_root(tmp_path)
    outside = tmp_path / "outside"
    outside.write_text(receipt().model_dump_json(), encoding="utf-8")
    (root / "intent.json").symlink_to(outside)
    with (
        LiveReceiptStore.open(root) as store,
        pytest.raises(LiveStorageInvalid, match="receipt_invalid"),
    ):
        store.read_receipt("intent.json", DraReceiptIdentityV1)

    (root / "intent.json").unlink()
    (root / "intent.json").write_text("{", encoding="utf-8")
    (root / "intent.json").chmod(0o600)
    with (
        LiveReceiptStore.open(root) as store,
        pytest.raises(LiveStorageInvalid, match="receipt_invalid"),
    ):
        store.read_receipt("intent.json", DraReceiptIdentityV1)


def test_recovery_bundle_is_content_free_and_rejects_unknown_residue(
    tmp_path: Path,
) -> None:
    root = private_root(tmp_path)
    with LiveReceiptStore.open(root) as store:
        store.write_receipt("intent.json", receipt())
        bundle = store.verify_recovery_bundle()
        encoded = bundle.model_dump_json()
        assert bundle.receipts[0].logical_name == "intent.json"
        for forbidden in (
            "content",
            "body",
            "prompt",
            "header",
            "environment",
            str(root),
        ):
            assert forbidden not in encoded

    (root / "unexpected.bin").write_bytes(b"x")
    with (
        LiveReceiptStore.open(root) as store,
        pytest.raises(LiveStorageInvalid, match="residue_invalid"),
    ):
        store.verify_recovery_bundle()


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX dir-fd CAS")
def test_two_process_same_and_different_receipt_races(tmp_path: Path) -> None:
    root = private_root(tmp_path)
    context = multiprocessing.get_context("fork")
    queue: multiprocessing.Queue[str] = context.Queue()
    same = [
        context.Process(target=race_writer, args=(str(root), "a" * 64, queue))
        for _ in range(2)
    ]
    for process in same:
        process.start()
    for process in same:
        process.join(timeout=10)
        assert process.exitcode == 0
    assert sorted(queue.get(timeout=1) for _ in same) == ["ok", "ok"]

    (root / "intent.json").unlink()
    different = [
        context.Process(target=race_writer, args=(str(root), value, queue))
        for value in ("a" * 64, "b" * 64)
    ]
    for process in different:
        process.start()
    for process in different:
        process.join(timeout=10)
        assert process.exitcode == 0
    assert sorted(queue.get(timeout=1) for _ in different) == [
        "conflict",
        "ok",
    ]


def test_recovery_bundle_bytes_are_canonical(tmp_path: Path) -> None:
    root = private_root(tmp_path)
    with LiveReceiptStore.open(root) as store:
        store.write_receipt("intent.json", receipt())
        bundle = store.verify_recovery_bundle()
    payload = json.loads(bundle.canonical_bytes())
    assert payload["schema_version"] == "night-voyager.dra-live-recovery.v1"
