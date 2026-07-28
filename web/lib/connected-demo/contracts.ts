import type { BudgetValue } from "../collaboration-demo/contracts";

export type DemoPhaseV2 =
  | "task_ready" | "active_task" | "review_required"
  | "revision_requested" | "revision_fact_pending" | "replan_required"
  | "revision_task_active" | "revision_review_required" | "revision_blocked"
  | "family_review" | "plan_ready" | "terminal_task_failure";
export type DemoPhase = DemoPhaseV2;
export type TaskStatus =
  | "preparing" | "needs_advisor_review" | "ready" | "needs_evidence"
  | "timed_out" | "failed" | "cancelled" | "outdated";
export type Country = "australia" | "japan" | "malaysia";
export type RouteOutcome = "recommended_with_condition" | "conditional" | "blocked";

export interface CanonicalTaskInputs {
  schema_version: 1; operation: "generate_planning_run_v1"; case_id: string;
  expected_case_revision: number; source_pack_id: string; source_pack_version: number;
  policy_version: "m3a-policy-v1";
}
export interface TaskProjection {
  schema_version?: 1; task_id: string; row_version: number; status: TaskStatus;
  public_code: string | null; attempt_count: number; planning_run_id: string | null;
  created_at?: string; updated_at: string; replayed?: boolean;
}
export interface SkillRuntimePin {
  skill_definition_id: string; skill_version_id: string; skill_activation_event_id: string;
  skill_activation_sequence: number; runtime_binding_sha256: string;
}
export type SkillLeafBindingV1 =
  | { operation: "generate_planning_run_v1"; adapter_id: "deterministic_planning"; adapter_version: "m4a-v1" }
  | { operation: "generate_governed_mixed_planning_run_v1"; adapter_id: "governed_mixed_planning"; adapter_version: "dra-mixed-v1" };
type StandaloneTaskRuntimeBinding =
  | { skill_pin: null; leaf_binding: null }
  | { skill_pin: SkillRuntimePin; leaf_binding: SkillLeafBindingV1 };
