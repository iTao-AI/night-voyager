import type { AdvisorLedger, CurrentDecisionBrief, TaskStatus } from "../../lib/connected-demo/contracts";

export const CASE_ID = "40000000-0000-0000-0000-000000000002";
export const CONTINUED_CASE_ID = "41000000-0000-0000-0000-000000000001";
export const TASK_ID = "61000000-0000-0000-0000-000000000001";
export const BRIEF_ID = "81000000-0000-0000-0000-000000000301";
export const ROUTE_ID = "71000000-0000-0000-0000-000000000001";
export const CONFIRMED_FACT = {
  schema_version: 1 as const,
  fact_key: "family.budget" as const,
  value: { schema_version: 1 as const, currency: "CNY" as const, period: "program_total" as const, preferred_minor: 30_000_000, hard_ceiling_minor: 40_000_000, elasticity_bps: 1000, refused: false },
  fact_version: 1,
  confirmed_at: "2026-07-20T01:02:03Z",
  subject_role: "parent" as const,
  confirming_advisor_role: "advisor" as const,
  confirmed_fact_id: "45000000-0000-0000-0000-000000000001",
  candidate_id: "44000000-0000-0000-0000-000000000001",
  verification_id: "46000000-0000-0000-0000-000000000001",
  source_message_event_id: "43000000-0000-0000-0000-000000000001",
  source_message_sequence_no: 1,
  source_message_sha256_prefix: "aaaaaaaaaaaa",
  confirming_advisor_actor_id: "20000000-0000-0000-0000-000000000001",
  reason: "Confirmed by the assigned advisor.",
  supersedes_fact_id: null,
};

const task = (status: TaskStatus) => ({ task_id: TASK_ID, row_version: 1, status, public_code: null, attempt_count: 1, planning_run_id: status === "preparing" ? null : "70000000-0000-0000-0000-000000000001", updated_at: "2026-07-14T00:00:00Z" });
export function standaloneTask(replayed?: boolean) {
  return {
    schema_version: 1,
    task_id: TASK_ID,
    row_version: 1,
    status: "preparing",
    public_code: null,
    attempt_count: 0,
    planning_run_id: null,
    created_at: "2026-07-14T00:00:00Z",
    updated_at: "2026-07-14T00:00:00Z",
    skill_pin: {
      skill_definition_id: "81000000-0000-0000-0000-000000000002",
      skill_version_id: "82000000-0000-0000-0000-000000000002",
      skill_activation_event_id: "84000000-0000-0000-0000-000000000001",
      skill_activation_sequence: 1,
      runtime_binding_sha256: "cd897b22d034c7aa1c841a3a5d67b70367a8556009cc665b4a27fa16e8170a29",
    },
    leaf_binding: {
      operation: "generate_planning_run_v1",
      adapter_id: "deterministic_planning",
      adapter_version: "m4a-v1",
    },
    ...(replayed === undefined ? {} : { replayed }),
  };
}
const route = (country: "australia" | "japan" | "malaysia", outcome: "recommended_with_condition" | "conditional" | "blocked", eligible: boolean) => ({
  route_id: country === "australia" ? ROUTE_ID : country === "japan" ? "71000000-0000-0000-0000-000000000002" : "71000000-0000-0000-0000-000000000003",
  country,
  outcome,
  reason_code: country === "australia"
    ? "complete_cost_and_fx_within_boundary"
    : country === "japan"
      ? "synthetic_high_risk_alternative"
      : "direct_program_fit_evidence_absent",
  eligible,
  dimensions: [{ key: "program_fit", outcome: eligible ? "supported" : "conditional", reason_code: `${country}_dimension` }],
  cost: country === "australia" ? { source_currency: "AUD" as const, tuition_minor: 1, living_minor: 1, fx_rate: "5", cny_total_minor: 10, fx_source: "synthetic", fx_date: "2026-07-01" } : null,
  ranking: null, required_claims: [`${country}_program_fit`], known_gaps: country === "australia" ? [] : [`${country}_gap`],
});
const evidence = { claim: "australia_program_fit", role: "program_fit", publisher: "Synthetic publisher", institution: "Synthetic institution", snapshot_date: "2026-07-01", authority: "accepted_synthetic_demo" as const, limitation: "Synthetic only", known_gaps: [] };

