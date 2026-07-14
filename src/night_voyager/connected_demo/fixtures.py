from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from night_voyager.planning.application import POLICY_VERSION
from night_voyager.planning.fixtures import validate_planning_fixture


@dataclass(frozen=True, slots=True)
class CanonicalDemoSourceContract:
    source_pack_id: UUID
    source_pack_version: int
    manifest_sha256: str
    policy_version: Literal["m3a-policy-v1"]

    def __post_init__(self) -> None:
        if self.source_pack_version <= 0:
            raise ValueError("source pack version must be positive")
        if len(self.manifest_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.manifest_sha256
        ):
            raise ValueError("manifest hash must be lowercase SHA-256")
        if self.policy_version != "m3a-policy-v1":
            raise ValueError("canonical demo policy version is invalid")


def resolve_canonical_demo_source_contract() -> CanonicalDemoSourceContract:
    fixture = validate_planning_fixture()
    pack = fixture.planning_input.source_pack
    if POLICY_VERSION != "m3a-policy-v1":
        raise ValueError("canonical demo policy version is invalid")
    return CanonicalDemoSourceContract(
        source_pack_id=pack.pack_id,
        source_pack_version=pack.version,
        manifest_sha256=fixture.manifest_sha256,
        policy_version="m3a-policy-v1",
    )
