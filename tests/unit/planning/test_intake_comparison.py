from __future__ import annotations

from copy import deepcopy
from typing import Any, cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from night_voyager.planning import revision
from night_voyager.planning.fixtures import validate_planning_fixture
from night_voyager.planning.hashing import canonical_sha256
from night_voyager.planning.models import FamilyPreferences, StudentPreferences
from tests.unit.planning.test_revision import (
    PREVIOUS_RUN,
    REVIEW,
    current_projection,
    preferred_country_delta,
    previous_projection,
)


def comparison_payload() -> dict[str, object]:
    previous, current = previous_projection(), current_projection()
    return revision.build_planning_revision_comparison_v2(
        changed_fact=revision.IntakeFactDeltaV1(
            fact_key="student.intake", previous_value="2027-02", current_value="2028-02"
        ),
        previous_request_review=revision.PreviousRequestReviewV1(
            review_id=REVIEW,
            review_version=1,
            planning_run_id=PREVIOUS_RUN,
            case_revision=1,
            action="request_revision",
        ),
        previous=previous,
        current=current,
        previous_output_sha256=canonical_sha256(previous.planning_result().model_dump(mode="json")),
        current_output_sha256=canonical_sha256(current.planning_result().model_dump(mode="json")),
    ).model_dump(mode="json", by_alias=True)


def test_intake_comparison_preserves_lineage_outcomes_hashes_and_bounded_review() -> None:
    payload = comparison_payload()
    assert payload["schema"] == "night-voyager.planning-revision-comparison.v2"
    assert payload["changed_fact"] == {
        "fact_key": "student.intake",
        "previous_value": "2027-02",
        "current_value": "2028-02",
    }
    assert payload["previous_request_review"] == {
        "review_id": str(REVIEW),
        "review_version": 1,
        "planning_run_id": str(PREVIOUS_RUN),
        "case_revision": 1,
        "action": "request_revision",
    }
    assert payload["approval_eligible"] is True
    assert payload["previous_output_sha256"] != payload["current_output_sha256"]


@pytest.mark.parametrize(
    "value", ["0000-02", "2028-13", "2028-00", " 2028-02", "２０２８-02", 202802]
)
def test_intake_delta_rejects_invalid_calendar_or_coercion(value: object) -> None:
    with pytest.raises(ValidationError):
        revision.IntakeFactDeltaV1.model_validate(
            {
                "fact_key": "student.intake",
                "previous_value": "2027-02",
                "current_value": value,
            }
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "unchanged",
        "extra_fact",
        "wrong_review_run",
        "wrong_review_revision",
        "review_notes",
        "wrong_hash",
    ],
)
def test_comparison_v2_rejects_unbounded_or_inconsistent_projection(mutation: str) -> None:
    payload = deepcopy(comparison_payload())
    if mutation == "unchanged":
        payload["changed_fact"] = {
            "fact_key": "student.intake",
            "previous_value": "2028-02",
            "current_value": "2028-02",
        }
    elif mutation == "extra_fact":
        payload["changed_fact"] = {
            "fact_key": "student.intake",
            "previous_value": "2027-02",
            "current_value": "2028-02",
            "family.budget": {},
        }
    elif mutation in {"wrong_review_run", "wrong_review_revision", "review_notes"}:
        review = dict(cast(dict[str, Any], payload["previous_request_review"]))
        if mutation == "wrong_review_run":
            review["planning_run_id"] = str(UUID(int=99))
        elif mutation == "wrong_review_revision":
            review["case_revision"] = 2
        else:
            review["reviewer_notes"] = "must not be exposed"
        payload["previous_request_review"] = review
    else:
        previous, current = previous_projection(), current_projection()
        with pytest.raises(ValueError, match="hash_mismatch"):
            revision.build_planning_revision_comparison_v2(
                changed_fact=preferred_country_delta(),
                previous_request_review=revision.PreviousRequestReviewV1.model_validate(
                    payload["previous_request_review"]
                ),
                previous=previous,
                current=current,
                previous_output_sha256="a" * 64,
                current_output_sha256=canonical_sha256(
                    current.planning_result().model_dump(mode="json")
                ),
            )
        return
    with pytest.raises(ValidationError):
        revision.PlanningRevisionComparisonV2.model_validate(payload)


def test_v1_union_keeps_rejecting_intake() -> None:
    payload = comparison_payload()
    payload["schema"] = "night-voyager.planning-revision-comparison.v1"
    payload.pop("previous_request_review")
    with pytest.raises(ValidationError):
        revision.PlanningRevisionComparisonV1.model_validate(payload)


@pytest.mark.parametrize("key", ["student.intake", "student.preferred_countries", "family.budget"])
def test_fact_projection_admits_exactly_one_of_three_deltas(key: str) -> None:
    case = validate_planning_fixture().planning_input.case
    student = case.student.model_dump(mode="json")
    family = case.family.model_dump(mode="json")
    if key == "student.intake":
        student["intake"] = "2028-02"
    elif key == "student.preferred_countries":
        student["preferred_countries"] = ["australia", "japan"]
    else:
        family["budget"]["preferred_minor"] = 31000000
    delta = revision.derive_planning_revision_fact_delta(
        previous_student=case.student,
        current_student=StudentPreferences.model_validate(student),
        previous_family=case.family,
        current_family=FamilyPreferences.model_validate(family),
    )
    assert delta.fact_key == key


@pytest.mark.parametrize("kind", ["none", "two", "unsupported"])
def test_fact_projection_refuses_simultaneous_or_unsupported_changes(kind: str) -> None:
    case = validate_planning_fixture().planning_input.case
    student = case.student.model_dump(mode="json")
    if kind == "two":
        student.update(intake="2028-02", preferred_countries=["australia"])
    elif kind == "unsupported":
        student.update(intake="2028-02", intended_field="different")
    with pytest.raises(ValueError, match="changed_fact_invalid"):
        revision.derive_planning_revision_fact_delta(
            previous_student=case.student,
            current_student=StudentPreferences.model_validate(student),
            previous_family=case.family,
            current_family=case.family,
        )
