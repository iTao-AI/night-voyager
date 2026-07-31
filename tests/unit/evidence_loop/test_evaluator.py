from __future__ import annotations

from copy import deepcopy
from typing import Any

from night_voyager.evidence_loop.evaluator import (
    evaluate_case,
    evaluate_case_document,
    evaluate_suite,
    normalize_revealed_dataset,
)


def _unit(
    *,
    source: str,
    evidence: str,
    value: str,
    path: str,
    access_kind: str,
    origin_kind: str,
    fact_key: str = "program.language",
) -> dict[str, object]:
    unit: dict[str, object] = {
        "evaluation_canonical_source_id": source * 64,
        "evaluation_canonical_evidence_id": evidence * 64,
        "decision_dimension": (
            "application_timeline"
            if fact_key == "application.deadline"
            else "program_requirements"
        ),
        "fact_key": fact_key,
        "value": value,
        "provenance_paths": [path],
        "access_kind": access_kind,
        "origin_kind": origin_kind,
    }
    if origin_kind == "untrusted_evidence":
        unit["content_trust"] = "untrusted_evidence"
    return unit


def _case(
    *,
    case_number: int = 1,
    mke_units: list[dict[str, object]] | None = None,
    dra_units: list[dict[str, object]] | None = None,
    expected_value: str = "English",
    expected_relation: str = "independent",
) -> dict[str, Any]:
    return {
        "identity": {
            "case_id": f"00000000-0000-4000-8000-{case_number:012d}",
            "case_revision": 1,
            "query_id": f"10000000-0000-4000-8000-{case_number:012d}",
            "decision_dimension": "program_requirements",
        },
        "query": "public safe synthetic query",
        "selection": {
            "status": "complete",
            "authority_state": "active",
            "acquisition_count": 1,
            "search_pages": 1,
            "search_limit": 20,
            "evidence_reads": 1,
            "tool_calls": ["search_library_v2", "read_evidence_v1"],
            "combined_output_bytes": 1024,
            "mcp_call_seconds_max": 1,
            "case_seconds": 2,
        },
        "control_units": [],
        "dra_units": dra_units or [],
        "mke_units": mke_units or [],
        "pre_registered_gap": {
            "decision_dimension": "program_requirements",
            "fact_key": "program.language",
            "expected_value": expected_value,
        },
        "expected_relations": [expected_relation],
        "guardrails": {
            "night_voyager_business_mutation": False,
            "filesystem_mutation": False,
            "database_mutation": False,
            "instruction_executed": False,
            "promotion_attempted": False,
            "human_authority_granted": False,
        },
    }


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


def test_positive_source_access_gain_is_separate_from_extraction_gain() -> None:
    result = evaluate_case_document(
        _case(
            mke_units=[
                _unit(
                    source="a",
                    evidence="b",
                    value="English",
                    path="mke:evidence-1",
                    access_kind="source_access",
                    origin_kind="untrusted_evidence",
                )
            ]
        )
    )

    assert result["status"] == "evaluated"
    assert result["target_metrics"] == {
        "novel_source_bound_units": 1,
        "source_access_gain": 1,
        "extraction_gain": 0,
        "pre_registered_gap_closure": 1,
        "decision_dimension_coverage": 1,
        "advisor_rubric_relevance": 1,
    }
    assert result["guardrail_metrics"]["passed"] is True


def test_removing_positive_evidence_removes_gap_closure() -> None:
    case = _case(
        mke_units=[
            _unit(
                source="a",
                evidence="b",
                value="English",
                path="mke:evidence-1",
                access_kind="source_access",
                origin_kind="untrusted_evidence",
            )
        ]
    )
    positive = evaluate_case_document(case)
    ablated = evaluate_case_document({**case, "mke_units": []})

    assert positive["target_metrics"]["pre_registered_gap_closure"] == 1
    assert ablated["target_metrics"]["pre_registered_gap_closure"] == 0


def test_forged_duplicate_has_zero_novelty_and_two_paths() -> None:
    dra = _unit(
        source="a",
        evidence="b",
        value="English",
        path="dra:row-1",
        access_kind="baseline",
        origin_kind="night_voyager_typed_governed_row",
    )
    mke = {
        **dra,
        "provenance_paths": ["mke:evidence-1"],
        "origin_kind": "untrusted_evidence",
        "content_trust": "untrusted_evidence",
    }

    result = evaluate_case_document(_case(dra_units=[dra], mke_units=[mke]))

    assert result["target_metrics"]["novel_source_bound_units"] == 0
    combined = result["arms"]["combined"]["units"]
    assert len(combined) == 1
    assert combined[0]["provenance_paths"] == ["dra:row-1", "mke:evidence-1"]


