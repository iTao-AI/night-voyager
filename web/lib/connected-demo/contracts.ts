export type DemoPhase =
  | "task-ready"
  | "active-task"
  | "review-required"
  | "family-review"
  | "plan-ready"
  | "terminal-task-failure";

export interface CanonicalTaskInputs {
  schema_version: 1;
  operation: "generate_planning_run_v1";
  case_id: string;
  expected_case_revision: number;
  source_pack_id: string;
  source_pack_version: number;
  policy_version: "m3a-policy-v1";
}

export interface TaskProjection {
  schema_version?: 1;
  task_id: string;
  row_version: number;
  status: string;
  public_code: string | null;
  attempt_count: number;
  planning_run_id: string | null;
  updated_at: string;
  replayed?: boolean;
}

export interface AdvisorLedger {
  schema_version: 1;
  proof_mode: "synthetic-demo";
  phase: DemoPhase;
  case_id: string;
  case_revision: number;
  case_state: string;
  canonical_task_inputs: CanonicalTaskInputs | null;
  task: TaskProjection | null;
  planning_run: Record<string, unknown> | null;
  routes: Array<Record<string, unknown>>;
  evidence: Array<Record<string, unknown>>;
  review_inputs: {
    planning_run_id: string;
    expected_case_revision: number;
    eligible_route_ids: string[];
    risk_acceptance_options: Array<Record<string, unknown>>;
  } | null;
  current_brief_id: string | null;
  recovery: Record<string, unknown> | null;
}

export interface CurrentDecisionBrief {
  schema_version: 1;
  proof_mode: "synthetic-demo";
  phase: "family-review" | "plan-ready";
  case_id: string;
  brief_id: string;
  brief_version: number;
  source_snapshot_date: string;
  family_safe_projection: {
    intake: string;
    routes: Array<Record<string, unknown>>;
    eligible_route_ids: string[];
    accepted_evidence_risks: Array<Record<string, unknown>>;
    synthetic_proof: boolean;
  };
  decision_requirements: {
    schema_version: 1;
    eligible_route_id: string;
    currency: "CNY";
    pinned_cost_minor: number;
    hard_ceiling_minor: number;
    required_trade_offs: ["budget_elasticity"];
  };
  receipt: Record<string, unknown> | null;
  timeline: Record<string, unknown> | null;
}

export interface SessionProjection {
  role: "advisor" | "parent";
  proof_mode: "synthetic-demo";
  csrf_token: string;
}

export type CreateTaskBody = Omit<CanonicalTaskInputs, "case_id">;

export interface CancelTaskBody {
  schema_version: 1;
  expected_row_version: number;
}

export interface AdvisorReviewBody {
  schema_version: 1;
  planning_run_id: string;
  expected_case_revision: number;
  action: "approve_for_consultation";
  eligible_route_ids: string[];
  risk_acceptances: Array<Record<string, unknown>>;
}

export interface FamilyDecisionBody {
  schema_version: 1;
  expected_brief_version: number;
  selected_route_id: string;
  accepted_budget_min_minor: number;
  accepted_budget_max_minor: number;
  currency: "CNY";
  accepted_trade_offs: ["budget_elasticity"];
}

export type ReviewResult = Record<string, unknown>;
export type DecisionResult = Record<string, unknown>;

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function exactKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  const actual = Object.keys(value).sort();
  return actual.length === keys.length && actual.every((key, index) => key === [...keys].sort()[index]);
}

export function parseBootstrap(value: unknown): { csrf_token: string } {
  if (!object(value) || !exactKeys(value, ["csrf_token"]) || typeof value.csrf_token !== "string") {
    throw new Error("invalid response");
  }
  return { csrf_token: value.csrf_token };
}

export function parseSession(value: unknown): SessionProjection {
  if (
    !object(value) ||
    !exactKeys(value, ["role", "proof_mode", "csrf_token"]) ||
    !["advisor", "parent"].includes(String(value.role)) ||
    value.proof_mode !== "synthetic-demo" ||
    typeof value.csrf_token !== "string"
  ) throw new Error("invalid response");
  return value as unknown as SessionProjection;
}

export function parseLedger(value: unknown): AdvisorLedger {
  const keys = [
    "schema_version", "proof_mode", "phase", "case_id", "case_revision", "case_state",
    "canonical_task_inputs", "task", "planning_run", "routes", "evidence", "review_inputs",
    "current_brief_id", "recovery",
  ];
  if (!object(value) || !exactKeys(value, keys) || value.schema_version !== 1 || value.proof_mode !== "synthetic-demo") {
    throw new Error("invalid response");
  }
  return value as unknown as AdvisorLedger;
}

export function parseBrief(value: unknown): CurrentDecisionBrief {
  const keys = [
    "schema_version", "proof_mode", "phase", "case_id", "brief_id", "brief_version",
    "source_snapshot_date", "family_safe_projection", "decision_requirements", "receipt", "timeline",
  ];
  if (!object(value) || !exactKeys(value, keys) || value.schema_version !== 1 || value.proof_mode !== "synthetic-demo") {
    throw new Error("invalid response");
  }
  const requirements = value.decision_requirements;
  if (
    !object(requirements) ||
    requirements.currency !== "CNY" ||
    JSON.stringify(requirements.required_trade_offs) !== '["budget_elasticity"]'
  ) throw new Error("invalid response");
  return value as unknown as CurrentDecisionBrief;
}

export function parseTask(value: unknown): TaskProjection {
  if (!object(value) || value.schema_version !== 1 || typeof value.task_id !== "string") {
    throw new Error("invalid response");
  }
  return value as unknown as TaskProjection;
}
