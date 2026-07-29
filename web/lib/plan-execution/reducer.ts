import type {
  PlanExecutionContext,
  PlanExecutionStateValue,
  TimelineExecutionView,
  TimelineMutationReceipt,
} from "./contracts";

export interface PlanExecutionState {
  value: PlanExecutionStateValue;
  context: PlanExecutionContext | null;
  view: TimelineExecutionView | null;
  receipt: TimelineMutationReceipt | null;
  error: string | null;
  operation: "start" | "attest" | "verify" | "reassess" | null;
  safeDisplayState: Exclude<PlanExecutionStateValue, "mutation_in_flight"> | null;
}
export function derivePlanExecutionState(
  context: PlanExecutionContext,
  view: TimelineExecutionView | null,
  receipt: TimelineMutationReceipt | null = null,
): PlanExecutionState {
  if (context.execution_id === null && view === null) return { value: "ready_to_start", context, view, receipt, error: null, operation: null, safeDisplayState: null };
  if (view === null || (context.execution_id !== null && context.execution_id !== view.execution.execution_id)) {
    return { value: "session_changed", context, view, receipt, error: "execution authority changed", operation: null, safeDisplayState: null };
  }
  const stateByAction: Record<TimelineExecutionView["current_action"]["code"], PlanExecutionStateValue> = {
    checkpoint_attestation_required: "checkpoint_active",
    advisor_verification_required: "awaiting_advisor",
    execution_completed: "execution_completed",
    reassessment_handoff_required: "reassessment_required",
  };
  const value = view.execution.state === "active"
    && view.current_checkpoint?.state === "blocked"
    ? "checkpoint_active"
    : stateByAction[view.current_action.code];
  return { value, context, view, receipt, error: null, operation: null, safeDisplayState: null };
}
export function beginPlanExecutionMutation(
  prior: PlanExecutionState,
  operation: "start" | "attest" | "verify" | "reassess",
): PlanExecutionState {
  return {
    ...prior,
    value: "mutation_in_flight",
    operation,
    safeDisplayState: prior.value === "mutation_in_flight"
      ? prior.safeDisplayState
      : prior.value,
    error: null,
  };
}
export const loadingPlanExecutionState: PlanExecutionState = {
  value: "loading", context: null, view: null, receipt: null, error: null,
  operation: null, safeDisplayState: null,
};
