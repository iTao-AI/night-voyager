"""Pre-install identity verification for the reviewed MKE candidate artifact."""

from __future__ import annotations

import hashlib
import json
import os
import re
import zipfile
from dataclasses import dataclass
from datetime import date
from email.parser import BytesParser
from pathlib import Path
from typing import Annotated, Literal

from packaging.specifiers import SpecifierSet
from packaging.version import Version
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator, model_validator

from night_voyager.evidence.mke_models import MkeConsumerError

SHA256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
COMMIT = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
WHEEL_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+\.whl$")


def canonical_sha256(value: dict[str, object]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class CandidateArtifactReceiptV1(StrictModel):
    schema_version: Literal["mke.candidate_artifact_receipt.v1"]
    repository: Literal["iTao-AI/multimodal-knowledge-engine"]
    source_commit: COMMIT
    package_name: Literal["multimodal-knowledge-engine"]
    package_version: str
    wheel_filename: str
    wheel_bytes: PositiveInt
    wheel_sha256: SHA256
    requires_python: str
    consumer_proof_schema: Literal["mke.consumer_source_pack_proof.v1"]
    consumer_proof_status: Literal["passed"]
    proof_input_wheel_sha256: SHA256
    receipt_sha256: SHA256

    @field_validator("wheel_filename")
    @classmethod
    def safe_wheel_filename(cls, value: str) -> str:
        if Path(value).name != value or not WHEEL_PATTERN.fullmatch(value):
            raise ValueError("wheel filename must be a safe basename")
        return value

    @model_validator(mode="after")
    def validate_receipt_identity(self) -> CandidateArtifactReceiptV1:
        if self.wheel_sha256 != self.proof_input_wheel_sha256:
            raise ValueError("proof input must be the candidate wheel")
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if self.receipt_sha256 != canonical_sha256(payload):
            raise ValueError("receipt canonical SHA-256 mismatch")
        return self


class CandidateArtifactLockV1(StrictModel):
    schema_version: Literal["night_voyager.mke_candidate_artifact_lock.v1"]
    repository: Literal["iTao-AI/multimodal-knowledge-engine"]
    source_commit: COMMIT
    package_name: Literal["multimodal-knowledge-engine"]
    package_version: str
    wheel_filename: str
    wheel_bytes: PositiveInt
    wheel_sha256: SHA256
    requires_python: str
    consumer_proof_schema: Literal["mke.consumer_source_pack_proof.v1"]
    consumer_proof_status: Literal["passed"]
    proof_input_wheel_sha256: SHA256
    receipt_sha256: SHA256
    artifact_locator: str
    reviewed_at: date

    _safe_wheel_filename = field_validator("wheel_filename")(
        CandidateArtifactReceiptV1.safe_wheel_filename.__func__
    )

    @field_validator("artifact_locator")
    @classmethod
    def validate_locator(cls, value: str) -> str:
        if value != "operator_supplied" and not value.startswith("https://"):
            raise ValueError("artifact locator must be operator_supplied or HTTPS")
        return value

    @model_validator(mode="after")
    def validate_lock_identity(self) -> CandidateArtifactLockV1:
        if self.wheel_sha256 != self.proof_input_wheel_sha256:
            raise ValueError("proof input must be the candidate wheel")
        return self


@dataclass(frozen=True)
class VerifiedCandidateArtifact:
    wheel: Path
    receipt: Path
    package_version: str
    wheel_bytes: int
    wheel_sha256: str
    receipt_sha256: str
    source_commit: str


def _load_receipt(path: Path) -> CandidateArtifactReceiptV1:
    try:
        return CandidateArtifactReceiptV1.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise MkeConsumerError("mke_candidate_mismatch") from error


def _load_lock(path: Path) -> CandidateArtifactLockV1:
    try:
        return CandidateArtifactLockV1.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise MkeConsumerError("mke_candidate_mismatch") from error


def _inspect_wheel(wheel: Path, receipt: CandidateArtifactReceiptV1) -> None:
    try:
        with zipfile.ZipFile(wheel) as archive:
            metadata_names = [
                name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
            ]
            entry_names = [
                name for name in archive.namelist() if name.endswith(".dist-info/entry_points.txt")
            ]
            if len(metadata_names) != 1 or len(entry_names) != 1:
                raise ValueError("wheel metadata inventory mismatch")
            metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
            entry_points = archive.read(entry_names[0]).decode("utf-8")
    except (OSError, UnicodeError, zipfile.BadZipFile, ValueError) as error:
        raise MkeConsumerError("mke_candidate_mismatch") from error
    if (
        metadata["Name"] != receipt.package_name
        or metadata["Version"] != receipt.package_version
        or SpecifierSet(metadata["Requires-Python"]) != SpecifierSet(receipt.requires_python)
        or "mke = mke.cli:console_main" not in entry_points.splitlines()
        or Version("3.12") not in SpecifierSet(receipt.requires_python)
    ):
        raise MkeConsumerError("mke_candidate_mismatch")


def lock_from_receipt(
    receipt: CandidateArtifactReceiptV1,
    *,
    artifact_locator: str,
    reviewed_at: date,
) -> CandidateArtifactLockV1:
    return CandidateArtifactLockV1(
        schema_version="night_voyager.mke_candidate_artifact_lock.v1",
        **receipt.model_dump(exclude={"schema_version"}),
        artifact_locator=artifact_locator,
        reviewed_at=reviewed_at,
    )


def build_candidate_lock(
    wheel: Path,
    receipt_path: Path,
    *,
    artifact_locator: str,
    reviewed_at: date,
) -> CandidateArtifactLockV1:
    if not wheel.is_file() or not receipt_path.is_file():
        raise MkeConsumerError("mke_candidate_inputs_missing")
    receipt = _load_receipt(receipt_path)
    try:
        wheel_bytes = wheel.stat().st_size
        wheel_sha256 = hashlib.sha256(wheel.read_bytes()).hexdigest()
    except OSError as error:
        raise MkeConsumerError("mke_candidate_mismatch") from error
    if (
        wheel.name != receipt.wheel_filename
        or wheel_bytes != receipt.wheel_bytes
        or wheel_sha256 != receipt.wheel_sha256
    ):
        raise MkeConsumerError("mke_candidate_mismatch")
    _inspect_wheel(wheel, receipt)
    return lock_from_receipt(
        receipt, artifact_locator=artifact_locator, reviewed_at=reviewed_at
    )


def verify_candidate_artifact(
    wheel: Path,
    receipt_path: Path,
    lock_path: Path,
) -> VerifiedCandidateArtifact:
    if not wheel.is_file() or not receipt_path.is_file() or not lock_path.is_file():
        raise MkeConsumerError("mke_candidate_inputs_missing")
    receipt = _load_receipt(receipt_path)
    lock = _load_lock(lock_path)
    try:
        wheel_bytes = wheel.stat().st_size
        wheel_sha256 = hashlib.sha256(wheel.read_bytes()).hexdigest()
    except OSError as error:
        raise MkeConsumerError("mke_candidate_mismatch") from error
    receipt_identity = receipt.model_dump(exclude={"schema_version"})
    lock_identity = lock.model_dump(exclude={"schema_version", "artifact_locator", "reviewed_at"})
    if (
        wheel.name != receipt.wheel_filename
        or wheel_bytes != receipt.wheel_bytes
        or wheel_sha256 != receipt.wheel_sha256
        or receipt_identity != lock_identity
    ):
        raise MkeConsumerError("mke_candidate_mismatch")
    _inspect_wheel(wheel, receipt)
    return VerifiedCandidateArtifact(
        wheel=wheel.resolve(),
        receipt=receipt_path.resolve(),
        package_version=receipt.package_version,
        wheel_bytes=wheel_bytes,
        wheel_sha256=wheel_sha256,
        receipt_sha256=receipt.receipt_sha256,
        source_commit=receipt.source_commit,
    )


def stage_candidate_artifact(
    wheel: Path,
    receipt_path: Path,
    lock_path: Path,
    owned_directory: Path,
) -> VerifiedCandidateArtifact:
    """Copy candidate bytes into controller-owned storage and verify only that copy."""
    if not wheel.is_file() or not receipt_path.is_file() or not lock_path.is_file():
        raise MkeConsumerError("mke_candidate_inputs_missing")
    lock = _load_lock(lock_path)
    if wheel.name != lock.wheel_filename:
        raise MkeConsumerError("mke_candidate_mismatch")
    destination = owned_directory / lock.wheel_filename
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        owned_directory.mkdir(mode=0o700)
        with wheel.open("rb") as source:
            descriptor = os.open(destination, flags, 0o400)
            with os.fdopen(descriptor, "wb") as target:
                remaining = lock.wheel_bytes + 1
                while remaining:
                    chunk = source.read(min(1_048_576, remaining))
                    if not chunk:
                        break
                    target.write(chunk)
                    remaining -= len(chunk)
                target.flush()
                os.fsync(target.fileno())
    except OSError as error:
        raise MkeConsumerError("mke_candidate_mismatch") from error
    return verify_candidate_artifact(destination, receipt_path, lock_path)
