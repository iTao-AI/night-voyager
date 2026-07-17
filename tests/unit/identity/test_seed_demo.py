from __future__ import annotations

import pytest

from night_voyager.identity.demo_seed import (
    COLLABORATION_ACTIVE_CASE_ID,
    COLLABORATION_ACTIVE_TASK_ID,
    COLLABORATION_CASE_ID,
    COLLABORATION_EXPIRED_CANDIDATE_ID,
    COLLABORATION_EXPIRED_CASE_ID,
    COLLABORATION_EXPIRED_MESSAGE_ID,
    COLLABORATION_STALE_CANDIDATE_ID,
    COLLABORATION_STALE_CASE_ID,
    COLLABORATION_STALE_MESSAGE_ID,
    COLLABORATION_THREAD_IDS,
    ensure_seed_allowed,
)


def test_demo_seed_fails_closed_without_nonproduction_demo_mode() -> None:
    with pytest.raises(ValueError, match="development or test"):
        ensure_seed_allowed("production", True)
    with pytest.raises(ValueError, match="demo mode"):
        ensure_seed_allowed("test", False)

    ensure_seed_allowed("development", True)
    ensure_seed_allowed("test", True)


def test_collaboration_seed_ids_are_fixed_and_cases_are_isolated() -> None:
    assert COLLABORATION_CASE_ID.hex == "41000000000000000000000000000001"
    assert COLLABORATION_ACTIVE_CASE_ID.hex == "41000000000000000000000000000002"
    assert COLLABORATION_STALE_CASE_ID.hex == "41000000000000000000000000000003"
    assert COLLABORATION_EXPIRED_CASE_ID.hex == "41000000000000000000000000000004"
    assert len(set(COLLABORATION_THREAD_IDS.values())) == 4
    assert COLLABORATION_STALE_MESSAGE_ID != COLLABORATION_EXPIRED_MESSAGE_ID
    assert COLLABORATION_STALE_CANDIDATE_ID != COLLABORATION_EXPIRED_CANDIDATE_ID
    assert COLLABORATION_ACTIVE_TASK_ID.hex == "48000000000000000000000000000002"
