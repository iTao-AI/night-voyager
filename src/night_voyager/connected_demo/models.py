from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveInt,
    model_validator,
)

from night_voyager.decision.models import (
    DecisionBriefProjection,
    DecisionReceiptProjection,
    EvidenceRiskKind,
    TimelinePlan,
)
from night_voyager.planning.models import CaseState, Country, RouteOutcome
from night_voyager.planning.revision import PlanningRevisionComparisonV1
from night_voyager.tasks.models import TaskViewStatus


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DemoPhase(StrEnum):
    TASK_READY = "task-ready"
    ACTIVE_TASK = "active-task"
    REVIEW_REQUIRED = "review-required"
    FAMILY_REVIEW = "family-review"
    PLAN_READY = "plan-ready"
    TERMINAL_TASK_FAILURE = "terminal-task-failure"


class DemoPhaseV2(StrEnum):
    TASK_READY = "task_ready"
    ACTIVE_TASK = "active_task"
    REVIEW_REQUIRED = "review_required"
    REVISION_REQUESTED = "revision_requested"
    REVISION_FACT_PENDING = "revision_fact_pending"
    REPLAN_REQUIRED = "replan_required"
    REVISION_TASK_ACTIVE = "revision_task_active"
    REVISION_REVIEW_REQUIRED = "revision_review_required"
    REVISION_BLOCKED = "revision_blocked"
    FAMILY_REVIEW = "family_review"
    PLAN_READY = "plan_ready"
    TERMINAL_TASK_FAILURE = "terminal_task_failure"


class CanonicalDemoTaskInputs(FrozenModel):
    schema_version: Literal[1] = 1
    operation: Literal["generate_planning_run_v1"] = "generate_planning_run_v1"
    case_id: UUID
    expected_case_revision: PositiveInt
    source_pack_id: UUID
    source_pack_version: PositiveInt
    policy_version: Literal["m3a-policy-v1"] = "m3a-policy-v1"


class FamilyDecisionRequirements(FrozenModel):
    schema_version: Literal[1] = 1
    eligible_route_id: UUID
    currency: Literal["CNY"]
    pinned_cost_minor: PositiveInt
    hard_ceiling_minor: PositiveInt
    required_trade_offs: tuple[Literal["budget_elasticity"]]

    @model_validator(mode="after")
    def pinned_cost_is_within_ceiling(self) -> FamilyDecisionRequirements:
        if self.pinned_cost_minor > self.hard_ceiling_minor:
            raise ValueError("pinned Australia cost exceeds hard ceiling")
        return self


class PublicTaskProjection(FrozenModel):
    task_id: UUID
    row_version: PositiveInt
    status: TaskViewStatus
    public_code: str | None
    attempt_count: NonNegativeInt
    planning_run_id: UUID | None
    updated_at: datetime


class PublicPlanningRunProjection(FrozenModel):
    planning_run_id: UUID
    state: Literal["review_required"]
    source_pack_id: UUID
    source_pack_version: PositiveInt
    policy_version: Literal["m3a-policy-v1"]
    source_snapshot_date: date


class PublicPlanningRunProjectionV2(FrozenModel):
    planning_run_id: UUID
    state: Literal["review_required", "blocked"]
    source_pack_id: UUID
    source_pack_version: PositiveInt
    policy_version: Literal["m3a-policy-v1"]
    source_snapshot_date: date


class ComparisonDimensionProjection(FrozenModel):
    key: str
    outcome: str
    reason_code: str


class CostProjection(FrozenModel):
    source_currency: Literal["AUD"]
    tuition_minor: NonNegativeInt
    living_minor: NonNegativeInt
    fx_rate: Decimal
    cny_total_minor: PositiveInt
    fx_source: str
    fx_date: date


class RankingProjection(FrozenModel):
    ranking_system: str
    rank: PositiveInt
    publication_year: PositiveInt


class EvidenceDisclosure(FrozenModel):
    claim: str
    role: str
    publisher: str
    institution: str
    snapshot_date: date
    authority: Literal["accepted_synthetic_demo"]
    limitation: str
    known_gaps: tuple[str, ...]


class AdvisorRouteProjection(FrozenModel):
    route_id: UUID
    country: Country
    outcome: RouteOutcome
    reason_code: str
    eligible: bool
    dimensions: tuple[ComparisonDimensionProjection, ...]
    cost: CostProjection | None
    ranking: RankingProjection | None
    required_claims: tuple[str, ...]
    known_gaps: tuple[str, ...]


