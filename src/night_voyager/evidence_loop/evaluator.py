from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationResult:
    disposition: str
    novel_source_bound_units: int
    pre_registered_gap_closed: bool
    explicit_conflicts: tuple[tuple[str, str], ...]


def evaluate_case(
    *,
    selection_status: str,
    control_values: tuple[str, ...],
    dra_values: tuple[str, ...],
    mke_values: tuple[str, ...],
    expected_value: str,
    conflicts: tuple[tuple[str, str], ...],
) -> EvaluationResult:
    if selection_status != "complete":
        return EvaluationResult("inconclusive", 0, False, conflicts)
    prior = set(control_values) | set(dra_values)
    novel = tuple(value for value in dict.fromkeys(mke_values) if value not in prior)
    return EvaluationResult(
        disposition="evaluated",
        novel_source_bound_units=len(novel),
        pre_registered_gap_closed=expected_value in novel,
        explicit_conflicts=conflicts,
    )
