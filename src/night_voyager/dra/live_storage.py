from __future__ import annotations

import hashlib
import json
import os
import stat
import uuid
from pathlib import Path
from typing import Literal, Self, TypeVar

from pydantic import BaseModel, ConfigDict

from night_voyager.dra.live_models import (
    DraArtifactIdentityV1,
    DraReceiptIdentityV1,
)

ReceiptModel = TypeVar("ReceiptModel", bound=BaseModel)
ARTIFACT_NAME = "artifact.research-report.md"
RECEIPT_NAMES = frozenset(
    {
        "intent.json",
        "preflight.json",
        "reconciliation-required.json",
        "poll-recovery.json",
        "inspection-required.json",
        "capture.json",
        "failure.json",
        "cleanup.json",
    }
)
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)


class LiveStorageError(RuntimeError):
    pass


class LiveStorageInvalid(LiveStorageError):
    pass


class LiveStorageConflict(LiveStorageError):
    pass


class CleanupResultV1(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["removed", "absent", "retained", "failed"]
    artifact_present: bool


class StoredArtifactIdentityV1(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    byte_length: int
    sha256: str


class RecoveryBundleV1(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["night-voyager.dra-live-recovery.v1"] = (
        "night-voyager.dra-live-recovery.v1"
    )
    receipts: tuple[DraReceiptIdentityV1, ...]
    artifact: StoredArtifactIdentityV1 | None

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self)


def _canonical_bytes(model: BaseModel) -> bytes:
    return json.dumps(
        model.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _write_all(file_descriptor: int, content: bytes) -> None:
    offset = 0
    while offset < len(content):
        written = os.write(file_descriptor, content[offset:])
        if written <= 0:
            raise LiveStorageInvalid("write_incomplete")
        offset += written


class LiveReceiptStore:
    def __init__(self, root: Path, root_fd: int) -> None:
        self._root = root
        self._root_fd = root_fd
        self._closed = False

    @classmethod
    def open(cls, root: Path) -> Self:
        if _NOFOLLOW == 0 or _DIRECTORY == 0:
            raise LiveStorageInvalid("root_primitives_unavailable")
        try:
            root_fd = os.open(
                root,
                os.O_RDONLY | _DIRECTORY | _NOFOLLOW,
            )
        except OSError as error:
            raise LiveStorageInvalid("root_invalid") from error
        try:
            root_stat = os.fstat(root_fd)
            if (
                not stat.S_ISDIR(root_stat.st_mode)
                or root_stat.st_uid != os.getuid()
                or stat.S_IMODE(root_stat.st_mode) != 0o700
            ):
                raise LiveStorageInvalid("root_invalid")
        except BaseException:
            os.close(root_fd)
            raise
        return cls(root, root_fd)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if not self._closed:
            os.close(self._root_fd)
            self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise LiveStorageInvalid("store_closed")

    @staticmethod
    def _validate_receipt_name(logical_name: str) -> None:
        if logical_name not in RECEIPT_NAMES:
            raise LiveStorageInvalid("receipt_name_invalid")

    def _read_bytes(self, logical_name: str, *, receipt: bool) -> bytes:
        self._ensure_open()
        try:
            descriptor = os.open(
                logical_name,
                os.O_RDONLY | _NOFOLLOW,
                dir_fd=self._root_fd,
            )
        except OSError as error:
            code = "receipt_invalid" if receipt else "artifact_invalid"
            raise LiveStorageInvalid(code) from error
        try:
            metadata = os.fstat(descriptor)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) != 0o600
                or metadata.st_size < 1
                or metadata.st_size > 1_048_576
            ):
                code = "receipt_invalid" if receipt else "artifact_invalid"
                raise LiveStorageInvalid(code)
            chunks: list[bytes] = []
            remaining = metadata.st_size
            while remaining:
                chunk = os.read(descriptor, min(remaining, 65_536))
                if not chunk:
                    code = "receipt_invalid" if receipt else "artifact_invalid"
                    raise LiveStorageInvalid(code)
                chunks.append(chunk)
                remaining -= len(chunk)
            if os.read(descriptor, 1):
                code = "receipt_invalid" if receipt else "artifact_invalid"
                raise LiveStorageInvalid(code)
            return b"".join(chunks)
        finally:
            os.close(descriptor)

    def _publish_bytes(
        self,
        logical_name: str,
        content: bytes,
        *,
        conflict_code: str,
    ) -> DraReceiptIdentityV1:
        self._ensure_open()
        if not content or len(content) > 1_048_576:
            raise LiveStorageInvalid("content_length_invalid")
        temporary_name = f".tmp-{os.getpid()}-{uuid.uuid4().hex}"
        descriptor = -1
        try:
            descriptor = os.open(
                temporary_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW,
                0o600,
                dir_fd=self._root_fd,
            )
            os.fchmod(descriptor, 0o600)
            _write_all(descriptor, content)
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            try:
                os.link(
                    temporary_name,
                    logical_name,
                    src_dir_fd=self._root_fd,
                    dst_dir_fd=self._root_fd,
                    follow_symlinks=False,
                )
                os.fsync(self._root_fd)
            except FileExistsError:
                existing = self._read_bytes(
                    logical_name,
                    receipt=logical_name != ARTIFACT_NAME,
                )
                if existing != content:
                    raise LiveStorageConflict(conflict_code) from None
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                os.unlink(temporary_name, dir_fd=self._root_fd)
                os.fsync(self._root_fd)
            except FileNotFoundError:
                pass
        return DraReceiptIdentityV1(
            logical_name=logical_name,
            byte_length=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )

    def write_receipt(
        self, logical_name: str, model: BaseModel
    ) -> DraReceiptIdentityV1:
        self._validate_receipt_name(logical_name)
        return self._publish_bytes(
            logical_name,
            _canonical_bytes(model),
            conflict_code="receipt_conflict",
        )

    def read_receipt(
        self,
        logical_name: str,
        model_type: type[ReceiptModel],
    ) -> ReceiptModel:
        self._validate_receipt_name(logical_name)
        try:
            return model_type.model_validate_json(
                self._read_bytes(logical_name, receipt=True)
            )
        except LiveStorageInvalid:
            raise
        except Exception as error:
            raise LiveStorageInvalid("receipt_invalid") from error

    def write_artifact_for_inspection(
        self,
        identity: DraArtifactIdentityV1,
        content: bytes,
    ) -> Path:
        if (
            len(content) != identity.byte_length
            or hashlib.sha256(content).hexdigest() != identity.sha256
        ):
            raise LiveStorageInvalid("artifact_hash_invalid")
        self._publish_bytes(
            ARTIFACT_NAME,
            content,
            conflict_code="artifact_conflict",
        )
        return self._root / ARTIFACT_NAME

    def artifact_path(self) -> Path | None:
        try:
            self._read_bytes(ARTIFACT_NAME, receipt=False)
        except LiveStorageInvalid:
            return None
        return self._root / ARTIFACT_NAME

    def read_artifact(self, identity: DraArtifactIdentityV1) -> bytes:
        content = self._read_bytes(ARTIFACT_NAME, receipt=False)
        if (
            len(content) != identity.byte_length
            or hashlib.sha256(content).hexdigest() != identity.sha256
        ):
            raise LiveStorageInvalid("artifact_hash_invalid")
        return content

    def delete_artifact(self) -> CleanupResultV1:
        self._ensure_open()
        try:
            metadata = os.stat(
                ARTIFACT_NAME,
                dir_fd=self._root_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return CleanupResultV1(status="absent", artifact_present=False)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) != 0o600
        ):
            return CleanupResultV1(status="failed", artifact_present=True)
        try:
            os.unlink(ARTIFACT_NAME, dir_fd=self._root_fd)
            os.fsync(self._root_fd)
        except OSError:
            return CleanupResultV1(status="failed", artifact_present=True)
        return CleanupResultV1(status="removed", artifact_present=False)

    def verify_recovery_bundle(self) -> RecoveryBundleV1:
        self._ensure_open()
        try:
            names = set(os.listdir(self._root_fd))
        except OSError as error:
            raise LiveStorageInvalid("residue_invalid") from error
        if not names.issubset(RECEIPT_NAMES | {ARTIFACT_NAME}):
            raise LiveStorageInvalid("residue_invalid")
        receipts: list[DraReceiptIdentityV1] = []
        for name in sorted(names & RECEIPT_NAMES):
            raw = self._read_bytes(name, receipt=True)
            try:
                payload = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise LiveStorageInvalid("receipt_invalid") from error
            if not isinstance(payload, dict):
                raise LiveStorageInvalid("receipt_invalid")
            receipts.append(
                DraReceiptIdentityV1(
                    logical_name=name,
                    byte_length=len(raw),
                    sha256=hashlib.sha256(raw).hexdigest(),
                )
            )
        artifact = None
        if ARTIFACT_NAME in names:
            raw_artifact = self._read_bytes(ARTIFACT_NAME, receipt=False)
            artifact = StoredArtifactIdentityV1(
                byte_length=len(raw_artifact),
                sha256=hashlib.sha256(raw_artifact).hexdigest(),
            )
        return RecoveryBundleV1(
            receipts=tuple(receipts),
            artifact=artifact,
        )
