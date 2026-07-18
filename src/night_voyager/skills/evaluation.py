from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from importlib import resources
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import StringConstraints, ValidationError, field_validator, model_validator

from night_voyager.collaboration.models import FactKey, IntendedFieldProposal
from night_voyager.collaboration.policy import project_candidate_state, role_allows_fact
from night_voyager.decision.models import BriefRoute, ReviewAction, ReviewCommand
from night_voyager.decision.policy import build_timeline_plan, eligible_route_ids
from night_voyager.dra.models import DraRunStateProjectionV1
from night_voyager.evidence.mke_contract import SearchLibrarySuccessV1
from night_voyager.evidence.mke_models import (
    CandidateStoreNoMatch,
    EvidenceQuery,
    M4BManifestV1,
)
from night_voyager.evidence.mke_projection import project_search_candidate
from night_voyager.identity.models import ActorRole
from night_voyager.planning.fixtures import build_dra_fallback_scenario
from night_voyager.planning.models import (
    Country,
    EvidenceAuthority,
    PlanningInput,
    RouteOutcome,
)
from night_voyager.planning.policy import evaluate_planning_run
from night_voyager.skills.models import (
    FrozenModel,
    SemanticVersion,
    Sha256,
    SkillEvaluationStatus,
    SkillKey,
    canonical_sha256,
)
from night_voyager.skills.registry import (
    SkillRuntimeIncompatibility,
    SkillRuntimeRegistry,
)

AssertionId = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z0-9][a-z0-9.-]{0,159}$"),
]

EXPECTED_ASSERTION_IDS: dict[tuple[SkillKey, str], tuple[str, ...]] = {
    (SkillKey.STUDENT_PROFILE_INTAKE, "1.0.0"): (
        "student-profile-intake.cross-role-fact-rejected",
        "student-profile-intake.unconfirmed-remains-unconfirmed",
        "student-profile-intake.unsafe-value-rejected",
    ),
    (SkillKey.STUDY_DESTINATION_COMPARE, "1.0.0"): (
        "study-destination-compare.australia-conditional",
        "study-destination-compare.baseline-hash-drift-failed",
        "study-destination-compare.budget-refusal-blocked",
        "study-destination-compare.malaysia-blocked",
    ),
    (SkillKey.STUDY_DESTINATION_COMPARE, "1.0.1"): (
        "study-destination-compare.australia-conditional",
        "study-destination-compare.baseline-hash-drift-failed",
        "study-destination-compare.budget-refusal-blocked",
        "study-destination-compare.duplicate-claim-failed",
        "study-destination-compare.malaysia-blocked",
        "study-destination-compare.untrusted-evidence-failed",
    ),
    (SkillKey.EVIDENCE_RESEARCH, "1.0.0"): (
        "evidence-research.fallback-remains-untrusted",
        "evidence-research.terminal-invalid-not-promotable",
    ),
    (SkillKey.DOCUMENT_EVIDENCE_RETRIEVAL, "1.0.0"): (
        "document-evidence-retrieval.active-no-match-not-evidence",
        "document-evidence-retrieval.no-match-not-sufficient",
    ),
    (SkillKey.FAMILY_DECISION_BRIEF, "1.0.0"): (
        "family-decision-brief.blocked-route-ineligible",
        "family-decision-brief.unreviewed-run-rejected",
    ),
    (SkillKey.APPLICATION_TIMELINE_GUARD, "1.0.0"): (
        "application-timeline-guard.dates-deterministic",
        "application-timeline-guard.no-decision-no-timeline",
    ),
}


class SkillEvaluationIncompatibility(ValueError):
    """Checked-in evaluation evidence is incompatible with the runtime catalog."""


class SkillEvaluationAssertionV1(FrozenModel):
    assertion_id: AssertionId
    expected_sha256: Sha256


