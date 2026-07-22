import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { loadDemoJourneyEnvelope } from "../../lib/connected-demo/session-storage";
import { collaborationNavigation, useCollaborationDemo } from "../../lib/collaboration-demo/use-collaboration-demo";

const CASE = "41000000-0000-0000-0000-000000000001";
const THREAD = "42000000-0000-0000-0000-000000000001";
const MESSAGE = "43000000-0000-0000-0000-000000000001";
const CANDIDATE = "44000000-0000-0000-0000-000000000001";
const FACT = "45000000-0000-0000-0000-000000000001";
const AT = "2026-07-20T01:02:03Z";
const SHA = "a".repeat(64);

afterEach(() => { sessionStorage.clear(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it("proves parent message through advisor confirmation and authoritative fact/revision reload", async () => {
  let role: "parent" | "advisor" = "parent";
  let proposed = false;
  let confirmed = false;
  const keys: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path.endsWith("/session-bootstrap")) return Response.json({ csrf_token: "bootstrap" });
    if (path.endsWith("/sessions")) { role = JSON.parse(String(init?.body)).demo_actor; return Response.json({ role, proof_mode: "synthetic-demo", csrf_token: `${role}-csrf` }, { status: 201 }); }
    if (path.endsWith("/session") && init?.method === "DELETE") return new Response(null, { status: 204 });
    if (path.endsWith("/collaboration-thread")) return Response.json({ schema_version: 1, thread_id: THREAD, case_id: CASE, created_by_actor_id: CASE, created_at: AT });
    if (path.includes(`/collaboration-threads/${THREAD}/messages`) && init?.method === "POST") { keys.push(new Headers(init.headers).get("Idempotency-Key") ?? ""); return Response.json({ schema_version: 1, message_event_id: MESSAGE, thread_id: THREAD, case_id: CASE, sequence_no: 1, actor_id: CASE, actor_role: "parent", body: "Our confirmed program budget is 300,000 to 400,000 CNY.", content_sha256: SHA, created_at: AT }, { status: 201 }); }
    if (path.includes(`/collaboration-threads/${THREAD}/messages`)) return Response.json({ schema_version: 1, items: proposed ? [{ schema_version: 1, message_event_id: MESSAGE, thread_id: THREAD, case_id: CASE, sequence_no: 1, actor_id: CASE, actor_role: "parent", body: "Our confirmed program budget is 300,000 to 400,000 CNY.", content_sha256: SHA, created_at: AT }] : [], next_after_sequence: null });
    if (path.includes(`/messages/${MESSAGE}/memory-candidates`)) { proposed = true; keys.push(new Headers(init?.headers).get("Idempotency-Key") ?? ""); return Response.json({ schema_version: 1, fact_key: "family.budget", value: { schema_version: 1, currency: "CNY", period: "program_total", preferred_minor: 30000000, hard_ceiling_minor: 40000000, elasticity_bps: 1000, refused: false }, state: "pending", created_at: AT, expires_at: "2026-07-27T01:02:03Z" }, { status: 201 }); }
    if (path.endsWith("/memory-candidates")) {
      const participant = { schema_version: 1, fact_key: "family.budget", value: { schema_version: 1, currency: "CNY", period: "program_total", preferred_minor: 30000000, hard_ceiling_minor: 40000000, elasticity_bps: 1000, refused: false }, state: confirmed ? "confirmed" : "pending", created_at: AT, expires_at: "2026-07-27T01:02:03Z" };
      const advisor = { ...participant, candidate_id: CANDIDATE, message_event_id: MESSAGE, source_message_sequence_no: 1, subject_actor_id: CASE, subject_role: "parent", case_revision: 1, verification_id: confirmed ? MESSAGE : null, decision: confirmed ? "confirm" : null, reason: confirmed ? "Confirmed by advisor." : null, request_sha256: SHA, value_sha256: SHA };
      return Response.json(role === "advisor" ? [advisor] : proposed ? [participant] : []);
    }
    if (path.includes("/verification-decisions")) { confirmed = true; keys.push(new Headers(init?.headers).get("Idempotency-Key") ?? ""); return Response.json({ schema_version: 1, verification_id: MESSAGE, candidate_id: CANDIDATE, decision: "confirm", result_fact_id: FACT, result_revision: 2, replayed: false }, { status: 201 }); }
    if (path.endsWith("/confirmed-facts")) return Response.json({ schema_version: 1, current: [{ schema_version: 1, fact_key: "family.budget", value: { schema_version: 1, currency: "CNY", period: "program_total", preferred_minor: 30000000, hard_ceiling_minor: 40000000, elasticity_bps: 1000, refused: false }, fact_version: 1, confirmed_at: AT, subject_role: "parent", confirming_advisor_role: "advisor", confirmed_fact_id: FACT, candidate_id: CANDIDATE, verification_id: MESSAGE, source_message_event_id: MESSAGE, source_message_sequence_no: 1, source_message_sha256_prefix: "aaaaaaaaaaaa", confirming_advisor_actor_id: CASE, reason: "Confirmed by advisor.", supersedes_fact_id: null }], history: [], next_cursor: null });
    if (path.endsWith("/advisor-ledger")) return Response.json({ schema_version: 1, proof_mode: "synthetic-demo", phase: "task-ready", case_id: CASE, case_revision: confirmed ? 2 : 1, case_state: "intake", canonical_task_inputs: { schema_version: 1, operation: "generate_planning_run_v1", case_id: CASE, expected_case_revision: confirmed ? 2 : 1, source_pack_id: "50000000-0000-0000-0000-000000000001", source_pack_version: 1, policy_version: "m3a-policy-v1" }, task: null, planning_run: null, routes: [], evidence: [], review_inputs: null, current_brief_id: null, recovery: null });
    if (path.endsWith("/planning-skill-inspector")) return Response.json({ schema_version: 1, case_id: CASE, operation: null, active_skill_key: "study-destination-compare", active_version: "1.0.0", activation_sequence: 1, evaluator_id: "night-voyager.deterministic-skill-evaluator", evaluator_version: "v1", evaluation_dataset_id: "night-voyager.study-destination-compare.eval", evaluation_dataset_version: "1.0.0", task_request_sha256_prefix: null, version_content_sha256_prefix: "111111111111", runtime_binding_sha256_prefix: "abcdef123456", adapter_id: null, adapter_version: null, pin_status: "not_created" });
    throw new Error(`unexpected ${path}`);
  }));
  const { result } = renderHook(() => useCollaborationDemo());
  await act(async () => result.current.connectParent());
  expect(result.current.state.value).toBe("thread_ready");
  await act(async () => result.current.appendMessage());
  await act(async () => result.current.proposeBudget());
  expect(result.current.state.value).toBe("proposal_pending");
  expect(loadDemoJourneyEnvelope()).toMatchObject({ journey: "collaboration", candidateId: null, phase: "proposal_pending" });
  await act(async () => result.current.switchToAdvisor());
  expect(result.current.state.value).toBe("advisor_reviewing");
  await act(async () => result.current.confirmCandidate());
  await waitFor(() => expect(result.current.state.value).toBe("replan_required"));
  expect(result.current.state.context.caseRevision).toBe(2);
  expect(keys).toHaveLength(3);
  expect(new Set(keys).size).toBe(3);
  expect(JSON.stringify(loadDemoJourneyEnvelope())).not.toContain("recoverable_error");

  const navigate = vi.spyOn(collaborationNavigation, "toPlanning").mockImplementation(() => undefined);
  const callsBeforeHandoff = vi.mocked(fetch).mock.calls.length;
  await act(async () => result.current.continueToPlanning());
  expect(loadDemoJourneyEnvelope()).toEqual({ schema_version: 2, journey: "advisor-family", role: "advisor", csrf: "advisor-csrf", caseId: CASE, taskId: null, briefId: null, cursor: 0, mutations: {} });
  expect(navigate).toHaveBeenCalledOnce();
  const handoffCalls = vi.mocked(fetch).mock.calls.slice(callsBeforeHandoff);
  expect(handoffCalls.map(([input]) => String(input))).toEqual([
    `/api/demo/cases/${CASE}/memory-candidates`,
    `/api/demo/cases/${CASE}/confirmed-facts`,
    `/api/demo/cases/${CASE}/advisor-ledger`,
    `/api/demo/cases/${CASE}/planning-skill-inspector`,
  ]);
  expect(handoffCalls.every(([, init]) => !init?.method || init.method === "GET")).toBe(true);
});

it("preserves a valid advisor-family journey instead of bootstrapping over it", async () => {
  sessionStorage.setItem("night-voyager:m5", JSON.stringify({ schema_version: 2, journey: "advisor-family", role: "advisor", csrf: "csrf", caseId: "40000000-0000-0000-0000-000000000002", taskId: null, briefId: null, cursor: 0, mutations: {} }));
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  const { result } = renderHook(() => useCollaborationDemo());
  await waitFor(() => expect(result.current.journeyConflict).toBe("advisor-family"));
  expect(fetchMock).not.toHaveBeenCalled();
  expect(loadDemoJourneyEnvelope()?.journey).toBe("advisor-family");
});