export type StandaloneTaskProjection = TaskProjection & {
  schema_version: 1; created_at: string;
} & StandaloneTaskRuntimeBinding;
export interface PlanningRunProjection {
  planning_run_id: string; state: "review_required" | "blocked"; source_pack_id: string;
  source_pack_version: number; policy_version: "m3a-policy-v1"; source_snapshot_date: string;
}
export interface PlanningRevisionCountryComparison {
  country: Country;
  delta: "added" | "removed" | "changed" | "unchanged";
  previous_outcome: RouteOutcome | null;
  previous_reason_code: string | null;
  current_outcome: RouteOutcome | null;
  current_reason_code: string | null;
}
export interface PlanningRevisionComparison {
  schema: "night-voyager.planning-revision-comparison.v1";
  case_id: string;
  previous_revision: number;
  current_revision: number;
  previous_planning_run_id: string;
  current_planning_run_id: string;
  previous_output_sha256: string;
  current_output_sha256: string;
  changed_fact:
    | { fact_key: "student.preferred_countries"; previous_value: Country[]; current_value: Country[] }
    | { fact_key: "family.budget"; previous_value: BudgetValue; current_value: BudgetValue };
  countries: PlanningRevisionCountryComparison[];
  current_run_state: "review_required" | "blocked";
  approval_eligible: boolean;
}
export interface RouteProjection {
  route_id: string; country: Country; outcome: RouteOutcome; reason_code: string;
  eligible: boolean; dimensions: Array<{ key: string; outcome: string; reason_code: string }>;
  cost: null | { source_currency: "AUD"; tuition_minor: number; living_minor: number; fx_rate: string | number; cny_total_minor: number; fx_source: string; fx_date: string };
  ranking: null | { ranking_system: string; rank: number; publication_year: number };
  required_claims: string[]; known_gaps: string[];
}
export interface EvidenceProjection {
  claim: string; role: string; publisher: string; institution: string; snapshot_date: string;
  authority: "accepted_synthetic_demo"; limitation: string; known_gaps: string[];
}
export interface AdvisorLedger {
  schema_version: 2; proof_mode: "synthetic-demo"; phase: DemoPhaseV2; case_id: string;
  case_revision: number; case_state: string; canonical_task_inputs: CanonicalTaskInputs | null;
  task: TaskProjection | null; planning_run: PlanningRunProjection | null;
  comparison: PlanningRevisionComparison | null;
  routes: RouteProjection[]; evidence: EvidenceProjection[];
  review_inputs: null | { planning_run_id: string; expected_case_revision: number;
    eligible_route_ids: string[]; risk_acceptance_options: Array<{ evidence_id: string; kind: "optional" | "stale" | "unverified"; reason: string }> };
  current_brief_id: string | null;
  recovery: null | { code: string; retry_allowed: boolean; guidance: string };
}
export interface BriefRoute { route_id: string; country: Country; outcome: RouteOutcome; reason_code: string }
export interface DecisionReceipt {
  schema_version: 1; decision_id: string; receipt_id: string; selected_route_id: string;
  accepted_budget_min_minor: number; accepted_budget_max_minor: number; currency: "CNY";
  accepted_trade_offs: string[]; decision_made_by_actor_id: string; recorded_by_actor_id: string;
  source: "direct" | "family_consultation";
}
export interface Timeline { schema_version: 1; country: Country; intake: string; milestones: Array<{ key: string; due_date: string }> }
export interface CurrentDecisionBrief {
  schema_version: 2; proof_mode: "synthetic-demo"; phase: "family_review" | "plan_ready";
  case_id: string; brief_id: string; brief_version: number; source_snapshot_date: string;
  family_safe_projection: { schema_version: 1; intake: string; routes: BriefRoute[];
    eligible_route_ids: string[]; accepted_evidence_risks: Array<{ evidence_id: string; kind: "optional" | "stale" | "unverified"; reason: string }>;
    synthetic_proof: boolean };
  decision_requirements: { schema_version: 1; eligible_route_id: string; currency: "CNY";
    pinned_cost_minor: number; hard_ceiling_minor: number; required_trade_offs: ["budget_elasticity"] };
  revision_context: {
    schema: "night-voyager.family-revision-context.v1";
    current_case_revision: number;
    planning_version: "initial" | "revised";
    advisor_authorization: "authorized_for_initial_revision" | "renewed_for_current_revision";
  };
  receipt: DecisionReceipt | null; timeline: Timeline | null;
}
export interface ConnectedJourneyStatus {
  schema: "night-voyager.connected-journey-status.v1";
  case_id: string;
  current_revision: number;
  phase: DemoPhaseV2;
  active_role: "advisor" | "student" | "parent";
}
export interface SessionProjection { role: "advisor" | "student" | "parent"; proof_mode: "synthetic-demo"; csrf_token: string }
export type CreateTaskBody = Omit<CanonicalTaskInputs, "case_id">;
export interface CancelTaskBody { schema_version: 1; expected_row_version: number }
type ReviewRisk = { evidence_id: string; kind: "optional" | "stale" | "unverified"; reason: string };
export type AdvisorReviewBody =
  | { schema_version: 1; planning_run_id: string; expected_case_revision: number; action: "approve_for_consultation"; eligible_route_ids: string[]; risk_acceptances: ReviewRisk[]; reviewer_notes?: null }
  | { schema_version: 1; planning_run_id: string; expected_case_revision: number; action: "request_revision"; eligible_route_ids: []; risk_acceptances: []; reviewer_notes: string };
