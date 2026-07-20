import type { CollaborationMessage, CollaborationThread, ConfirmedFactProjection, MemoryCandidateProjection } from "./contracts";
import type { CollaborationPersistedPhase } from "../connected-demo/session-storage";

export type CollaborationErrorCategory = "stale" | "expired_or_terminal" | "active_task_blocked" | "unsafe_or_unsupported" | "wrong_role_or_not_found" | "session_recovery_required" | "transport_unavailable_or_timeout";

export interface CollaborationContext {
  role: "parent" | "advisor";
  caseId: string;
  thread: CollaborationThread | null;
  messages: readonly CollaborationMessage[];
  candidate: MemoryCandidateProjection | null;
  fact: ConfirmedFactProjection | null;
  caseRevision: number;
}

type PersistedState = { value: CollaborationPersistedPhase; context: CollaborationContext };
export type CollaborationState = PersistedState | { value: "recoverable_error"; category: CollaborationErrorCategory; resumePhase: CollaborationPersistedPhase; context: CollaborationContext };
export type CollaborationEvent =
  | { type: "HYDRATE"; phase: CollaborationPersistedPhase; context: CollaborationContext }
  | { type: "PARENT_RELOADED"; context: CollaborationContext }
  | { type: "MESSAGE_SUBMIT" }
  | { type: "PROPOSAL_RELOADED"; context: CollaborationContext }
  | { type: "ROLE_SWITCH" }
  | { type: "ADVISOR_RELOADED"; context: CollaborationContext }
  | { type: "CONFIRM_SUBMIT" }
  | { type: "CONFIRMED_RELOADED"; context: CollaborationContext }
  | { type: "FAILURE"; category: CollaborationErrorCategory };

export function initialCollaborationState(caseId: string): CollaborationState {
  return { value: "bootstrapping_parent", context: { role: "parent", caseId, thread: null, messages: [], candidate: null, fact: null, caseRevision: 1 } };
}

function failure(state: CollaborationState, category: CollaborationErrorCategory): CollaborationState {
  return { value: "recoverable_error", category, resumePhase: state.value === "recoverable_error" ? state.resumePhase : state.value, context: state.context };
}

export function collaborationReducer(state: CollaborationState, event: CollaborationEvent): CollaborationState {
  if (event.type === "FAILURE") return failure(state, event.category);
  const current = state.value === "recoverable_error" ? state.resumePhase : state.value;
  switch (event.type) {
    case "HYDRATE":
      return { value: event.phase, context: event.context };
    case "PARENT_RELOADED":
      return current === "bootstrapping_parent" || current === "thread_ready" || current === "message_submitting" ? { value: "thread_ready", context: event.context } : failure(state, "transport_unavailable_or_timeout");
    case "MESSAGE_SUBMIT":
      return current === "thread_ready" ? { value: "message_submitting", context: state.context } : failure(state, "transport_unavailable_or_timeout");
    case "PROPOSAL_RELOADED":
      return current === "thread_ready" || current === "message_submitting" || current === "proposal_pending" ? { value: "proposal_pending", context: event.context } : failure(state, "transport_unavailable_or_timeout");
    case "ROLE_SWITCH":
      return current === "proposal_pending" ? { value: "switching_to_advisor", context: state.context } : failure(state, "transport_unavailable_or_timeout");
    case "ADVISOR_RELOADED":
      return current === "switching_to_advisor" || current === "advisor_reviewing" ? { value: "advisor_reviewing", context: event.context } : failure(state, "transport_unavailable_or_timeout");
    case "CONFIRM_SUBMIT":
      return current === "advisor_reviewing" ? { value: "confirmation_submitting", context: state.context } : failure(state, "transport_unavailable_or_timeout");
    case "CONFIRMED_RELOADED":
      return current === "confirmation_submitting" || current === "replan_required" ? { value: "replan_required", context: event.context } : failure(state, "transport_unavailable_or_timeout");
  }
}

export function classifyCollaborationProblem(code: string): CollaborationErrorCategory {
  if (["case_revision_stale", "memory_candidate_stale"].includes(code)) return "stale";
  if (["memory_candidate_expired", "memory_candidate_terminal"].includes(code)) return "expired_or_terminal";
  if (code === "active_task_blocks_revision") return "active_task_blocked";
  if (["invalid_collaboration_message", "unsupported_fact_key", "unsafe_fact_value", "idempotency_conflict", "collaboration_thread_full"].includes(code)) return "unsafe_or_unsupported";
  if (code === "resource_unavailable") return "wrong_role_or_not_found";
  if (code === "bff_session_recovery_required") return "session_recovery_required";
  return "transport_unavailable_or_timeout";
}
