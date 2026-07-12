from __future__ import annotations

import pytest

from night_voyager.planning.models import CaseState, RunState
from night_voyager.planning.transitions import (
    InvalidTransition,
    transition_case,
    transition_run,
)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (RunState.DRAFT, RunState.COLLECTING_EVIDENCE),
        (RunState.COLLECTING_EVIDENCE, RunState.SYNTHESIZING),
        (RunState.SYNTHESIZING, RunState.REVIEW_REQUIRED),
        (RunState.SYNTHESIZING, RunState.BLOCKED),
        (RunState.SYNTHESIZING, RunState.FAILED),
    ],
)
def test_planning_run_lifecycle(current: RunState, target: RunState) -> None:
    assert transition_run(current, target) is target


@pytest.mark.parametrize("terminal", [RunState.FAILED, RunState.BLOCKED, RunState.REVIEW_REQUIRED])
def test_terminal_planning_output_is_immutable(terminal: RunState) -> None:
    with pytest.raises(InvalidTransition):
        transition_run(terminal, RunState.SYNTHESIZING)


def test_student_case_lifecycle_is_exact() -> None:
    assert transition_case(CaseState.INTAKE, CaseState.PLANNING) is CaseState.PLANNING
    assert transition_case(CaseState.PLANNING, CaseState.ADVISOR_REVIEW) is CaseState.ADVISOR_REVIEW
    with pytest.raises(InvalidTransition):
        transition_case(CaseState.ADVISOR_REVIEW, CaseState.PLANNING)
