import pytest

from night_voyager.dra.fixtures import load_live_closure_scenario
from night_voyager.dra.live_evaluation import (
    OUTCOME_ASSERTIONS,
    TRAJECTORY_ASSERTIONS,
    evaluate_full_closure,
    evaluate_strict_candidate,
)

from .test_live_evaluation import (
    expected_outcome,
    outcome_projection,
    strict_outcome_projection,
    strict_readiness,
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


def test_strict_outcome_request_hash_must_match_readiness() -> None:
    projection = strict_outcome_projection()
    durable = projection.durable_candidate
    assert durable is not None
    mismatched = projection.model_copy(
        update={
            "durable_candidate": durable.model_copy(
                update={
                    "request_identity": durable.request_identity.model_copy(
                        update={"request_sha256": "0" * 64}
                    )
                }
            )
        }
    )

    with pytest.raises(ValueError, match="strict_candidate_identity"):
        evaluate_strict_candidate(strict_readiness(), mismatched)
