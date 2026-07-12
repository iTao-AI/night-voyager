from __future__ import annotations

import pytest

from night_voyager.identity.demo_seed import ensure_seed_allowed


def test_demo_seed_fails_closed_without_nonproduction_demo_mode() -> None:
    with pytest.raises(ValueError, match="development or test"):
        ensure_seed_allowed("production", True)
    with pytest.raises(ValueError, match="demo mode"):
        ensure_seed_allowed("test", False)

    ensure_seed_allowed("development", True)
    ensure_seed_allowed("test", True)