class SkillEvaluationDatasetV1(FrozenModel):
    skill_key: SkillKey
    version: SemanticVersion
    dataset_id: Annotated[
        str,
        StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]{0,127}$"),
    ]
    dataset_version: SemanticVersion
    assertions: tuple[SkillEvaluationAssertionV1, ...]
    dataset_sha256: Sha256

    @field_validator("assertions")
    @classmethod
    def sorted_unique_assertions(
        cls,
        value: tuple[SkillEvaluationAssertionV1, ...],
    ) -> tuple[SkillEvaluationAssertionV1, ...]:
        identifiers = tuple(item.assertion_id for item in value)
        if (
            not identifiers
            or identifiers != tuple(sorted(identifiers))
            or len(identifiers) != len(set(identifiers))
        ):
            raise ValueError("assertion IDs must be non-empty, sorted, and unique")
        return value

    @model_validator(mode="after")
    def canonical_dataset_hash(self) -> Self:
        projection = self.model_dump(mode="json", exclude={"dataset_sha256"})
        if self.dataset_sha256 != canonical_sha256(projection):
            raise ValueError("dataset hash does not match canonical assertions")
        return self


class SkillEvaluationManifestV1(FrozenModel):
    schema_version: Literal[1]
    manifest_id: Literal["night-voyager.skill-eval-manifest"]
    manifest_version: Literal["1.0.0"]
    evaluator_id: Literal["night-voyager.deterministic-skill-evaluator"]
    evaluator_version: Literal["v1"]
    datasets: tuple[SkillEvaluationDatasetV1, ...]
    manifest_sha256: Sha256

    @model_validator(mode="after")
    def exact_datasets(self) -> Self:
        actual = tuple((dataset.skill_key, dataset.version) for dataset in self.datasets)
        if actual != tuple(EXPECTED_ASSERTION_IDS):
            raise ValueError("evaluation manifest must contain the exact supported datasets")
        for dataset in self.datasets:
            identifiers = tuple(item.assertion_id for item in dataset.assertions)
            if identifiers != EXPECTED_ASSERTION_IDS[(dataset.skill_key, dataset.version)]:
                raise ValueError(
                    "evaluation dataset assertion IDs do not match the stable contract"
                )
        projection = self.model_dump(mode="json", exclude={"manifest_sha256"})
        if self.manifest_sha256 != canonical_sha256(projection):
            raise ValueError("evaluation manifest hash does not match canonical content")
        return self


class SkillEvaluationAssertionResultV1(FrozenModel):
    assertion_id: AssertionId
    observed_sha256: Sha256
    passed: bool


class SkillEvaluationResultV1(FrozenModel):
    schema_version: Literal[1]
    skill_key: SkillKey
    version: SemanticVersion
    evaluator_id: Literal["night-voyager.deterministic-skill-evaluator"]
    evaluator_version: Literal["v1"]
    dataset_id: str
    dataset_version: SemanticVersion
    dataset_sha256: Sha256
    assertions: tuple[SkillEvaluationAssertionResultV1, ...]
    failed_assertion_ids: tuple[AssertionId, ...]
    status: SkillEvaluationStatus
    output_sha256: Sha256

    @model_validator(mode="after")
    def computed_result_contract(self) -> Self:
        identifiers = tuple(item.assertion_id for item in self.assertions)
        if identifiers != tuple(sorted(identifiers)) or len(identifiers) != len(
            set(identifiers)
        ):
            raise ValueError("result assertion IDs must be sorted and unique")
        failed = tuple(item.assertion_id for item in self.assertions if not item.passed)
        if self.failed_assertion_ids != failed:
            raise ValueError("failed assertion projection does not match results")
        expected_status = (
            SkillEvaluationStatus.FAILED if failed else SkillEvaluationStatus.PASSED
        )
        if self.status is not expected_status:
            raise ValueError("evaluation status must be computed from assertion results")
        projection = self.model_dump(mode="json", exclude={"output_sha256"})
        if self.output_sha256 != canonical_sha256(projection):
            raise ValueError("evaluation output hash does not match canonical result")
        return self


