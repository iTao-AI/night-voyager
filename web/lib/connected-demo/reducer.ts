import type { AdvisorLedger, CurrentDecisionBrief } from "./contracts";

export type RecoveryCode =
  | "invalid_transition"
  | "session_expired"
  | "session_recovery_required"
  | "stale_conflict"
  | "transport_failure";

export type DemoDisplayState =
  | { value: "bootstrapping" }
  | { value: "advisor_ready"; ledger: AdvisorLedger }
  | { value: "task_creating"; ledger: AdvisorLedger }
  | { value: "task_streaming"; ledger: AdvisorLedger; taskId: string; after: number }
  | { value: "advisor_review"; ledger: AdvisorLedger }
  | { value: "review_submitting"; ledger: AdvisorLedger }
  | { value: "role_switching"; caseId: string }
  | { value: "family_review"; brief: CurrentDecisionBrief }
  | { value: "decision_submitting"; brief: CurrentDecisionBrief }
  | { value: "plan_ready"; brief: CurrentDecisionBrief }
  | { value: "recoverable_error"; code: RecoveryCode; prior?: DemoDisplayState }
  | { value: "terminal_task_failure"; ledger: AdvisorLedger };

export type DemoEvent =
  | { type: "ADVISOR_SESSION_READY"; ledger: AdvisorLedger }
  | { type: "CREATE_TASK" }
  | { type: "TASK_ACCEPTED"; taskId: string }
  | { type: "TASK_REFRESHED"; ledger: AdvisorLedger; after: number }
  | { type: "REVIEW_SUBMIT" }
  | { type: "REVIEW_ACCEPTED"; caseId: string }
  | { type: "PARENT_SESSION_READY"; brief: CurrentDecisionBrief }
  | { type: "DECISION_SUBMIT" }
  | { type: "DECISION_ACCEPTED"; brief: CurrentDecisionBrief }
  | { type: "AUTHORITATIVE_RELOAD"; ledger?: AdvisorLedger; brief?: CurrentDecisionBrief }
  | { type: "RECOVERABLE_FAILURE"; code: RecoveryCode }
  | { type: "TERMINAL_TASK"; ledger: AdvisorLedger };

const invalid: DemoDisplayState = { value: "recoverable_error", code: "invalid_transition" };

function advisorState(ledger: AdvisorLedger, after = 0): DemoDisplayState {
  switch (ledger.phase) {
    case "task-ready":
    case "family-review":
    case "plan-ready":
      return { value: "advisor_ready", ledger };
    case "active-task":
      return ledger.task
        ? { value: "task_streaming", ledger, taskId: ledger.task.task_id, after }
        : invalid;
    case "review-required":
      return { value: "advisor_review", ledger };
    case "terminal-task-failure":
      return { value: "terminal_task_failure", ledger };
  }
}

export function demoReducer(state: DemoDisplayState, event: DemoEvent): DemoDisplayState {
  if (event.type === "RECOVERABLE_FAILURE") return { value: "recoverable_error", code: event.code, prior: state };
  if (state.value === "recoverable_error" && state.prior) return demoReducer(state.prior, event);
  if (event.type === "TERMINAL_TASK") return { value: "terminal_task_failure", ledger: event.ledger };
  if (event.type === "AUTHORITATIVE_RELOAD") {
    if (event.brief) return event.brief.phase === "plan-ready" ? { value: "plan_ready", brief: event.brief } : { value: "family_review", brief: event.brief };
    if (event.ledger) return advisorState(event.ledger);
    return invalid;
  }
  switch (state.value) {
    case "bootstrapping":
      return event.type === "ADVISOR_SESSION_READY" ? { value: "advisor_ready", ledger: event.ledger } : invalid;
    case "advisor_ready":
      return event.type === "CREATE_TASK" ? { value: "task_creating", ledger: state.ledger } : invalid;
    case "task_creating":
      return event.type === "TASK_ACCEPTED" ? { value: "task_streaming", ledger: state.ledger, taskId: event.taskId, after: 0 } : invalid;
    case "task_streaming":
      if (event.type !== "TASK_REFRESHED") return invalid;
      if (event.ledger.phase === "terminal-task-failure") return { value: "terminal_task_failure", ledger: event.ledger };
      if (event.ledger.phase === "review-required") return { value: "advisor_review", ledger: event.ledger };
      if (event.ledger.phase !== "active-task" || event.ledger.task?.task_id !== state.taskId) return invalid;
      return { value: "task_streaming", ledger: event.ledger, taskId: state.taskId, after: Math.max(state.after, event.after) };
    case "advisor_review":
      if (event.type === "TASK_REFRESHED" && event.ledger.phase === "review-required") {
        return { value: "advisor_review", ledger: event.ledger };
      }
      return event.type === "REVIEW_SUBMIT" ? { value: "review_submitting", ledger: state.ledger } : invalid;
    case "review_submitting":
      return event.type === "REVIEW_ACCEPTED" ? { value: "role_switching", caseId: event.caseId } : invalid;
    case "role_switching":
      return event.type === "PARENT_SESSION_READY" ? { value: "family_review", brief: event.brief } : invalid;
    case "family_review":
      return event.type === "DECISION_SUBMIT" ? { value: "decision_submitting", brief: state.brief } : invalid;
    case "decision_submitting":
      return event.type === "DECISION_ACCEPTED" && event.brief.phase === "plan-ready" ? { value: "plan_ready", brief: event.brief } : invalid;
    default:
      return invalid;
  }
}
