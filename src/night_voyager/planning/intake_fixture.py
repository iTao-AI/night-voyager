"""Closed, hypothetical February 2028 source pack; never a current-data lookup."""

from __future__ import annotations

import hashlib
from importlib.resources import files
from pathlib import Path
from uuid import UUID

from night_voyager.planning.fixtures import validate_planning_fixture
from night_voyager.planning.models import PlanningInput

INTAKE_DELAY_SOURCE_PACK_ID = UUID("50000000-0000-0000-0000-000000000017")
INTAKE_DELAY_SOURCE_PACK_VERSION = 1
INTAKE_DELAY_INTAKE = "2028-02"
INTAKE_DELAY_POLICY_VERSION = "m3a-policy-v1"
INTAKE_DELAY_MANIFEST_SHA256 = "832aab1715564dee0e3a4530a181ccd4581bb7e5199144cb34dc55b20077add1"
INTAKE_DELAY_RAW_MANIFEST_SHA256 = (
    "27cde816426600fe355eaca842a028b451395be5c9ded0b0e29418d58998cee2"
)


def _manifest_path() -> Path:
    packaged = files("night_voyager.planning").joinpath("data/intake-delay-v1/manifest.json")
    if packaged.is_file():
        return Path(str(packaged))
    # Editable development has no force-included wheel data. Resolve this
    # checkout explicitly; an installed wheel uses the packaged branch above.
    return Path(__file__).resolve().parents[3] / "fixtures/intake-delay-v1/manifest.json"


def load_exact_intake_delay_fixture(*, manifest_path: Path | None = None) -> PlanningInput:
    manifest_path = manifest_path if manifest_path is not None else _manifest_path()
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != INTAKE_DELAY_RAW_MANIFEST_SHA256:
        raise ValueError("intake fixture raw manifest mismatch")
    fixture = validate_planning_fixture(manifest_path)
    value = fixture.planning_input
    if (
        value.source_pack.pack_id != INTAKE_DELAY_SOURCE_PACK_ID
        or value.source_pack.version != INTAKE_DELAY_SOURCE_PACK_VERSION
        or fixture.manifest_sha256 != INTAKE_DELAY_MANIFEST_SHA256
        or value.case.student.intake != INTAKE_DELAY_INTAKE
        or len(value.costs) != 1
        or value.costs[0].intake != INTAKE_DELAY_INTAKE
    ):
        raise ValueError("intake fixture identity mismatch")
    return value
