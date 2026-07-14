export type DemoPhase =
  | "task-ready" | "active-task" | "review-required" | "family-review"
  | "plan-ready" | "terminal-task-failure";
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
export interface PlanningRunProjection {
  planning_run_id: string; state: "review_required"; source_pack_id: string;
  source_pack_version: number; policy_version: "m3a-policy-v1"; source_snapshot_date: string;
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
  schema_version: 1; proof_mode: "synthetic-demo"; phase: DemoPhase; case_id: string;
  case_revision: number; case_state: string; canonical_task_inputs: CanonicalTaskInputs | null;
  task: TaskProjection | null; planning_run: PlanningRunProjection | null;
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
  schema_version: 1; proof_mode: "synthetic-demo"; phase: "family-review" | "plan-ready";
  case_id: string; brief_id: string; brief_version: number; source_snapshot_date: string;
  family_safe_projection: { schema_version: 1; intake: string; routes: BriefRoute[];
    eligible_route_ids: string[]; accepted_evidence_risks: Array<{ evidence_id: string; kind: "optional" | "stale" | "unverified"; reason: string }>;
    synthetic_proof: boolean };
  decision_requirements: { schema_version: 1; eligible_route_id: string; currency: "CNY";
    pinned_cost_minor: number; hard_ceiling_minor: number; required_trade_offs: ["budget_elasticity"] };
  receipt: DecisionReceipt | null; timeline: Timeline | null;
}
export interface SessionProjection { role: "advisor" | "parent"; proof_mode: "synthetic-demo"; csrf_token: string }
export type CreateTaskBody = Omit<CanonicalTaskInputs, "case_id">;
export interface CancelTaskBody { schema_version: 1; expected_row_version: number }
export interface AdvisorReviewBody { schema_version: 1; planning_run_id: string; expected_case_revision: number; action: "approve_for_consultation"; eligible_route_ids: string[]; risk_acceptances: Array<{ evidence_id: string; kind: "optional" | "stale" | "unverified"; reason: string }> }
export interface FamilyDecisionBody { schema_version: 1; expected_brief_version: number; selected_route_id: string; accepted_budget_min_minor: number; accepted_budget_max_minor: number; currency: "CNY"; accepted_trade_offs: ["budget_elasticity"] }
export type ReviewResult = Record<string, unknown>;
export type DecisionResult = Record<string, unknown>;

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const PHASES = ["task-ready", "active-task", "review-required", "family-review", "plan-ready", "terminal-task-failure"];
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
function task(value: unknown, standalone = false): value is TaskProjection {
  if (!object(value)) return false;
  const keys = ["task_id", "row_version", "status", "public_code", "attempt_count", "planning_run_id", "updated_at", ...(standalone ? ["schema_version", "created_at"] : []), ...(standalone && "replayed" in value ? ["replayed"] : [])];
  return exact(value, keys) && (!standalone || value.schema_version === 1) && uuid(value.task_id) && positive(value.row_version) && STATUSES.includes(String(value.status)) && (value.public_code === null || typeof value.public_code === "string") && nonnegative(value.attempt_count) && (value.planning_run_id === null || uuid(value.planning_run_id)) && (!standalone || typeof value.created_at === "string") && typeof value.updated_at === "string" && (!standalone || !("replayed" in value) || typeof value.replayed === "boolean");
}
function canonical(value: unknown): value is CanonicalTaskInputs { return object(value) && exact(value, ["schema_version", "operation", "case_id", "expected_case_revision", "source_pack_id", "source_pack_version", "policy_version"]) && value.schema_version === 1 && value.operation === "generate_planning_run_v1" && uuid(value.case_id) && positive(value.expected_case_revision) && uuid(value.source_pack_id) && positive(value.source_pack_version) && value.policy_version === "m3a-policy-v1"; }
function planningRun(value: unknown): value is PlanningRunProjection { return object(value) && exact(value, ["planning_run_id", "state", "source_pack_id", "source_pack_version", "policy_version", "source_snapshot_date"]) && uuid(value.planning_run_id) && value.state === "review_required" && uuid(value.source_pack_id) && positive(value.source_pack_version) && value.policy_version === "m3a-policy-v1" && date(value.source_snapshot_date); }
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
function phaseValid(value: Record<string, unknown>): boolean {
  const hasTask = value.task !== null; const hasRun = value.planning_run !== null; const hasRoutes = Array.isArray(value.routes) && value.routes.length > 0; const hasEvidence = Array.isArray(value.evidence) && value.evidence.length > 0;
  switch (value.phase) {
    case "task-ready": return value.canonical_task_inputs !== null && !hasTask && !hasRun && !hasRoutes && !hasEvidence && value.review_inputs === null && value.current_brief_id === null && value.recovery === null;
    case "active-task": return value.canonical_task_inputs !== null && hasTask && (value.task as TaskProjection).status === "preparing" && !hasRun && !hasRoutes && !hasEvidence && value.review_inputs === null && value.current_brief_id === null && value.recovery === null;
    case "review-required": return hasTask && (value.task as TaskProjection).status === "needs_advisor_review" && hasRun && hasRoutes && hasEvidence && value.review_inputs !== null && value.current_brief_id === null && value.recovery === null;
    case "family-review": case "plan-ready": return value.canonical_task_inputs === null && !hasRun && !hasRoutes && !hasEvidence && value.current_brief_id !== null && value.review_inputs === null && value.recovery === null;
    case "terminal-task-failure": return hasTask && ["needs_evidence", "timed_out", "failed", "cancelled", "outdated"].includes((value.task as TaskProjection).status) && !hasRun && !hasRoutes && !hasEvidence && value.review_inputs === null && value.current_brief_id === null && value.recovery !== null;
    default: return false;
  }
}

