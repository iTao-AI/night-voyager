from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path
from types import TracebackType
from typing import IO, Any, cast

import pytest
from pydantic import ValidationError

from night_voyager.evidence.candidate_lock import (
    CandidateArtifactLockV1,
    CandidateArtifactReceiptV1,
    canonical_sha256,
    lock_from_receipt,
    stage_candidate_artifact,
    verify_candidate_artifact,
)
from night_voyager.evidence.mke_models import MkeConsumerError

REPOSITORY = Path(__file__).parents[2]
FIXTURES = REPOSITORY / "fixtures" / "m4b"
EXPECTED_TEXT = "Synthetic Australia program fit requires advisor evidence review."


def synthetic_candidate(tmp_path: Path) -> tuple[Path, Path, Path]:
    wheel = tmp_path / "multimodal_knowledge_engine-0.1.1-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            "multimodal_knowledge_engine-0.1.1.dist-info/METADATA",
            "Metadata-Version: 2.4\nName: multimodal-knowledge-engine\nVersion: 0.1.1\n"
            "Requires-Python: >=3.12,<3.14\n",
        )
        archive.writestr(
            "multimodal_knowledge_engine-0.1.1.dist-info/entry_points.txt",
            "[console_scripts]\nmke = mke.cli:console_main\n",
        )
    wheel_sha256 = hashlib.sha256(wheel.read_bytes()).hexdigest()
    receipt_payload: dict[str, object] = {
        "schema_version": "mke.candidate_artifact_receipt.v1",
        "repository": "iTao-AI/multimodal-knowledge-engine",
        "source_commit": "1" * 40,
        "package_name": "multimodal-knowledge-engine",
        "package_version": "0.1.1",
        "wheel_filename": wheel.name,
        "wheel_bytes": wheel.stat().st_size,
        "wheel_sha256": wheel_sha256,
        "requires_python": ">=3.12,<3.14",
        "consumer_proof_schema": "mke.consumer_source_pack_proof.v1",
        "consumer_proof_status": "passed",
        "proof_input_wheel_sha256": wheel_sha256,
    }
    receipt_payload["receipt_sha256"] = canonical_sha256(receipt_payload)
    receipt = CandidateArtifactReceiptV1.model_validate(receipt_payload)
    receipt_path = tmp_path / "candidate-artifact-receipt.json"
    receipt_path.write_text(receipt.model_dump_json(), encoding="utf-8")
    lock = lock_from_receipt(
        receipt, artifact_locator="operator_supplied", reviewed_at=date(2026, 7, 14)
    )
    lock_path = tmp_path / "candidate-artifact-lock.json"
    lock_path.write_text(lock.model_dump_json(), encoding="utf-8")
    return wheel, receipt_path, lock_path


def test_checked_in_lock_is_strict_and_records_reviewed_candidate() -> None:
    lock = CandidateArtifactLockV1.model_validate_json(
        (FIXTURES / "candidate-artifact-lock.json").read_text(encoding="utf-8")
    )
    assert lock.source_commit == "16fae017ced5fe67da3fae4a01f26e9e9f1084aa"
    assert lock.wheel_bytes == 250284
    assert lock.wheel_sha256 == "616549f172fba2482f82b450452b134de541d172384883282de26f6178e362b2"
    assert lock.receipt_sha256 == "a8f73318c2b14eeaa0bc8e27890c1f15e232b92d50019602f28ec9fbbb659e54"
    assert lock.artifact_locator == "operator_supplied"
    assert lock.reviewed_at.isoformat() == "2026-07-14"

    payload = json.loads((FIXTURES / "candidate-artifact-lock.json").read_text())
    payload["unexpected"] = True
    with pytest.raises(ValidationError):
        CandidateArtifactLockV1.model_validate(payload)


def test_receipt_rejects_bad_hashes_unsafe_filename_and_self_hash(tmp_path: Path) -> None:
    _, receipt_path, _ = synthetic_candidate(tmp_path)
    payload = json.loads(receipt_path.read_text())
    assert len(CandidateArtifactReceiptV1.model_validate(payload).receipt_sha256) == 64

    for field, value in (
        ("wheel_sha256", "x" * 64),
        ("proof_input_wheel_sha256", "f" * 64),
        ("receipt_sha256", "0" * 64),
        ("wheel_filename", "../candidate.whl"),
    ):
        changed = {**payload, field: value}
        with pytest.raises(ValidationError):
            CandidateArtifactReceiptV1.model_validate(changed)


def test_candidate_is_verified_before_install(tmp_path: Path) -> None:
    wheel, receipt, lock = synthetic_candidate(tmp_path)
    verified = verify_candidate_artifact(
        wheel,
        receipt,
        lock,
    )
    assert verified.wheel_sha256 == hashlib.sha256(wheel.read_bytes()).hexdigest()
    assert verified.package_version == "0.1.1"


