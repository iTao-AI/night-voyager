from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

POST_REVEAL_ALLOWLIST = (
    "tests/fixtures/evidence_loop/holdout-dataset-v1.json",
    "tests/fixtures/evidence_loop/mke-capture-v2.json",
    "tests/fixtures/evidence_loop/slice0-receipt-v2.json",
)

_ROLES = (
    "independent-dataset-author-v3",
    "night-voyager-slice0-evaluator-v1",
    "independent-holdout-custodian-v3",
)


@dataclass(frozen=True)
class PublicCommitmentValidation:
    author_revision: int
    roles: tuple[str, str, str]
    source_digests: tuple[str, ...]
    holdout_content_reachable: bool


def _load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must be a JSON object")
    return value


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_public_commitments(root: Path) -> PublicCommitmentValidation:
    manifest = _load_object(root / "holdout-manifest-v1.json")
    fragment = _load_object(root / "source-manifest-fragment-v1.json")
    roles = (
        manifest.get("dataset_author_id"),
        manifest.get("evaluator_id"),
        manifest.get("proposed_holdout_custodian_id"),
    )
    if manifest.get("author_revision") != 3 or roles != _ROLES:
        raise ValueError("revision three role identity mismatch")
    if manifest.get("rejected_pre_admission_revisions") != [
        {"author_revision": 1, "status": "rejected_pre_admission"},
        {"author_revision": 2, "status": "rejected_pre_admission"},
    ]:
        raise ValueError("rejected revision identity mismatch")
    if (
        manifest.get("holdout_content_included") is not False
        or manifest.get("oracle_content_included") is not False
    ):
        raise ValueError("holdout content must remain unreachable")

    sources = fragment.get("sources")
    if not isinstance(sources, list) or len(sources) != 4:
        raise ValueError("source identity mismatch")
    digests: list[str] = []
    identities: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("source identity mismatch")
        relative = source.get("relative_path")
        if not isinstance(relative, str):
            raise ValueError("source identity mismatch")
        posix = PurePosixPath(relative)
        if posix.is_absolute() or ".." in posix.parts:
            raise ValueError("source identity mismatch")
        path = root.joinpath(*posix.parts)
        digest = _digest(path)
        if (
            source.get("media_type") != "application/pdf"
            or path.stat().st_size != source.get("byte_length")
            or digest != source.get("content_sha256")
        ):
            raise ValueError("source identity mismatch")
        identity = source.get("evaluation_canonical_source_id")
        if not isinstance(identity, str) or identity in identities:
            raise ValueError("source identity mismatch")
        identities.add(identity)
        digests.append(digest)
    return PublicCommitmentValidation(
        author_revision=3,
        roles=_ROLES,
        source_digests=tuple(digests),
        holdout_content_reachable=False,
    )
