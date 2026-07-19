from __future__ import annotations

import pytest

from scripts.verify_collaboration_flow import expect_problem


def test_problem_mismatch_reports_only_bounded_expected_and_actual_codes() -> None:
    with pytest.raises(
        SystemExit,
        match=(
            "expected=active_task_blocks_revision "
            "actual=memory_candidate_stale"
        ),
    ):
        expect_problem(
            {"code": "memory_candidate_stale", "status": 409},
            "active_task_blocks_revision",
        )


def test_problem_mismatch_does_not_echo_untrusted_payload_code() -> None:
    secret = "raw-secret-payload"
    with pytest.raises(SystemExit) as raised:
        expect_problem(
            {"code": secret, "status": 409},
            "active_task_blocks_revision",
        )

    assert secret not in str(raised.value)
    assert "actual=resource_unavailable" in str(raised.value)
