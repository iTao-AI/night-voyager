export type PlanExecutionRole = "advisor" | "student" | "parent";
export type PlanExecutionStateValue =
  | "loading" | "ready_to_start" | "checkpoint_active" | "mutation_in_flight" | "awaiting_advisor"
  | "execution_completed" | "reassessment_required" | "session_changed"
  | "recoverable_error";

export interface PlanExecutionContext {
  schema_version: 1;
  scenario: "governed-plan-execution-v1";
  case_id: string;
  case_revision: number;
  decision_id: string;
  decision_receipt_id: string;
  timeline_plan_id: string;
  execution_id: string | null;
  active_role: PlanExecutionRole;
  assignment_status: "assigned";
}

export interface TimelineExecution {
  schema_version: 1; execution_id: string; case_id: string; case_revision: number;
  decision_id: string; decision_receipt_id: string; timeline_plan_id: string;
  state: "active" | "reassessment_required" | "completed"; row_version: number;
  created_at: string; updated_at: string;
}
export interface TimelineCheckpoint {
  schema_version: 1; checkpoint_id: string; execution_id: string; ordinal: number;
  milestone_key: "documents" | "application" | "visa" | "arrival";
  due_date: string; accountable_role: "student" | "parent";
  state: "pending" | "in_progress" | "awaiting_advisor" | "verified" | "blocked";
  risk_state: "on_track" | "due_soon" | "overdue"; row_version: number;
  created_at: string; updated_at: string;
}
export interface TimelineAttestation {
  schema_version: 1; attestation_id: string; execution_id: string;
  checkpoint_id: string; reporter_actor_id: string; reporter_role: "student" | "parent";
  attestation_kind: "progress" | "completion" | "blocked";
  status_code: "work_in_progress" | "ready_for_advisor" | "work_blocked";
  attestation_code: `${"documents" | "application" | "visa" | "arrival"}_status_confirmed`;
  reason_code: "not_applicable" | "missing_required_input" | "external_dependency_unavailable" | "deadline_at_risk";
  observed_execution_version: number; observed_checkpoint_version: number; created_at: string;
}
export interface TimelineVerification {
  schema_version: 1; verification_id: string; execution_id: string;
  checkpoint_id: string; attestation_id: string; advisor_actor_id: string;
  action: "verify" | "request_update";
  reason_code: "attestation_verified" | "status_update_required" | "status_inconsistent";
  observed_execution_version: number; observed_checkpoint_version: number; created_at: string;
}
export interface TimelineReassessment {
  schema_version: 1; reassessment_id: string; execution_id: string;
  checkpoint_id: string; advisor_actor_id: string;
  trigger: "blocked_attestation" | "deadline_elapsed"; trigger_reference_id: string | null;
  accepted_database_date: string; accepted_trigger_projection_sha256: string;
  handoff_schema_version: 1; predecessor_case_id: string;
  predecessor_case_revision: number; predecessor_decision_id: string;
  predecessor_decision_receipt_id: string; predecessor_timeline_plan_id: string;
  predecessor_execution_id: string; predecessor_checkpoint_id: string;
  owner_role: "advisor"; successor_status: "pending_future_authorization"; created_at: string;
}
export interface TimelineActivity {
  schema_version: 1;
  kind: "attestation_recorded" | "verification_recorded" | "reassessment_recorded" | "mutation_receipt_recorded";
  durable_id: string; execution_id: string; checkpoint_id: string | null; created_at: string;
}
export interface TimelineCurrentAction {
  schema_version: 1;
  code: "checkpoint_attestation_required" | "advisor_verification_required" | "execution_completed" | "reassessment_handoff_required";
  owner_role: "advisor" | "student" | "parent" | "none";
  checkpoint_id: string | null;
  execution_version: number;
  checkpoint_version: number | null;
}
export interface TimelineExecutionView {
  schema_version: 1; execution: TimelineExecution; checkpoints: TimelineCheckpoint[];
  current_checkpoint: TimelineCheckpoint | null; latest_attestation: TimelineAttestation | null;
  latest_verification: TimelineVerification | null; reassessment: TimelineReassessment | null;
  current_action: TimelineCurrentAction;
  observed_date: string; activity: TimelineActivity[]; activity_total: number;
  activity_truncated: boolean;
}
export interface TimelineMutationReceipt {
  schema_version: 1; receipt_id: string; operation: "start" | "attest" | "verify" | "reassess";
  result_kind: "timeline_execution_started" | "timeline_checkpoint_attested" | "timeline_checkpoint_verified" | "timeline_reassessment_requested";
  result_id: string; execution_id: string; checkpoint_id: string | null;
  before_execution_version: number | null; after_execution_version: number;
  before_checkpoint_version: number | null; after_checkpoint_version: number | null;
  created_at: string;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const SHA = /^[0-9a-f]{64}$/;
function object(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, keys: readonly string[]): boolean {
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  return actual.length === expected.length && actual.every((key, index) => key === expected[index]);
}
function uuid(value: unknown): value is string { return typeof value === "string" && UUID.test(value); }
function nullableUuid(value: unknown): value is string | null { return value === null || uuid(value); }
function positive(value: unknown): value is number { return Number.isSafeInteger(value) && Number(value) > 0; }
function nonnegative(value: unknown): value is number { return Number.isSafeInteger(value) && Number(value) >= 0; }
function timestamp(value: unknown): value is string {
  return typeof value === "string" && !Number.isNaN(Date.parse(value));
}
function date(value: unknown): value is string { return typeof value === "string" && DATE.test(value); }
function oneOf(value: unknown, options: readonly string[]): boolean {
  return typeof value === "string" && options.includes(value);
}

function checkpoint(value: unknown): value is TimelineCheckpoint {
  if (!object(value) || !exact(value, ["schema_version", "checkpoint_id", "execution_id", "ordinal", "milestone_key", "due_date", "accountable_role", "state", "risk_state", "row_version", "created_at", "updated_at"])) return false;
  return value.schema_version === 1 && uuid(value.checkpoint_id) && uuid(value.execution_id)
    && positive(value.ordinal) && oneOf(value.milestone_key, ["documents", "application", "visa", "arrival"])
    && date(value.due_date) && oneOf(value.accountable_role, ["student", "parent"])
    && oneOf(value.state, ["pending", "in_progress", "awaiting_advisor", "verified", "blocked"])
    && oneOf(value.risk_state, ["on_track", "due_soon", "overdue"]) && positive(value.row_version)
    && timestamp(value.created_at) && timestamp(value.updated_at);
}
function attestation(value: unknown): value is TimelineAttestation {
  if (!object(value) || !exact(value, ["schema_version", "attestation_id", "execution_id", "checkpoint_id", "reporter_actor_id", "reporter_role", "attestation_kind", "status_code", "attestation_code", "reason_code", "observed_execution_version", "observed_checkpoint_version", "created_at"])) return false;
  return value.schema_version === 1 && uuid(value.attestation_id) && uuid(value.execution_id)
    && uuid(value.checkpoint_id) && uuid(value.reporter_actor_id)
    && oneOf(value.reporter_role, ["student", "parent"])
    && oneOf(value.attestation_kind, ["progress", "completion", "blocked"])
    && oneOf(value.status_code, ["work_in_progress", "ready_for_advisor", "work_blocked"])
    && oneOf(value.attestation_code, ["documents_status_confirmed", "application_status_confirmed", "visa_status_confirmed", "arrival_status_confirmed"])
    && oneOf(value.reason_code, ["not_applicable", "missing_required_input", "external_dependency_unavailable", "deadline_at_risk"])
    && positive(value.observed_execution_version) && positive(value.observed_checkpoint_version)
    && timestamp(value.created_at);
}
function verification(value: unknown): value is TimelineVerification {
  if (!object(value) || !exact(value, ["schema_version", "verification_id", "execution_id", "checkpoint_id", "attestation_id", "advisor_actor_id", "action", "reason_code", "observed_execution_version", "observed_checkpoint_version", "created_at"])) return false;
  return value.schema_version === 1 && uuid(value.verification_id) && uuid(value.execution_id)
    && uuid(value.checkpoint_id) && uuid(value.attestation_id) && uuid(value.advisor_actor_id)
    && oneOf(value.action, ["verify", "request_update"])
    && oneOf(value.reason_code, ["attestation_verified", "status_update_required", "status_inconsistent"])
    && positive(value.observed_execution_version) && positive(value.observed_checkpoint_version)
    && timestamp(value.created_at);
}
function reassessment(value: unknown): value is TimelineReassessment {
  if (!object(value) || !exact(value, ["schema_version", "reassessment_id", "execution_id", "checkpoint_id", "advisor_actor_id", "trigger", "trigger_reference_id", "accepted_database_date", "accepted_trigger_projection_sha256", "handoff_schema_version", "predecessor_case_id", "predecessor_case_revision", "predecessor_decision_id", "predecessor_decision_receipt_id", "predecessor_timeline_plan_id", "predecessor_execution_id", "predecessor_checkpoint_id", "owner_role", "successor_status", "created_at"])) return false;
  return value.schema_version === 1 && uuid(value.reassessment_id) && uuid(value.execution_id)
    && uuid(value.checkpoint_id) && uuid(value.advisor_actor_id)
    && oneOf(value.trigger, ["blocked_attestation", "deadline_elapsed"])
    && nullableUuid(value.trigger_reference_id) && date(value.accepted_database_date)
    && typeof value.accepted_trigger_projection_sha256 === "string" && SHA.test(value.accepted_trigger_projection_sha256)
    && value.handoff_schema_version === 1 && uuid(value.predecessor_case_id)
    && positive(value.predecessor_case_revision) && uuid(value.predecessor_decision_id)
    && uuid(value.predecessor_decision_receipt_id) && uuid(value.predecessor_timeline_plan_id)
    && uuid(value.predecessor_execution_id) && uuid(value.predecessor_checkpoint_id)
    && value.owner_role === "advisor" && value.successor_status === "pending_future_authorization"
    && timestamp(value.created_at);
}
function currentAction(value: unknown): value is TimelineCurrentAction {
  if (!object(value) || !exact(value, ["schema_version", "code", "owner_role", "checkpoint_id", "execution_version", "checkpoint_version"])) return false;
  return value.schema_version === 1
    && oneOf(value.code, ["checkpoint_attestation_required", "advisor_verification_required", "execution_completed", "reassessment_handoff_required"])
    && oneOf(value.owner_role, ["advisor", "student", "parent", "none"])
    && nullableUuid(value.checkpoint_id) && positive(value.execution_version)
    && (value.checkpoint_version === null || positive(value.checkpoint_version));
}

export function parsePlanExecutionContext(value: unknown): PlanExecutionContext {
  if (!object(value) || !exact(value, ["schema_version", "scenario", "case_id", "case_revision", "decision_id", "decision_receipt_id", "timeline_plan_id", "execution_id", "active_role", "assignment_status"])
    || value.schema_version !== 1 || value.scenario !== "governed-plan-execution-v1"
    || !uuid(value.case_id) || !positive(value.case_revision) || !uuid(value.decision_id)
    || !uuid(value.decision_receipt_id) || !uuid(value.timeline_plan_id)
    || !nullableUuid(value.execution_id) || !oneOf(value.active_role, ["advisor", "student", "parent"])
    || value.assignment_status !== "assigned") throw new Error("invalid plan execution context");
  return value as unknown as PlanExecutionContext;
}

export function parseTimelineExecutionView(value: unknown): TimelineExecutionView {
  if (!object(value) || !exact(value, ["schema_version", "execution", "checkpoints", "current_checkpoint", "latest_attestation", "latest_verification", "reassessment", "current_action", "observed_date", "activity", "activity_total", "activity_truncated"]) || value.schema_version !== 1) throw new Error("invalid timeline execution view");
  const execution = value.execution;
  if (!object(execution) || !exact(execution, ["schema_version", "execution_id", "case_id", "case_revision", "decision_id", "decision_receipt_id", "timeline_plan_id", "state", "row_version", "created_at", "updated_at"])
    || execution.schema_version !== 1 || !uuid(execution.execution_id) || !uuid(execution.case_id)
    || !positive(execution.case_revision) || !uuid(execution.decision_id)
    || !uuid(execution.decision_receipt_id) || !uuid(execution.timeline_plan_id)
    || !oneOf(execution.state, ["active", "reassessment_required", "completed"])
    || !positive(execution.row_version) || !timestamp(execution.created_at) || !timestamp(execution.updated_at)) throw new Error("invalid timeline execution view");
  if (!Array.isArray(value.checkpoints) || !value.checkpoints.every(checkpoint)
    || (value.current_checkpoint !== null && !checkpoint(value.current_checkpoint))
    || (value.latest_attestation !== null && !attestation(value.latest_attestation))
    || (value.latest_verification !== null && !verification(value.latest_verification))
    || (value.reassessment !== null && !reassessment(value.reassessment))
    || !currentAction(value.current_action)
    || !date(value.observed_date) || !Array.isArray(value.activity)
    || !value.activity.every((item) => object(item)
      && exact(item, ["schema_version", "kind", "durable_id", "execution_id", "checkpoint_id", "created_at"])
      && item.schema_version === 1
      && oneOf(item.kind, ["attestation_recorded", "verification_recorded", "reassessment_recorded", "mutation_receipt_recorded"])
      && uuid(item.durable_id) && uuid(item.execution_id) && nullableUuid(item.checkpoint_id)
      && timestamp(item.created_at))
    || value.activity.length > 64
    || !nonnegative(value.activity_total) || typeof value.activity_truncated !== "boolean"
    || Number(value.activity_total) < value.activity.length
    || value.activity_truncated !== (Number(value.activity_total) > value.activity.length)) throw new Error("invalid timeline execution view");
  const view = value as unknown as TimelineExecutionView;
  const milestones = ["documents", "application", "visa", "arrival"] as const;
  const roles = ["student", "student", "student", "parent"] as const;
  if (view.checkpoints.length !== 4 || view.checkpoints.some((item, index) =>
    item.execution_id !== view.execution.execution_id
    || item.ordinal !== index + 1
    || item.milestone_key !== milestones[index]
    || item.accountable_role !== roles[index]
  )) throw new Error("invalid timeline execution view");
  const checkpointIds = new Set(view.checkpoints.map((item) => item.checkpoint_id));
  const current = view.checkpoints.filter((item) => !["pending", "verified"].includes(item.state));
  if ((view.current_checkpoint !== null
      && (!checkpointIds.has(view.current_checkpoint.checkpoint_id)
        || JSON.stringify(view.current_checkpoint) !== JSON.stringify(
          view.checkpoints.find((item) => item.checkpoint_id === view.current_checkpoint?.checkpoint_id),
        )))
    || (view.execution.state === "active" && (current.length !== 1 || view.current_checkpoint?.checkpoint_id !== current[0]?.checkpoint_id))
    || (view.execution.state === "completed" && (current.length !== 0 || view.current_checkpoint !== null || view.checkpoints.some((item) => item.state !== "verified")))
    || (view.execution.state === "reassessment_required" && view.reassessment === null)
  ) throw new Error("invalid timeline execution view");
  if ((view.latest_attestation !== null
      && (view.latest_attestation.execution_id !== view.execution.execution_id
        || !checkpointIds.has(view.latest_attestation.checkpoint_id)))
    || (view.latest_verification !== null
      && (view.latest_verification.execution_id !== view.execution.execution_id
        || !checkpointIds.has(view.latest_verification.checkpoint_id)))
    || (view.reassessment !== null
      && (view.reassessment.execution_id !== view.execution.execution_id
        || !checkpointIds.has(view.reassessment.checkpoint_id)
        || view.reassessment.predecessor_execution_id !== view.execution.execution_id
        || view.reassessment.predecessor_checkpoint_id !== view.reassessment.checkpoint_id
        || view.reassessment.predecessor_case_id !== view.execution.case_id
        || view.reassessment.predecessor_case_revision !== view.execution.case_revision
        || view.reassessment.predecessor_decision_id !== view.execution.decision_id
        || view.reassessment.predecessor_decision_receipt_id !== view.execution.decision_receipt_id
        || view.reassessment.predecessor_timeline_plan_id !== view.execution.timeline_plan_id))
    || view.activity.some((item) =>
      item.execution_id !== view.execution.execution_id
      || (item.checkpoint_id !== null && !checkpointIds.has(item.checkpoint_id)))
  ) throw new Error("invalid timeline execution view");
  const sortedActivity = [...view.activity].sort((left, right) =>
    right.created_at.localeCompare(left.created_at) || right.durable_id.localeCompare(left.durable_id));
  if (view.activity.some((item, index) => item !== sortedActivity[index])) throw new Error("invalid timeline execution view");
  const expectedAction: TimelineCurrentAction = view.execution.state === "completed"
    ? { schema_version: 1, code: "execution_completed", owner_role: "none", checkpoint_id: null, execution_version: view.execution.row_version, checkpoint_version: null }
    : view.execution.state === "reassessment_required" || view.current_checkpoint?.state === "blocked"
      ? { schema_version: 1, code: "reassessment_handoff_required", owner_role: "advisor", checkpoint_id: view.current_checkpoint?.checkpoint_id ?? null, execution_version: view.execution.row_version, checkpoint_version: view.current_checkpoint?.row_version ?? null }
      : view.current_checkpoint?.state === "awaiting_advisor"
        ? { schema_version: 1, code: "advisor_verification_required", owner_role: "advisor", checkpoint_id: view.current_checkpoint.checkpoint_id, execution_version: view.execution.row_version, checkpoint_version: view.current_checkpoint.row_version }
        : { schema_version: 1, code: "checkpoint_attestation_required", owner_role: view.current_checkpoint?.accountable_role ?? "none", checkpoint_id: view.current_checkpoint?.checkpoint_id ?? null, execution_version: view.execution.row_version, checkpoint_version: view.current_checkpoint?.row_version ?? null };
  if (JSON.stringify(view.current_action) !== JSON.stringify(expectedAction)) throw new Error("invalid timeline execution view");
  return view;
}

export function parseTimelineMutationReceipt(value: unknown): TimelineMutationReceipt {
  if (!object(value) || !exact(value, ["schema_version", "receipt_id", "operation", "result_kind", "result_id", "execution_id", "checkpoint_id", "before_execution_version", "after_execution_version", "before_checkpoint_version", "after_checkpoint_version", "created_at"])
    || value.schema_version !== 1 || !uuid(value.receipt_id)
    || !oneOf(value.operation, ["start", "attest", "verify", "reassess"])
    || !oneOf(value.result_kind, ["timeline_execution_started", "timeline_checkpoint_attested", "timeline_checkpoint_verified", "timeline_reassessment_requested"])
    || !uuid(value.result_id) || !uuid(value.execution_id) || !nullableUuid(value.checkpoint_id)
    || !(value.before_execution_version === null || positive(value.before_execution_version))
    || !positive(value.after_execution_version)
    || !(value.before_checkpoint_version === null || positive(value.before_checkpoint_version))
    || !(value.after_checkpoint_version === null || positive(value.after_checkpoint_version))
    || !timestamp(value.created_at)) throw new Error("invalid timeline mutation receipt");
  return value as unknown as TimelineMutationReceipt;
}
