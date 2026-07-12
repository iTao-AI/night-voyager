from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from night_voyager.planning.hashing import canonical_sha256
from night_voyager.planning.models import (
    Country,
    PlanningInput,
    PlanningResult,
    SourcePackManifestV1,
    StudentCaseRevision,
)
from night_voyager.planning.policy import evaluate_planning_run

DEFAULT_MANIFEST = Path("fixtures/m3a/manifest.json")
EVAL_IDS = frozenset(
    {
        "golden_australia_conditional",
        "budget_refused",
        "japan_risk_accepted",
        "malaysia_program_fit_gap",
        "stale_cost_ranking",
        "dra_fallback_ready",
        "mke_zero_hit",
        "family_preference_conflict",
    }
)


@dataclass(frozen=True)
class ValidatedPlanningFixture:
    planning_input: PlanningInput
    result: PlanningResult
    manifest_sha256: str
    evidence_projection_sha256: str
    output_sha256: str
    eval_assertions: dict[str, str]

    def snapshot(self) -> dict[str, str]:
        snapshot = {route.country.value: route.outcome.value for route in self.result.routes}
        snapshot["run_state"] = self.result.state.value
        return snapshot


def evaluate_stable_scenarios(fixture: ValidatedPlanningFixture) -> dict[str, str]:
    base = fixture.planning_input
    budget = base.case.family.budget
    refused_budget = budget.model_copy(
        update={"preferred_minor": None, "hard_ceiling_minor": None, "refused": True}
    )
    refused = base.model_copy(
        update={
            "case": base.case.model_copy(
                update={"family": base.case.family.model_copy(update={"budget": refused_budget})}
            )
        }
    )
    stale_ranking = base.model_copy(
        update={
            "evidence": tuple(
                item.model_copy(update={"source_sha256": "f" * 64})
                if item.claim == "australia_ranking"
                else item
                for item in base.evidence
            )
        }
    )
    zero_hit = base.model_copy(
        update={
            "evidence": tuple(
                item for item in base.evidence if item.claim != "australia_program_fit"
            )
        }
    )
    conflict_budget = budget.model_copy(
        update={"preferred_minor": 10000000, "hard_ceiling_minor": 10000000}
    )
    conflict = base.model_copy(
        update={
            "case": base.case.model_copy(
                update={"family": base.case.family.model_copy(update={"budget": conflict_budget})}
            )
        }
    )
    golden = evaluate_planning_run(base)
    japan = next(route for route in golden.routes if route.country is Country.JAPAN)
    malaysia = next(route for route in golden.routes if route.country is Country.MALAYSIA)
    return {
        "golden_australia_conditional": golden.state.value,
        "budget_refused": evaluate_planning_run(refused).state.value,
        "japan_risk_accepted": japan.outcome.value,
        "malaysia_program_fit_gap": malaysia.outcome.value,
        "stale_cost_ranking": evaluate_planning_run(stale_ranking).state.value,
        "dra_fallback_ready": golden.state.value,
        "mke_zero_hit": evaluate_planning_run(zero_hit).state.value,
        "family_preference_conflict": evaluate_planning_run(conflict).state.value,
    }


def validate_planning_fixture(
    manifest_path: Path = DEFAULT_MANIFEST,
) -> ValidatedPlanningFixture:
    payload: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_pack = SourcePackManifestV1.model_validate(payload["source_pack"])
    root = manifest_path.parent.resolve()
    for entry in source_pack.entries:
        path = (root / entry.path).resolve()
        if root not in path.parents:
            raise ValueError("source path escapes manifest root")
        import hashlib

        if hashlib.sha256(path.read_bytes()).hexdigest() != entry.sha256:
            raise ValueError(f"source hash mismatch: {entry.entry_id}")

    planning_input = PlanningInput.model_validate(
        {
            "schema_version": payload["schema_version"],
            "organization_id": payload["organization_id"],
            "case": StudentCaseRevision.model_validate(payload["case"]),
            "source_pack": source_pack,
            "evidence": payload["evidence"],
            "costs": payload["costs"],
            "rankings": payload["rankings"],
        }
    )
    result = evaluate_planning_run(planning_input)
    fixture = ValidatedPlanningFixture(
        planning_input=planning_input,
        result=result,
        manifest_sha256=canonical_sha256(source_pack.model_dump(mode="json")),
        evidence_projection_sha256=canonical_sha256(
            [item.model_dump(mode="json") for item in planning_input.evidence]
        ),
        output_sha256=canonical_sha256(result.model_dump(mode="json")),
        eval_assertions=dict(payload["eval"]),
    )
    if fixture.snapshot() != payload["expected"]:
        raise ValueError("planning snapshot does not match expected assertions")
    if set(fixture.eval_assertions) != set(EVAL_IDS):
        raise ValueError("eval manifest IDs do not match the stable M3A contract")
    if evaluate_stable_scenarios(fixture) != fixture.eval_assertions:
        raise ValueError("stable eval scenario assertions do not match policy results")
    if any(item.authority.value != "accepted_synthetic_demo" for item in planning_input.evidence):
        raise ValueError("checked-in M3A fixtures may use only accepted_synthetic_demo")
    return fixture