export function parseBootstrap(value: unknown): { csrf_token: string } { if (!object(value) || !exact(value, ["csrf_token"]) || typeof value.csrf_token !== "string" || !value.csrf_token) throw new Error("invalid response"); return { csrf_token: value.csrf_token }; }
export function parseSession(value: unknown): SessionProjection { if (!object(value) || !exact(value, ["role", "proof_mode", "csrf_token"]) || !["advisor", "parent"].includes(String(value.role)) || value.proof_mode !== "synthetic-demo" || typeof value.csrf_token !== "string" || !value.csrf_token) throw new Error("invalid response"); return value as unknown as SessionProjection; }
export function parseLedger(value: unknown): AdvisorLedger {
  const keys = ["schema_version", "proof_mode", "phase", "case_id", "case_revision", "case_state", "canonical_task_inputs", "task", "planning_run", "routes", "evidence", "review_inputs", "current_brief_id", "recovery"];
  if (!object(value) || !exact(value, keys) || value.schema_version !== 1 || value.proof_mode !== "synthetic-demo" || !PHASES.includes(String(value.phase)) || !uuid(value.case_id) || !positive(value.case_revision) || typeof value.case_state !== "string" || !(value.canonical_task_inputs === null || canonical(value.canonical_task_inputs)) || !(value.task === null || task(value.task)) || !(value.planning_run === null || planningRun(value.planning_run)) || !Array.isArray(value.routes) || !value.routes.every(route) || !Array.isArray(value.evidence) || !value.evidence.every(evidence) || !(value.review_inputs === null || reviewInputs(value.review_inputs)) || !(value.current_brief_id === null || uuid(value.current_brief_id)) || !(value.recovery === null || recovery(value.recovery)) || !phaseValid(value)) throw new Error("invalid response");
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
  if (value.phase === "family-review") return value.receipt === null && value.timeline === null;
  const recorded = value.receipt as DecisionReceipt;
  const plan = value.timeline as Timeline;
  return recorded.selected_route_id === required.eligible_route_id && recorded.currency === required.currency && recorded.accepted_budget_min_minor <= required.pinned_cost_minor && required.pinned_cost_minor <= recorded.accepted_budget_max_minor && recorded.accepted_budget_max_minor <= required.hard_ceiling_minor && JSON.stringify(recorded.accepted_trade_offs) === JSON.stringify(required.required_trade_offs) && plan.country === selected.country && plan.intake === projection.intake;
}
export function parseBrief(value: unknown): CurrentDecisionBrief {
  const keys = ["schema_version", "proof_mode", "phase", "case_id", "brief_id", "brief_version", "source_snapshot_date", "family_safe_projection", "decision_requirements", "receipt", "timeline"];
  if (!object(value) || !exact(value, keys) || value.schema_version !== 1 || value.proof_mode !== "synthetic-demo" || !["family-review", "plan-ready"].includes(String(value.phase)) || !uuid(value.case_id) || !uuid(value.brief_id) || !positive(value.brief_version) || !date(value.source_snapshot_date) || !familyProjection(value.family_safe_projection) || !requirements(value.decision_requirements) || !(value.receipt === null || receipt(value.receipt)) || !(value.timeline === null || timeline(value.timeline)) || (value.phase === "family-review" ? value.receipt !== null || value.timeline !== null : value.receipt === null || value.timeline === null) || !briefConsistent(value)) throw new Error("invalid response");
  return value as unknown as CurrentDecisionBrief;
}
export function parseTask(value: unknown): TaskProjection { if (!task(value, true)) throw new Error("invalid response"); return value; }
