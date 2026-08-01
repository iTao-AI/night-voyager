"""Canonical public-safe Slice 0 evaluation receipts."""

from __future__ import annotations

import hashlib
import json
from typing import Any, cast

from night_voyager.evidence_loop.canonicalization import (
    CANONICALIZATION_ID,
    canonical_json_bytes,
)


def _public_unit(unit: dict[str, Any]) -> dict[str, Any]:
    paths = unit.get("provenance_paths")
    path_count = len(cast(list[object], paths)) if isinstance(paths, list) else 0
    return {
        "evaluation_canonical_source_id": unit.get(
            "evaluation_canonical_source_id"
        ),
        "evaluation_canonical_evidence_id": unit.get(
            "evaluation_canonical_evidence_id"
        ),
        "decision_dimension": unit.get("decision_dimension"),
        "fact_key": unit.get("fact_key"),
        "value_sha256": hashlib.sha256(
            str(unit.get("value")).encode("utf-8")
        ).hexdigest(),
        "provenance_path_count": path_count,
        "access_kind": unit.get("access_kind"),
    }


def _public_case(result: dict[str, Any]) -> dict[str, Any]:
    projection: dict[str, Any] = {
        key: result[key]
        for key in (
            "identity",
            "status",
            "reason_code",
            "mechanism_metrics",
            "target_metrics",
            "guardrail_metrics",
            "sensitivity",
        )
        if key in result
    }
    arms_value = result.get("arms")
    if isinstance(arms_value, dict):
        arms = cast(dict[str, object], arms_value)
        projected_arms: dict[str, Any] = {}
        for name, arm_value in arms.items():
            if not isinstance(arm_value, dict):
                continue
            arm = cast(dict[str, Any], arm_value)
            units_value = arm.get("units")
            units = (
                cast(list[object], units_value)
                if isinstance(units_value, list)
                else []
            )
            projected_arms[name] = {
                "canonical_source_count": arm.get("canonical_source_count"),
                "canonical_evidence_count": arm.get("canonical_evidence_count"),
                "units": [
                    _public_unit(cast(dict[str, Any], unit))
                    for unit in units
                    if isinstance(unit, dict)
                ],
            }
        projection["arms"] = projected_arms
    conflicts_value = result.get("conflicts")
    conflicts = (
        cast(list[object], conflicts_value)
        if isinstance(conflicts_value, list)
        else []
    )
    projection["conflicts"] = [
        {
            "decision_dimension": conflict.get("decision_dimension"),
            "fact_key": conflict.get("fact_key"),
            "value_sha256s": [
                hashlib.sha256(str(value).encode("utf-8")).hexdigest()
                for value in cast(list[object], conflict.get("values", []))
            ],
            "provenance_path_count": len(
                cast(list[object], conflict.get("provenance_paths", []))
            ),
        }
        for conflict in (
            cast(dict[str, Any], value)
            for value in conflicts
            if isinstance(value, dict)
        )
    ]
    return projection


def _public_evaluation(evaluation: dict[str, Any]) -> dict[str, Any]:
    cases_value = evaluation.get("case_results")
    cases = (
        cast(list[object], cases_value)
        if isinstance(cases_value, list)
        else []
    )
    return {
        "schema_version": evaluation.get("schema_version"),
        "terminal_disposition": evaluation.get("terminal_disposition"),
        "case_results": [
            _public_case(cast(dict[str, Any], case))
            for case in cases
            if isinstance(case, dict)
        ],
    }


def build_terminal_receipt(
    evaluation: dict[str, Any],
    *,
    run_kind: str,
    artifact_bindings: dict[str, Any] | None = None,
) -> bytes:
    body = {
        "schema_version": "night-voyager.evidence-loop-receipt.v2",
        "canonicalization_id": CANONICALIZATION_ID,
        "run_kind": run_kind,
        "terminal_disposition": evaluation["terminal_disposition"],
        "evaluation": _public_evaluation(evaluation),
    }
    if artifact_bindings is not None:
        body["artifact_bindings"] = artifact_bindings
    digest = hashlib.sha256(canonical_json_bytes(body)).hexdigest()
    return canonical_json_bytes({**body, "receipt_sha256": digest})


def verify_terminal_receipt(content: bytes) -> dict[str, Any]:
    value = json.loads(content)
    if not isinstance(value, dict):
        raise ValueError("receipt must be an object")
    receipt = cast(dict[str, Any], value)
    digest = receipt.pop("receipt_sha256", None)
    actual = hashlib.sha256(canonical_json_bytes(receipt)).hexdigest()
    if digest != actual:
        raise ValueError("receipt digest mismatch")
    if receipt.get("canonicalization_id") != CANONICALIZATION_ID:
        raise ValueError("receipt canonicalization mismatch")
    evaluation_value = receipt.get("evaluation")
    if not isinstance(evaluation_value, dict):
        raise ValueError("receipt contract invalid")
    evaluation = cast(dict[str, Any], evaluation_value)
    disposition = receipt.get("terminal_disposition")
    if (
        receipt.get("schema_version")
        != "night-voyager.evidence-loop-receipt.v2"
        or receipt.get("run_kind") not in {"development", "holdout"}
        or disposition
        not in {
            "incremental_value_confirmed",
            "no_incremental_value",
            "inconclusive",
            "evaluation_invalid",
        }
        or evaluation.get("schema_version")
        != "night-voyager.evidence-loop-evaluation.v2"
        or evaluation.get("terminal_disposition") != disposition
        or not isinstance(evaluation.get("case_results"), list)
        or len(cast(list[object], evaluation["case_results"])) != 4
    ):
        raise ValueError("receipt contract invalid")
    return receipt


def seal_pre_registration_receipt(body: dict[str, Any]) -> bytes:
    digest = hashlib.sha256(canonical_json_bytes(body)).hexdigest()
    return canonical_json_bytes({**body, "pre_registration_sha256": digest})


def verify_pre_registration_receipt(content: bytes) -> dict[str, Any]:
    value = json.loads(content)
    if not isinstance(value, dict):
        raise ValueError("pre-registration must be an object")
    receipt = cast(dict[str, Any], value)
    digest = receipt.pop("pre_registration_sha256", None)
    actual = hashlib.sha256(canonical_json_bytes(receipt)).hexdigest()
    if digest != actual:
        raise ValueError("pre-registration digest mismatch")
    if (
        receipt.get("schema_version")
        != "night-voyager.evidence-loop-pre-registration.v2"
        or receipt.get("canonicalization_id") != CANONICALIZATION_ID
    ):
        raise ValueError("pre-registration identity mismatch")
    return receipt
