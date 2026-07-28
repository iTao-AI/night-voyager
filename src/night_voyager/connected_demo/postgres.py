from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from night_voyager.connected_demo.errors import DemoContractUnavailableError
from night_voyager.connected_demo.fixtures import CanonicalDemoSourceContract
from night_voyager.connected_demo.models import (
    AdvisorLedgerV1,
    AdvisorLedgerV2,
    AdvisorReviewInputs,
    AdvisorRouteProjection,
    CanonicalDemoTaskInputs,
    ComparisonDimensionProjection,
    ConnectedJourneyStatusV1,
    CostProjection,
    CurrentDecisionBriefV1,
    CurrentDecisionBriefV2,
    DemoPhase,
    DemoPhaseV2,
    EvidenceDisclosure,
    FamilyDecisionRequirements,
    FamilyRevisionContextV1,
    PublicPlanningRunProjection,
    PublicPlanningRunProjectionV2,
    PublicRecoveryProjection,
    PublicTaskProjection,
    RankingProjection,
)
from night_voyager.decision.models import (
    DecisionBriefProjection,
    DecisionReceiptProjection,
    TimelinePlan,
)
from night_voyager.identity.models import ActorContext, ActorRole
from night_voyager.planning.models import (
    Country,
    DimensionOutcome,
    DimensionResult,
    EvidenceRole,
    EvidenceUse,
    RouteOutcome,
    RouteResult,
    RunState,
)
from night_voyager.planning.revision import (
    FamilyBudgetFactDeltaV1,
    PersistedPlanningResultProjectionV1,
    PlanningRevisionComparisonV1,
    PreferredCountriesFactDeltaV1,
    build_planning_revision_comparison,
)
from night_voyager.tasks.models import AgentTaskState, TaskViewStatus
from night_voyager.tasks.policy import project_task_status


class PostgresConnectedDemoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def advisor_ledger(
        self,
        context: ActorContext,
        case_id: UUID,
        source: CanonicalDemoSourceContract,
    ) -> AdvisorLedgerV1 | None:
        case = (
            await self._session.execute(
                text(
                    "SELECT c.state,c.current_revision FROM app.student_cases c JOIN "
                    "app.student_case_participants p ON p.organization_id=c.organization_id "
                    "AND p.case_id=c.id AND p.actor_id=:actor AND p.role='advisor' "
                    "WHERE c.organization_id=:org AND c.id=:case"
                ),
                {"org": context.organization_id, "actor": context.actor_id, "case": case_id},
            )
        ).mappings().one_or_none()
        if context.role is not ActorRole.ADVISOR or case is None:
            return None
        revision = case["current_revision"]
        if revision is None:
            raise DemoContractUnavailableError("canonical demo source contract unavailable")
        await self._verify_source(context, source)
        task = (
            await self._session.execute(
                text(
                    "SELECT t.id,t.row_version,t.state,t.attempt_count,t.terminal_code,"
                    "t.result_planning_run_id,t.case_revision,t.source_pack_id,"
                    "t.source_pack_version,t.policy_version,t.updated_at,"
                    "COALESCE(r.is_current,true) AS result_is_current "
                    "FROM app.agent_tasks t LEFT JOIN app.planning_runs r "
                    "ON r.organization_id=t.organization_id AND r.id=t.result_planning_run_id "
                    "WHERE t.organization_id=:org AND t.case_id=:case "
                    "AND t.case_revision=:revision "
                    "ORDER BY t.created_at DESC,t.id LIMIT 1"
                ),
                {
                    "org": context.organization_id,
                    "case": case_id,
                    "revision": revision,
                },
            )
        ).mappings().one_or_none()
        inputs = CanonicalDemoTaskInputs(
            case_id=case_id,
            expected_case_revision=revision,
            source_pack_id=source.source_pack_id,
            source_pack_version=source.source_pack_version,
            policy_version=source.policy_version,
        )
        authoritative_brief = await self._authoritative_brief_id(
            context, case_id, case["state"], revision
        )
        if authoritative_brief is not None:
            return self._ledger(
                phase=(
                    DemoPhase.PLAN_READY
                    if case["state"] == "plan_ready"
                    else DemoPhase.FAMILY_REVIEW
                ),
                case_id=case_id,
                revision=revision,
                state=case["state"],
                task=(
                    PublicTaskProjection(
                        task_id=task["id"],
                        row_version=task["row_version"],
                        status=project_task_status(
                            AgentTaskState(task["state"]),
                            result_is_current=task["result_is_current"],
                        ),
                        public_code=task["terminal_code"],
                        attempt_count=task["attempt_count"],
                        planning_run_id=task["result_planning_run_id"],
                        updated_at=task["updated_at"],
                    )
                    if task is not None
                    else None
                ),
                current_brief_id=authoritative_brief,
            )
        if task is None:
            return self._ledger(
                phase=DemoPhase.TASK_READY,
                case_id=case_id,
                revision=revision,
                state=case["state"],
                inputs=inputs,
            )
        if (
            task["case_revision"] != revision
            or task["source_pack_id"] != source.source_pack_id
            or task["source_pack_version"] != source.source_pack_version
            or task["policy_version"] != source.policy_version
        ):
            raise DemoContractUnavailableError(
                "persisted task pins do not match canonical inputs"
            )
        status = project_task_status(
            AgentTaskState(task["state"]), result_is_current=task["result_is_current"]
        )
        public_task = PublicTaskProjection(
            task_id=task["id"],
            row_version=task["row_version"],
            status=status,
            public_code=task["terminal_code"],
            attempt_count=task["attempt_count"],
            planning_run_id=task["result_planning_run_id"],
            updated_at=task["updated_at"],
        )
        if status is TaskViewStatus.PREPARING:
            return self._ledger(
                phase=DemoPhase.ACTIVE_TASK,
                case_id=case_id,
                revision=revision,
                state=case["state"],
                inputs=inputs,
                task=public_task,
            )
        terminal = {
            TaskViewStatus.NEEDS_EVIDENCE,
            TaskViewStatus.TIMED_OUT,
            TaskViewStatus.FAILED,
            TaskViewStatus.CANCELLED,
            TaskViewStatus.OUTDATED,
        }
        if status in terminal:
            return self._ledger(
                phase=DemoPhase.TERMINAL_TASK_FAILURE,
                case_id=case_id,
                revision=revision,
                state=case["state"],
                task=public_task,
                recovery=PublicRecoveryProjection(
                    code=task["terminal_code"] or status.value,
                    retry_allowed=status
                    in {TaskViewStatus.TIMED_OUT, TaskViewStatus.FAILED},
                    guidance="Review the public task status before retrying.",
                ),
            )
        run_id = task["result_planning_run_id"]
        if run_id is None:
            raise DemoContractUnavailableError("persisted task result is unavailable")
        run, routes, evidence = await self._review_projection(context, run_id)
        if not isinstance(run, PublicPlanningRunProjection):
            raise DemoContractUnavailableError(
                "legacy planning run projection is unavailable"
            )
        eligible = tuple(
            route.route_id
            for route in routes
            if route.country is Country.AUSTRALIA
            and route.outcome is RouteOutcome.RECOMMENDED_WITH_CONDITION
        )
        return self._ledger(
            phase=DemoPhase.REVIEW_REQUIRED,
            case_id=case_id,
            revision=revision,
            state=case["state"],
            task=public_task,
            planning_run=run,
            routes=routes,
            evidence=evidence,
            review_inputs=AdvisorReviewInputs(
                planning_run_id=run_id,
                expected_case_revision=revision,
                eligible_route_ids=eligible,
                risk_acceptance_options=(),
            ),
        )

    async def advisor_ledger_v2(
        self,
        context: ActorContext,
        case_id: UUID,
        source: CanonicalDemoSourceContract,
    ) -> AdvisorLedgerV2 | None:
        legacy = await self.advisor_ledger(context, case_id, source)
        if legacy is None:
            return None
        revision_request = (
            await self._session.execute(
                text(
                    "SELECT EXISTS(SELECT 1 FROM app.advisor_reviews review_row "
                    "JOIN app.planning_runs run_row "
                    "ON run_row.organization_id=review_row.organization_id "
                    "AND run_row.id=review_row.planning_run_id "
                    "AND run_row.case_id=review_row.case_id "
                    "AND run_row.case_revision=review_row.case_revision "
                    "AND run_row.is_current "
                    "WHERE review_row.organization_id=:org "
                    "AND review_row.case_id=:case "
                    "AND review_row.case_revision=:revision "
                    "AND review_row.action='request_revision') AS requested,"
                    "app.read_connected_journey_fact_pending("
                    ":org,:actor,:role,:case) AS fact_pending"
                ),
                {
                    "org": context.organization_id,
                    "actor": context.actor_id,
                    "role": context.role.value,
                    "case": case_id,
                    "revision": legacy.case_revision,
                },
            )
        ).mappings().one()
        phase = {
            DemoPhase.TASK_READY: DemoPhaseV2.TASK_READY,
            DemoPhase.ACTIVE_TASK: DemoPhaseV2.ACTIVE_TASK,
            DemoPhase.REVIEW_REQUIRED: DemoPhaseV2.REVIEW_REQUIRED,
            DemoPhase.FAMILY_REVIEW: DemoPhaseV2.FAMILY_REVIEW,
            DemoPhase.PLAN_READY: DemoPhaseV2.PLAN_READY,
            DemoPhase.TERMINAL_TASK_FAILURE: DemoPhaseV2.TERMINAL_TASK_FAILURE,
        }[legacy.phase]
        comparison: PlanningRevisionComparisonV1 | None = None
        payload = legacy.model_dump(mode="python")
        if revision_request["requested"]:
            phase = (
                DemoPhaseV2.REVISION_FACT_PENDING
                if revision_request["fact_pending"]
                else DemoPhaseV2.REVISION_REQUESTED
            )
        elif legacy.case_revision > 1:
            if (
                legacy.task is not None
                and legacy.task.planning_run_id is not None
                and legacy.task.status
                in {
                    TaskViewStatus.NEEDS_ADVISOR_REVIEW,
                    TaskViewStatus.NEEDS_EVIDENCE,
                }
            ):
                run, routes, evidence = await self._review_projection(
                    context, legacy.task.planning_run_id, allow_blocked=True
                )
                if not isinstance(run, PublicPlanningRunProjectionV2):
                    raise DemoContractUnavailableError(
                        "versioned planning run projection is unavailable"
                    )
                comparison = await self._planning_revision_comparison(
                    context, case_id, legacy.case_revision, run.planning_run_id
                )
                phase = (
                    DemoPhaseV2.REVISION_REVIEW_REQUIRED
                    if run.state == "review_required"
                    else DemoPhaseV2.REVISION_BLOCKED
                )
                payload.update(
                    {
                        "planning_run": run,
                        "routes": routes,
                        "evidence": evidence,
                        "review_inputs": (
                            legacy.review_inputs
                            if run.state == "review_required"
                            else None
                        ),
                    }
                )
            elif legacy.task is None:
                phase = DemoPhaseV2.REPLAN_REQUIRED
            elif legacy.task.status is TaskViewStatus.PREPARING:
                phase = DemoPhaseV2.REVISION_TASK_ACTIVE
        payload.update(
            {
                "schema_version": 2,
                "phase": phase,
                "comparison": comparison,
            }
        )
        return AdvisorLedgerV2.model_validate(payload)

    async def current_decision_brief_v2(
        self, context: ActorContext, case_id: UUID
    ) -> CurrentDecisionBriefV2 | None:
        legacy = await self.current_decision_brief(context, case_id)
        if legacy is None:
            return None
        authority = (
            await self._session.execute(
                text(
                    "SELECT c.current_revision,r.supersedes_run_id,"
                    "review_row.id AS approval_review_id "
                    "FROM app.decision_briefs b JOIN app.student_cases c "
                    "ON c.organization_id=b.organization_id AND c.id=b.case_id "
                    "JOIN app.planning_runs r ON r.organization_id=b.organization_id "
                    "AND r.id=b.planning_run_id "
                    "JOIN app.advisor_reviews review_row "
                    "ON review_row.organization_id=b.organization_id "
                    "AND review_row.id=b.advisor_review_id "
                    "AND review_row.case_revision=b.case_revision "
                    "AND review_row.planning_run_id=b.planning_run_id "
                    "AND review_row.action='approve_for_consultation' "
                    "WHERE b.organization_id=:org AND b.id=:brief "
                    "AND b.case_revision=c.current_revision AND r.is_current"
                ),
                {
                    "org": context.organization_id,
                    "brief": legacy.brief_id,
                },
            )
        ).mappings().one_or_none()
        if authority is None:
            raise DemoContractUnavailableError(
                "current brief revision authority is unavailable"
            )
        revised = authority["supersedes_run_id"] is not None
        payload = legacy.model_dump(mode="python")
        payload.update(
            {
                "schema_version": 2,
                "phase": DemoPhaseV2(legacy.phase.value.replace("-", "_")),
                "revision_context": FamilyRevisionContextV1(
                    schema="night-voyager.family-revision-context.v1",
                    current_case_revision=authority["current_revision"],
                    planning_version="revised" if revised else "initial",
                    advisor_authorization=(
                        "renewed_for_current_revision"
                        if revised
                        else "authorized_for_initial_revision"
                    ),
                ),
            }
        )
        return CurrentDecisionBriefV2.model_validate(payload)

    async def journey_status(
        self, context: ActorContext, case_id: UUID
    ) -> ConnectedJourneyStatusV1 | None:
        row = (
            await self._session.execute(
                text(
                    "SELECT c.state,c.current_revision,p.role,"
                    "t.state AS task_state,r.state AS run_state,"
                    "r.supersedes_run_id,b.id AS brief_id,d.id AS decision_id,"
                    "EXISTS(SELECT 1 FROM app.advisor_reviews request_review "
                    "JOIN app.planning_runs requested_run "
                    "ON requested_run.organization_id=request_review.organization_id "
                    "AND requested_run.id=request_review.planning_run_id "
                    "AND requested_run.case_id=request_review.case_id "
                    "AND requested_run.case_revision=request_review.case_revision "
                    "AND requested_run.is_current "
                    "WHERE request_review.organization_id=c.organization_id "
                    "AND request_review.case_id=c.id "
                    "AND request_review.case_revision=c.current_revision "
                    "AND request_review.action='request_revision') AS revision_requested,"
                    "app.read_connected_journey_fact_pending("
                    "c.organization_id,:actor,:role,c.id) "
                    "AS revision_fact_pending "
                    "FROM app.student_cases c JOIN app.student_case_participants p "
                    "ON p.organization_id=c.organization_id AND p.case_id=c.id "
                    "AND p.actor_id=:actor AND p.role=:role "
                    "LEFT JOIN LATERAL (SELECT task_row.state,"
                    "task_row.result_planning_run_id FROM app.agent_tasks task_row "
                    "WHERE task_row.organization_id=c.organization_id "
                    "AND task_row.case_id=c.id "
                    "AND task_row.case_revision=c.current_revision "
                    "ORDER BY task_row.created_at DESC,task_row.id LIMIT 1) t ON true "
                    "LEFT JOIN app.planning_runs r ON r.organization_id=c.organization_id "
                    "AND r.id=t.result_planning_run_id "
                    "LEFT JOIN app.decision_briefs b ON b.organization_id=c.organization_id "
                    "AND b.case_id=c.id AND b.case_revision=c.current_revision "
                    "AND b.is_current "
                    "LEFT JOIN app.family_decisions d ON d.organization_id=b.organization_id "
                    "AND d.decision_brief_id=b.id "
                    "WHERE c.organization_id=:org AND c.id=:case"
                ),
                {
                    "org": context.organization_id,
                    "actor": context.actor_id,
                    "role": context.role.value,
                    "case": case_id,
                },
            )
        ).mappings().one_or_none()
        if row is None:
            return None
        phase = self._journey_phase(dict(row))
        return ConnectedJourneyStatusV1(
            schema="night-voyager.connected-journey-status.v1",
            case_id=case_id,
            current_revision=row["current_revision"],
            phase=phase,
            active_role=self._journey_active_role(phase),
        )

    async def current_decision_brief(
        self, context: ActorContext, case_id: UUID
    ) -> CurrentDecisionBriefV1 | None:
        row = (
            await self._session.execute(
                text(
                    "SELECT b.id,b.brief_version,b.source_snapshot_date,"
                    "b.family_safe_projection,b.planning_run_id,c.state,"
                    "d.id AS decision_id,d.receipt_id,d.selected_route_id,"
                    "d.accepted_budget_min_minor,d.accepted_budget_max_minor,d.currency,"
                    "d.accepted_trade_offs,d.decision_made_by_actor_id,"
                    "d.recorded_by_actor_id,d.source,t.country,t.intake,t.milestones,"
                    "(cr.family_preferences->'budget'->>'hard_ceiling_minor')::bigint "
                    "AS hard_ceiling,pr.id AS route_id,"
                    "round((ce.tuition_minor+ce.living_minor)*ce.fx_rate)::bigint AS cost "
                    "FROM app.decision_briefs b JOIN app.student_cases c "
                    "ON c.organization_id=b.organization_id AND c.id=b.case_id "
                    "JOIN app.student_case_participants p "
                    "ON p.organization_id=b.organization_id AND p.case_id=b.case_id "
                    "AND p.actor_id=:actor AND p.role=:role "
                    "JOIN app.student_case_revisions cr "
                    "ON cr.organization_id=b.organization_id AND cr.case_id=b.case_id "
                    "AND cr.revision=b.case_revision JOIN app.planning_routes pr "
                    "ON pr.organization_id=b.organization_id "
                    "AND pr.planning_run_id=b.planning_run_id "
                    "AND pr.country='australia' AND pr.outcome<>'blocked' "
                    "JOIN app.cost_evidence ce ON ce.organization_id=b.organization_id "
                    "AND ce.planning_run_id=b.planning_run_id AND ce.country='australia' "
                    "LEFT JOIN app.family_decisions d "
                    "ON d.organization_id=b.organization_id AND d.decision_brief_id=b.id "
                    "LEFT JOIN app.timeline_plans t ON t.organization_id=d.organization_id "
                    "AND t.family_decision_id=d.id WHERE b.organization_id=:org "
                    "AND b.case_id=:case AND b.case_revision=c.current_revision "
                    "AND ((c.state='family_review' AND b.is_current AND d.id IS NULL) "
                    "OR (c.state='plan_ready' AND d.id IS NOT NULL))"
                ),
                {
                    "org": context.organization_id,
                    "actor": context.actor_id,
                    "role": context.role,
                    "case": case_id,
                },
            )
        ).mappings().one_or_none()
        if row is None:
            return None
        if row["hard_ceiling"] is None or row["cost"] is None:
            raise DemoContractUnavailableError("decision requirements are unavailable")
        requirements = FamilyDecisionRequirements(
            eligible_route_id=row["route_id"],
            currency="CNY",
            pinned_cost_minor=row["cost"],
            hard_ceiling_minor=row["hard_ceiling"],
            required_trade_offs=("budget_elasticity",),
        )
        receipt = self._receipt(dict(row))
        timeline = (
            TimelinePlan(
                schema_version=1,
                country=Country(row["country"]),
                intake=row["intake"],
                milestones=tuple(row["milestones"]),
            )
            if row["decision_id"] is not None
            else None
        )
        phase = (
            DemoPhase.PLAN_READY if receipt is not None else DemoPhase.FAMILY_REVIEW
        )
        return CurrentDecisionBriefV1(
            phase=phase,
            case_id=case_id,
            brief_id=row["id"],
            brief_version=row["brief_version"],
            source_snapshot_date=row["source_snapshot_date"],
            family_safe_projection=DecisionBriefProjection.model_validate(
                row["family_safe_projection"]
            ),
            decision_requirements=requirements,
            receipt=receipt,
            timeline=timeline,
        )

    async def _verify_source(
        self, context: ActorContext, source: CanonicalDemoSourceContract
    ) -> None:
        manifest = await self._session.scalar(
            text(
                "SELECT manifest_sha256 FROM app.source_packs WHERE organization_id=:org "
                "AND id=:pack AND version=:version"
            ),
            {
                "org": context.organization_id,
                "pack": source.source_pack_id,
                "version": source.source_pack_version,
            },
        )
        if manifest != source.manifest_sha256:
            raise DemoContractUnavailableError("canonical demo source contract unavailable")

    async def _planning_revision_comparison(
        self,
        context: ActorContext,
        case_id: UUID,
        revision: int,
        current_run_id: UUID,
    ) -> PlanningRevisionComparisonV1:
        lineage = (
            await self._session.execute(
                text(
                    "SELECT current_revision.superseded_planning_run_id,"
                    "current_revision.student_preferences AS current_student,"
                    "current_revision.family_preferences AS current_family,"
                    "previous_revision.student_preferences AS previous_student,"
                    "previous_revision.family_preferences AS previous_family "
                    "FROM app.student_case_revisions current_revision "
                    "JOIN app.student_case_revisions previous_revision "
                    "ON previous_revision.organization_id=current_revision.organization_id "
                    "AND previous_revision.case_id=current_revision.case_id "
                    "AND previous_revision.revision=current_revision.revision-1 "
                    "WHERE current_revision.organization_id=:org "
                    "AND current_revision.case_id=:case "
                    "AND current_revision.revision=:revision "
                    "AND current_revision.superseded_planning_run_id IS NOT NULL"
                ),
                {
                    "org": context.organization_id,
                    "case": case_id,
                    "revision": revision,
                },
            )
        ).mappings().one_or_none()
        if lineage is None:
            raise DemoContractUnavailableError("revision lineage is unavailable")
        previous_student = dict(lineage["previous_student"])
        current_student = dict(lineage["current_student"])
        previous_family = dict(lineage["previous_family"])
        current_family = dict(lineage["current_family"])
        preferred_changed = (
            previous_student.get("preferred_countries")
            != current_student.get("preferred_countries")
        )
        budget_changed = previous_family.get("budget") != current_family.get("budget")
        previous_student["preferred_countries"] = current_student.get(
            "preferred_countries"
        )
        previous_family["budget"] = current_family.get("budget")
        if (
            previous_student != current_student
            or previous_family != current_family
            or preferred_changed == budget_changed
        ):
            raise DemoContractUnavailableError(
                "revision changed fact is outside the planning contract"
            )
        if preferred_changed:
            changed_fact = PreferredCountriesFactDeltaV1(
                fact_key="student.preferred_countries",
                previous_value=tuple(lineage["previous_student"]["preferred_countries"]),
                current_value=tuple(lineage["current_student"]["preferred_countries"]),
            )
        else:
            changed_fact = FamilyBudgetFactDeltaV1(
                fact_key="family.budget",
                previous_value=lineage["previous_family"]["budget"],
                current_value=lineage["current_family"]["budget"],
            )
        previous, previous_hash = await self._persisted_planning_result(
            context, lineage["superseded_planning_run_id"]
        )
        current, current_hash = await self._persisted_planning_result(
            context, current_run_id
        )
        return build_planning_revision_comparison(
            changed_fact=changed_fact,
            previous=previous,
            current=current,
            previous_output_sha256=previous_hash,
            current_output_sha256=current_hash,
        )

    async def _persisted_planning_result(
        self, context: ActorContext, run_id: UUID
    ) -> tuple[PersistedPlanningResultProjectionV1, str]:
        run = (
            await self._session.execute(
                text(
                    "SELECT id,case_id,case_revision,supersedes_run_id,state,"
                    "reason_code,output_sha256 FROM app.planning_runs "
                    "WHERE organization_id=:org AND id=:run "
                    "AND state IN ('review_required','blocked')"
                ),
                {"org": context.organization_id, "run": run_id},
            )
        ).mappings().one_or_none()
        if run is None:
            raise DemoContractUnavailableError("persisted planning result is unavailable")
        rows = (
            await self._session.execute(
                text(
                    "SELECT route.id AS route_id,route.country,route.outcome AS route_outcome,"
                    "route.reason_code AS route_reason,dimension.id AS dimension_id,"
                    "dimension.dimension_key,dimension.outcome AS dimension_outcome,"
                    "dimension.reason_code AS dimension_reason,reference.evidence_role,"
                    "reference.evidence_ref_id FROM app.planning_routes route "
                    "JOIN app.comparison_dimensions dimension "
                    "ON dimension.organization_id=route.organization_id "
                    "AND dimension.planning_run_id=route.planning_run_id "
                    "AND dimension.route_id=route.id "
                    "LEFT JOIN app.comparison_dimension_evidence_refs reference "
                    "ON reference.organization_id=dimension.organization_id "
                    "AND reference.planning_run_id=dimension.planning_run_id "
                    "AND reference.route_id=dimension.route_id "
                    "AND reference.dimension_id=dimension.id "
                    "WHERE route.organization_id=:org AND route.planning_run_id=:run "
                    "ORDER BY route.id,dimension.id,"
                    "array_position(ARRAY['program_fit','tuition','living_cost',"
                    "'fx','ranking']::text[],reference.evidence_role),"
                    "reference.evidence_ref_id"
                ),
                {"org": context.organization_id, "run": run_id},
            )
        ).mappings().all()
        routes: list[RouteResult] = []
        route_groups: dict[UUID, list[Mapping[str, Any]]] = {}
        for row in rows:
            route_groups.setdefault(row["route_id"], []).append(dict(row))
        for route_rows in route_groups.values():
            first = route_rows[0]
            dimension_groups: dict[UUID, list[Mapping[str, Any]]] = {}
            for row in route_rows:
                dimension_groups.setdefault(row["dimension_id"], []).append(row)
            dimensions = tuple(
                DimensionResult(
                    dimension_key=dimension_rows[0]["dimension_key"],
                    outcome=DimensionOutcome(
                        dimension_rows[0]["dimension_outcome"]
                    ),
                    reason_code=dimension_rows[0]["dimension_reason"],
                    evidence_uses=tuple(
                        EvidenceUse(
                            role=EvidenceRole(row["evidence_role"]),
                            evidence_id=row["evidence_ref_id"],
                        )
                        for row in dimension_rows
                        if row["evidence_ref_id"] is not None
                    ),
                )
                for dimension_rows in dimension_groups.values()
            )
            routes.append(
                RouteResult(
                    country=Country(first["country"]),
                    outcome=RouteOutcome(first["route_outcome"]),
                    reason_code=first["route_reason"],
                    dimensions=dimensions,
                )
            )
        projection = PersistedPlanningResultProjectionV1(
            case_id=run["case_id"],
            case_revision=run["case_revision"],
            planning_run_id=run["id"],
            supersedes_run_id=run["supersedes_run_id"],
            state=RunState(run["state"]),
            reason_code=run["reason_code"],
            routes=tuple(routes),
        )
        return projection, run["output_sha256"]

    @staticmethod
    def _journey_phase(row: Mapping[str, Any]) -> DemoPhaseV2:
        state = row["state"]
        revision = row["current_revision"]
        if state == "family_review" and row["brief_id"] is not None:
            return DemoPhaseV2.FAMILY_REVIEW
        if state == "plan_ready" and row["decision_id"] is not None:
            return DemoPhaseV2.PLAN_READY
        if row["revision_requested"]:
            return (
                DemoPhaseV2.REVISION_FACT_PENDING
                if row["revision_fact_pending"]
                else DemoPhaseV2.REVISION_REQUESTED
            )
        if row["run_state"] == "blocked":
            return DemoPhaseV2.REVISION_BLOCKED
        if row["run_state"] == "review_required":
            return (
                DemoPhaseV2.REVISION_REVIEW_REQUIRED
                if row["supersedes_run_id"] is not None
                else DemoPhaseV2.REVIEW_REQUIRED
            )
        if row["task_state"] in {"blocked", "timed_out", "failed", "cancelled"}:
            return DemoPhaseV2.TERMINAL_TASK_FAILURE
        if row["task_state"] is not None:
            return (
                DemoPhaseV2.REVISION_TASK_ACTIVE
                if revision > 1
                else DemoPhaseV2.ACTIVE_TASK
            )
        if revision > 1:
            return DemoPhaseV2.REPLAN_REQUIRED
        return DemoPhaseV2.TASK_READY

    @staticmethod
    def _journey_active_role(
        phase: DemoPhaseV2,
    ) -> Literal["advisor", "student", "parent"]:
        if phase is DemoPhaseV2.REVISION_REQUESTED:
            return "student"
        if phase in {DemoPhaseV2.FAMILY_REVIEW, DemoPhaseV2.PLAN_READY}:
            return "parent"
        return "advisor"

    async def _authoritative_brief_id(
        self, context: ActorContext, case_id: UUID, case_state: str, revision: int
    ) -> UUID | None:
        if case_state not in {"family_review", "plan_ready"}:
            return None
        return await self._session.scalar(
            text(
                "SELECT b.id FROM app.decision_briefs b "
                "LEFT JOIN app.family_decisions d ON d.organization_id=b.organization_id "
                "AND d.decision_brief_id=b.id WHERE b.organization_id=:org "
                "AND b.case_id=:case AND b.case_revision=:revision AND "
                "((:state='family_review' AND b.is_current AND d.id IS NULL) OR "
                "(:state='plan_ready' AND NOT b.is_current AND d.id IS NOT NULL))"
            ),
            {
                "org": context.organization_id,
                "case": case_id,
                "revision": revision,
                "state": case_state,
            },
        )

    async def _review_projection(
        self,
        context: ActorContext,
        run_id: UUID,
        *,
        allow_blocked: bool = False,
    ) -> tuple[
        PublicPlanningRunProjection | PublicPlanningRunProjectionV2,
        tuple[AdvisorRouteProjection, ...],
        tuple[EvidenceDisclosure, ...],
    ]:
        run = (
            await self._session.execute(
                text(
                    "SELECT r.id,r.state,r.source_pack_id,r.source_pack_version,"
                    "r.policy_version,max(e.snapshot_date) AS snapshot "
                    "FROM app.planning_runs r JOIN "
                    "app.source_pack_entries e ON e.organization_id=r.organization_id "
                    "AND e.source_pack_id=r.source_pack_id "
                    "AND e.source_pack_version=r.source_pack_version "
                    "WHERE r.organization_id=:org AND r.id=:run AND r.is_current "
                    "AND (r.state='review_required' "
                    "OR (:allow_blocked AND r.state='blocked')) "
                    "GROUP BY r.id,r.state,r.source_pack_id,"
                    "r.source_pack_version,r.policy_version"
                ),
                {
                    "org": context.organization_id,
                    "run": run_id,
                    "allow_blocked": allow_blocked,
                },
            )
        ).mappings().one_or_none()
        if run is None:
            raise DemoContractUnavailableError("persisted planning run is unavailable")
        route_rows = (
            await self._session.execute(
                text(
                    "SELECT p.id,p.country,p.outcome,p.reason_code,d.dimension_key,"
                    "d.outcome AS dimension_outcome,d.reason_code AS dimension_reason,"
                    "ce.currency,ce.tuition_minor,ce.living_minor,ce.fx_rate,ce.fx_source,"
                    "ce.fx_date,re.ranking_system,re.rank,re.publication_year "
                    "FROM app.planning_routes p LEFT JOIN app.comparison_dimensions d "
                    "ON d.organization_id=p.organization_id "
                    "AND d.planning_run_id=p.planning_run_id AND d.route_id=p.id "
                    "LEFT JOIN app.cost_evidence ce ON ce.organization_id=p.organization_id "
                    "AND ce.planning_run_id=p.planning_run_id AND ce.country=p.country "
                    "LEFT JOIN app.ranking_evidence re "
                    "ON re.organization_id=p.organization_id "
                    "AND re.planning_run_id=p.planning_run_id AND re.country=p.country "
                    "WHERE p.organization_id=:org AND p.planning_run_id=:run "
                    "ORDER BY p.country,d.dimension_key"
                ),
                {"org": context.organization_id, "run": run_id},
            )
        ).mappings().all()
        grouped: dict[UUID, list[Mapping[str, Any]]] = {}
        for row in route_rows:
            grouped.setdefault(row["id"], []).append(dict(row))
        fact_rows = (
            await self._session.execute(
                text(
                    "SELECT dr.route_id,array_agg(DISTINCT er.claim ORDER BY er.claim) "
                    "AS required_claims,array_agg(DISTINCT gap.value ORDER BY gap.value) "
                    "FILTER (WHERE gap.value IS NOT NULL) AS known_gaps "
                    "FROM app.comparison_dimension_evidence_refs dr "
                    "JOIN app.evidence_refs er ON er.organization_id=dr.organization_id "
                    "AND er.id=dr.evidence_ref_id JOIN app.source_pack_entries se "
                    "ON se.organization_id=er.organization_id "
                    "AND se.source_pack_id=er.source_pack_id "
                    "AND se.source_pack_version=er.source_pack_version "
                    "AND se.id=er.source_entry_id LEFT JOIN LATERAL "
                    "jsonb_array_elements_text(se.known_gaps) gap(value) ON true "
                    "WHERE dr.organization_id=:org AND dr.planning_run_id=:run "
                    "GROUP BY dr.route_id"
                ),
                {"org": context.organization_id, "run": run_id},
            )
        ).mappings().all()
        facts = {row["route_id"]: dict(row) for row in fact_rows}
        gap_rows = (
            await self._session.execute(
                text(
                    "SELECT p.id AS route_id,array_agg(DISTINCT gap.value ORDER BY gap.value) "
                    "FILTER (WHERE gap.value IS NOT NULL) AS known_gaps "
                    "FROM app.planning_routes p JOIN app.planning_runs r "
                    "ON r.organization_id=p.organization_id AND r.id=p.planning_run_id "
                    "JOIN app.source_pack_entries se ON se.organization_id=r.organization_id "
                    "AND se.source_pack_id=r.source_pack_id "
                    "AND se.source_pack_version=r.source_pack_version "
                    "AND EXISTS (SELECT 1 FROM jsonb_array_elements_text(se.coverage) c(value) "
                    "WHERE left(c.value,length(p.country)+1)=p.country || '_') "
                    "LEFT JOIN LATERAL jsonb_array_elements_text(se.known_gaps) "
                    "gap(value) ON true WHERE p.organization_id=:org "
                    "AND p.planning_run_id=:run GROUP BY p.id"
                ),
                {"org": context.organization_id, "run": run_id},
            )
        ).mappings().all()
        for row in gap_rows:
            facts.setdefault(row["route_id"], {})["known_gaps"] = row["known_gaps"]
        routes = tuple(
            self._route(rows, facts.get(route_id))
            for route_id, rows in grouped.items()
        )
        evidence_rows = (
            await self._session.execute(
                text(
                    "SELECT er.claim,dr.evidence_role,se.publisher,se.institution,"
                    "se.snapshot_date,er.authority,se.known_gaps "
                    "FROM app.comparison_dimension_evidence_refs dr JOIN app.evidence_refs er "
                    "ON er.organization_id=dr.organization_id AND er.id=dr.evidence_ref_id "
                    "JOIN app.source_pack_entries se ON se.organization_id=er.organization_id "
                    "AND se.source_pack_id=er.source_pack_id "
                    "AND se.source_pack_version=er.source_pack_version "
                    "AND se.id=er.source_entry_id WHERE dr.organization_id=:org "
                    "AND dr.planning_run_id=:run ORDER BY er.claim,dr.evidence_role"
                ),
                {"org": context.organization_id, "run": run_id},
            )
        ).mappings().all()
        evidence = tuple(
            EvidenceDisclosure(
                claim=row["claim"],
                role=row["evidence_role"],
                publisher=row["publisher"],
                institution=row["institution"],
                snapshot_date=row["snapshot_date"],
                authority=row["authority"],
                limitation="Synthetic evidence is limited to this local demo.",
                known_gaps=tuple(row["known_gaps"]),
            )
            for row in evidence_rows
        )
        run_projection: PublicPlanningRunProjection | PublicPlanningRunProjectionV2
        if allow_blocked:
            run_projection = PublicPlanningRunProjectionV2(
                planning_run_id=run["id"],
                state=run["state"],
                source_pack_id=run["source_pack_id"],
                source_pack_version=run["source_pack_version"],
                policy_version=run["policy_version"],
                source_snapshot_date=run["snapshot"],
            )
        else:
            run_projection = PublicPlanningRunProjection(
                planning_run_id=run["id"],
                state="review_required",
                source_pack_id=run["source_pack_id"],
                source_pack_version=run["source_pack_version"],
                policy_version=run["policy_version"],
                source_snapshot_date=run["snapshot"],
            )
        return (
            run_projection,
            routes,
            evidence,
        )

    @staticmethod
    def _route(
        rows: list[Mapping[str, Any]], facts: Mapping[str, Any] | None
    ) -> AdvisorRouteProjection:
        first = rows[0]
        dimensions = tuple(
            ComparisonDimensionProjection(
                key=row["dimension_key"],
                outcome=row["dimension_outcome"],
                reason_code=row["dimension_reason"],
            )
            for row in rows
            if row["dimension_key"] is not None
        )
        cost = None
        if first["currency"] is not None:
            cost = CostProjection(
                source_currency=first["currency"],
                tuition_minor=first["tuition_minor"],
                living_minor=first["living_minor"],
                fx_rate=first["fx_rate"],
                cny_total_minor=round(
                    (first["tuition_minor"] + first["living_minor"])
                    * first["fx_rate"]
                ),
                fx_source=first["fx_source"],
                fx_date=first["fx_date"],
            )
        ranking = None
        if first["ranking_system"] is not None:
            ranking = RankingProjection(
                ranking_system=first["ranking_system"],
                rank=first["rank"],
                publication_year=first["publication_year"],
            )
        required_claims: set[str] = set(
            facts.get("required_claims", ()) if facts else ()
        )
        required_claims.add(f"{first['country']}_program_fit")
        return AdvisorRouteProjection(
            route_id=first["id"],
            country=Country(first["country"]),
            outcome=RouteOutcome(first["outcome"]),
            reason_code=first["reason_code"],
            eligible=(
                first["country"] == "australia"
                and first["outcome"] == "recommended_with_condition"
            ),
            dimensions=dimensions,
            cost=cost,
            ranking=ranking,
            required_claims=tuple(sorted(required_claims)),
            known_gaps=tuple(facts["known_gaps"] if facts and facts["known_gaps"] else ()),
        )

    @staticmethod
    def _receipt(row: Mapping[str, Any]) -> DecisionReceiptProjection | None:
        if row["decision_id"] is None:
            return None
        return DecisionReceiptProjection(
            schema_version=1,
            decision_id=row["decision_id"],
            receipt_id=row["receipt_id"],
            selected_route_id=row["selected_route_id"],
            accepted_budget_min_minor=row["accepted_budget_min_minor"],
            accepted_budget_max_minor=row["accepted_budget_max_minor"],
            currency=row["currency"],
            accepted_trade_offs=tuple(row["accepted_trade_offs"]),
            decision_made_by_actor_id=row["decision_made_by_actor_id"],
            recorded_by_actor_id=row["recorded_by_actor_id"],
            source=row["source"],
        )

    @staticmethod
    def _ledger(
        *,
        phase: DemoPhase,
        case_id: UUID,
        revision: int,
        state: str,
        inputs: CanonicalDemoTaskInputs | None = None,
        task: PublicTaskProjection | None = None,
        planning_run: PublicPlanningRunProjection | None = None,
        routes: tuple[AdvisorRouteProjection, ...] = (),
        evidence: tuple[EvidenceDisclosure, ...] = (),
        review_inputs: AdvisorReviewInputs | None = None,
        current_brief_id: UUID | None = None,
        recovery: PublicRecoveryProjection | None = None,
    ) -> AdvisorLedgerV1:
        return AdvisorLedgerV1(
            phase=phase,
            case_id=case_id,
            case_revision=revision,
            case_state=state,
            canonical_task_inputs=inputs,
            task=task,
            planning_run=planning_run,
            routes=routes,
            evidence=evidence,
            review_inputs=review_inputs,
            current_brief_id=current_brief_id,
            recovery=recovery,
        )