def test_candidate_mismatch_is_rejected_before_any_install(tmp_path: Path) -> None:
    wheel, receipt, lock = synthetic_candidate(tmp_path)
    changed = tmp_path / "candidate.whl"
    changed.write_bytes(wheel.read_bytes() + b"changed")
    with pytest.raises(MkeConsumerError) as captured:
        verify_candidate_artifact(
            changed,
            receipt,
            lock,
        )
    assert captured.value.failure.code == "mke_candidate_mismatch"


def test_staged_candidate_is_immune_to_source_symlink_rename_during_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wheel, receipt, lock = synthetic_candidate(tmp_path)
    expected_sha256 = hashlib.sha256(wheel.read_bytes()).hexdigest()
    original = tmp_path / "original-wheel-bytes"
    wheel.rename(original)
    replacement = tmp_path / "replacement-wheel-bytes"
    replacement.write_bytes(b"replacement")
    wheel.symlink_to(original)
    real_open = Path.open

    class RenameOnRead:
        def __init__(self, handle: IO[bytes]) -> None:
            self.handle = handle
            self.changed = False

        def __enter__(self) -> RenameOnRead:
            return self

        def __exit__(
            self,
            error_type: type[BaseException] | None,
            error: BaseException | None,
            traceback: TracebackType | None,
        ) -> bool | None:
            return self.handle.__exit__(error_type, error, traceback)

        def read(self, size: int = -1) -> bytes:
            if not self.changed:
                wheel.unlink()
                wheel.symlink_to(replacement)
                self.changed = True
            return self.handle.read(size)

    def racing_open(path: Path, *args: Any, **kwargs: Any) -> Any:
        handle = cast(IO[bytes], real_open(path, *args, **kwargs))
        return RenameOnRead(handle) if path == wheel else handle

    monkeypatch.setattr(Path, "open", racing_open)
    staged = stage_candidate_artifact(wheel, receipt, lock, tmp_path / "owned")

    assert staged.wheel.parent == tmp_path / "owned"
    assert hashlib.sha256(staged.wheel.read_bytes()).hexdigest() == expected_sha256
    assert hashlib.sha256(wheel.read_bytes()).hexdigest() != staged.wheel_sha256


def test_staged_candidate_rejects_in_place_mutation_during_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wheel, receipt, lock = synthetic_candidate(tmp_path)
    real_open = Path.open

    class MutateOnRead:
        def __init__(self, handle: IO[bytes]) -> None:
            self.handle = handle
            self.changed = False

        def __enter__(self) -> MutateOnRead:
            return self

        def __exit__(
            self,
            error_type: type[BaseException] | None,
            error: BaseException | None,
            traceback: TracebackType | None,
        ) -> bool | None:
            return self.handle.__exit__(error_type, error, traceback)

        def read(self, size: int = -1) -> bytes:
            if not self.changed:
                wheel.write_bytes(b"mutated during copy")
                self.changed = True
            return self.handle.read(size)

    def racing_open(path: Path, *args: Any, **kwargs: Any) -> Any:
        handle = cast(IO[bytes], real_open(path, *args, **kwargs))
        mode = args[0] if args else kwargs.get("mode", "r")
        return MutateOnRead(handle) if path == wheel and mode == "rb" else handle

    monkeypatch.setattr(Path, "open", racing_open)
    with pytest.raises(MkeConsumerError) as captured:
        stage_candidate_artifact(wheel, receipt, lock, tmp_path / "owned")

    assert captured.value.failure.code == "mke_candidate_mismatch"


def test_pdf_generator_is_byte_stable_and_matches_manifest(tmp_path: Path) -> None:
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    for output in (first, second):
        subprocess.run(
            [sys.executable, "scripts/generate_m4b_fixture.py", "--output", str(output)],
            cwd=REPOSITORY,
            check=True,
        )
    assert first.read_bytes() == second.read_bytes()
    pdf_bytes = first.read_bytes()
    assert b"/Count 1" in pdf_bytes
    assert EXPECTED_TEXT.encode("ascii") in pdf_bytes
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    source = manifest["sources"][0]
    assert source["sha256"] == hashlib.sha256(first.read_bytes()).hexdigest()
    assert (FIXTURES / source["path"]).read_bytes() == first.read_bytes()


def test_smoke_assertions_are_test_only_and_exact() -> None:
    assertions = json.loads((FIXTURES / "smoke-assertions.json").read_text())
    assert set(assertions) == {"schema_version", "positive", "no_match"}
    assert assertions["positive"]["expected_status"] == "manifest_mapped"
    assert assertions["no_match"]["expected_status"] == "proof_pack_no_match"
    manifest_text = (FIXTURES / "manifest.json").read_text()
    assert assertions["no_match"]["query"] not in manifest_text