class SkillEvaluator:
    def __init__(
        self,
        manifest: SkillEvaluationManifestV1,
        registry: SkillRuntimeRegistry,
    ) -> None:
        self.manifest = manifest
        self.registry = registry
        self._datasets = {
            (dataset.skill_key, dataset.version): dataset
            for dataset in manifest.datasets
        }
        for dataset in manifest.datasets:
            try:
                entry = registry.get(dataset.skill_key, dataset.version)
            except SkillRuntimeIncompatibility as error:
                raise SkillEvaluationIncompatibility(
                    "evaluation dataset has no supported runtime entry"
                ) from error
            identity = (
                entry.evaluation_dataset_id,
                entry.evaluation_dataset_version,
                entry.evaluation_dataset_sha256,
            )
            if identity != (
                dataset.dataset_id,
                dataset.dataset_version,
                dataset.dataset_sha256,
            ):
                raise SkillEvaluationIncompatibility(
                    "evaluation dataset identity does not match runtime entry"
                )

    @classmethod
    def from_json(
        cls,
        payload: bytes | str,
        registry: SkillRuntimeRegistry,
    ) -> SkillEvaluator:
        return cls(SkillEvaluationManifestV1.model_validate_json(payload), registry)

    @classmethod
    def load_packaged(
        cls,
        registry: SkillRuntimeRegistry | None = None,
    ) -> SkillEvaluator:
        resource = resources.files("night_voyager.skills").joinpath("data", "eval-manifest-v1.json")
        return cls.from_json(
            resource.read_bytes(),
            registry or SkillRuntimeRegistry.load_packaged(),
        )

    def evaluate(
        self,
        skill_key: SkillKey | str,
        semantic_version: str,
    ) -> SkillEvaluationResultV1:
        try:
            key = SkillKey(skill_key)
            dataset = self._datasets[(key, semantic_version)]
        except (KeyError, ValueError) as error:
            raise SkillEvaluationIncompatibility("unsupported evaluation key/version") from error

        assertion_results = tuple(
            _evaluate_assertion(assertion) for assertion in dataset.assertions
        )
        failed = tuple(
            result.assertion_id for result in assertion_results if not result.passed
        )
        status = SkillEvaluationStatus.FAILED if failed else SkillEvaluationStatus.PASSED
        projection = {
            "schema_version": 1,
            "skill_key": key.value,
            "version": semantic_version,
            "evaluator_id": self.manifest.evaluator_id,
            "evaluator_version": self.manifest.evaluator_version,
            "dataset_id": dataset.dataset_id,
            "dataset_version": dataset.dataset_version,
            "dataset_sha256": dataset.dataset_sha256,
            "assertions": [
                item.model_dump(mode="json") for item in assertion_results
            ],
            "failed_assertion_ids": list(failed),
            "status": status.value,
        }
        return SkillEvaluationResultV1.model_validate_json(
            json.dumps(
                {
                    **projection,
                    "output_sha256": canonical_sha256(projection),
                }
            )
        )


def _evaluate_assertion(
    assertion: SkillEvaluationAssertionV1,
) -> SkillEvaluationAssertionResultV1:
    evaluator = _ASSERTION_EVALUATORS[assertion.assertion_id]
    observed_sha256 = canonical_sha256(evaluator())
    return SkillEvaluationAssertionResultV1(
        assertion_id=assertion.assertion_id,
        observed_sha256=observed_sha256,
        passed=observed_sha256 == assertion.expected_sha256,
    )


def _student_cross_role() -> dict[str, object]:
    return {
        "allowed": role_allows_fact(
            ActorRole.STUDENT,
            FactKey.FAMILY_BUDGET,
        )
    }


def _student_unconfirmed() -> dict[str, object]:
    now = datetime(2026, 7, 18, tzinfo=UTC)
    state = project_candidate_state(
        decision=None,
        pinned_revision=1,
        current_revision=1,
        expires_at=now + timedelta(days=1),
        now=now,
    )
    return {"state": state.value}


