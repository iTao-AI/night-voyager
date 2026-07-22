import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { CollaborationDemoApiError } from "../../lib/collaboration-demo/api";
import { ConnectedDemoApiError } from "../../lib/connected-demo/api";
import { idempotencyFor } from "../../lib/connected-demo/idempotency";
import { continueCollaborationAsAdvisorFamily, loadDemoJourneyEnvelope, saveRecoveryMetadata } from "../../lib/connected-demo/session-storage";

const mocks = vi.hoisted(() => ({
  identity: {
    bootstrap: vi.fn(), mint: vi.fn(), revoke: vi.fn(), advisorLedger: vi.fn(),
  },
  collaboration: {
    thread: vi.fn(), messages: vi.fn(), appendMessage: vi.fn(), proposeCandidate: vi.fn(),
    candidates: vi.fn(), verifyCandidate: vi.fn(), confirmedFacts: vi.fn(), planningSkillInspector: vi.fn(),
  },
}));

vi.mock("../../lib/connected-demo/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/connected-demo/api")>();
  return { ...actual, createConnectedDemoApi: () => mocks.identity };
});
vi.mock("../../lib/collaboration-demo/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/collaboration-demo/api")>();
  return { ...actual, createCollaborationDemoApi: () => mocks.collaboration };
});

import { collaborationNavigation, useCollaborationDemo } from "../../lib/collaboration-demo/use-collaboration-demo";

const CASE = "41000000-0000-0000-0000-000000000001";
const THREAD = "42000000-0000-0000-0000-000000000001";
const MESSAGE = "43000000-0000-0000-0000-000000000001";
const CANDIDATE = "44000000-0000-0000-0000-000000000001";
const FACT = "45000000-0000-0000-0000-000000000001";
const TASK = "61000000-0000-0000-0000-000000000001";
const AT = "2026-07-20T01:02:03Z";
const SHA = "a".repeat(64);
const MESSAGE_BODY = "Our confirmed program budget is 300,000 to 400,000 CNY.";
const BUDGET = { schema_version: 1 as const, currency: "CNY" as const, period: "program_total" as const, preferred_minor: 30_000_000, hard_ceiling_minor: 40_000_000, elasticity_bps: 1000, refused: false };
const thread = { schema_version: 1 as const, thread_id: THREAD, case_id: CASE, created_by_actor_id: CASE, created_at: AT };
const message = { schema_version: 1 as const, message_event_id: MESSAGE, thread_id: THREAD, case_id: CASE, sequence_no: 1, actor_id: CASE, actor_role: "parent" as const, body: MESSAGE_BODY, content_sha256: SHA, created_at: AT };
const participant = { schema_version: 1 as const, fact_key: "family.budget" as const, value: BUDGET, state: "pending" as const, created_at: AT, expires_at: "2026-07-27T01:02:03Z" };
const advisor = { ...participant, candidate_id: CANDIDATE, message_event_id: MESSAGE, source_message_sequence_no: 1, subject_actor_id: CASE, subject_role: "parent" as const, case_revision: 1, verification_id: null, decision: null, reason: null, request_sha256: SHA, value_sha256: SHA };
const fact = { schema_version: 1 as const, fact_key: "family.budget" as const, value: BUDGET, fact_version: 1, confirmed_at: AT, subject_role: "parent" as const, confirming_advisor_role: "advisor" as const, confirmed_fact_id: FACT, candidate_id: CANDIDATE, verification_id: MESSAGE, source_message_event_id: MESSAGE, source_message_sequence_no: 1, source_message_sha256_prefix: "aaaaaaaaaaaa", confirming_advisor_actor_id: CASE, reason: "Confirmed by advisor.", supersedes_fact_id: null };

