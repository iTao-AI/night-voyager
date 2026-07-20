import { expect, it } from "vitest";

import { classifyCollaborationProblem, collaborationReducer, initialCollaborationState } from "../../lib/collaboration-demo/reducer";

const CASE = "41000000-0000-0000-0000-000000000001";
const context = { role: "parent" as const, caseId: CASE, thread: null, messages: [], candidate: null, fact: null, caseRevision: 1 };

it("moves only through the closed collaboration authority states", () => {
  const thread = { schema_version: 1 as const, thread_id: "42000000-0000-0000-0000-000000000001", case_id: CASE, created_by_actor_id: CASE, created_at: "2026-07-20T01:02:03Z" };
  let state = collaborationReducer(initialCollaborationState(CASE), { type: "PARENT_RELOADED", context: { ...context, thread } });
  expect(state.value).toBe("thread_ready");
  state = collaborationReducer(state, { type: "MESSAGE_SUBMIT" });
  expect(state.value).toBe("message_submitting");
  state = collaborationReducer(state, { type: "PROPOSAL_RELOADED", context: { ...context, thread } });
  expect(state.value).toBe("proposal_pending");
  state = collaborationReducer(state, { type: "ROLE_SWITCH" });
  expect(state.value).toBe("switching_to_advisor");
  state = collaborationReducer(state, { type: "ADVISOR_RELOADED", context: { ...context, role: "advisor", thread } });
  expect(state.value).toBe("advisor_reviewing");
  state = collaborationReducer(state, { type: "CONFIRM_SUBMIT" });
  expect(state.value).toBe("confirmation_submitting");
  state = collaborationReducer(state, { type: "CONFIRMED_RELOADED", context: { ...context, role: "advisor", thread, caseRevision: 2 } });
  expect(state.value).toBe("replan_required");
});

it("keeps recoverable_error reducer-only with a persisted resume phase", () => {
  const state = collaborationReducer(initialCollaborationState(CASE), { type: "FAILURE", category: "transport_unavailable_or_timeout" });
  expect(state).toMatchObject({ value: "recoverable_error", category: "transport_unavailable_or_timeout", resumePhase: "bootstrapping_parent" });
  expect(JSON.stringify(state)).not.toContain("raw failure");
  const invalid = collaborationReducer(initialCollaborationState(CASE), { type: "CONFIRM_SUBMIT" });
  expect(invalid).toMatchObject({ value: "recoverable_error", category: "transport_unavailable_or_timeout", resumePhase: "bootstrapping_parent" });
});

it("maps the complete public problem allowlist into seven bounded categories", () => {
  const cases = new Map([
    ["case_revision_stale", "stale"], ["memory_candidate_stale", "stale"],
    ["memory_candidate_expired", "expired_or_terminal"], ["memory_candidate_terminal", "expired_or_terminal"],
    ["active_task_blocks_revision", "active_task_blocked"],
    ["invalid_collaboration_message", "unsafe_or_unsupported"], ["unsupported_fact_key", "unsafe_or_unsupported"], ["unsafe_fact_value", "unsafe_or_unsupported"], ["idempotency_conflict", "unsafe_or_unsupported"],
    ["resource_unavailable", "wrong_role_or_not_found"],
    ["bff_session_recovery_required", "session_recovery_required"],
    ["persistence_unavailable", "transport_unavailable_or_timeout"], ["bff_upstream_unavailable", "transport_unavailable_or_timeout"], ["bff_upstream_timeout", "transport_unavailable_or_timeout"], ["unknown-code", "transport_unavailable_or_timeout"],
  ]);
  for (const [code, category] of cases) expect(classifyCollaborationProblem(code)).toBe(category);
});
