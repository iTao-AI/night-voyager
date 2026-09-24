from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_anyio_lock_meets_open_security_advisories() -> None:
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    package = next(item for item in lock["package"] if item.get("name") == "anyio")
    version = tuple(int(part) for part in package["version"].split("."))
    assert version >= (4, 14, 2)
