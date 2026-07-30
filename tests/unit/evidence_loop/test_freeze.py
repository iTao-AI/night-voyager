from __future__ import annotations

import json
from pathlib import Path

import pytest

from night_voyager.evidence_loop.freeze import (
    POST_REVEAL_ALLOWLIST,
    validate_public_commitments,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests/fixtures/evidence_loop"


def test_public_commitments_admit_only_revision_three() -> None:
    result = validate_public_commitments(FIXTURES)
    assert result.author_revision == 3
    assert result.roles == (
        "independent-dataset-author-v3",
        "night-voyager-slice0-evaluator-v1",
        "independent-holdout-custodian-v3",
    )
    assert len(result.source_digests) == 4
    assert result.holdout_content_reachable is False


def test_public_commitments_fail_on_source_drift(tmp_path: Path) -> None:
    for path in FIXTURES.iterdir():
        if path.is_file():
            (tmp_path / path.name).write_bytes(path.read_bytes())
    corpus = tmp_path / "mke-corpus"
    corpus.mkdir()
    for path in (FIXTURES / "mke-corpus").iterdir():
        (corpus / path.name).write_bytes(path.read_bytes())
    (corpus / "rf-0a6f5c9d.pdf").write_bytes(b"drift")

    with pytest.raises(ValueError, match="source identity mismatch"):
        validate_public_commitments(tmp_path)


def test_post_reveal_allowlist_is_exact() -> None:
    assert POST_REVEAL_ALLOWLIST == (
        "tests/fixtures/evidence_loop/holdout-dataset-v1.json",
        "tests/fixtures/evidence_loop/mke-capture-v2.json",
        "tests/fixtures/evidence_loop/slice0-receipt-v2.json",
    )
    manifest = json.loads((FIXTURES / "holdout-manifest-v1.json").read_text())
    assert manifest["holdout_content_included"] is False
    assert manifest["oracle_content_included"] is False