function ledger(caseRevision: number) {
  return { schema_version: 1 as const, proof_mode: "synthetic-demo" as const, phase: "task-ready" as const, case_id: CASE, case_revision: caseRevision, case_state: "intake" as const, canonical_task_inputs: { schema_version: 1 as const, operation: "generate_planning_run_v1" as const, case_id: CASE, expected_case_revision: caseRevision, source_pack_id: "50000000-0000-0000-0000-000000000001", source_pack_version: 1, policy_version: "m3a-policy-v1" }, task: null, planning_run: null, routes: [], evidence: [], review_inputs: null, current_brief_id: null, recovery: null };
}

function handoffLedger(phase: "task-ready" | "active-task" | "review-required" | "terminal-task-failure" | "family-review" | "plan-ready") {
  return {
    ...ledger(2),
    phase,
    task: ["active-task", "review-required", "terminal-task-failure"].includes(phase) ? { task_id: TASK } : null,
    current_brief_id: ["family-review", "plan-ready"].includes(phase) ? FACT : null,
  };
}

function confirmedCandidate() {
  return { ...advisor, state: "confirmed" as const, verification_id: MESSAGE, decision: "confirm" as const, reason: "Confirmed by advisor." };
}

function saveConfirmed() {
  save({ role: "advisor", candidateId: CANDIDATE, phase: "replan_required" });
  mocks.collaboration.candidates.mockResolvedValue([confirmedCandidate()]);
  mocks.identity.advisorLedger.mockResolvedValue(handoffLedger("task-ready"));
}

function save(value: Record<string, unknown>) {
  sessionStorage.setItem("night-voyager:m5", JSON.stringify({ schema_version: 2, journey: "collaboration", csrf: "stored-csrf", caseId: CASE, threadId: THREAD, messageId: MESSAGE, candidateId: null, mutations: {}, ...value }));
}

beforeEach(() => {
  mocks.identity.bootstrap.mockResolvedValue({ csrf_token: "bootstrap" });
  mocks.identity.mint.mockResolvedValue({ role: "parent", proof_mode: "synthetic-demo", csrf_token: "parent-csrf" });
  mocks.identity.revoke.mockResolvedValue(undefined);
  mocks.identity.advisorLedger.mockResolvedValue(ledger(1));
  mocks.collaboration.thread.mockResolvedValue(thread);
  mocks.collaboration.messages.mockResolvedValue({ schema_version: 1, items: [message], next_after_sequence: null });
  mocks.collaboration.appendMessage.mockResolvedValue(message);
  mocks.collaboration.proposeCandidate.mockResolvedValue(participant);
  mocks.collaboration.candidates.mockResolvedValue([participant]);
  mocks.collaboration.verifyCandidate.mockResolvedValue({ schema_version: 1, verification_id: MESSAGE, candidate_id: CANDIDATE, decision: "confirm", result_fact_id: FACT, result_revision: 2, replayed: false });
  mocks.collaboration.confirmedFacts.mockResolvedValue({ schema_version: 1, current: [fact], history: [], next_cursor: null });
  mocks.collaboration.planningSkillInspector.mockResolvedValue(null);
});