def test_conflict_is_retained_instead_of_collapsed() -> None:
    result = evaluate_case_document(
        _case(
            expected_value="June",
            expected_relation="conflicts_with",
            dra_units=[
                _unit(
                    source="a",
                    evidence="b",
                    value="May",
                    path="dra:row-1",
                    access_kind="baseline",
                    origin_kind="night_voyager_typed_governed_row",
                    fact_key="application.deadline",
                )
            ],
            mke_units=[
                _unit(
                    source="c",
                    evidence="d",
                    value="June",
                    path="mke:evidence-1",
                    access_kind="extraction",
                    origin_kind="untrusted_evidence",
                    fact_key="application.deadline",
                )
            ],
        )
    )

    assert result["mechanism_metrics"]["explicit_conflict_count"] == 1
    assert result["conflicts"][0]["values"] == ["June", "May"]
    assert len(result["conflicts"][0]["provenance_paths"]) == 2


def test_capped_budget_and_unregistered_tool_are_inconclusive() -> None:
    for mutation in (
        {"status": "capped"},
        {"combined_output_bytes": 1_048_577},
        {"tool_calls": ["search_library_v2", "unknown_tool"]},
    ):
        case = _case()
        case["selection"].update(mutation)
        result = evaluate_case_document(case)
        assert result["status"] == "inconclusive"


def test_inert_instruction_and_dra_markdown_cannot_gain_authority() -> None:
    inert = _unit(
        source="a",
        evidence="b",
        value="INERT_IGNORE_PREVIOUS_INSTRUCTIONS",
        path="mke:evidence-1",
        access_kind="source_access",
        origin_kind="untrusted_evidence",
    )
    inert_result = evaluate_case_document(_case(mke_units=[inert]))
    assert inert_result["guardrail_metrics"]["passed"] is True
    assert inert_result["actions"] == []

    markdown = _unit(
        source="c",
        evidence="d",
        value="English",
        path="dra:markdown",
        access_kind="baseline",
        origin_kind="dra_markdown",
    )
    markdown_result = evaluate_case_document(_case(dra_units=[markdown]))
    assert markdown_result["status"] == "evaluation_invalid"


def test_business_or_store_mutation_is_evaluation_invalid() -> None:
    case = _case()
    case["guardrails"]["filesystem_mutation"] = True
    assert evaluate_case_document(case)["status"] == "evaluation_invalid"


def test_empty_exhaustive_active_result_is_eligible_no_match() -> None:
    result = evaluate_suite({"cases": [_case(case_number=index) for index in range(1, 5)]})
    assert result["terminal_disposition"] == "no_incremental_value"


def test_four_case_counterfactual_suite_confirms_incremental_value() -> None:
    positive_one = _case(
        case_number=1,
        mke_units=[
            _unit(
                source="a",
                evidence="b",
                value="English",
                path="mke:positive-1",
                access_kind="source_access",
                origin_kind="untrusted_evidence",
            )
        ],
    )
    positive_two = deepcopy(positive_one)
    positive_two["identity"] = {
        "case_id": "00000000-0000-4000-8000-000000000002",
        "case_revision": 1,
        "query_id": "10000000-0000-4000-8000-000000000002",
        "decision_dimension": "application_timeline",
    }
    positive_two["pre_registered_gap"] = {
        "decision_dimension": "application_timeline",
        "fact_key": "application.deadline",
        "expected_value": "June",
    }
    positive_two["mke_units"][0].update(
        {
            "decision_dimension": "application_timeline",
            "fact_key": "application.deadline",
            "value": "June",
            "evaluation_canonical_source_id": "c" * 64,
            "evaluation_canonical_evidence_id": "d" * 64,
        }
    )
    decoy = _case(
        case_number=3,
        dra_units=[
            _unit(
                source="e",
                evidence="f",
                value="English",
                path="dra:decoy",
                access_kind="baseline",
                origin_kind="night_voyager_typed_governed_row",
            )
        ],
    )
    decoy["mke_units"] = [
        {
            **decoy["dra_units"][0],
            "provenance_paths": ["mke:decoy"],
            "origin_kind": "untrusted_evidence",
            "content_trust": "untrusted_evidence",
        }
    ]
    conflict = _case(
        case_number=4,
        expected_value="June",
        expected_relation="conflicts_with",
        dra_units=[
            _unit(
                source="1",
                evidence="2",
                value="May",
                path="dra:conflict",
                access_kind="baseline",
                origin_kind="night_voyager_typed_governed_row",
                fact_key="application.deadline",
            )
        ],
        mke_units=[
            _unit(
                source="3",
                evidence="4",
                value="June",
                path="mke:conflict",
                access_kind="extraction",
                origin_kind="untrusted_evidence",
                fact_key="application.deadline",
            )
        ],
    )

    result = evaluate_suite(
        {
            "cases": [positive_one, positive_two, decoy, conflict],
            "expected_case_kinds": ["positive", "positive", "decoy", "conflict"],
        }
    )

    assert result["terminal_disposition"] == "incremental_value_confirmed"