def _student_unsafe_value() -> dict[str, object]:
    try:
        IntendedFieldProposal(
            schema_version=1,
            fact_key=FactKey.STUDENT_INTENDED_FIELD,
            value="api_key=synthetic-placeholder",
        )
    except ValidationError:
        return {"validation": "rejected"}
    return {"validation": "accepted"}


def _planning_input() -> PlanningInput:
    organization_id = "10000000-0000-0000-0000-000000000001"
    source_pack_id = "50000000-0000-0000-0000-000000000001"
    source_entry_id = "51000000-0000-0000-0000-000000000001"
    source_sha256 = "a" * 64
    evidence = [
        {
            "schema_version": 1,
            "organization_id": organization_id,
            "evidence_id": f"60000000-0000-0000-0000-00000000000{index}",
            "claim": claim,
            "source_pack_id": source_pack_id,
            "source_pack_version": 1,
            "source_entry_id": source_entry_id,
            "source_sha256": source_sha256,
            "authority": "accepted_synthetic_demo",
        }
        for index, claim in enumerate(
            (
                "australia_program_fit",
                "australia_tuition",
                "australia_living_cost",
                "australia_fx",
            ),
            start=1,
        )
    ]
    return PlanningInput.model_validate(
        {
            "schema_version": 1,
            "organization_id": organization_id,
            "case": {
                "schema_version": 1,
                "organization_id": organization_id,
                "case_id": "40000000-0000-0000-0000-000000000001",
                "revision": 1,
                "student": {
                    "schema_version": 1,
                    "intended_field": "computing",
                    "preferred_countries": ["australia", "japan", "malaysia"],
                    "intake": "2027-02",
                },
                "family": {
                    "schema_version": 1,
                    "risk_tolerance": "high",
                    "japan_risk_accepted": False,
                    "budget": {
                        "schema_version": 1,
                        "currency": "CNY",
                        "period": "program_total",
                        "preferred_minor": 34_000_000,
                        "hard_ceiling_minor": 40_000_000,
                        "elasticity_bps": 1_000,
                        "refused": False,
                    },
                },
            },
            "source_pack": {
                "schema_version": 1,
                "organization_id": organization_id,
                "pack_id": source_pack_id,
                "version": 1,
                "entries": [
                    {
                        "schema_version": 1,
                        "entry_id": source_entry_id,
                        "path": "sources/australia.txt",
                        "sha256": source_sha256,
                        "snapshot_date": "2026-07-01",
                        "publisher": "Synthetic Demo Publisher",
                        "institution": "Synthetic Australia Institution",
                        "canonical_url": "https://example.invalid/australia",
                        "freshness_days": 365,
                        "redistribution_class": "synthetic_public",
                        "evidence_class": "synthetic_demo",
                        "coverage": [
                            "australia_program_fit",
                            "australia_tuition",
                            "australia_living_cost",
                            "australia_fx",
                        ],
                        "known_gaps": [],
                    }
                ],
            },
            "evidence": evidence,
            "costs": [
                {
                    "schema_version": 1,
                    "organization_id": organization_id,
                    "country": "australia",
                    "intake": "2027-02",
                    "period": "program_total",
                    "currency": "AUD",
                    "tuition_minor": 4_000_000,
                    "living_minor": 2_500_000,
                    "fx_rate": "4.70",
                    "fx_source": "Synthetic central-bank fixture",
                    "fx_date": "2026-07-01",
                    "tuition_evidence_id": evidence[1]["evidence_id"],
                    "living_evidence_id": evidence[2]["evidence_id"],
                    "fx_evidence_id": evidence[3]["evidence_id"],
                }
            ],
            "rankings": [],
        }
    )


def _route_outcome(country: Country) -> dict[str, object]:
    result = evaluate_planning_run(_planning_input())
    route = next(item for item in result.routes if item.country is country)
    return {"outcome": route.outcome.value}


