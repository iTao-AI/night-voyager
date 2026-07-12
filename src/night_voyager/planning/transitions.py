from __future__ import annotations

from night_voyager.planning.models import CaseState, RunState


class InvalidTransition(ValueError):
    pass


RUN_TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    RunState.DRAFT: frozenset({RunState.COLLECTING_EVIDENCE, RunState.FAILED}),
    RunState.COLLECTING_EVIDENCE: frozenset({RunState.SYNTHESIZING, RunState.FAILED}),
    RunState.SYNTHESIZING: frozenset({RunState.FAILED, RunState.BLOCKED, RunState.REVIEW_REQUIRED}),
    RunState.FAILED: frozenset(),
    RunState.BLOCKED: frozenset(),
    RunState.REVIEW_REQUIRED: frozenset(),
}

CASE_TRANSITIONS: dict[CaseState, frozenset[CaseState]] = {
    CaseState.INTAKE: frozenset({CaseState.PLANNING}),
    CaseState.PLANNING: frozenset({CaseState.ADVISOR_REVIEW}),
    CaseState.ADVISOR_REVIEW: frozenset(),
}


def transition_run(current: RunState, target: RunState) -> RunState:
    if target not in RUN_TRANSITIONS[current]:
        raise InvalidTransition(f"invalid planning run transition: {current} -> {target}")
    return target


def transition_case(current: CaseState, target: CaseState) -> CaseState:
    if target not in CASE_TRANSITIONS[current]:
        raise InvalidTransition(f"invalid student case transition: {current} -> {target}")
    return target