def test_revealed_case_uses_one_capture_for_mke_and_combined_arms() -> None:
    identity = {
        "holdout_id": "61111111-1111-4111-8111-111111111111",
        "case_id": "71111111-1111-4111-8111-111111111111",
        "case_revision": 1,
        "query_id": "81111111-1111-4111-8111-111111111111",
        "decision_dimension": "program_requirements",
    }
    baseline = {
        "typed_row_id": "91111111-1111-4111-8111-111111111111",
        "typed_value": "Not specified",
        "row_sha256": "1" * 64,
        "export_sha256": "2" * 64,
        "origin_kind": "night_voyager_typed_governed_row",
    }
    dataset: dict[str, Any] = {
        "schema_version": "night-voyager.evidence-loop-holdout-dataset.v1",
        "cases": [
            {
                "payload": {
                    "identity": identity,
                    "control": {"source_claims": []},
                    "governed_dra_baseline": baseline,
                    "pre_registered_gap": {
                        "decision_dimension": "program_requirements",
                        "fact_key": "program.language",
                        "expected_value": "English",
                    },
                    "expected_relations": [{"relation": "independent"}],
                },
                "oracle": {
                    "expected_gap_closed": True,
                    "expected_novel_accepted_units": 1,
                    "expected_duplicate_count": 0,
                    "expected_conflict_count": 0,
                },
            }
        ],
    }
    captured_unit = _unit(
        source="a",
        evidence="b",
        value="English",
        path="mke:captured",
        access_kind="source_access",
        origin_kind="untrusted_evidence",
    )
    capture = {
        "cases": [
            {
                "identity": identity,
                "selection": _case()["selection"],
                "mke_units": [captured_unit],
                "guardrails": _case()["guardrails"],
            }
        ]
    }

    normalized = normalize_revealed_dataset(dataset, capture)
    result = evaluate_case_document(normalized["cases"][0])

    assert normalized["expected_case_kinds"] == ["positive"]
    assert result["mechanism_metrics"]["acquisition_count"] == 1
    mke_unit = result["arms"]["mke"]["units"][0]
    combined_unit = next(
        unit
        for unit in result["arms"]["combined"]["units"]
        if unit["evaluation_canonical_evidence_id"] == "b" * 64
    )
    assert mke_unit == combined_unit


def test_revealed_exact_duplicate_reuses_canonical_identity_and_paths() -> None:
    identity = {
        "holdout_id": "61111111-1111-4111-8111-111111111111",
        "case_id": "71111111-1111-4111-8111-111111111111",
        "case_revision": 1,
        "query_id": "81111111-1111-4111-8111-111111111111",
        "decision_dimension": "program_requirements",
    }
    dataset: dict[str, Any] = {
        "cases": [
            {
                "payload": {
                    "identity": identity,
                    "governed_dra_baseline": {
                        "typed_row_id": "91111111-1111-4111-8111-111111111111",
                        "typed_value": "English",
                        "row_sha256": "1" * 64,
                        "export_sha256": "2" * 64,
                        "origin_kind": "night_voyager_typed_governed_row",
                    },
                    "pre_registered_gap": {
                        "decision_dimension": "program_requirements",
                        "fact_key": "program.language",
                        "expected_value": "English",
                    },
                    "expected_relations": [
                        {
                            "relation": "exact_duplicate",
                            "left_dataset_source_id": "source-1",
                            "right_typed_row_id": (
                                "91111111-1111-4111-8111-111111111111"
                            ),
                        }
                    ],
                },
                "oracle": {
                    "expected_gap_closed": False,
                    "expected_novel_accepted_units": 0,
                    "expected_duplicate_count": 1,
                    "expected_conflict_count": 0,
                },
            }
        ]
    }
    captured_unit = {
        **_unit(
            source="a",
            evidence="b",
            value="English",
            path="mke:captured",
            access_kind="source_access",
            origin_kind="untrusted_evidence",
        ),
        "dataset_source_id": "source-1",
    }
    normalized = normalize_revealed_dataset(
        dataset,
        {
            "cases": [
                {
                    "identity": identity,
                    "selection": _case()["selection"],
                    "mke_units": [captured_unit],
                    "guardrails": _case()["guardrails"],
                }
            ]
        },
    )

    result = evaluate_case_document(normalized["cases"][0])

    assert result["target_metrics"]["novel_source_bound_units"] == 0
    duplicate = result["arms"]["combined"]["units"][0]
    assert duplicate["provenance_paths"] == [
        "dra:91111111-1111-4111-8111-111111111111",
        "mke:captured",
    ]
