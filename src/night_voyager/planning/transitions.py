from __future__ import annotations

from night_voyager.planning.models import RunState


class InvalidTransition(ValueError):
    pass


TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    RunState.PENDING: frozenset({RunState.RUNNING, RunState.FAILED}),
    RunState.RUNNING: frozenset(
        {RunState.FAILED, RunState.BLOCKED, RunState.REVIEW_REQUIRED}
    ),
    RunState.FAILED: frozenset(),
    RunState.BLOCKED: frozenset(),
    RunState.REVIEW_REQUIRED: frozenset(),
}


def transition_run(current: RunState, target: RunState) -> RunState:
    if target not in TRANSITIONS[current]:
        raise InvalidTransition(f"invalid planning run transition: {current} -> {target}")
    return target