class RiskAcceptanceOption(FrozenModel):
    evidence_id: UUID
    kind: EvidenceRiskKind
    reason: str


class AdvisorReviewInputs(FrozenModel):
    planning_run_id: UUID
    expected_case_revision: PositiveInt
    eligible_route_ids: tuple[UUID, ...]
    risk_acceptance_options: tuple[RiskAcceptanceOption, ...]


class PublicRecoveryProjection(FrozenModel):
    code: str
    retry_allowed: bool
    guidance: str


class AdvisorLedgerV1(FrozenModel):
    schema_version: Literal[1] = 1
    proof_mode: Literal["synthetic-demo"] = "synthetic-demo"
    phase: DemoPhase
    case_id: UUID
    case_revision: PositiveInt
    case_state: str
    canonical_task_inputs: CanonicalDemoTaskInputs | None
    task: PublicTaskProjection | None
    planning_run: PublicPlanningRunProjection | None
    routes: tuple[AdvisorRouteProjection, ...]
    evidence: tuple[EvidenceDisclosure, ...]
    review_inputs: AdvisorReviewInputs | None
    current_brief_id: UUID | None
    recovery: PublicRecoveryProjection | None

    @model_validator(mode="after")
    def validate_phase_projection(self) -> AdvisorLedgerV1:
        if self.phase is DemoPhase.TASK_READY:
            if (
                self.canonical_task_inputs is None
                or self.task is not None
                or self.planning_run is not None
                or self.routes
                or self.evidence
                or self.review_inputs is not None
                or self.current_brief_id is not None
                or self.recovery is not None
            ):
                raise ValueError("task-ready projection contains unavailable authority")
        elif self.phase is DemoPhase.ACTIVE_TASK:
            if (
                self.canonical_task_inputs is None
                or self.task is None
                or self.task.status is not TaskViewStatus.PREPARING
                or self.planning_run is not None
                or self.routes
                or self.evidence
                or self.review_inputs is not None
                or self.current_brief_id is not None
                or self.recovery is not None
            ):
                raise ValueError("active-task projection contains unavailable authority")
        elif self.phase is DemoPhase.REVIEW_REQUIRED:
            if (
                self.task is None
                or self.task.status is not TaskViewStatus.NEEDS_ADVISOR_REVIEW
                or self.planning_run is None
                or not self.routes
                or not self.evidence
                or self.review_inputs is None
                or self.current_brief_id is not None
                or self.recovery is not None
            ):
                raise ValueError("review-required projection is incomplete")
        elif self.phase in {DemoPhase.FAMILY_REVIEW, DemoPhase.PLAN_READY}:
            if (
                self.canonical_task_inputs is not None
                or self.planning_run is not None
                or self.routes
                or self.evidence
                or self.current_brief_id is None
                or self.review_inputs is not None
                or self.recovery
            ):
                raise ValueError(f"{self.phase.value} projection is incomplete")
        elif self.phase is DemoPhase.TERMINAL_TASK_FAILURE:
            terminal = {
                TaskViewStatus.NEEDS_EVIDENCE,
                TaskViewStatus.TIMED_OUT,
                TaskViewStatus.FAILED,
                TaskViewStatus.CANCELLED,
                TaskViewStatus.OUTDATED,
            }
            if (
                self.task is None
                or self.task.status not in terminal
                or self.planning_run is not None
                or self.routes
                or self.evidence
                or self.review_inputs is not None
                or self.current_brief_id is not None
                or self.recovery is None
            ):
                raise ValueError("terminal-task-failure projection is invalid")
        return self


