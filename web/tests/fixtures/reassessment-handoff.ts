import type {
  PlanExecutionContext, TimelineExecutionView,
} from "../../lib/plan-execution/contracts";

export const handoffId = (number: number) =>
  `20000000-0000-0000-0000-${String(number).padStart(12, "0")}`;

/** Complete synthetic read DTOs; these fixtures prove no native mutation. */
export function handoffFixture(trigger: "blocked_attestation" | "deadline_elapsed" = "blocked_attestation") {
  const at = "2026-10-07T12:00:00Z";
  const context: PlanExecutionContext = {
    schema_version: 1, scenario: "governed-plan-execution-v1",
    case_id: handoffId(1), case_revision: 2, decision_id: handoffId(2),
    decision_receipt_id: handoffId(3), timeline_plan_id: handoffId(4),
    execution_id: handoffId(5), active_role: "advisor", assignment_status: "assigned",
  };
  const checkpoints = ([
    ["documents", "student", "2026-09-01"],
    ["application", "student", "2026-10-15"],
    ["visa", "student", "2026-12-15"],
    ["arrival", "parent", "2027-01-20"],
  ] as const).map(([milestone_key, accountable_role, due_date], index) => ({
    schema_version: 1 as const, checkpoint_id: handoffId(10 + index),
    execution_id: handoffId(5), ordinal: index + 1,
    milestone_key, accountable_role, due_date,
    state: index === 0 ? "verified" as const : index === 1
      ? trigger === "blocked_attestation" ? "blocked" as const : "in_progress" as const
      : "pending" as const,
    risk_state: trigger === "deadline_elapsed" && index === 1 ? "overdue" as const : "on_track" as const,
    row_version: index < 2 ? 2 : 1, created_at: at, updated_at: at,
  }));
  const view: TimelineExecutionView = {
    schema_version: 1,
    execution: {
      schema_version: 1, execution_id: handoffId(5), case_id: handoffId(1),
      case_revision: 2, decision_id: handoffId(2), decision_receipt_id: handoffId(3),
      timeline_plan_id: handoffId(4), state: "reassessment_required", row_version: 4,
      created_at: at, updated_at: at,
    },
    checkpoints, current_checkpoint: checkpoints[1],
    latest_attestation: trigger === "blocked_attestation" ? {
      schema_version: 1, attestation_id: handoffId(20), execution_id: handoffId(5),
      checkpoint_id: handoffId(11), reporter_actor_id: handoffId(90),
      reporter_role: "student", attestation_kind: "blocked", status_code: "work_blocked",
      attestation_code: "application_status_confirmed", reason_code: "missing_required_input",
      observed_execution_version: 2, observed_checkpoint_version: 1, created_at: at,
    } : null,
    latest_verification: null,
    reassessment: {
      schema_version: 1, reassessment_id: handoffId(30), execution_id: handoffId(5),
      checkpoint_id: handoffId(11), advisor_actor_id: handoffId(91), trigger,
      trigger_reference_id: trigger === "blocked_attestation" ? handoffId(20) : null,
      accepted_database_date: trigger === "blocked_attestation" ? "2026-10-07" : "2026-10-16",
      accepted_trigger_projection_sha256: "b".repeat(64), handoff_schema_version: 1,
      predecessor_case_id: handoffId(1), predecessor_case_revision: 2,
      predecessor_decision_id: handoffId(2), predecessor_decision_receipt_id: handoffId(3),
      predecessor_timeline_plan_id: handoffId(4), predecessor_execution_id: handoffId(5),
      predecessor_checkpoint_id: handoffId(11), owner_role: "advisor",
      successor_status: "pending_future_authorization", created_at: at,
    },
    current_action: {
      schema_version: 1, code: "reassessment_handoff_required", owner_role: "advisor",
      checkpoint_id: handoffId(11), execution_version: 4, checkpoint_version: 2,
    },
    observed_date: trigger === "blocked_attestation" ? "2026-10-09" : "2026-10-20",
    activity: [], activity_total: 0, activity_truncated: false,
  };
  return { context, view };
}
