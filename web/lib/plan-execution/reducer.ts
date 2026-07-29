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
}
export function derivePlanExecutionState(
  context: PlanExecutionContext,
  view: TimelineExecutionView | null,
  receipt: TimelineMutationReceipt | null = null,
): PlanExecutionState {
  if (context.execution_id === null && view === null) return { value: "ready_to_start", context, view, receipt, error: null };
  if (view === null || (context.execution_id !== null && context.execution_id !== view.execution.execution_id)) {
    return { value: "session_changed", context, view, receipt, error: "execution authority changed" };
  }
  if (view.execution.state === "completed") return { value: "execution_completed", context, view, receipt, error: null };
  if (view.execution.state === "reassessment_required" || view.current_checkpoint?.state === "blocked") {
    return { value: "reassessment_required", context, view, receipt, error: null };
  }
  if (view.current_checkpoint?.state === "awaiting_advisor") {
    return { value: "awaiting_advisor", context, view, receipt, error: null };
  }
  return { value: "checkpoint_active", context, view, receipt, error: null };
}
export const loadingPlanExecutionState: PlanExecutionState = {
  value: "loading", context: null, view: null, receipt: null, error: null,
};
