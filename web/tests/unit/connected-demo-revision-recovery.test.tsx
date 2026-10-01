import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { BudgetValue } from "../../lib/collaboration-demo/contracts";
import { useConnectedDemo } from "../../lib/connected-demo/use-connected-demo";
import { loadRecoveryMetadata, saveRecoveryMetadata } from "../../lib/connected-demo/session-storage";
import { CASE_ID, status } from "./connected-demo-test-data";

const THREAD_ID = "42000000-0000-0000-0000-000000000001";
const MESSAGE_ID = "43000000-0000-0000-0000-000000000001";
const AT = "2026-10-01T00:00:00Z";
const budget: BudgetValue = { schema_version: 1, currency: "CNY", period: "program_total", preferred_minor: 30000000, hard_ceiling_minor: 40000000, elasticity_bps: 0, refused: false };
const facts = [
  { schema_version: 1, fact_key: "student.preferred_countries", value: ["japan", "malaysia"], fact_version: 1, confirmed_at: AT, subject_role: "student", confirming_advisor_role: "advisor" },
  { schema_version: 1, fact_key: "family.budget", value: budget, fact_version: 1, confirmed_at: AT, subject_role: "parent", confirming_advisor_role: "advisor" },
];
function setup(candidateStatus = 201, bootstrapFailures = 0) {
  saveRecoveryMetadata({ schema_version: 3, journey: "advisor-family", role: "student", csrf: "csrf", caseId: CASE_ID, currentRevision: 1, currentTaskId: null, predecessorRunId: null, currentRunId: null, cursor: 0, phase: "revision_requested", mutations: {} });
  const writes: Array<{ path: string; body: Record<string, unknown>; key: string }> = [];
  const sessionEvents: string[] = [];
  const mutationRoles: string[] = [];
  let role: "student" | "parent" = "student";
  let currentRevision = 1;
  let phase: "revision_requested" | "revision_fact_pending" = "revision_requested";
  let statusReads = 0;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path.endsWith("/session") && init?.method === "DELETE") { sessionEvents.push("revoke"); return new Response(null, { status: 204 }); }
    if (path.endsWith("/session-bootstrap")) {
      sessionEvents.push("bootstrap");
      if (bootstrapFailures-- > 0) return Response.json({ code: "unavailable" }, { status: 503 });
      return Response.json({ csrf_token: "bootstrap-csrf" });
    }
    if (path.endsWith("/sessions") && init?.method === "POST") {
      role = JSON.parse(String(init.body)).demo_actor;
      sessionEvents.push(`mint:${role}`);
      return Response.json({ role, proof_mode: "synthetic-demo", csrf_token: `${role}-csrf` }, { status: 201 });
    }
    if (init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      mutationRoles.push(role);
      writes.push({ path, body, key: new Headers(init.headers).get("Idempotency-Key") ?? "" });
      if (path.endsWith("/messages")) return Response.json({ schema_version: 1, message_event_id: MESSAGE_ID, thread_id: THREAD_ID, case_id: CASE_ID, sequence_no: 1, actor_id: CASE_ID, actor_role: role, body: body.body, content_sha256: "a".repeat(64), created_at: AT });
      if ((body.proposal.fact_key === "family.budget") !== (role === "parent")) return Response.json({ code: "forbidden_fact" }, { status: 403 });
      if (candidateStatus === 409) { currentRevision = 2; return Response.json({ code: "stale_revision" }, { status: 409 }); }
      if (candidateStatus !== 201) return Response.json({ code: "unavailable" }, { status: candidateStatus });
      phase = "revision_fact_pending";
      return Response.json({ schema_version: 1, fact_key: body.proposal.fact_key, value: body.proposal.value, state: "pending", created_at: AT, expires_at: "2026-10-08T00:00:00Z" });
    }
    if (path.endsWith("/journey-status")) { statusReads++; return Response.json({ ...status(phase), current_revision: currentRevision, active_role: phase === "revision_requested" ? role : "advisor" }); }
    if (path.endsWith("/collaboration-thread")) return Response.json({ schema_version: 1, thread_id: THREAD_ID, case_id: CASE_ID, created_by_actor_id: CASE_ID, created_at: AT });
    if (path.endsWith("/confirmed-facts")) return Response.json({ schema_version: 1, current: facts });
    if (path.endsWith("/memory-candidates")) return Response.json([]);
    if (path.includes("/messages?")) return Response.json({ schema_version: 1, items: [], next_after_sequence: null });
    throw new Error(`unexpected ${path}`);
  }));
  return { writes, mutationRoles, sessionEvents, statusReads: () => statusReads };
}
afterEach(() => { sessionStorage.clear(); vi.unstubAllGlobals(); });

