from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_RELEASE_DIGESTS = {
    "docs/releases/v0.1.1.md": (
        "0e7724ca54a9d9c8b3ed403f6bbbd86c04dde3ee79e0644e95ee3ccf90513ab2"
    ),
    "docs/how-to/verify-v0.1.1-release.md": (
        "3e20b41e3256c275d557e6165e7e224a95a3a642286f6993da209a51aebe8f16"
    ),
}


def test_v0_1_1_release_documents_are_immutable_history() -> None:
    for relative, expected in HISTORICAL_RELEASE_DIGESTS.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected


def test_v0_1_1_release_notes_freeze_the_governed_dra_release_claim() -> None:
    release = (ROOT / "docs/releases/v0.1.1.md").read_text(encoding="utf-8")
    headings = (
        "## Summary",
        "## Completion",
        "## Verification",
        "## Scope",
        "## Risk / Impact",
        "## Documentation impact",
    )
    assert [release.index(heading) for heading in headings] == sorted(
        release.index(heading) for heading in headings
    )
    for token in (
        "local synthetic portfolio release",
        "deterministic offline governed DRA closure",
        "UNTRUSTED_CANDIDATE",
        "atomic authority gate",
        "australia_program_fit -> program_fit -> externally_verified",
        "synthetic baseline",
        "cost/FX",
        "ranking",
        "pinned current Case revision",
        "Live provider proof was not run",
        "local synthetic walkthrough",
        "GitHub-generated source archive",
    ):
        assert token in release


def test_v0_1_1_verification_guide_defines_publication_and_archive_gates() -> None:
    how_to = (ROOT / "docs/how-to/verify-v0.1.1-release.md").read_text(
        encoding="utf-8"
    )
    for token in (
        "local synthetic portfolio release",
        "git fetch origin --tags --prune",
        "git status --short --branch",
        "git rev-parse HEAD",
        "git rev-parse origin/main",
        "git describe --tags --exact-match HEAD",
        "git cat-file -t v0.1.1",
        "git rev-parse v0.1.1^{tag}",
        "git rev-parse v0.1.1^{commit}",
        'curl --fail --location --output "$archive"',
        "https://github.com/iTao-AI/night-voyager/archive/refs/tags/v0.1.1.tar.gz",
        'wc -c "$archive"',
        'shasum -a 256 "$archive"',
        'tar -xzf "$archive" -C "$tmp_dir"',
        'cd "$tmp_dir/night-voyager-0.1.1"',
        "make doctor",
        "make dra-check",
        "make db-check",
        "make check",
        "make proof",
        "make compose-proof",
        "make down",
        "docker compose ps --all",
        "Never move the tag after publication",
        "Use the extracted source archive",
        "Do not force-move `v0.1.1`",
        "normal pull request",
    ):
        assert token in how_to
