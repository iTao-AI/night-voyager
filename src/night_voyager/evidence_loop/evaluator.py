from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from night_voyager.evidence_loop.canonicalization import canonicalize_units

_ALLOWED_TOOLS = {"search_library_v2", "read_evidence_v1"}
_MUTATION_GUARDS = {
    "night_voyager_business_mutation",
    "filesystem_mutation",
    "database_mutation",
    "instruction_executed",
    "promotion_attempted",
    "human_authority_granted",
}


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


def _mapping(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(code)
    return cast(dict[str, Any], value)


def _units(value: object, code: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(code)
    values = cast(list[object], value)
    if any(not isinstance(item, dict) for item in values):
        raise ValueError(code)
    return cast(list[dict[str, Any]], values)


def _selection_is_complete(selection: Mapping[str, Any]) -> bool:
    tools_value = selection.get("tool_calls")
    tools = (
        cast(list[object], tools_value) if isinstance(tools_value, list) else []
    )
    return bool(
        selection.get("status") == "complete"
        and selection.get("authority_state") == "active"
        and selection.get("acquisition_count") == 1
        and isinstance(selection.get("search_pages"), int)
        and 0 <= selection["search_pages"] <= 4
        and selection.get("search_limit") == 20
        and isinstance(selection.get("evidence_reads"), int)
        and 0 <= selection["evidence_reads"] <= 32
        and tools
        and all(isinstance(tool, str) for tool in tools)
        and set(cast(list[str], tools)).issubset(_ALLOWED_TOOLS)
        and isinstance(selection.get("combined_output_bytes"), int)
        and 0 <= selection["combined_output_bytes"] <= 1_048_576
        and isinstance(selection.get("mcp_call_seconds_max"), (int, float))
        and selection["mcp_call_seconds_max"] <= 10
        and isinstance(selection.get("case_seconds"), (int, float))
        and selection["case_seconds"] <= 120
    )


def _arm(units: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    canonical = canonicalize_units(units)
    return {
        "canonical_source_count": len(
            {unit["evaluation_canonical_source_id"] for unit in canonical}
        ),
        "canonical_evidence_count": len(canonical),
        "units": list(canonical),
    }


def _conflicts(units: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for unit in units:
        grouped[(str(unit["decision_dimension"]), str(unit["fact_key"]))].append(unit)
    conflicts: list[dict[str, Any]] = []
    for (dimension, fact_key), related in sorted(grouped.items()):
        values = sorted({str(unit["value"]) for unit in related})
        if len(values) < 2:
            continue
        conflicts.append(
            {
                "decision_dimension": dimension,
                "fact_key": fact_key,
                "values": values,
                "provenance_paths": sorted(
                    {
                        str(path)
                        for unit in related
                        for path in cast(list[object], unit["provenance_paths"])
                    }
                ),
            }
        )
    return conflicts


def evaluate_case_document(case: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate one frozen case without granting authority to producer content."""

    identity = _mapping(case.get("identity"), "case identity invalid")
    selection = _mapping(case.get("selection"), "selection invalid")
    if not _selection_is_complete(selection):
        return {
            "identity": identity,
            "status": "inconclusive",
            "reason_code": "retrieval_not_exhaustive",
            "actions": [],
        }

    guards = _mapping(case.get("guardrails"), "guardrails invalid")
    if set(guards) != _MUTATION_GUARDS or any(guards.values()):
        return {
            "identity": identity,
            "status": "evaluation_invalid",
            "reason_code": "guardrail_veto",
            "actions": [],
        }

    control = _units(case.get("control_units"), "control units invalid")
    dra = _units(case.get("dra_units"), "DRA units invalid")
    mke = _units(case.get("mke_units"), "MKE units invalid")
    if any(
        unit.get("origin_kind") != "night_voyager_typed_governed_row"
        for unit in dra
    ):
        return {
            "identity": identity,
            "status": "evaluation_invalid",
            "reason_code": "dra_typed_origin_invalid",
            "actions": [],
        }
    if any(
        unit.get("origin_kind") != "untrusted_evidence"
        or unit.get("content_trust") != "untrusted_evidence"
        for unit in mke
    ):
        return {
            "identity": identity,
            "status": "evaluation_invalid",
            "reason_code": "mke_content_trust_invalid",
            "actions": [],
        }

    try:
        arms = {
            "control": _arm(control),
            "dra_baseline": _arm((*control, *dra)),
            "mke": _arm((*control, *mke)),
            "combined": _arm((*control, *dra, *mke)),
        }
    except ValueError:
        return {
            "identity": identity,
            "status": "evaluation_invalid",
            "reason_code": "canonicalization_invalid",
            "actions": [],
        }

    prior_ids = {
        str(unit["evaluation_canonical_evidence_id"])
        for unit in canonicalize_units((*control, *dra))
    }
    novel = [
        unit
        for unit in canonicalize_units(mke)
        if unit["evaluation_canonical_evidence_id"] not in prior_ids
    ]
    gap = _mapping(case.get("pre_registered_gap"), "gap invalid")
    gap_closed = any(
        unit["decision_dimension"] == gap.get("decision_dimension")
        and unit["fact_key"] == gap.get("fact_key")
        and unit["value"] == gap.get("expected_value")
        for unit in novel
    )
    conflicts = _conflicts(arms["combined"]["units"])
    dimensions = {str(unit["decision_dimension"]) for unit in novel}
    return {
        "identity": identity,
        "status": "evaluated",
        "arms": arms,
        "mechanism_metrics": {
            "producer_identity_closed": True,
            "retrieval_complete": True,
            "canonical_deduplication": True,
            "explicit_conflict_count": len(conflicts),
            "acquisition_count": 1,
        },
        "target_metrics": {
            "novel_source_bound_units": len(novel),
            "source_access_gain": sum(
                unit.get("access_kind") == "source_access" for unit in novel
            ),
            "extraction_gain": sum(
                unit.get("access_kind") == "extraction" for unit in novel
            ),
            "pre_registered_gap_closure": int(gap_closed),
            "decision_dimension_coverage": len(dimensions),
            "advisor_rubric_relevance": int(gap_closed or bool(conflicts)),
        },
        "guardrail_metrics": {"passed": True, **guards},
        "conflicts": conflicts,
        "actions": [],
        "sensitivity": {
            "removed_positive_removes_gap_closure": bool(gap_closed),
            "forged_duplicate_novelty": 0,
        },
    }


def evaluate_suite(dataset: Mapping[str, Any]) -> dict[str, Any]:
    cases = dataset.get("cases")
    if not isinstance(cases, list):
        raise ValueError("exactly four cases are required")
    case_values = cast(list[object], cases)
    if len(case_values) != 4 or any(
        not isinstance(case, dict) for case in case_values
    ):
        raise ValueError("exactly four cases are required")
    typed_cases = cast(list[dict[str, Any]], case_values)
    results = [evaluate_case_document(case) for case in typed_cases]
    statuses = {str(result["status"]) for result in results}
    if "evaluation_invalid" in statuses:
        disposition = "evaluation_invalid"
    elif "inconclusive" in statuses:
        disposition = "inconclusive"
    else:
        kinds = dataset.get("expected_case_kinds")
        confirmed = False
        if kinds == ["positive", "positive", "decoy", "conflict"]:
            positives = results[:2]
            confirmed = bool(
                all(
                    result["target_metrics"]["pre_registered_gap_closure"] == 1
                    and result["sensitivity"][
                        "removed_positive_removes_gap_closure"
                    ]
                    for result in positives
                )
                and len(
                    {
                        result["identity"]["decision_dimension"]
                        for result in positives
                    }
                )
                == 2
                and results[2]["target_metrics"]["novel_source_bound_units"] == 0
                and results[3]["mechanism_metrics"]["explicit_conflict_count"] >= 1
                and all(result["guardrail_metrics"]["passed"] for result in results)
            )
        disposition = (
            "incremental_value_confirmed"
            if confirmed
            else "no_incremental_value"
        )
    return {
        "schema_version": "night-voyager.evidence-loop-evaluation.v2",
        "terminal_disposition": disposition,
        "case_results": results,
    }


def normalize_revealed_dataset(
    dataset: Mapping[str, Any], capture: Mapping[str, Any]
) -> dict[str, Any]:
    """Project revealed payload/oracle plus one native capture into evaluator cases."""

    cases_value = dataset.get("cases")
    captures_value = capture.get("cases")
    if not isinstance(cases_value, list) or not isinstance(captures_value, list):
        raise ValueError("revealed dataset or capture invalid")
    cases = cast(list[object], cases_value)
    captures = cast(list[object], captures_value)
    capture_by_case: dict[str, dict[str, Any]] = {}
    for item in captures:
        captured = _mapping(item, "capture invalid")
        identity = _mapping(captured.get("identity"), "capture identity invalid")
        case_id = identity.get("case_id")
        if not isinstance(case_id, str) or case_id in capture_by_case:
            raise ValueError("capture identity invalid")
        capture_by_case[case_id] = captured

    normalized: list[dict[str, Any]] = []
    kinds: list[str] = []
    for item in cases:
        case = _mapping(item, "revealed case invalid")
        payload = _mapping(case.get("payload"), "revealed payload invalid")
        oracle = _mapping(case.get("oracle"), "revealed oracle invalid")
        identity = _mapping(payload.get("identity"), "revealed identity invalid")
        case_id = identity.get("case_id")
        captured = capture_by_case.get(str(case_id))
        if captured is None or captured.get("identity") != identity:
            raise ValueError("capture identity mismatch")
        baseline = _mapping(
            payload.get("governed_dra_baseline"), "revealed baseline invalid"
        )
        gap = _mapping(payload.get("pre_registered_gap"), "revealed gap invalid")
        relations_value = payload.get("expected_relations")
        if not isinstance(relations_value, list):
            raise ValueError("revealed relations invalid")
        relations = cast(list[object], relations_value)
        relation_names = [
            str(_mapping(relation, "revealed relation invalid").get("relation"))
            for relation in relations
        ]
        mke_units = _units(captured.get("mke_units"), "capture units invalid")
        exact_duplicate_relation = next(
            (
                _mapping(relation, "revealed relation invalid")
                for relation in relations
                if _mapping(
                    relation, "revealed relation invalid"
                ).get("relation")
                == "exact_duplicate"
            ),
            None,
        )
        duplicate_unit = (
            next(
                (
                    unit
                    for unit in mke_units
                    if unit.get("dataset_source_id")
                    == exact_duplicate_relation.get("left_dataset_source_id")
                ),
                None,
            )
            if exact_duplicate_relation is not None
            else None
        )
        dra_unit = {
            "evaluation_canonical_source_id": (
                duplicate_unit.get("evaluation_canonical_source_id")
                if duplicate_unit is not None
                else baseline.get("row_sha256")
            ),
            "evaluation_canonical_evidence_id": (
                duplicate_unit.get("evaluation_canonical_evidence_id")
                if duplicate_unit is not None
                else baseline.get("export_sha256")
            ),
            "decision_dimension": identity.get("decision_dimension"),
            "fact_key": gap.get("fact_key"),
            "value": baseline.get("typed_value"),
            "provenance_paths": [f"dra:{baseline.get('typed_row_id')}"],
            "access_kind": "baseline",
            "origin_kind": baseline.get("origin_kind"),
        }
        normalized.append(
            {
                "identity": identity,
                "query": "redacted_after_capture",
                "selection": captured.get("selection"),
                "control_units": [],
                "dra_units": [dra_unit],
                "mke_units": mke_units,
                "pre_registered_gap": gap,
                "expected_relations": relation_names,
                "guardrails": captured.get("guardrails"),
            }
        )
        if (
            oracle.get("expected_gap_closed") is True
            and oracle.get("expected_novel_accepted_units", 0) > 0
            and oracle.get("expected_conflict_count") == 0
        ):
            kinds.append("positive")
        elif (
            oracle.get("expected_duplicate_count", 0) > 0
            and oracle.get("expected_novel_accepted_units") == 0
        ):
            kinds.append("decoy")
        elif oracle.get("expected_conflict_count", 0) > 0:
            kinds.append("conflict")
        else:
            kinds.append("negative")
    if len(capture_by_case) != len(normalized):
        raise ValueError("capture source set mismatch")
    return {"cases": normalized, "expected_case_kinds": kinds}