export function ledger(phase: AdvisorLedger["phase"], status: TaskStatus = "preparing"): AdvisorLedger {
  const base: AdvisorLedger = { schema_version: 1, proof_mode: "synthetic-demo", phase, case_id: CASE_ID, case_revision: 1, case_state: "planning", canonical_task_inputs: null, task: null, planning_run: null, routes: [], evidence: [], review_inputs: null, current_brief_id: null, recovery: null };
  if (phase === "task-ready") base.canonical_task_inputs = { schema_version: 1, operation: "generate_planning_run_v1", case_id: CASE_ID, expected_case_revision: 1, source_pack_id: "50000000-0000-0000-0000-000000000001", source_pack_version: 1, policy_version: "m3a-policy-v1" };
  if (phase === "active-task") { base.canonical_task_inputs = { schema_version: 1, operation: "generate_planning_run_v1", case_id: CASE_ID, expected_case_revision: 1, source_pack_id: "50000000-0000-0000-0000-000000000001", source_pack_version: 1, policy_version: "m3a-policy-v1" }; base.task = task("preparing"); }
  if (phase === "review-required") { base.task = task("needs_advisor_review"); base.planning_run = { planning_run_id: "70000000-0000-0000-0000-000000000001", state: "review_required", source_pack_id: "50000000-0000-0000-0000-000000000001", source_pack_version: 1, policy_version: "m3a-policy-v1", source_snapshot_date: "2026-07-01" }; base.routes = [route("australia", "recommended_with_condition", true), route("japan", "conditional", false), route("malaysia", "blocked", false)]; base.evidence = [evidence]; base.review_inputs = { planning_run_id: base.planning_run.planning_run_id, expected_case_revision: 1, eligible_route_ids: [ROUTE_ID], risk_acceptance_options: [] }; }
  if (phase === "family-review" || phase === "plan-ready") { base.case_state = phase === "plan-ready" ? "plan_ready" : "family_review"; base.task = task("needs_advisor_review"); base.current_brief_id = BRIEF_ID; }
  if (phase === "terminal-task-failure") { base.task = task(status); base.recovery = { code: status, retry_allowed: status === "failed" || status === "timed_out", guidance: "Review status." }; }
  return base;
}

export function brief(phase: CurrentDecisionBrief["phase"] = "family-review"): CurrentDecisionBrief {
  const value: CurrentDecisionBrief = {
    schema_version: 1, proof_mode: "synthetic-demo", phase, case_id: CASE_ID, brief_id: BRIEF_ID, brief_version: 1, source_snapshot_date: "2026-07-01",
    family_safe_projection: { schema_version: 1, intake: "2027-02", routes: [{ route_id: ROUTE_ID, country: "australia", outcome: "recommended_with_condition", reason_code: "complete" }], eligible_route_ids: [ROUTE_ID], accepted_evidence_risks: [], synthetic_proof: true },
    decision_requirements: { schema_version: 1, eligible_route_id: ROUTE_ID, currency: "CNY", pinned_cost_minor: 30_550_000, hard_ceiling_minor: 40_000_000, required_trade_offs: ["budget_elasticity"] }, receipt: null, timeline: null,
  };
  if (phase === "plan-ready") {
    value.receipt = { schema_version: 1, decision_id: "82000000-0000-0000-0000-000000000301", receipt_id: "83000000-0000-0000-0000-000000000301", selected_route_id: ROUTE_ID, accepted_budget_min_minor: 30_550_000, accepted_budget_max_minor: 40_000_000, currency: "CNY", accepted_trade_offs: ["budget_elasticity"], decision_made_by_actor_id: "20000000-0000-0000-0000-000000000003", recorded_by_actor_id: "20000000-0000-0000-0000-000000000001", source: "family_consultation" };
    value.timeline = { schema_version: 1, country: "australia", intake: "2027-02", milestones: [{ key: "documents", due_date: "2026-09-01" }] };
  }
  return value;
}
