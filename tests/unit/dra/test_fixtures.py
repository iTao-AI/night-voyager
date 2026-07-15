from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from night_voyager.dra.fixtures import (
    DRA_FIXTURE,
    DRA_MANIFEST,
    build_fixture_candidate_import,
    load_dra_fixture,
)


def test_copied_fixture_and_manifest_pin_exact_releases() -> None:
    manifest = json.loads(DRA_MANIFEST.read_text(encoding="utf-8"))
    assert hashlib.sha256(DRA_FIXTURE.read_bytes()).hexdigest() == (
        "cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157"
    )
    assert manifest["producer"] == {
        "repository": "decision-research-agent",
        "release": "v0.1.3",
        "commit": "87b2a8e335385eb865086f7a69fe2b190567cfa2",
        "fixture_path": "docs/evidence/downstream-consumer-contract-v1.json",
        "fixture_schema": "dra.downstream-consumer.v1",
        "fixture_sha256": "cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157",
    }
    assert manifest["baseline"]["policy_version"] == "m3a-policy-v1"
    assert manifest["baseline"]["manifest_raw_sha256"] == (
        "5d455d2c409c322e093f3a116387f3cef0fb7ea0f7357fec5e76e9da5b3a2a25"
    )
    assert manifest["baseline"]["canonical_manifest_sha256"] == (
        "84350ea5705d9681d3e6550e1bd06e3340a9fcf0e7e7bbed4478ed3403405f28"
    )


def test_loader_has_no_arbitrary_path_argument() -> None:
    with pytest.raises(TypeError):
        load_dra_fixture(Path("/tmp/untrusted.json"))  # type: ignore[call-arg]


def test_fixture_candidate_selects_one_public_source() -> None:
    candidate = build_fixture_candidate_import()
    selected = [item for item in candidate.evidence if item.is_promotable]
    assert len(selected) == 1
    assert str(selected[0].source_url) == selected[0].source_identity