def _budget_refusal() -> dict[str, object]:
    baseline = _planning_input()
    budget = baseline.case.family.budget.model_copy(
        update={
            "preferred_minor": None,
            "hard_ceiling_minor": None,
            "refused": True,
        }
    )
    refused = baseline.model_copy(
        update={
            "case": baseline.case.model_copy(
                update={
                    "family": baseline.case.family.model_copy(
                        update={"budget": budget}
                    )
                }
            )
        }
    )
    result = evaluate_planning_run(refused)
    australia = next(item for item in result.routes if item.country is Country.AUSTRALIA)
    return {"outcome": australia.outcome.value, "reason_code": australia.reason_code}


def _planning_hash_drift() -> dict[str, object]:
    baseline = _planning_input()
    drifted = baseline.model_copy(
        update={
            "evidence": (
                baseline.evidence[0].model_copy(update={"source_sha256": "f" * 64}),
                *baseline.evidence[1:],
            )
        }
    )
    result = evaluate_planning_run(drifted)
    return {"reason_code": result.reason_code, "state": result.state.value}


def _planning_duplicate_claim() -> dict[str, object]:
    baseline = _planning_input()
    duplicate = baseline.model_copy(
        update={"evidence": (*baseline.evidence, baseline.evidence[0])}
    )
    result = evaluate_planning_run(duplicate)
    return {"reason_code": result.reason_code, "state": result.state.value}


def _planning_untrusted_evidence() -> dict[str, object]:
    baseline = _planning_input()
    untrusted = baseline.model_copy(
        update={
            "evidence": (
                baseline.evidence[0].model_copy(
                    update={"authority": EvidenceAuthority.UNTRUSTED_CANDIDATE}
                ),
                *baseline.evidence[1:],
            )
        }
    )
    result = evaluate_planning_run(untrusted)
    return {"reason_code": result.reason_code, "state": result.state.value}


def _dra_terminal_invalid() -> dict[str, object]:
    state = DraRunStateProjectionV1(
        run_id="run_00000000000000000000000000000001",
        state_version=1,
        execution_status="completed_with_fallback",
        review_status="not_required",
        delivery_status="ready",
    )
    return {"disposition": state.disposition}


def _dra_fallback_authority() -> dict[str, object]:
    fallback = build_dra_fallback_scenario(_planning_input())
    return {"authority": fallback.evidence[0].authority.value}


def _mke_no_match() -> CandidateStoreNoMatch:
    manifest = M4BManifestV1.model_validate_json(
        json.dumps(
            {
                "schema_version": "night_voyager.m4b_manifest.v1",
                "organization_id": "10000000-0000-0000-0000-000000000001",
                "source_pack_id": "50000000-0000-0000-0000-000000000001",
                "source_pack_version": 1,
                "sources": [
                    {
                        "schema_version": "night_voyager.m4b_source_entry.v1",
                        "entry_id": "51000000-0000-0000-0000-000000000001",
                        "path": "sources/synthetic.pdf",
                        "sha256": "a" * 64,
                        "media_type": "application/pdf",
                        "claim": "australia_program_fit",
                        "evidence_role": "program_fit",
                        "allowed_locators": [{"kind": "page", "start": 1, "end": 1}],
                    }
                ],
            }
        )
    )
    query = EvidenceQuery.model_validate_json(
        json.dumps(
            {
                "schema_version": 1,
                "organization_id": "10000000-0000-0000-0000-000000000001",
                "source_pack_id": "50000000-0000-0000-0000-000000000001",
                "source_pack_version": 1,
                "claim": "australia_program_fit",
                "evidence_role": "program_fit",
                "query": "absent synthetic token",
                "allowed_locator_kinds": ["page"],
                "limit": 1,
            }
        )
    )
    response = SearchLibrarySuccessV1.model_validate_json(
        json.dumps(
            {
                "schema_version": "mke.search_library_response.v1",
                "ok": True,
                "query": "absent synthetic token",
                "observation": {
                    "schema_version": "mke.active_publication_observation.v1",
                    "library_id": "local",
                    "state": "active",
                    "source_count": 1,
                    "active_publication_count": 1,
                    "active_evidence_count": 1,
                },
                "results": [],
            }
        )
    )
    candidate = project_search_candidate(query, manifest, response)
    if not isinstance(candidate, CandidateStoreNoMatch):
        raise ValueError("active zero-hit projection must remain a no-match candidate")
    return candidate


