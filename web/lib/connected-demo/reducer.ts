import type {
  AdvisorLedger,
  ConnectedJourneyStatus,
  CurrentDecisionBrief,
} from "./contracts";

export type RecoveryCode =
  | "invalid_transition"
  | "session_expired"
  | "session_recovery_required"
  | "stale_conflict"
  | "transport_failure";

type AdvisorState =
  | { value: "advisor_ready"; status: ConnectedJourneyStatus; ledger: AdvisorLedger }
  | { value: "task_creating"; status: ConnectedJourneyStatus; ledger: AdvisorLedger }
  | { value: "task_streaming"; status: ConnectedJourneyStatus; ledger: AdvisorLedger; taskId: string; after: number }
  | { value: "advisor_review"; status: ConnectedJourneyStatus; ledger: AdvisorLedger }
  | { value: "review_submitting"; status: ConnectedJourneyStatus; ledger: AdvisorLedger }
  | { value: "revision_fact_pending"; status: ConnectedJourneyStatus; ledger: AdvisorLedger }
  | { value: "replan_required"; status: ConnectedJourneyStatus; ledger: AdvisorLedger }
  | { value: "revision_blocked"; status: ConnectedJourneyStatus; ledger: AdvisorLedger }
  | { value: "terminal_task_failure"; status: ConnectedJourneyStatus; ledger: AdvisorLedger };

export type DemoDisplayState =
  | { value: "bootstrapping" }
  | AdvisorState
  | { value: "revision_requested"; status: ConnectedJourneyStatus }
  | { value: "role_switching"; caseId: string; targetRole: "advisor" | "student" | "parent"; prior?: DemoDisplayState }
  | { value: "family_review"; status: ConnectedJourneyStatus; brief: CurrentDecisionBrief }
  | { value: "decision_submitting"; status: ConnectedJourneyStatus; brief: CurrentDecisionBrief }
  | { value: "plan_ready"; status: ConnectedJourneyStatus; brief: CurrentDecisionBrief }
  | { value: "recoverable_error"; code: RecoveryCode; prior?: DemoDisplayState };

export type DemoEvent =
  | { type: "STATUS_RELOADED"; status: ConnectedJourneyStatus; ledger?: AdvisorLedger; brief?: CurrentDecisionBrief }
  | { type: "CREATE_TASK" }
  | { type: "TASK_ACCEPTED"; taskId: string }
  | { type: "TASK_REFRESHED"; status: ConnectedJourneyStatus; ledger: AdvisorLedger; taskId: string; after: number }
  | { type: "REVIEW_SUBMIT" }
  | { type: "ROLE_SWITCH"; caseId: string; targetRole: "advisor" | "student" | "parent" }
  | { type: "DECISION_SUBMIT" }
  | { type: "RECOVERABLE_FAILURE"; code: RecoveryCode };

const invalid: DemoDisplayState = { value: "recoverable_error", code: "invalid_transition" };

function identitiesMatch(status: ConnectedJourneyStatus, detail: AdvisorLedger | CurrentDecisionBrief): boolean {
  if (status.case_id !== detail.case_id || status.phase !== detail.phase) return false;
  if ("case_revision" in detail) return status.current_revision === detail.case_revision;
  return status.current_revision === detail.revision_context.current_case_revision;
}

function authoritative(
  status: ConnectedJourneyStatus,
  ledger?: AdvisorLedger,
  brief?: CurrentDecisionBrief,
  after = 0,
): DemoDisplayState {
  if (status.phase === "revision_requested") {
    return status.active_role === "student" && ledger === undefined && brief === undefined
      ? { value: "revision_requested", status }
      : invalid;
  }
  if (status.phase === "family_review" || status.phase === "plan_ready") {
    if (status.active_role !== "parent" || !brief || ledger || !identitiesMatch(status, brief)) return invalid;
    return status.phase === "family_review"
      ? { value: "family_review", status, brief }
      : { value: "plan_ready", status, brief };
  }
  if (status.active_role !== "advisor" || !ledger || brief || !identitiesMatch(status, ledger)) return invalid;
  switch (status.phase) {
    case "task_ready":
      return { value: "advisor_ready", status, ledger };
    case "active_task":
    case "revision_task_active":
      return ledger.task
        ? { value: "task_streaming", status, ledger, taskId: ledger.task.task_id, after }
        : invalid;
    case "review_required":
    case "revision_review_required":
      return { value: "advisor_review", status, ledger };
    case "revision_fact_pending":
      return { value: "revision_fact_pending", status, ledger };
    case "replan_required":
      return { value: "replan_required", status, ledger };
    case "revision_blocked":
      return { value: "revision_blocked", status, ledger };
    case "terminal_task_failure":
      return { value: "terminal_task_failure", status, ledger };
    default:
      return invalid;
  }
}

export function demoReducer(state: DemoDisplayState, event: DemoEvent): DemoDisplayState {
  if (event.type === "RECOVERABLE_FAILURE") return { value: "recoverable_error", code: event.code, prior: state };
  if (state.value === "recoverable_error" && state.prior) return demoReducer(state.prior, event);
  if (event.type === "ROLE_SWITCH") return { value: "role_switching", caseId: event.caseId, targetRole: event.targetRole, prior: state };
  if (event.type === "STATUS_RELOADED") return authoritative(event.status, event.ledger, event.brief);
  switch (state.value) {
    case "advisor_ready":
    case "replan_required":
      return event.type === "CREATE_TASK" ? { value: "task_creating", status: state.status, ledger: state.ledger } : invalid;
    case "task_creating":
      return event.type === "TASK_ACCEPTED"
        ? { value: "task_streaming", status: state.status, ledger: state.ledger, taskId: event.taskId, after: 0 }
        : invalid;
    case "task_streaming":
      if (event.type !== "TASK_REFRESHED") return invalid;
      if (event.taskId !== state.taskId) return state;
      if (event.after < state.after) return state;
      return authoritative(event.status, event.ledger, undefined, Math.max(state.after, event.after));
    case "advisor_review":
    case "revision_fact_pending":
      return event.type === "REVIEW_SUBMIT" ? { value: "review_submitting", status: state.status, ledger: state.ledger } : invalid;
    case "family_review":
      return event.type === "DECISION_SUBMIT" ? { value: "decision_submitting", status: state.status, brief: state.brief } : invalid;
    default:
      return invalid;
  }
}