export interface FamilyDecisionBody { schema_version: 1; expected_brief_version: number; selected_route_id: string; accepted_budget_min_minor: number; accepted_budget_max_minor: number; currency: "CNY"; accepted_trade_offs: ["budget_elasticity"] }
export type ReviewResult = Record<string, unknown>;
export type DecisionResult = Record<string, unknown>;

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const SHA256 = /^[0-9a-f]{64}$/;
const PHASES: readonly DemoPhaseV2[] = [
  "task_ready", "active_task", "review_required", "revision_requested",
  "revision_fact_pending", "replan_required", "revision_task_active",
  "revision_review_required", "revision_blocked", "family_review",
  "plan_ready", "terminal_task_failure",
];
const STATUSES = ["preparing", "needs_advisor_review", "ready", "needs_evidence", "timed_out", "failed", "cancelled", "outdated"];
const COUNTRIES = ["australia", "japan", "malaysia"];
const OUTCOMES = ["recommended_with_condition", "conditional", "blocked"];
function object(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function exact(value: Record<string, unknown>, keys: readonly string[]): boolean { const a = Object.keys(value).sort(); const b = [...keys].sort(); return a.length === b.length && a.every((key, index) => key === b[index]); }
function uuid(value: unknown): value is string { return typeof value === "string" && UUID.test(value); }
function positive(value: unknown): value is number { return Number.isSafeInteger(value) && Number(value) > 0; }
function nonnegative(value: unknown): value is number { return Number.isSafeInteger(value) && Number(value) >= 0; }
function strings(value: unknown): value is string[] { return Array.isArray(value) && value.every((item) => typeof item === "string"); }
function date(value: unknown): value is string { return typeof value === "string" && DATE.test(value); }
function risk(value: unknown): boolean { return object(value) && exact(value, ["evidence_id", "kind", "reason"]) && uuid(value.evidence_id) && ["optional", "stale", "unverified"].includes(String(value.kind)) && typeof value.reason === "string"; }
function skillPin(value: unknown): value is SkillRuntimePin {
  return object(value) && exact(value, ["skill_definition_id", "skill_version_id", "skill_activation_event_id", "skill_activation_sequence", "runtime_binding_sha256"]) && uuid(value.skill_definition_id) && uuid(value.skill_version_id) && uuid(value.skill_activation_event_id) && positive(value.skill_activation_sequence) && typeof value.runtime_binding_sha256 === "string" && SHA256.test(value.runtime_binding_sha256);
}
function leafBinding(value: unknown): value is SkillLeafBindingV1 {
  if (!object(value) || !exact(value, ["operation", "adapter_id", "adapter_version"])) return false;
  return (value.operation === "generate_planning_run_v1" && value.adapter_id === "deterministic_planning" && value.adapter_version === "m4a-v1") || (value.operation === "generate_governed_mixed_planning_run_v1" && value.adapter_id === "governed_mixed_planning" && value.adapter_version === "dra-mixed-v1");
}
function task(value: unknown, standalone = false): value is TaskProjection {
  if (!object(value)) return false;
  const keys = ["task_id", "row_version", "status", "public_code", "attempt_count", "planning_run_id", "updated_at", ...(standalone ? ["schema_version", "created_at", "skill_pin", "leaf_binding"] : []), ...(standalone && "replayed" in value ? ["replayed"] : [])];
  const validRuntimeBinding = !standalone || (value.skill_pin === null && value.leaf_binding === null) || (skillPin(value.skill_pin) && leafBinding(value.leaf_binding));
  return exact(value, keys) && (!standalone || value.schema_version === 1) && uuid(value.task_id) && positive(value.row_version) && STATUSES.includes(String(value.status)) && (value.public_code === null || typeof value.public_code === "string") && nonnegative(value.attempt_count) && (value.planning_run_id === null || uuid(value.planning_run_id)) && (!standalone || typeof value.created_at === "string") && typeof value.updated_at === "string" && (!standalone || !("replayed" in value) || typeof value.replayed === "boolean") && validRuntimeBinding;
}
function canonical(value: unknown): value is CanonicalTaskInputs { return object(value) && exact(value, ["schema_version", "operation", "case_id", "expected_case_revision", "source_pack_id", "source_pack_version", "policy_version"]) && value.schema_version === 1 && value.operation === "generate_planning_run_v1" && uuid(value.case_id) && positive(value.expected_case_revision) && uuid(value.source_pack_id) && positive(value.source_pack_version) && value.policy_version === "m3a-policy-v1"; }
function planningRun(value: unknown): value is PlanningRunProjection { return object(value) && exact(value, ["planning_run_id", "state", "source_pack_id", "source_pack_version", "policy_version", "source_snapshot_date"]) && uuid(value.planning_run_id) && ["review_required", "blocked"].includes(String(value.state)) && uuid(value.source_pack_id) && positive(value.source_pack_version) && value.policy_version === "m3a-policy-v1" && date(value.source_snapshot_date); }
function dimension(value: unknown): boolean { return object(value) && exact(value, ["key", "outcome", "reason_code"]) && typeof value.key === "string" && typeof value.outcome === "string" && typeof value.reason_code === "string"; }
function route(value: unknown): value is RouteProjection {
  if (!object(value) || !exact(value, ["route_id", "country", "outcome", "reason_code", "eligible", "dimensions", "cost", "ranking", "required_claims", "known_gaps"])) return false;
  const cost = value.cost === null || (object(value.cost) && exact(value.cost, ["source_currency", "tuition_minor", "living_minor", "fx_rate", "cny_total_minor", "fx_source", "fx_date"]) && value.cost.source_currency === "AUD" && nonnegative(value.cost.tuition_minor) && nonnegative(value.cost.living_minor) && (typeof value.cost.fx_rate === "number" || typeof value.cost.fx_rate === "string") && positive(value.cost.cny_total_minor) && typeof value.cost.fx_source === "string" && date(value.cost.fx_date));
  const ranking = value.ranking === null || (object(value.ranking) && exact(value.ranking, ["ranking_system", "rank", "publication_year"]) && typeof value.ranking.ranking_system === "string" && positive(value.ranking.rank) && positive(value.ranking.publication_year));
  return uuid(value.route_id) && COUNTRIES.includes(String(value.country)) && OUTCOMES.includes(String(value.outcome)) && typeof value.reason_code === "string" && typeof value.eligible === "boolean" && Array.isArray(value.dimensions) && value.dimensions.every(dimension) && cost && ranking && strings(value.required_claims) && strings(value.known_gaps);
}
function evidence(value: unknown): value is EvidenceProjection { return object(value) && exact(value, ["claim", "role", "publisher", "institution", "snapshot_date", "authority", "limitation", "known_gaps"]) && typeof value.claim === "string" && typeof value.role === "string" && typeof value.publisher === "string" && typeof value.institution === "string" && date(value.snapshot_date) && value.authority === "accepted_synthetic_demo" && typeof value.limitation === "string" && strings(value.known_gaps); }
function reviewInputs(value: unknown): boolean { return object(value) && exact(value, ["planning_run_id", "expected_case_revision", "eligible_route_ids", "risk_acceptance_options"]) && uuid(value.planning_run_id) && positive(value.expected_case_revision) && Array.isArray(value.eligible_route_ids) && value.eligible_route_ids.every(uuid) && Array.isArray(value.risk_acceptance_options) && value.risk_acceptance_options.every(risk); }
function recovery(value: unknown): boolean { return object(value) && exact(value, ["code", "retry_allowed", "guidance"]) && typeof value.code === "string" && typeof value.retry_allowed === "boolean" && typeof value.guidance === "string"; }
function countryScope(value: unknown): value is Country[] {
  return Array.isArray(value) && value.length > 0 && value.every((item) => COUNTRIES.includes(String(item))) && new Set(value).size === value.length && value.join() === [...value].sort().join();
}
function budget(value: unknown): value is BudgetValue {
  if (!object(value) || !exact(value, ["schema_version", "currency", "period", "preferred_minor", "hard_ceiling_minor", "elasticity_bps", "refused"])) return false;
  if (value.schema_version !== 1 || value.currency !== "CNY" || value.period !== "program_total" || typeof value.refused !== "boolean" || !Number.isSafeInteger(value.elasticity_bps) || Number(value.elasticity_bps) < 0 || Number(value.elasticity_bps) > 2500) return false;
  if (value.refused) return value.preferred_minor === null && value.hard_ceiling_minor === null;
  return positive(value.preferred_minor) && positive(value.hard_ceiling_minor) && Number(value.preferred_minor) <= Number(value.hard_ceiling_minor);
}
function changedFact(value: unknown): boolean {
  if (!object(value) || !exact(value, ["fact_key", "previous_value", "current_value"])) return false;
  if (value.fact_key === "student.preferred_countries") return countryScope(value.previous_value) && countryScope(value.current_value) && JSON.stringify(value.previous_value) !== JSON.stringify(value.current_value);
  if (value.fact_key === "family.budget") return budget(value.previous_value) && budget(value.current_value) && JSON.stringify(value.previous_value) !== JSON.stringify(value.current_value);
  return false;
}
function nullableOutcomeReason(outcome: unknown, reason: unknown): boolean {
  return (outcome === null && reason === null) || (OUTCOMES.includes(String(outcome)) && typeof reason === "string" && /^[a-z0-9][a-z0-9_]{0,99}$/.test(reason));
}
function comparisonCountry(value: unknown): value is PlanningRevisionCountryComparison {
  if (!object(value) || !exact(value, ["country", "delta", "previous_outcome", "previous_reason_code", "current_outcome", "current_reason_code"]) || !COUNTRIES.includes(String(value.country)) || !["added", "removed", "changed", "unchanged"].includes(String(value.delta)) || !nullableOutcomeReason(value.previous_outcome, value.previous_reason_code) || !nullableOutcomeReason(value.current_outcome, value.current_reason_code)) return false;
  const previous = value.previous_outcome !== null;
  const current = value.current_outcome !== null;
  if (value.delta === "added") return !previous && current;
  if (value.delta === "removed") return previous && !current;
  if (!previous || !current) return false;
  const same = value.previous_outcome === value.current_outcome && value.previous_reason_code === value.current_reason_code;
  return value.delta === "unchanged" ? same : !same;
}
function comparison(value: unknown): value is PlanningRevisionComparison {
  const keys = ["schema", "case_id", "previous_revision", "current_revision", "previous_planning_run_id", "current_planning_run_id", "previous_output_sha256", "current_output_sha256", "changed_fact", "countries", "current_run_state", "approval_eligible"];
  if (!object(value) || !exact(value, keys) || value.schema !== "night-voyager.planning-revision-comparison.v1" || !uuid(value.case_id) || !positive(value.previous_revision) || value.current_revision !== Number(value.previous_revision) + 1 || !uuid(value.previous_planning_run_id) || !uuid(value.current_planning_run_id) || typeof value.previous_output_sha256 !== "string" || !SHA256.test(value.previous_output_sha256) || typeof value.current_output_sha256 !== "string" || !SHA256.test(value.current_output_sha256) || !changedFact(value.changed_fact) || !Array.isArray(value.countries) || !value.countries.every(comparisonCountry) || !["review_required", "blocked"].includes(String(value.current_run_state)) || typeof value.approval_eligible !== "boolean" || value.approval_eligible !== (value.current_run_state === "review_required")) return false;
  const countries = value.countries.map((item) => (item as PlanningRevisionCountryComparison).country);
  return countries.join() === [...new Set(countries)].sort().join();
}
function phaseValid(value: Record<string, unknown>): boolean {
  const hasTask = value.task !== null; const hasRun = value.planning_run !== null; const hasRoutes = Array.isArray(value.routes) && value.routes.length > 0; const hasEvidence = Array.isArray(value.evidence) && value.evidence.length > 0;
  switch (value.phase) {
    case "task_ready": return value.canonical_task_inputs !== null && !hasTask && !hasRun && !hasRoutes && !hasEvidence && value.comparison === null && value.review_inputs === null && value.current_brief_id === null && value.recovery === null;
    case "active_task": return value.canonical_task_inputs !== null && hasTask && (value.task as TaskProjection).status === "preparing" && !hasRun && !hasRoutes && !hasEvidence && value.comparison === null && value.review_inputs === null && value.current_brief_id === null && value.recovery === null;
    case "review_required": return hasTask && (value.task as TaskProjection).status === "needs_advisor_review" && hasRun && (value.planning_run as PlanningRunProjection).state === "review_required" && hasRoutes && hasEvidence && value.comparison === null && value.review_inputs !== null && value.current_brief_id === null && value.recovery === null;
    case "revision_requested":
    case "revision_fact_pending": return hasTask && hasRun && value.comparison === null && value.current_brief_id === null && value.recovery === null;
    case "replan_required": return value.case_revision !== 1 && !hasTask && !hasRun && value.comparison === null && value.review_inputs === null && value.current_brief_id === null && value.recovery === null;
    case "revision_task_active": return value.case_revision !== 1 && hasTask && (value.task as TaskProjection).status === "preparing" && !hasRun && value.comparison === null && value.review_inputs === null && value.current_brief_id === null && value.recovery === null;
    case "revision_review_required": return value.case_revision !== 1 && hasTask && (value.task as TaskProjection).status === "needs_advisor_review" && hasRun && (value.planning_run as PlanningRunProjection).state === "review_required" && value.comparison !== null && value.review_inputs !== null && value.current_brief_id === null && value.recovery === null;
    case "revision_blocked": return value.case_revision !== 1 && hasTask && (value.task as TaskProjection).status === "needs_evidence" && hasRun && (value.planning_run as PlanningRunProjection).state === "blocked" && value.comparison !== null && value.review_inputs === null && value.current_brief_id === null && value.recovery === null;
    case "family_review": case "plan_ready": return value.canonical_task_inputs === null && !hasRun && !hasRoutes && !hasEvidence && value.comparison === null && value.current_brief_id !== null && value.review_inputs === null && value.recovery === null;
    case "terminal_task_failure": return hasTask && ["needs_evidence", "timed_out", "failed", "cancelled", "outdated"].includes((value.task as TaskProjection).status) && !hasRun && !hasRoutes && !hasEvidence && value.comparison === null && value.review_inputs === null && value.current_brief_id === null && value.recovery !== null;
    default: return false;
  }
}

export function parseBootstrap(value: unknown): { csrf_token: string } { if (!object(value) || !exact(value, ["csrf_token"]) || typeof value.csrf_token !== "string" || !value.csrf_token) throw new Error("invalid response"); return { csrf_token: value.csrf_token }; }
export function parseSession(value: unknown): SessionProjection { if (!object(value) || !exact(value, ["role", "proof_mode", "csrf_token"]) || !["advisor", "student", "parent"].includes(String(value.role)) || value.proof_mode !== "synthetic-demo" || typeof value.csrf_token !== "string" || !value.csrf_token) throw new Error("invalid response"); return value as unknown as SessionProjection; }
export function parseJourneyStatus(value: unknown): ConnectedJourneyStatus {
  if (!object(value) || !exact(value, ["schema", "case_id", "current_revision", "phase", "active_role"]) || value.schema !== "night-voyager.connected-journey-status.v1" || !uuid(value.case_id) || !positive(value.current_revision) || !PHASES.includes(value.phase as DemoPhaseV2) || !["advisor", "student", "parent"].includes(String(value.active_role))) throw new Error("invalid response");
  const expectedRole = value.phase === "revision_requested" ? "student" : value.phase === "family_review" || value.phase === "plan_ready" ? "parent" : "advisor";
  if (value.active_role !== expectedRole) throw new Error("invalid response");
  return value as unknown as ConnectedJourneyStatus;
}
export function parseLedger(value: unknown): AdvisorLedger {
  const keys = ["schema_version", "proof_mode", "phase", "case_id", "case_revision", "case_state", "canonical_task_inputs", "task", "planning_run", "comparison", "routes", "evidence", "review_inputs", "current_brief_id", "recovery"];
  if (!object(value) || !exact(value, keys) || value.schema_version !== 2 || value.proof_mode !== "synthetic-demo" || !PHASES.includes(value.phase as DemoPhaseV2) || !uuid(value.case_id) || !positive(value.case_revision) || typeof value.case_state !== "string" || !(value.canonical_task_inputs === null || canonical(value.canonical_task_inputs)) || !(value.task === null || task(value.task)) || !(value.planning_run === null || planningRun(value.planning_run)) || !(value.comparison === null || comparison(value.comparison)) || !Array.isArray(value.routes) || !value.routes.every(route) || !Array.isArray(value.evidence) || !value.evidence.every(evidence) || !(value.review_inputs === null || reviewInputs(value.review_inputs)) || !(value.current_brief_id === null || uuid(value.current_brief_id)) || !(value.recovery === null || recovery(value.recovery)) || !phaseValid(value)) throw new Error("invalid response");
  if (value.comparison && (value.comparison.case_id !== value.case_id || value.comparison.current_revision !== value.case_revision || value.comparison.current_planning_run_id !== (value.planning_run as PlanningRunProjection | null)?.planning_run_id)) throw new Error("invalid response");
  return value as unknown as AdvisorLedger;
}
function briefRoute(value: unknown): value is BriefRoute { return object(value) && exact(value, ["route_id", "country", "outcome", "reason_code"]) && uuid(value.route_id) && COUNTRIES.includes(String(value.country)) && OUTCOMES.includes(String(value.outcome)) && typeof value.reason_code === "string"; }
function familyProjection(value: unknown): boolean { return object(value) && exact(value, ["schema_version", "intake", "routes", "eligible_route_ids", "accepted_evidence_risks", "synthetic_proof"]) && value.schema_version === 1 && typeof value.intake === "string" && Array.isArray(value.routes) && value.routes.every(briefRoute) && Array.isArray(value.eligible_route_ids) && value.eligible_route_ids.every(uuid) && Array.isArray(value.accepted_evidence_risks) && value.accepted_evidence_risks.every(risk) && typeof value.synthetic_proof === "boolean"; }
function requirements(value: unknown): boolean { return object(value) && exact(value, ["schema_version", "eligible_route_id", "currency", "pinned_cost_minor", "hard_ceiling_minor", "required_trade_offs"]) && value.schema_version === 1 && uuid(value.eligible_route_id) && value.currency === "CNY" && positive(value.pinned_cost_minor) && positive(value.hard_ceiling_minor) && Number(value.pinned_cost_minor) <= Number(value.hard_ceiling_minor) && JSON.stringify(value.required_trade_offs) === '["budget_elasticity"]'; }
function receipt(value: unknown): value is DecisionReceipt { return object(value) && exact(value, ["schema_version", "decision_id", "receipt_id", "selected_route_id", "accepted_budget_min_minor", "accepted_budget_max_minor", "currency", "accepted_trade_offs", "decision_made_by_actor_id", "recorded_by_actor_id", "source"]) && value.schema_version === 1 && uuid(value.decision_id) && uuid(value.receipt_id) && uuid(value.selected_route_id) && positive(value.accepted_budget_min_minor) && positive(value.accepted_budget_max_minor) && Number(value.accepted_budget_min_minor) <= Number(value.accepted_budget_max_minor) && value.currency === "CNY" && strings(value.accepted_trade_offs) && uuid(value.decision_made_by_actor_id) && uuid(value.recorded_by_actor_id) && ["direct", "family_consultation"].includes(String(value.source)); }
function timeline(value: unknown): value is Timeline { return object(value) && exact(value, ["schema_version", "country", "intake", "milestones"]) && value.schema_version === 1 && COUNTRIES.includes(String(value.country)) && typeof value.intake === "string" && Array.isArray(value.milestones) && value.milestones.every((item) => object(item) && exact(item, ["key", "due_date"]) && typeof item.key === "string" && date(item.due_date)); }
function briefConsistent(value: Record<string, unknown>): boolean {
  const projection = value.family_safe_projection as CurrentDecisionBrief["family_safe_projection"];
  const required = value.decision_requirements as CurrentDecisionBrief["decision_requirements"];
  const selected = projection.routes.find((route) => route.route_id === required.eligible_route_id);
  if (!selected || selected.country !== "australia" || selected.outcome !== "recommended_with_condition" || !projection.eligible_route_ids.includes(required.eligible_route_id)) return false;
  if (value.phase === "family_review") return value.receipt === null && value.timeline === null;
  const recorded = value.receipt as DecisionReceipt;
  const plan = value.timeline as Timeline;
  return recorded.selected_route_id === required.eligible_route_id && recorded.currency === required.currency && recorded.accepted_budget_min_minor <= required.pinned_cost_minor && required.pinned_cost_minor <= recorded.accepted_budget_max_minor && recorded.accepted_budget_max_minor <= required.hard_ceiling_minor && JSON.stringify(recorded.accepted_trade_offs) === JSON.stringify(required.required_trade_offs) && plan.country === selected.country && plan.intake === projection.intake;
}
export function parseBrief(value: unknown): CurrentDecisionBrief {
  const keys = ["schema_version", "proof_mode", "phase", "case_id", "brief_id", "brief_version", "source_snapshot_date", "family_safe_projection", "decision_requirements", "revision_context", "receipt", "timeline"];
  const context = object(value) && object(value.revision_context) ? value.revision_context : null;
  const contextValid = context !== null && exact(context, ["schema", "current_case_revision", "planning_version", "advisor_authorization"]) && context.schema === "night-voyager.family-revision-context.v1" && positive(context.current_case_revision) && ["initial", "revised"].includes(String(context.planning_version)) && ["authorized_for_initial_revision", "renewed_for_current_revision"].includes(String(context.advisor_authorization)) && (context.planning_version === "revised") === (context.advisor_authorization === "renewed_for_current_revision");
  if (!object(value) || !exact(value, keys) || value.schema_version !== 2 || value.proof_mode !== "synthetic-demo" || !["family_review", "plan_ready"].includes(String(value.phase)) || !uuid(value.case_id) || !uuid(value.brief_id) || !positive(value.brief_version) || !date(value.source_snapshot_date) || !familyProjection(value.family_safe_projection) || !requirements(value.decision_requirements) || !contextValid || !(value.receipt === null || receipt(value.receipt)) || !(value.timeline === null || timeline(value.timeline)) || (value.phase === "family_review" ? value.receipt !== null || value.timeline !== null : value.receipt === null || value.timeline === null) || !briefConsistent(value)) throw new Error("invalid response");
  return value as unknown as CurrentDecisionBrief;
}
export function parseTask(value: unknown): StandaloneTaskProjection { if (!task(value, true)) throw new Error("invalid response"); return value as StandaloneTaskProjection; }
