from __future__ import annotations

from night_voyager.evidence_loop.evaluator import evaluate_case


def test_capped_is_inconclusive() -> None:
    result = evaluate_case(
        selection_status="capped",
        control_values=(),
        dra_values=(),
        mke_values=("new",),
        expected_value="new",
        conflicts=(),
    )
    assert result.disposition == "inconclusive"


def test_exact_duplicate_has_zero_novelty() -> None:
    result = evaluate_case(
        selection_status="complete",
        control_values=("same",),
        dra_values=("same",),
        mke_values=("same",),
        expected_value="same",
        conflicts=(),
    )
    assert result.novel_source_bound_units == 0


def test_conflict_remains_explicit() -> None:
    result = evaluate_case(
        selection_status="complete",
        control_values=(),
        dra_values=("before",),
        mke_values=("after",),
        expected_value="after",
        conflicts=(("before", "after"),),
    )
    assert result.explicit_conflicts == (("before", "after"),)
    assert result.pre_registered_gap_closed is True
