from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from night_voyager.evidence_loop.provider_locks import ProviderLockSetV1

ROOT = Path(__file__).resolve().parents[3]


def provider_payload() -> dict[str, object]:
    return json.loads(
        (
            ROOT / "tests/fixtures/evidence_loop/provider-locks-v1.json"
        ).read_text(encoding="utf-8")
    )


def test_exact_release_objects_are_closed() -> None:
    locks = ProviderLockSetV1.model_validate(provider_payload())
    assert locks.night_voyager.commit == "3a82721a86f65353b849e9ee93050912d0cb079a"
    assert locks.mke.tag_object == "1ca0a0b348638369e8407270ca5f363b0e551a9e"
    assert locks.mke.commit == "d258c10dc40bd9eccd67c858b56f4e4cf5fe4610"
    assert locks.mke.a3_source_tree_archive_basename == "mke-v0.1.5.tar"
    assert (
        locks.mke.a3_source_tree_archive_sha256
        == "12e0dc785723bd35e4f1ba40d3935fd4d906ae360b1e99fcecb43d24a009aa5a"
    )
    assert not hasattr(locks.mke, "source_archive_basename")
    assert not hasattr(locks.mke, "source_archive_sha256")
    assert locks.dra.tag_object == "f828606741f636bca7ddbb66244ca60019eaa3c8"
    assert locks.dra.commit == "cb1f4660ee4ac7d81b04ffea014362e933487e61"


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (("mke", "ref_kind"), "branch"),
        (("mke", "release"), "main"),
        (("mke", "tag_object"), "0" * 40),
        (("mke", "a3_source_tree_archive_sha256"), "0" * 64),
        (("mke", "wheel_sha256"), "0" * 64),
        (("mke", "tool_schema_sha256"), "0" * 64),
        (("dra", "commit"), "0" * 40),
        (("dra", "source_archive_sha256"), "0" * 64),
        (("night_voyager", "tree"), "0" * 40),
    ),
)
def test_moving_or_mixed_identity_is_rejected(
    path: tuple[str, str], value: str
) -> None:
    payload = provider_payload()
    provider = payload[path[0]]
    assert isinstance(provider, dict)
    provider[path[1]] = value
    with pytest.raises(ValidationError):
        ProviderLockSetV1.model_validate(payload)
