import { afterEach, expect, it, vi } from "vitest";

import { createCollaborationDemoApi } from "../../lib/collaboration-demo/api";

const CASE = "40000000-0000-0000-0000-000000000031";
const THREAD = "40000000-0000-0000-0000-000000000032";
const MESSAGE = "40000000-0000-0000-0000-000000000033";
const CANDIDATE = "40000000-0000-0000-0000-000000000034";
const AT = "2026-07-20T01:02:03Z";
const SHA = "a".repeat(64);

afterEach(() => vi.unstubAllGlobals());

it("uses the exact eight collaboration/inspector methods with no-store", async () => {
  const calls: Array<{ path: string; init?: RequestInit }> = [];
  const responses: unknown[] = [
    { schema_version: 1, thread_id: THREAD, case_id: CASE, created_by_actor_id: CASE, created_at: AT },
    { schema_version: 1, items: [], next_after_sequence: null },
    { schema_version: 1, message_event_id: MESSAGE, thread_id: THREAD, case_id: CASE, sequence_no: 1, actor_id: CASE, actor_role: "parent", body: "Budget confirmed.", content_sha256: SHA, created_at: AT },
    { schema_version: 1, fact_key: "family.risk_tolerance", value: "high", state: "pending", created_at: AT, expires_at: "2026-07-27T01:02:03Z" },
    [],
    { schema_version: 1, verification_id: MESSAGE, candidate_id: CANDIDATE, decision: "confirm", result_fact_id: MESSAGE, result_revision: 2, replayed: false },
    { schema_version: 1, current: [] },
    { schema_version: 1, case_id: CASE, operation: null, active_skill_key: "study-destination-compare", active_version: "1.0.0", activation_sequence: 1, evaluator_id: "night-voyager.deterministic-skill-evaluator", evaluator_version: "v1", evaluation_dataset_id: "night-voyager.study-destination-compare.eval", evaluation_dataset_version: "1.0.0", task_request_sha256_prefix: null, version_content_sha256_prefix: "111111111111", runtime_binding_sha256_prefix: "abcdef123456", adapter_id: null, adapter_version: null, pin_status: "not_created" },
  ];
  vi.stubGlobal("fetch", vi.fn(async (path: string, init?: RequestInit) => { calls.push({ path, init }); return Response.json(responses.shift()); }));
  const api = createCollaborationDemoApi();
  await api.thread(CASE);
  await api.messages(THREAD, 0, 50);
  await api.appendMessage(THREAD, { schema_version: 1, body: "Budget confirmed." }, "csrf", CASE);
  await api.proposeCandidate(MESSAGE, { schema_version: 1, case_revision: 1, proposal: { schema_version: 1, fact_key: "family.risk_tolerance", value: "high" } }, "csrf", CASE);
  await api.candidates(CASE, "parent");
  await api.verifyCandidate(CANDIDATE, { schema_version: 1, expected_case_revision: 1, decision: "confirm", reason: "Confirmed." }, "csrf", CASE);
  await api.confirmedFacts(CASE, "parent");
  await api.planningSkillInspector(CASE);
  expect(calls.map(({ path }) => path)).toEqual([
    `/api/demo/cases/${CASE}/collaboration-thread`,
    `/api/demo/collaboration-threads/${THREAD}/messages?after_sequence=0&limit=50`,
    `/api/demo/collaboration-threads/${THREAD}/messages`,
    `/api/demo/messages/${MESSAGE}/memory-candidates`,
    `/api/demo/cases/${CASE}/memory-candidates`,
    `/api/demo/memory-candidates/${CANDIDATE}/verification-decisions`,
    `/api/demo/cases/${CASE}/confirmed-facts`,
    `/api/demo/cases/${CASE}/planning-skill-inspector`,
  ]);
  expect(calls.every(({ init }) => init?.cache === "no-store")).toBe(true);
});

it("fails closed on malformed success payloads", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({ schema_version: 1, thread_id: THREAD })));
  await expect(createCollaborationDemoApi().thread(CASE)).rejects.toThrow("invalid response");
});

it("rejects wrong-role candidate projections in both directions", async () => {
  const participant = { schema_version: 1, fact_key: "family.risk_tolerance", value: "high", state: "pending", created_at: AT, expires_at: "2026-07-27T01:02:03Z" };
  const advisor = { ...participant, candidate_id: CANDIDATE, message_event_id: MESSAGE, source_message_sequence_no: 1, subject_actor_id: CASE, subject_role: "parent", case_revision: 1, verification_id: null, decision: null, reason: null, request_sha256: SHA, value_sha256: SHA };
  const responses = [advisor, participant, [participant, advisor]];
  vi.stubGlobal("fetch", vi.fn(async () => Response.json([responses.shift()])));
  const api = createCollaborationDemoApi();
  await expect(api.candidates(CASE, "parent")).rejects.toThrow("invalid response");
  await expect(api.candidates(CASE, "advisor")).rejects.toThrow("invalid response");
  await expect(api.candidates(CASE, "parent")).rejects.toThrow("invalid response");
});