def _mke_no_match_kind() -> dict[str, object]:
    _mke_no_match()
    return {"candidate_kind": "no_match", "evidence_count": 0}


def _mke_no_match_sufficiency() -> dict[str, object]:
    _mke_no_match()
    return {"sufficient": False}


def _blocked_route_ineligible() -> dict[str, object]:
    route = BriefRoute(
        route_id=UUID(int=1),
        country=Country.MALAYSIA,
        outcome=RouteOutcome.BLOCKED,
        reason_code="direct_program_fit_evidence_absent",
    )
    return {"eligible_route_ids": [str(item) for item in eligible_route_ids((route,))]}


def _unreviewed_run_rejected() -> dict[str, object]:
    try:
        ReviewCommand(
            schema_version=1,
            case_id=UUID(int=1),
            planning_run_id=UUID(int=2),
            expected_case_revision=1,
            action=ReviewAction.REQUEST_REVISION,
            review_id=UUID(int=3),
            eligible_route_ids=(),
            risk_acceptances=(),
            reviewer_notes="Needs advisor review",
            brief_id=UUID(int=4),
        )
    except ValidationError:
        return {"brief_created": False}
    return {"brief_created": True}


def _timeline_for_decision(country: Country | None) -> object | None:
    if country is None:
        return None
    return build_timeline_plan(country, "2027-02", date(2026, 7, 18))


def _no_decision_no_timeline() -> dict[str, object]:
    return {"timeline_created": _timeline_for_decision(None) is not None}


def _timeline_dates() -> dict[str, object]:
    first = build_timeline_plan(Country.AUSTRALIA, "2027-02", date(2026, 7, 18))
    second = build_timeline_plan(Country.AUSTRALIA, "2027-02", date(2026, 7, 18))
    if first != second:
        raise ValueError("timeline policy must be deterministic")
    return {"milestones": [item.due_date.isoformat() for item in first.milestones]}


_ASSERTION_EVALUATORS: dict[str, Callable[[], dict[str, object]]] = {
    "student-profile-intake.cross-role-fact-rejected": _student_cross_role,
    "student-profile-intake.unconfirmed-remains-unconfirmed": _student_unconfirmed,
    "student-profile-intake.unsafe-value-rejected": _student_unsafe_value,
    "study-destination-compare.australia-conditional": lambda: _route_outcome(
        Country.AUSTRALIA
    ),
    "study-destination-compare.baseline-hash-drift-failed": _planning_hash_drift,
    "study-destination-compare.budget-refusal-blocked": _budget_refusal,
    "study-destination-compare.duplicate-claim-failed": _planning_duplicate_claim,
    "study-destination-compare.malaysia-blocked": lambda: _route_outcome(
        Country.MALAYSIA
    ),
    "study-destination-compare.untrusted-evidence-failed": _planning_untrusted_evidence,
    "evidence-research.fallback-remains-untrusted": _dra_fallback_authority,
    "evidence-research.terminal-invalid-not-promotable": _dra_terminal_invalid,
    "document-evidence-retrieval.active-no-match-not-evidence": _mke_no_match_kind,
    "document-evidence-retrieval.no-match-not-sufficient": _mke_no_match_sufficiency,
    "family-decision-brief.blocked-route-ineligible": _blocked_route_ineligible,
    "family-decision-brief.unreviewed-run-rejected": _unreviewed_run_rejected,
    "application-timeline-guard.dates-deterministic": _timeline_dates,
    "application-timeline-guard.no-decision-no-timeline": _no_decision_no_timeline,
}

if set(_ASSERTION_EVALUATORS) != {
    assertion_id
    for assertion_ids in EXPECTED_ASSERTION_IDS.values()
    for assertion_id in assertion_ids
}:
    raise RuntimeError("deterministic evaluator does not cover the exact assertion catalog")
