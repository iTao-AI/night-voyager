from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from night_voyager.connected_demo.errors import DemoContractUnavailableError
from night_voyager.connected_demo.fixtures import CanonicalDemoSourceContract
from night_voyager.connected_demo.models import (
    AdvisorLedgerV1,
    AdvisorReviewInputs,
    AdvisorRouteProjection,
    CanonicalDemoTaskInputs,
    ComparisonDimensionProjection,
    CostProjection,
    CurrentDecisionBriefV1,
    DemoPhase,
    EvidenceDisclosure,
    FamilyDecisionRequirements,
    PublicPlanningRunProjection,
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
from night_voyager.planning.models import Country, RouteOutcome
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
                    "ORDER BY t.created_at DESC LIMIT 1"
                ),
                {"org": context.organization_id, "case": case_id},
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
        self, context: ActorContext, run_id: UUID
    ) -> tuple[
        PublicPlanningRunProjection,
        tuple[AdvisorRouteProjection, ...],
        tuple[EvidenceDisclosure, ...],
    ]:
        run = (
            await self._session.execute(
                text(
                    "SELECT r.id,r.source_pack_id,r.source_pack_version,r.policy_version,"
                    "max(e.snapshot_date) AS snapshot FROM app.planning_runs r JOIN "
                    "app.source_pack_entries e ON e.organization_id=r.organization_id "
                    "AND e.source_pack_id=r.source_pack_id "
                    "AND e.source_pack_version=r.source_pack_version "
                    "WHERE r.organization_id=:org AND r.id=:run AND r.is_current "
                    "AND r.state='review_required' GROUP BY r.id,r.source_pack_id,"
                    "r.source_pack_version,r.policy_version"
                ),
                {"org": context.organization_id, "run": run_id},
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
        return (
            PublicPlanningRunProjection(
                planning_run_id=run["id"],
                state="review_required",
                source_pack_id=run["source_pack_id"],
                source_pack_version=run["source_pack_version"],
                policy_version=run["policy_version"],
                source_snapshot_date=run["snapshot"],
            ),
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