class AdvisorLedgerV2(FrozenModel):
    schema_version: Literal[2] = 2
    proof_mode: Literal["synthetic-demo"] = "synthetic-demo"
    phase: DemoPhaseV2
    case_id: UUID
    case_revision: PositiveInt
    case_state: CaseState
    canonical_task_inputs: CanonicalDemoTaskInputs | None
    task: PublicTaskProjection | None
    planning_run: PublicPlanningRunProjectionV2 | None
    comparison: PlanningRevisionComparisonV1 | None
    routes: tuple[AdvisorRouteProjection, ...]
    evidence: tuple[EvidenceDisclosure, ...]
    review_inputs: AdvisorReviewInputs | None
    current_brief_id: UUID | None
    recovery: PublicRecoveryProjection | None

    @model_validator(mode="after")
    def validate_revision_projection(self) -> AdvisorLedgerV2:
        revised = {
            DemoPhaseV2.REVISION_REVIEW_REQUIRED,
            DemoPhaseV2.REVISION_BLOCKED,
        }
        if self.phase in revised and (
            self.case_revision < 2
            or self.planning_run is None
            or self.comparison is None
            or self.comparison.current_revision != self.case_revision
            or self.comparison.current_planning_run_id
            != self.planning_run.planning_run_id
        ):
            raise ValueError(f"{self.phase.value.replace('_', '-')} projection is incomplete")
        if self.phase is DemoPhaseV2.REVISION_REVIEW_REQUIRED and (
            self.planning_run is None
            or self.planning_run.state != "review_required"
            or self.review_inputs is None
        ):
            raise ValueError("revision-review-required projection is incomplete")
        if self.phase is DemoPhaseV2.REVISION_BLOCKED and (
            self.task is None
            or self.task.status is not TaskViewStatus.NEEDS_EVIDENCE
            or self.planning_run is None
            or self.planning_run.state != "blocked"
            or self.review_inputs is not None
            or self.recovery is not None
        ):
            raise ValueError("revision-blocked projection is invalid")
        return self


class ConnectedJourneyStatusV1(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    schema_: Literal["night-voyager.connected-journey-status.v1"] = Field(
        alias="schema",
        serialization_alias="schema",
    )
    case_id: UUID
    current_revision: PositiveInt
    phase: DemoPhaseV2
    active_role: Literal["advisor", "student", "parent"]


class FamilyRevisionContextV1(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    schema_: Literal["night-voyager.family-revision-context.v1"] = Field(
        alias="schema",
        serialization_alias="schema",
    )
    current_case_revision: PositiveInt
    planning_version: Literal["initial", "revised"]
    advisor_authorization: Literal[
        "authorized_for_initial_revision",
        "renewed_for_current_revision",
    ]


class CurrentDecisionBriefV1(FrozenModel):
    schema_version: Literal[1] = 1
    proof_mode: Literal["synthetic-demo"] = "synthetic-demo"
    phase: Literal[DemoPhase.FAMILY_REVIEW, DemoPhase.PLAN_READY]
    case_id: UUID
    brief_id: UUID
    brief_version: PositiveInt
    source_snapshot_date: date
    family_safe_projection: DecisionBriefProjection
    decision_requirements: FamilyDecisionRequirements
    receipt: DecisionReceiptProjection | None
    timeline: TimelinePlan | None

    @model_validator(mode="after")
    def validate_phase_projection(self) -> CurrentDecisionBriefV1:
        if self.phase is DemoPhase.FAMILY_REVIEW and (
            self.receipt is not None or self.timeline is not None
        ):
            raise ValueError("family-review projection cannot contain receipt or timeline")
        if self.phase is DemoPhase.PLAN_READY and (
            self.receipt is None or self.timeline is None
        ):
            raise ValueError("plan-ready projection requires receipt and timeline")
        return self


class CurrentDecisionBriefV2(FrozenModel):
    schema_version: Literal[2] = 2
    proof_mode: Literal["synthetic-demo"] = "synthetic-demo"
    phase: Literal[DemoPhaseV2.FAMILY_REVIEW, DemoPhaseV2.PLAN_READY]
    case_id: UUID
    brief_id: UUID
    brief_version: PositiveInt
    source_snapshot_date: date
    family_safe_projection: DecisionBriefProjection
    decision_requirements: FamilyDecisionRequirements
    revision_context: FamilyRevisionContextV1
    receipt: DecisionReceiptProjection | None
    timeline: TimelinePlan | None

    @model_validator(mode="after")
    def validate_phase_projection(self) -> CurrentDecisionBriefV2:
        if self.phase is DemoPhaseV2.FAMILY_REVIEW and (
            self.receipt is not None or self.timeline is not None
        ):
            raise ValueError("family-review projection cannot contain receipt or timeline")
        if self.phase is DemoPhaseV2.PLAN_READY and (
            self.receipt is None or self.timeline is None
        ):
            raise ValueError("plan-ready projection requires receipt and timeline")
        return self
