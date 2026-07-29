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
  const stateByAction: Record<TimelineExecutionView["current_action"]["code"], PlanExecutionStateValue> = {
    checkpoint_attestation_required: "checkpoint_active",
    advisor_verification_required: "awaiting_advisor",
    execution_completed: "execution_completed",
    reassessment_handoff_required: "reassessment_required",
  };
  return { value: stateByAction[view.current_action.code], context, view, receipt, error: null };
}
export const loadingPlanExecutionState: PlanExecutionState = {
  value: "loading", context: null, view: null, receipt: null, error: null,
};
