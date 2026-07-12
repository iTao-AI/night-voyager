from __future__ import annotations

import pytest

from night_voyager.planning.models import RunState
from night_voyager.planning.transitions import InvalidTransition, transition_run


@pytest.mark.parametrize("terminal", [RunState.FAILED, RunState.BLOCKED, RunState.REVIEW_REQUIRED])
def test_terminal_planning_output_is_immutable(terminal: RunState) -> None:
    with pytest.raises(InvalidTransition):
        transition_run(terminal, RunState.RUNNING)


def test_pending_can_start_and_running_can_finish() -> None:
    assert transition_run(RunState.PENDING, RunState.RUNNING) is RunState.RUNNING
    assert transition_run(RunState.RUNNING, RunState.REVIEW_REQUIRED) is RunState.REVIEW_REQUIRED
