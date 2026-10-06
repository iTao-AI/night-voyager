from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from uuid import UUID

import pytest

from night_voyager.planning.fixtures import validate_planning_fixture
from night_voyager.planning.intake_fixture import load_exact_intake_delay_fixture
from night_voyager.planning.models import EvidenceAuthority
from night_voyager.planning.synthetic import (
    PersistedSyntheticSnapshotV1,
    materialize_persisted_synthetic_input,
)

PACK = UUID("50000000-0000-0000-0000-000000000017")
MANIFEST = Path("fixtures/intake-delay-v1/manifest.json")


def intake_snapshot() -> PersistedSyntheticSnapshotV1:
    old = validate_planning_fixture().planning_input
    case = old.case.model_copy(
        update={
            "case_id": UUID("49000000-0000-0000-0000-000000000003"),
            "revision": 2,
            "student": old.case.student.model_copy(update={"intake": "2028-02"}),
        }
    )
    return PersistedSyntheticSnapshotV1(
        schema_version=1,
        organization_id=old.organization_id,
        case=case,
        source_pack_id=PACK,
        source_pack_version=1,
        policy_version="m3a-policy-v1",
    )


def test_delayed_intake_uses_distinct_cost_evidence_and_persisted_case() -> None:
    old = validate_planning_fixture().planning_input
    snapshot = intake_snapshot()
    value = materialize_persisted_synthetic_input(snapshot)
    assert value.case == snapshot.case
    assert value.source_pack.pack_id == PACK
    assert len(value.costs) == 1
    cost = value.costs[0]
    assert cost.intake == "2028-02"
    assert cost.tuition_minor == 4200000
    assert cost.living_minor == 2600000
    assert str(cost.fx_rate) == "4.80"
    assert int((cost.tuition_minor + cost.living_minor) * cost.fx_rate) == 32640000
    assert all(e.authority is EvidenceAuthority.ACCEPTED_SYNTHETIC_DEMO for e in value.evidence)
    assert {e.evidence_id for e in value.evidence}.isdisjoint(e.evidence_id for e in old.evidence)
    assert {e.entry_id for e in value.source_pack.entries}.isdisjoint(
        e.entry_id for e in old.source_pack.entries
    )
    assert hashlib.sha256(Path("fixtures/m3a/manifest.json").read_bytes()).hexdigest() == (
        "5d455d2c409c322e093f3a116387f3cef0fb7ea0f7357fec5e76e9da5b3a2a25"
    )


@pytest.mark.parametrize("version", (2, 17))
def test_unregistered_intake_pack_version_cannot_reuse_old_costs(version: int) -> None:
    with pytest.raises(ValueError, match="pins"):
        materialize_persisted_synthetic_input(
            intake_snapshot().model_copy(update={"source_pack_version": version})
        )


def test_new_pack_cannot_cost_another_intake() -> None:
    snapshot = intake_snapshot()
    wrong = snapshot.case.model_copy(
        update={"student": snapshot.case.student.model_copy(update={"intake": "2028-09"})}
    )
    with pytest.raises(ValueError, match="intake"):
        materialize_persisted_synthetic_input(snapshot.model_copy(update={"case": wrong}))


@pytest.mark.parametrize("drift", ("manifest", "source", "missing_source", "path"))
def test_intake_fixture_refuses_manifest_source_or_path_drift(tmp_path: Path, drift: str) -> None:
    root = tmp_path / "pack"
    shutil.copytree(MANIFEST.parent, root)
    manifest = root / "manifest.json"
    source = root / "sources/australia.txt"
    if drift == "manifest":
        manifest.write_bytes(manifest.read_bytes() + b"\n")
    elif drift == "source":
        source.write_text("different synthetic cost", encoding="utf-8")
    elif drift == "missing_source":
        source.unlink()
    else:
        manifest.write_text(manifest.read_text().replace("sources/australia.txt", "../outside.txt"))
    with pytest.raises((ValueError, FileNotFoundError)):
        load_exact_intake_delay_fixture(manifest_path=manifest)


def test_new_identity_cannot_accept_baseline_manifest_or_change_tenant_facts() -> None:
    with pytest.raises(ValueError, match="manifest"):
        materialize_persisted_synthetic_input(
            intake_snapshot(), manifest_path=Path("fixtures/m3a/manifest.json")
        )
    snapshot = intake_snapshot()
    org = UUID("10000000-0000-0000-0000-000000000099")
    case = snapshot.case.model_copy(update={"organization_id": org})
    value = materialize_persisted_synthetic_input(
        snapshot.model_copy(update={"organization_id": org, "case": case})
    )
    assert value.case == case
    assert all(e.organization_id == org for e in value.evidence)
    assert all(c.organization_id == org for c in value.costs)
    assert value.source_pack.organization_id == org
