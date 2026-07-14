from __future__ import annotations

from pathlib import Path
from shutil import copytree

import pytest

import night_voyager.connected_demo.fixtures as fixtures_module
from night_voyager.connected_demo.fixtures import resolve_canonical_demo_source_contract
from night_voyager.planning.fixtures import validate_planning_fixture


def test_resolver_returns_only_validated_fixture_identity() -> None:
    fixture = validate_planning_fixture()
    contract = resolve_canonical_demo_source_contract()
    assert contract.source_pack_id == fixture.planning_input.source_pack.pack_id
    assert contract.source_pack_version == fixture.planning_input.source_pack.version
    assert contract.manifest_sha256 == fixture.manifest_sha256
    assert contract.policy_version == "m3a-policy-v1"


def test_resolver_fails_closed_when_fixture_validation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject() -> object:
        raise ValueError("source hash mismatch")

    monkeypatch.setattr(fixtures_module, "validate_planning_fixture", reject)
    with pytest.raises(ValueError, match="source hash mismatch"):
        resolve_canonical_demo_source_contract()


def test_resolver_rejects_policy_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fixtures_module, "POLICY_VERSION", "m5-client-policy")
    with pytest.raises(ValueError, match="policy version"):
        resolve_canonical_demo_source_contract()


def test_fixture_validator_rejects_mutated_manifest_source(tmp_path: Path) -> None:
    root = tmp_path / "m3a"
    copytree(Path("fixtures/m3a"), root)
    (root / "sources/australia.txt").write_text("mutated", encoding="utf-8")
    with pytest.raises(ValueError, match="source hash mismatch"):
        validate_planning_fixture(root / "manifest.json")
