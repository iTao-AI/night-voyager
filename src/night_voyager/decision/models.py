from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, PositiveInt, field_validator, model_validator

from night_voyager.planning.models import Country, RouteOutcome


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ReviewAction(StrEnum):
    APPROVE_FOR_CONSULTATION = "approve_for_consultation"
    REJECT = "reject"
    REQUEST_REVISION = "request_revision"


class DecisionSource(StrEnum):
    DIRECT = "direct"
    FAMILY_CONSULTATION = "family_consultation"


class EvidenceRiskKind(StrEnum):
    OPTIONAL = "optional"
    STALE = "stale"
    UNVERIFIED = "unverified"


class EvidenceRiskAcceptance(FrozenModel):
    evidence_id: UUID
    kind: EvidenceRiskKind | str
    reason: str

    @field_validator("kind")
    @classmethod
    def narrow_kind(cls, value: EvidenceRiskKind | str) -> EvidenceRiskKind:
        try:
            return EvidenceRiskKind(value)
        except ValueError as error:
            raise ValueError("Evidence risk acceptance cannot waive this risk") from error


class BriefRoute(FrozenModel):
    route_id: UUID
    country: Country
    outcome: RouteOutcome
    reason_code: str


class DecisionBriefProjection(FrozenModel):
    schema_version: Literal[1]
    intake: str
    routes: tuple[BriefRoute, ...]
    eligible_route_ids: tuple[UUID, ...]
    accepted_evidence_risks: tuple[EvidenceRiskAcceptance, ...]
    synthetic_proof: bool

    @model_validator(mode="after")
    def eligible_routes_are_present_and_unblocked(self) -> DecisionBriefProjection:
        routes = {route.route_id: route for route in self.routes}
        if any(
            route_id not in routes or routes[route_id].outcome is RouteOutcome.BLOCKED
            for route_id in self.eligible_route_ids
        ):
            raise ValueError("eligible route must be present and non-blocked")
        return self


class FamilyDecisionCommand(FrozenModel):
    schema_version: Literal[1]
    brief_id: UUID
    expected_brief_version: PositiveInt
    selected_route_id: UUID
    accepted_budget_min_minor: PositiveInt
    accepted_budget_max_minor: PositiveInt
    currency: Literal["CNY"]
    accepted_trade_offs: tuple[str, ...]
    decision_made_by_actor_id: UUID
    source: DecisionSource

    @model_validator(mode="after")
    def valid_range(self) -> FamilyDecisionCommand:
        if self.accepted_budget_min_minor > self.accepted_budget_max_minor:
            raise ValueError("accepted budget range is invalid")
        return self


class TimelineMilestone(FrozenModel):
    key: str
    due_date: date


class TimelinePlan(FrozenModel):
    schema_version: Literal[1]
    country: Country
    intake: str
    milestones: tuple[TimelineMilestone, ...]


class DecisionReceiptProjection(FrozenModel):
    schema_version: Literal[1]
    decision_id: UUID
    receipt_id: UUID
    selected_route_id: UUID
    accepted_budget_min_minor: PositiveInt
    accepted_budget_max_minor: PositiveInt
    currency: Literal["CNY"]
    accepted_trade_offs: tuple[str, ...]
    decision_made_by_actor_id: UUID
    recorded_by_actor_id: UUID
    source: DecisionSource


class ReviewCommand(FrozenModel):
    schema_version: Literal[1]
    case_id: UUID
    planning_run_id: UUID
    expected_case_revision: PositiveInt
    action: ReviewAction
    review_id: UUID
    eligible_route_ids: tuple[UUID, ...]
    risk_acceptances: tuple[EvidenceRiskAcceptance, ...]
    reviewer_notes: str | None
    brief_id: UUID | None

    @model_validator(mode="after")
    def action_payload(self) -> ReviewCommand:
        approving = self.action is ReviewAction.APPROVE_FOR_CONSULTATION
        if approving != (self.brief_id is not None):
            raise ValueError("only approval creates a decision brief")
        if not approving and (self.eligible_route_ids or self.risk_acceptances):
            raise ValueError("non-approval review cannot grant eligibility or accept risks")
        return self