it.each([
  { factKey: "student.preferred_countries" as const, value: ["malaysia"] as const },
  { factKey: "family.budget" as const, value: { ...budget, preferred_minor: 32000000, hard_ceiling_minor: 42000000 } },
])("submits the entered $factKey body and saves its intention for same-tab recovery", async (proposal) => {
  const { writes, mutationRoles, sessionEvents } = setup();
  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("revision_requested"));
  await act(() => result.current.submitRevision({ expectedCaseRevision: 1, ...proposal }));
  expect(writes[1].body).toEqual({ schema_version: 1, case_revision: 1, proposal: { schema_version: 1, fact_key: proposal.factKey, value: proposal.value } });
  expect(writes[0].body.body).toContain(proposal.factKey);
  expect(loadRecoveryMetadata()?.revisionIntent).toEqual({ expectedCaseRevision: 1, ...proposal });
  expect(mutationRoles).toEqual(proposal.factKey === "family.budget" ? ["parent", "parent"] : ["student", "student"]);
  expect(sessionEvents).toEqual(proposal.factKey === "family.budget" ? ["revoke", "bootstrap", "mint:parent"] : []);
});

it("rejects a stale local intention without sending either mutation", async () => {
  const { writes, statusReads } = setup();
  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("revision_requested"));
  await act(() => result.current.submitRevision({ expectedCaseRevision: 2, factKey: "student.preferred_countries", value: ["australia"] }));
  expect(writes).toHaveLength(0);
  expect(statusReads()).toBeGreaterThan(1);
});

it("reloads authoritative facts after a typed collaboration 409 and drops the stale intention", async () => {
  const { writes, statusReads } = setup(409);
  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("revision_requested"));
  await act(() => result.current.submitRevision({ expectedCaseRevision: 1, factKey: "student.preferred_countries", value: ["australia"] }));
  expect(writes).toHaveLength(2);
  expect(statusReads()).toBeGreaterThan(1);
  expect(result.current.currentFacts?.caseRevision).toBe(2);
  expect(loadRecoveryMetadata()?.revisionIntent).toBeUndefined();
  expect(loadRecoveryMetadata()?.mutations["fact-proposal-candidate"]).toBeUndefined();
});

it("reuses exact submitted bodies on retry, while an edited intention gets fresh message and proposal keys", async () => {
  const { writes } = setup(503);
  const { result, unmount } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("revision_requested"));
  const first = { expectedCaseRevision: 1, factKey: "student.preferred_countries" as const, value: ["australia"] as const };
  await act(() => result.current.submitRevision(first));
  await act(() => result.current.retry());
  expect(writes[0]).toEqual(writes[2]);
  expect(writes[1]).toEqual(writes[3]);
  unmount();
  const restored = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(restored.result.current.state.value).toBe("revision_requested"));
  expect(restored.result.current.revisionIntent).toEqual(first);
  await act(() => restored.result.current.submitRevision({ ...first, value: ["malaysia"] }));
  expect(writes[4].key).not.toBe(writes[0].key);
  expect(writes[5].key).not.toBe(writes[1].key);
  expect((writes[5].body.proposal as Record<string, unknown>).value).toEqual(["malaysia"]);
});

it("recovers a parent budget rotation after bootstrap loss without sending as student", async () => {
  const { writes, mutationRoles, sessionEvents } = setup(503, 1);
  const { result, unmount } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("revision_requested"));
  const intent = { expectedCaseRevision: 1, factKey: "family.budget" as const, value: { ...budget, preferred_minor: 32000000 } };
  await act(() => result.current.submitRevision(intent));
  expect(writes).toHaveLength(0);
  expect(loadRecoveryMetadata()).toMatchObject({ role: "student", pendingRole: "parent", revisionIntent: intent });
  const keysBefore = loadRecoveryMetadata()?.mutations;
  unmount();
  const restored = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(restored.result.current.state.value).toBe("revision_requested"));
  expect(restored.result.current.state).toMatchObject({ status: { active_role: "parent" } });
  expect(restored.result.current.revisionIntent).toEqual(intent);
  expect(writes).toHaveLength(0);
  await act(() => restored.result.current.submitRevision(intent));
  expect(mutationRoles).toEqual(["parent", "parent"]);
  expect(loadRecoveryMetadata()?.mutations).toMatchObject(keysBefore!);
  expect(sessionEvents).toContain("mint:parent");
});