afterEach(() => {
  sessionStorage.clear();
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

it("requires candidate, confirmed fact, and advisor ledger before recovering confirmation lost acknowledgement", async () => {
  const confirmed = { ...advisor, state: "confirmed" as const, verification_id: MESSAGE, decision: "confirm" as const, reason: "Confirmed by advisor." };
  save({ role: "advisor", candidateId: CANDIDATE, phase: "confirmation_submitting" });
  mocks.collaboration.candidates.mockResolvedValue([confirmed]);
  mocks.identity.advisorLedger.mockResolvedValue(ledger(2));
  const { result } = renderHook(() => useCollaborationDemo());
  await waitFor(() => expect(result.current.state.value).toBe("replan_required"));
  expect(mocks.collaboration.confirmedFacts).toHaveBeenCalledWith(CASE, "advisor");
  expect(result.current.state.context.fact).toEqual(fact);
  expect(result.current.state.context.caseRevision).toBe(2);
});

it("treats a completed conversion as the existing advisor-family journey on collaboration reload", async () => {
  const current = {
    schema_version: 2 as const,
    journey: "collaboration" as const,
    role: "advisor" as const,
    csrf: "stored-csrf",
    caseId: CASE,
    threadId: THREAD,
    messageId: MESSAGE,
    candidateId: CANDIDATE,
    phase: "replan_required" as const,
    mutations: {},
  };
  saveRecoveryMetadata(continueCollaborationAsAdvisorFamily(current, null));

  const { result } = renderHook(() => useCollaborationDemo());

  await waitFor(() => expect(result.current.journeyConflict).toBe("advisor-family"));
  expect(mocks.identity.bootstrap).not.toHaveBeenCalled();
  expect(loadDemoJourneyEnvelope()?.journey).toBe("advisor-family");
});

it.each([
  ["task-ready", null],
  ["active-task", TASK],
  ["review-required", TASK],
  ["terminal-task-failure", TASK],
  ["family-review", null],
  ["plan-ready", null],
] as const)("validates exact authority and adopts %s task identity only from the ledger", async (phase, expectedTaskId) => {
  saveConfirmed();
  mocks.identity.advisorLedger.mockResolvedValue(handoffLedger(phase));
  const navigate = vi.spyOn(collaborationNavigation, "toPlanning").mockImplementation(() => undefined);
  const { result } = renderHook(() => useCollaborationDemo());
  await waitFor(() => expect(result.current.state.value).toBe("replan_required"));
  vi.clearAllMocks();
  mocks.collaboration.candidates.mockResolvedValue([confirmedCandidate()]);
  mocks.collaboration.confirmedFacts.mockResolvedValue({ schema_version: 1, current: [fact], history: [], next_cursor: null });
  mocks.identity.advisorLedger.mockResolvedValue(handoffLedger(phase));
  mocks.collaboration.planningSkillInspector.mockResolvedValue(null);
  const writes = vi.spyOn(Storage.prototype, "setItem");

  await act(async () => result.current.continueToPlanning());

  expect(mocks.collaboration.candidates).toHaveBeenCalledWith(CASE, "advisor");
  expect(mocks.collaboration.confirmedFacts).toHaveBeenCalledWith(CASE, "advisor");
  expect(mocks.identity.advisorLedger).toHaveBeenCalledWith(CASE);
  expect(mocks.collaboration.planningSkillInspector).toHaveBeenCalledWith(CASE);
  expect(mocks.collaboration.candidates.mock.invocationCallOrder[0]).toBeLessThan(mocks.collaboration.confirmedFacts.mock.invocationCallOrder[0]);
  expect(mocks.collaboration.confirmedFacts.mock.invocationCallOrder[0]).toBeLessThan(mocks.identity.advisorLedger.mock.invocationCallOrder[0]);
  expect(mocks.identity.advisorLedger.mock.invocationCallOrder[0]).toBeLessThan(mocks.collaboration.planningSkillInspector.mock.invocationCallOrder[0]);
  expect(loadDemoJourneyEnvelope()).toEqual({ schema_version: 2, journey: "advisor-family", role: "advisor", csrf: "stored-csrf", caseId: CASE, taskId: expectedTaskId, briefId: null, cursor: 0, mutations: {} });
  expect(writes).toHaveBeenCalledOnce();
  expect(navigate).toHaveBeenCalledOnce();
  expect(mocks.identity.bootstrap).not.toHaveBeenCalled();
  expect(mocks.identity.mint).not.toHaveBeenCalled();
  expect(mocks.identity.revoke).not.toHaveBeenCalled();
  expect(mocks.collaboration.verifyCandidate).not.toHaveBeenCalled();
});

it.each([
  ["candidate missing", () => mocks.collaboration.candidates.mockResolvedValue([])],
  ["candidate stale", () => mocks.collaboration.candidates.mockResolvedValue([{ ...confirmedCandidate(), state: "stale" }])],
  ["fact missing", () => mocks.collaboration.confirmedFacts.mockResolvedValue({ schema_version: 1, current: [], history: [], next_cursor: null })],
  ["fact provenance mismatch", () => mocks.collaboration.confirmedFacts.mockResolvedValue({ schema_version: 1, current: [{ ...fact, candidate_id: FACT }], history: [], next_cursor: null })],
  ["Case drift", () => mocks.identity.advisorLedger.mockResolvedValue({ ...handoffLedger("task-ready"), case_id: FACT })],
  ["revision drift", () => mocks.identity.advisorLedger.mockResolvedValue({ ...handoffLedger("task-ready"), case_revision: 3 })],
  ["wrong role is non-enumerating", () => mocks.collaboration.candidates.mockRejectedValue(new CollaborationDemoApiError(404, "resource_unavailable"))],
  ["session expired", () => mocks.collaboration.candidates.mockRejectedValue(new CollaborationDemoApiError(401, "unknown"))],
  ["malformed ledger phase", () => mocks.identity.advisorLedger.mockResolvedValue({ ...handoffLedger("task-ready"), phase: "unknown" })],
  ["ledger unavailable", () => mocks.identity.advisorLedger.mockRejectedValue(new Error("unavailable"))],
  ["inspector unavailable", () => mocks.collaboration.planningSkillInspector.mockRejectedValue(new Error("unavailable"))],
  ["unknown failure", () => mocks.collaboration.candidates.mockRejectedValue(new Error("unknown"))],
] as const)("leaves the collaboration envelope byte-identical when %s", async (_name, mutate) => {
  saveConfirmed();
  const navigate = vi.spyOn(collaborationNavigation, "toPlanning").mockImplementation(() => undefined);
  const { result } = renderHook(() => useCollaborationDemo());
  await waitFor(() => expect(result.current.state.value).toBe("replan_required"));
  vi.clearAllMocks();
  mocks.collaboration.candidates.mockResolvedValue([confirmedCandidate()]);
  mocks.collaboration.confirmedFacts.mockResolvedValue({ schema_version: 1, current: [fact], history: [], next_cursor: null });
  mocks.identity.advisorLedger.mockResolvedValue(handoffLedger("task-ready"));
  mocks.collaboration.planningSkillInspector.mockResolvedValue(null);
  mutate();
  const before = sessionStorage.getItem("night-voyager:m5");

  await act(async () => result.current.continueToPlanning());

  expect(result.current.state.value).toBe("recoverable_error");
  expect(sessionStorage.getItem("night-voyager:m5")).toBe(before);
  expect(navigate).not.toHaveBeenCalled();
  expect(mocks.collaboration.verifyCandidate).not.toHaveBeenCalled();
  const readsBeforeRetry = mocks.collaboration.candidates.mock.calls.length;
  await act(async () => result.current.retry());
  expect(mocks.collaboration.candidates.mock.calls.length).toBe(readsBeforeRetry + 1);
  expect(mocks.collaboration.verifyCandidate).not.toHaveBeenCalled();
});

it("recovers a parent session when mint succeeds before the first authority read fails", async () => {
  let cookieRole: "parent" | null = null;
  mocks.identity.bootstrap.mockImplementation(async () => {
    if (cookieRole) throw new ConnectedDemoApiError(409, "bff_session_recovery_required");
    return { csrf_token: "bootstrap" };
  });
  mocks.identity.mint.mockImplementation(async () => {
    cookieRole = "parent";
    return { role: "parent", proof_mode: "synthetic-demo", csrf_token: "parent-csrf" };
  });
  mocks.collaboration.thread.mockRejectedValueOnce(new Error("read failed"));
  const { result } = renderHook(() => useCollaborationDemo());

  await act(async () => result.current.connectParent());
  expect(result.current.state.value).toBe("recoverable_error");
  expect(loadDemoJourneyEnvelope()).toMatchObject({ role: "parent", csrf: "parent-csrf", phase: "bootstrapping_parent" });

  await act(async () => result.current.retry());
  await waitFor(() => expect(result.current.state.value).toBe("thread_ready"));
  expect(mocks.identity.bootstrap).toHaveBeenCalledOnce();
  expect(mocks.identity.mint).toHaveBeenCalledOnce();
  expect(mocks.identity.revoke).not.toHaveBeenCalled();
});

it("recovers an advisor session when mint succeeds before an advisor authority read fails", async () => {
  let cookieRole: "parent" | "advisor" | null = "parent";
  save({ role: "parent", phase: "proposal_pending" });
  mocks.collaboration.candidates.mockImplementation(async (_caseId: string, role?: string) => {
    if (role !== cookieRole) throw new Error("wrong role projection");
    return role === "advisor" ? [advisor] : [participant];
  });
  mocks.identity.revoke.mockImplementation(async () => { cookieRole = null; });
  mocks.identity.bootstrap.mockImplementation(async () => {
    if (cookieRole) throw new ConnectedDemoApiError(409, "bff_session_recovery_required");
    return { csrf_token: "bootstrap" };
  });
  mocks.identity.mint.mockImplementation(async () => {
    cookieRole = "advisor";
    return { role: "advisor", proof_mode: "synthetic-demo", csrf_token: "advisor-csrf" };
  });
  const { result } = renderHook(() => useCollaborationDemo());
  await waitFor(() => expect(result.current.state.value).toBe("proposal_pending"));
  mocks.collaboration.candidates.mockRejectedValueOnce(new Error("advisor read failed"));

  await act(async () => result.current.switchToAdvisor());
  expect(result.current.state.value).toBe("recoverable_error");
  expect(loadDemoJourneyEnvelope()).toMatchObject({ role: "advisor", csrf: "advisor-csrf", phase: "switching_to_advisor" });

  await act(async () => result.current.retry());
  await waitFor(() => expect(result.current.state.value).toBe("advisor_reviewing"));
  expect(result.current.state.context.candidate).toEqual(advisor);
  expect(mocks.identity.bootstrap).toHaveBeenCalledOnce();
  expect(mocks.identity.mint).toHaveBeenCalledOnce();
  expect(mocks.identity.revoke).toHaveBeenCalledOnce();
});

it("turns an unknown message outcome into an explicit exact-body/key retry", async () => {
  const body = { schema_version: 1 as const, body: MESSAGE_BODY };
  const record = await idempotencyFor(body);
  save({ role: "parent", messageId: null, phase: "message_submitting", mutations: { "append-message": record } });
  mocks.collaboration.messages.mockResolvedValueOnce({ schema_version: 1, items: [], next_after_sequence: null }).mockResolvedValue({ schema_version: 1, items: [message], next_after_sequence: null });
  mocks.collaboration.candidates.mockResolvedValue([]);
  const { result } = renderHook(() => useCollaborationDemo());
  await waitFor(() => expect(result.current.state.value).toBe("recoverable_error"));
  await act(async () => result.current.retry());
  expect(mocks.collaboration.appendMessage).toHaveBeenCalledWith(THREAD, body, "stored-csrf", record.idempotencyKey);
  await waitFor(() => expect(result.current.state.value).toBe("thread_ready"));
});

it("reconciles a lost proposal acknowledgement from the parent projection", async () => {
  const body = { schema_version: 1 as const, case_revision: 1, proposal: { schema_version: 1 as const, fact_key: "family.budget", value: BUDGET } };
  const record = await idempotencyFor(body);
  save({ role: "parent", phase: "thread_ready", mutations: { "propose-memory-candidate": record } });
  const { result } = renderHook(() => useCollaborationDemo());
  await waitFor(() => expect(result.current.state.value).toBe("proposal_pending"));
  expect(result.current.state.context.candidate).toEqual(participant);
  expect(loadDemoJourneyEnvelope()).toMatchObject({ phase: "proposal_pending", mutations: {} });
  expect(mocks.collaboration.proposeCandidate).not.toHaveBeenCalled();
});

it("reloads advisor_reviewing from advisor candidate and ledger authority", async () => {
  save({ role: "advisor", candidateId: CANDIDATE, phase: "advisor_reviewing" });
  mocks.collaboration.candidates.mockResolvedValue([advisor]);
  const { result } = renderHook(() => useCollaborationDemo());
  await waitFor(() => expect(result.current.state.value).toBe("advisor_reviewing"));
  expect(result.current.state.context.candidate).toEqual(advisor);
  expect(result.current.state.context.caseRevision).toBe(1);
  expect(mocks.identity.advisorLedger).toHaveBeenCalledWith(CASE);
});

it("requires an explicit same-body/key retry for a pending confirmation outcome", async () => {
  const body = { schema_version: 1 as const, expected_case_revision: 1, decision: "confirm" as const, reason: "The family confirmed this bounded program budget." };
  const record = await idempotencyFor(body);
  let confirmed = false;
  const confirmedCandidate = { ...advisor, state: "confirmed" as const, verification_id: MESSAGE, decision: "confirm" as const, reason: "Confirmed by advisor." };
  save({ role: "advisor", candidateId: CANDIDATE, phase: "confirmation_submitting", mutations: { "verify-memory-candidate": record } });
  mocks.collaboration.candidates.mockImplementation(async () => [confirmed ? confirmedCandidate : advisor]);
  mocks.collaboration.confirmedFacts.mockImplementation(async () => ({ schema_version: 1, current: confirmed ? [fact] : [], history: [], next_cursor: null }));
  mocks.identity.advisorLedger.mockImplementation(async () => ledger(confirmed ? 2 : 1));
  mocks.collaboration.verifyCandidate.mockImplementation(async () => { confirmed = true; return { schema_version: 1, verification_id: MESSAGE, candidate_id: CANDIDATE, decision: "confirm", result_fact_id: FACT, result_revision: 2, replayed: true }; });
  const { result } = renderHook(() => useCollaborationDemo());
  await waitFor(() => expect(result.current.state.value).toBe("recoverable_error"));
  await act(async () => result.current.retry());
  expect(mocks.collaboration.verifyCandidate).toHaveBeenCalledWith(CANDIDATE, body, "stored-csrf", record.idempotencyKey);
  await waitFor(() => expect(result.current.state.value).toBe("replan_required"));
  expect(result.current.state.context.fact).toEqual(fact);
});

it("clears a confirmed 401 and makes explicit retry start a fresh parent bootstrap", async () => {
  save({ role: "parent", phase: "thread_ready" });
  mocks.collaboration.thread.mockRejectedValueOnce(new CollaborationDemoApiError(401, "unknown"));
  const { result } = renderHook(() => useCollaborationDemo());
  await waitFor(() => expect(result.current.state.value).toBe("recoverable_error"));
  expect(result.current.state).toMatchObject({ value: "recoverable_error", category: "session_recovery_required" });
  expect(loadDemoJourneyEnvelope()).toBeNull();
  await act(async () => result.current.retry());
  expect(mocks.identity.bootstrap).toHaveBeenCalledOnce();
  await waitFor(() => expect(result.current.state.value).toBe("thread_ready"));
});

it("does not replay confirmation after 401 and resets advisor recovery to fresh parent bootstrap", async () => {
  save({ role: "advisor", candidateId: CANDIDATE, phase: "advisor_reviewing" });
  mocks.collaboration.candidates.mockResolvedValue([advisor]);
  mocks.collaboration.verifyCandidate.mockRejectedValueOnce(new CollaborationDemoApiError(401, "unknown"));
  const { result } = renderHook(() => useCollaborationDemo());
  await waitFor(() => expect(result.current.state.value).toBe("advisor_reviewing"));
  await act(async () => result.current.confirmCandidate());
  expect(result.current.state).toMatchObject({ value: "recoverable_error", category: "session_recovery_required" });
  expect(loadDemoJourneyEnvelope()).toBeNull();
  await act(async () => result.current.retry());
  await waitFor(() => expect(result.current.state.value).toBe("thread_ready"));
  expect(mocks.collaboration.verifyCandidate).toHaveBeenCalledOnce();
  expect(mocks.identity.bootstrap).toHaveBeenCalledOnce();
});

it("coordinates a partial role switch with server projection instead of stored role", async () => {
  save({ role: "parent", phase: "switching_to_advisor" });
  mocks.collaboration.candidates.mockImplementation(async (_caseId: string, role?: string) => {
    if (role === "parent") throw new Error("invalid response");
    return [advisor];
  });
  const { result } = renderHook(() => useCollaborationDemo());
  await waitFor(() => expect(result.current.state.value).toBe("recoverable_error"));
  expect(result.current.state).toMatchObject({ value: "recoverable_error", category: "session_recovery_required" });
  expect(loadDemoJourneyEnvelope()).toBeNull();
  expect(mocks.collaboration.candidates).toHaveBeenCalledWith(CASE, "advisor");
});

it("discards a stale verification retry after 409 authority reload changes revision", async () => {
  const changed = { ...advisor, case_revision: 2 };
  save({ role: "advisor", candidateId: CANDIDATE, phase: "advisor_reviewing" });
  mocks.collaboration.candidates.mockResolvedValueOnce([advisor]).mockResolvedValue([changed]);
  mocks.identity.advisorLedger.mockResolvedValueOnce(ledger(1)).mockResolvedValueOnce(ledger(1)).mockResolvedValue(ledger(2));
  mocks.collaboration.verifyCandidate.mockRejectedValueOnce(new CollaborationDemoApiError(409, "case_revision_stale"));
  const { result } = renderHook(() => useCollaborationDemo());
  await waitFor(() => expect(result.current.state.value).toBe("advisor_reviewing"));
  await act(async () => result.current.confirmCandidate());
  await waitFor(() => expect(result.current.state.value).toBe("recoverable_error"));
  await act(async () => result.current.retry());
  expect(mocks.collaboration.verifyCandidate).toHaveBeenCalledOnce();
  expect(loadDemoJourneyEnvelope()).toMatchObject({ phase: "advisor_reviewing", mutations: {} });
});

it("does not append again after a 409 reload discards the append mutation", async () => {
  save({ role: "parent", messageId: null, phase: "thread_ready" });
  mocks.collaboration.messages.mockResolvedValue({ schema_version: 1, items: [], next_after_sequence: null });
  mocks.collaboration.appendMessage.mockRejectedValueOnce(new CollaborationDemoApiError(409, "case_revision_stale"));
  const { result } = renderHook(() => useCollaborationDemo());
  await waitFor(() => expect(result.current.state.value).toBe("thread_ready"));

  await act(async () => result.current.appendMessage());
  await waitFor(() => expect(result.current.state.value).toBe("recoverable_error"));
  await act(async () => result.current.retry());

  expect(mocks.collaboration.appendMessage).toHaveBeenCalledOnce();
  expect(loadDemoJourneyEnvelope()).toMatchObject({ phase: "thread_ready", mutations: {} });
});

it("does not propose again after a 409 reload discards the proposal mutation", async () => {
  save({ role: "parent", phase: "thread_ready" });
  mocks.collaboration.proposeCandidate.mockRejectedValueOnce(new CollaborationDemoApiError(409, "case_revision_stale"));
  mocks.collaboration.candidates.mockResolvedValue([]);
  const { result } = renderHook(() => useCollaborationDemo());
  await waitFor(() => expect(result.current.state.value).toBe("thread_ready"));

  await act(async () => result.current.proposeBudget());
  await waitFor(() => expect(result.current.state.value).toBe("recoverable_error"));
  await act(async () => result.current.retry());

  expect(mocks.collaboration.proposeCandidate).toHaveBeenCalledOnce();
  expect(loadDemoJourneyEnvelope()).toMatchObject({ phase: "thread_ready", mutations: {} });
});
