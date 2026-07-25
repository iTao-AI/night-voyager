from night_voyager.dra.fixtures import load_live_closure_scenario
from night_voyager.dra.live_evaluation import (
    OUTCOME_ASSERTIONS,
    TRAJECTORY_ASSERTIONS,
    evaluate_full_closure,
)

from .test_live_evaluation import (
    expected_outcome,
    outcome_projection,
    typed_receipts,
)


def test_full_closure_requires_typed_trajectory_and_authoritative_outcome() -> None:
    report = evaluate_full_closure(
        load_live_closure_scenario(),
        typed_receipts(),
        expected_outcome(),
        outcome_projection(),
    )
    assert report.status == "passed"
    assert len(report.assertions) == len(
        (*TRAJECTORY_ASSERTIONS, *OUTCOME_ASSERTIONS)
    )
    failed = outcome_projection().model_copy(update={"timeline_plan_count": 0})
    assert (
        evaluate_full_closure(
            load_live_closure_scenario(),
            typed_receipts(),
            expected_outcome(),
            failed,
        ).status
        == "failed"
    )
