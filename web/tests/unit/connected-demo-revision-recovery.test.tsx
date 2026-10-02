import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { BudgetValue } from "../../lib/collaboration-demo/contracts";
import { ConnectedDemo } from "../../components/connected-demo/ConnectedDemo";
import { PresentationProvider } from "../../lib/presentation/context";
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
function setup(candidateStatus = 201, bootstrapFailures = 0, parentFactFailures = 0, revisionAfterParentMint = 1, sharedParticipantFacts = false) {
  saveRecoveryMetadata({ schema_version: 3, journey: "advisor-family", role: "student", csrf: "csrf", caseId: CASE_ID, currentRevision: 1, currentTaskId: null, predecessorRunId: null, currentRunId: null, cursor: 0, phase: "revision_requested", mutations: {} });
  const writes: Array<{ path: string; body: Record<string, unknown>; key: string }> = [];
  const sessionEvents: string[] = [];
  const mutationRoles: string[] = [];
  let role: "student" | "parent" = "student";
  let liveSession: { role: "student" | "parent"; csrf: string } | null = { role, csrf: "csrf" };
  let bootstrapCookie: string | null = null;
  let sessionCount = 0;
  let studentFactFailures = 0;
  const identityFailures: string[] = [];
  let currentRevision = 1;
  let phase: "revision_requested" | "revision_fact_pending" = "revision_requested";
  let statusReads = 0;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    const csrf = new Headers(init?.headers).get("X-CSRF-Token");
    if (path.endsWith("/session") && init?.method === "DELETE") {
      sessionEvents.push("revoke");
      if (!liveSession || csrf !== liveSession.csrf) {
        identityFailures.push("revoke:401");
        return Response.json({ code: "authentication_failed" }, { status: 401 });
      }
      liveSession = null;
      bootstrapCookie = null;
      return new Response(null, { status: 204 });
    }
    if (path.endsWith("/session-bootstrap")) {
      sessionEvents.push("bootstrap");
      if (bootstrapFailures-- > 0) return Response.json({ code: "unavailable" }, { status: 503 });
      bootstrapCookie = "bootstrap-csrf";
      return Response.json({ csrf_token: bootstrapCookie });
    }
    if (path.endsWith("/sessions") && init?.method === "POST") {
      if (!csrf || csrf !== (liveSession ? liveSession.csrf : bootstrapCookie)) {
        identityFailures.push("mint:401");
        return Response.json({ code: "authentication_failed" }, { status: 401 });
      }
      role = JSON.parse(String(init.body)).demo_actor;
      sessionEvents.push(`mint:${role}`);
      if (role === "parent") currentRevision = revisionAfterParentMint;
      liveSession = { role, csrf: `${role}-csrf-${++sessionCount}` };
      bootstrapCookie = null;
      return Response.json({ role, proof_mode: "synthetic-demo", csrf_token: liveSession.csrf }, { status: 201 });
    }
    if (init?.method === "POST") {
      if (!liveSession || csrf !== liveSession.csrf) return Response.json({ code: "authentication_failed" }, { status: 401 });
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
    if (path.endsWith("/confirmed-facts")) {
      if (role === "parent" && parentFactFailures-- > 0) return Response.json({ code: "unavailable" }, { status: 503 });
      if (role === "student" && studentFactFailures-- > 0) return Response.json({ code: "unavailable" }, { status: 503 });
      return Response.json({ schema_version: 1, current: sharedParticipantFacts ? facts : facts.filter((fact) => fact.subject_role === role) });
    }
    if (path.endsWith("/memory-candidates")) return Response.json([]);
    if (path.includes("/messages?")) return Response.json({ schema_version: 1, items: [], next_after_sequence: null });
    throw new Error(`unexpected ${path}`);
  }));
  return {
    writes, mutationRoles, sessionEvents, identityFailures,
    statusReads: () => statusReads, advanceRevision: () => { currentRevision++; },
    failNextStudentFactRead: () => { studentFactFailures = 1; },
  };
}
afterEach(() => { cleanup(); sessionStorage.clear(); localStorage.clear(); vi.unstubAllGlobals(); });

it.each([
  { factKey: "student.preferred_countries" as const, value: ["malaysia"] as const },
  { factKey: "family.budget" as const, value: { ...budget, preferred_minor: 32000000, hard_ceiling_minor: 42000000 } },
])("submits the entered $factKey body and saves its intention for same-tab recovery", async (proposal) => {
  const { writes, mutationRoles, sessionEvents } = setup();
  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("revision_requested"));
  if (proposal.factKey === "family.budget") await act(() => result.current.prepareRevisionFact("family.budget"));
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

it("does not prepare a budget proposal from the student-only fact projection", async () => {
  const { writes, sessionEvents } = setup();
  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("revision_requested"));
  expect(result.current.currentFacts?.facts.map((fact) => fact.fact_key)).toEqual(["student.preferred_countries"]);
  await act(() => result.current.submitRevision({ expectedCaseRevision: 1, factKey: "family.budget", value: { ...budget, hard_ceiling_minor: 39000000 } }));
  expect(writes).toEqual([]);
  expect(sessionEvents).toEqual([]);
  expect(loadRecoveryMetadata()?.revisionIntent).toBeUndefined();
  expect(loadRecoveryMetadata()?.mutations).toEqual({});
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

it("recovers budget editor preparation after bootstrap loss without inventing a submitted intention", async () => {
  const { writes, mutationRoles, sessionEvents } = setup(503, 1);
  const { result, unmount } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("revision_requested"));
  await act(() => result.current.prepareRevisionFact("family.budget"));
  expect(writes).toHaveLength(0);
  expect(loadRecoveryMetadata()).toMatchObject({ role: "student", pendingRole: "parent", mutations: {} });
  expect(loadRecoveryMetadata()?.revisionIntent).toBeUndefined();
  unmount();
  const restored = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(restored.result.current.state.value).toBe("revision_requested"));
  expect(restored.result.current.state).toMatchObject({ status: { active_role: "parent" } });
  expect(restored.result.current.currentFacts?.facts.map((fact) => fact.fact_key)).toEqual(["family.budget"]);
  expect(writes).toHaveLength(0);
  const intent = { expectedCaseRevision: 1, factKey: "family.budget" as const, value: { ...budget, preferred_minor: 32000000 } };
  await act(() => restored.result.current.submitRevision(intent));
  await act(() => restored.result.current.retry());
  expect(writes[0]).toEqual(writes[2]);
  expect(writes[1]).toEqual(writes[3]);
  expect(mutationRoles).toEqual(["parent", "parent", "parent", "parent"]);
  expect(sessionEvents).toContain("mint:parent");
});

it.each([false, true])("requires explicit parent authority before the actual editor can propose budget, shared participant facts=%s", async (sharedParticipantFacts) => {
  const { writes, mutationRoles, sessionEvents } = setup(201, 0, 0, 1, sharedParticipantFacts);
  render(<ConnectedDemo />, { wrapper: PresentationProvider });
  await screen.findByRole("combobox", { name: "要修改的事实" });
  if (!sharedParticipantFacts) {
    expect(screen.queryByRole("option", { name: "家庭预算" })).toBeNull();
    expect(screen.queryByRole("button", { name: "以家长编辑预算" })).toBeNull();
    expect(writes).toEqual([]);
    expect(sessionEvents).toEqual([]);
    return;
  }
  fireEvent.change(screen.getByRole("combobox", { name: "要修改的事实" }), { target: { value: "family.budget" } });
  expect(screen.queryByLabelText("常规预算")).not.toBeInTheDocument();
  expect(writes).toHaveLength(0);
  const handoff = screen.getByRole("button", { name: "以家长编辑预算" });
  expect(handoff).toBeEnabled();
  fireEvent.click(handoff);
  await waitFor(() => expect(screen.getByLabelText("常规预算")).toHaveValue("300000"));
  expect(screen.getByLabelText("最高预算")).toHaveValue("400000");
  expect(sessionEvents).toEqual(["revoke", "bootstrap", "mint:parent"]);
  expect(writes).toHaveLength(0);
  expect(loadRecoveryMetadata()?.mutations).toEqual({});
  fireEvent.change(screen.getByLabelText("最高预算"), { target: { value: "390000" } });
  fireEvent.click(screen.getByRole("button", { name: "以家长提交预算提案" }));
  await waitFor(() => expect(writes).toHaveLength(2));
  expect(writes[1].body).toEqual({ schema_version: 1, case_revision: 1, proposal: { schema_version: 1, fact_key: "family.budget", value: { ...budget, hard_ceiling_minor: 39000000 } } });
  expect(mutationRoles).toEqual(["parent", "parent"]);
});

it.each(["retry", "reload"] as const)("persists minted parent authority before a fact-load failure and recovers on %s", async (recovery) => {
  const { writes, identityFailures, sessionEvents } = setup(201, 0, 1, 1, true);
  const mounted = render(<ConnectedDemo />, { wrapper: PresentationProvider });
  await screen.findByRole("combobox", { name: "要修改的事实" });
  fireEvent.change(screen.getByRole("combobox", { name: "要修改的事实" }), { target: { value: "family.budget" } });
  fireEvent.click(screen.getByRole("button", { name: "以家长编辑预算" }));
  const retry = await screen.findByRole("button", { name: "重新连接顾问流程" });
  expect(screen.queryByLabelText("常规预算")).not.toBeInTheDocument();
  expect(writes).toHaveLength(0);
  const minted = loadRecoveryMetadata();
  if (recovery === "reload") {
    mounted.unmount();
    render(<ConnectedDemo />, { wrapper: PresentationProvider });
  } else fireEvent.click(retry);
  await waitFor(() => expect(screen.getByLabelText("常规预算")).toHaveValue("300000"));
  expect(minted).toMatchObject({ role: "parent", csrf: "parent-csrf-1", mutations: {} });
  expect(minted?.pendingRole).toBeUndefined();
  expect(screen.getByLabelText("最高预算")).toHaveValue("400000");
  expect(writes).toHaveLength(0);
  expect(identityFailures).toEqual([]);
  expect(sessionEvents).toEqual(["revoke", "bootstrap", "mint:parent"]);
  expect(loadRecoveryMetadata()?.revisionIntent).toBeUndefined();
});

it.each(["retry", "reload"] as const)("persists minted student authority before a fact-load failure and recovers on %s", async (recovery) => {
  const { writes, identityFailures, sessionEvents, failNextStudentFactRead } = setup(201, 0, 0, 1, true);
  const mounted = render(<ConnectedDemo />, { wrapper: PresentationProvider });
  await screen.findByRole("combobox", { name: "要修改的事实" });
  fireEvent.change(screen.getByRole("combobox", { name: "要修改的事实" }), { target: { value: "family.budget" } });
  fireEvent.click(screen.getByRole("button", { name: "以家长编辑预算" }));
  await screen.findByLabelText("常规预算");
  failNextStudentFactRead();
  fireEvent.change(screen.getByRole("combobox", { name: "要修改的事实" }), { target: { value: "student.preferred_countries" } });
  fireEvent.click(screen.getByRole("button", { name: "以学生编辑意向国家" }));
  const retry = await screen.findByRole("button", { name: "重新连接顾问流程" });
  expect(screen.queryByRole("checkbox", { name: "日本" })).not.toBeInTheDocument();
  const minted = loadRecoveryMetadata();
  if (recovery === "reload") {
    mounted.unmount();
    render(<ConnectedDemo />, { wrapper: PresentationProvider });
  } else fireEvent.click(retry);
  await waitFor(() => expect(screen.getByRole("checkbox", { name: "日本" })).toBeChecked());
  expect(minted).toMatchObject({ role: "student", csrf: "student-csrf-2", mutations: {} });
  expect(minted?.pendingRole).toBeUndefined();
  expect(screen.getByRole("checkbox", { name: "马来西亚" })).toBeChecked();
  expect(writes).toEqual([]);
  expect(identityFailures).toEqual([]);
  expect(sessionEvents).toEqual(["revoke", "bootstrap", "mint:parent", "revoke", "bootstrap", "mint:student"]);
});

it.each(["student.preferred_countries", "family.budget"] as const)("opens the opposite fact after an ambiguous submitted %s without discarding its replay data", async (submittedFact) => {
  const { writes, mutationRoles, failNextStudentFactRead, identityFailures } = setup(503, 0, submittedFact === "student.preferred_countries" ? 1 : 0, 1, true);
  const mounted = render(<ConnectedDemo />, { wrapper: PresentationProvider });
  await screen.findByRole("combobox", { name: "要修改的事实" });
  if (submittedFact === "family.budget") {
    fireEvent.change(screen.getByRole("combobox", { name: "要修改的事实" }), { target: { value: submittedFact } });
    fireEvent.click(screen.getByRole("button", { name: "以家长编辑预算" }));
    await screen.findByLabelText("最高预算");
    fireEvent.change(screen.getByLabelText("最高预算"), { target: { value: "390000" } });
    fireEvent.click(screen.getByRole("button", { name: "以家长提交预算提案" }));
  } else {
    fireEvent.click(screen.getByRole("checkbox", { name: "澳大利亚" }));
    fireEvent.click(screen.getByRole("button", { name: "提交变更提案" }));
  }
  await screen.findByRole("button", { name: "重新连接顾问流程" });
  const submitted = loadRecoveryMetadata();
  expect(submitted?.revisionIntent?.factKey).toBe(submittedFact);
  expect(writes).toHaveLength(2);
  mounted.unmount();
  render(<ConnectedDemo />, { wrapper: PresentationProvider });
  await screen.findByRole("combobox", { name: "要修改的事实" });
  const targetFact = submittedFact === "family.budget" ? "student.preferred_countries" : "family.budget";
  if (targetFact === "student.preferred_countries") failNextStudentFactRead();
  fireEvent.change(screen.getByRole("combobox", { name: "要修改的事实" }), { target: { value: targetFact } });
  fireEvent.click(screen.getByRole("button", { name: targetFact === "family.budget" ? "以家长编辑预算" : "以学生编辑意向国家" }));
  const retry = await screen.findByRole("button", { name: "重新连接顾问流程" });
  expect(loadRecoveryMetadata()?.role).toBe(targetFact === "family.budget" ? "parent" : "student");
  expect(loadRecoveryMetadata()?.pendingRole).toBeUndefined();
  expect(loadRecoveryMetadata()?.revisionIntent).toEqual(submitted?.revisionIntent);
  expect(loadRecoveryMetadata()?.mutations).toEqual(submitted?.mutations);
  fireEvent.click(retry);
  if (targetFact === "family.budget") await waitFor(() => expect(screen.getByLabelText("常规预算")).toHaveValue("300000"));
  else await waitFor(() => expect(screen.getByRole("checkbox", { name: "日本" })).toBeChecked());
  expect(screen.getByRole("combobox", { name: "要修改的事实" })).toHaveValue(targetFact);
  expect(loadRecoveryMetadata()?.revisionIntent).toEqual(submitted?.revisionIntent);
  expect(loadRecoveryMetadata()?.mutations).toEqual(submitted?.mutations);
  expect(writes).toHaveLength(2);
  expect(mutationRoles).toEqual(submittedFact === "family.budget" ? ["parent", "parent"] : ["student", "student"]);
  expect(identityFailures).toEqual([]);
  fireEvent.change(screen.getByRole("combobox", { name: "要修改的事实" }), { target: { value: submittedFact } });
  fireEvent.click(screen.getByRole("button", { name: submittedFact === "family.budget" ? "以家长编辑预算" : "以学生编辑意向国家" }));
  if (submittedFact === "family.budget") await waitFor(() => expect(screen.getByLabelText("最高预算")).toHaveValue("390000"));
  else await waitFor(() => expect(screen.getByRole("checkbox", { name: "澳大利亚" })).toBeChecked());
  fireEvent.click(screen.getByRole("button", { name: submittedFact === "family.budget" ? "以家长提交预算提案" : "提交变更提案" }));
  await waitFor(() => expect(writes).toHaveLength(4));
  expect(writes[0]).toEqual(writes[2]);
  expect(writes[1]).toEqual(writes[3]);
  expect(mutationRoles).toEqual(Array(4).fill(submittedFact === "family.budget" ? "parent" : "student"));
});

it("adopts a changed revision after parent preparation and rejects the old revision without a proposal", async () => {
  const { writes } = setup(201, 0, 0, 2);
  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("revision_requested"));
  await act(() => result.current.prepareRevisionFact("family.budget"));
  expect(result.current.currentFacts?.caseRevision).toBe(2);
  expect(loadRecoveryMetadata()).toMatchObject({ role: "parent", currentRevision: 2, mutations: {} });
  await act(() => result.current.submitRevision({ expectedCaseRevision: 1, factKey: "family.budget", value: { ...budget, hard_ceiling_minor: 39000000 } }));
  expect(writes).toHaveLength(0);
  expect(loadRecoveryMetadata()?.revisionIntent).toBeUndefined();
});

it("reloads a revision that changed before handoff without minting a parent or saving a proposal", async () => {
  const { writes, sessionEvents, advanceRevision } = setup();
  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("revision_requested"));
  advanceRevision();
  await act(() => result.current.prepareRevisionFact("family.budget"));
  expect(result.current.currentFacts?.caseRevision).toBe(2);
  expect(result.current.currentFacts?.facts.map((fact) => fact.fact_key)).toEqual(["student.preferred_countries"]);
  expect(sessionEvents).toEqual([]);
  expect(writes).toEqual([]);
  expect(loadRecoveryMetadata()).toMatchObject({ role: "student", currentRevision: 2, mutations: {} });
  expect(loadRecoveryMetadata()?.pendingRole).toBeUndefined();
  expect(loadRecoveryMetadata()?.revisionIntent).toBeUndefined();
});

it("hands back to student authority before editing countries from the parent budget editor", async () => {
  const { writes, mutationRoles, sessionEvents } = setup(201, 0, 0, 1, true);
  render(<ConnectedDemo />, { wrapper: PresentationProvider });
  await screen.findByRole("combobox", { name: "要修改的事实" });
  fireEvent.change(screen.getByRole("combobox", { name: "要修改的事实" }), { target: { value: "family.budget" } });
  fireEvent.click(screen.getByRole("button", { name: "以家长编辑预算" }));
  await screen.findByLabelText("常规预算");
  fireEvent.change(screen.getByRole("combobox", { name: "要修改的事实" }), { target: { value: "student.preferred_countries" } });
  expect(screen.queryByRole("checkbox", { name: "澳大利亚" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "以学生编辑意向国家" }));
  const australia = await screen.findByRole("checkbox", { name: "澳大利亚" });
  expect(screen.getByRole("checkbox", { name: "日本" })).toBeChecked();
  expect(screen.getByRole("checkbox", { name: "马来西亚" })).toBeChecked();
  expect(screen.queryByLabelText("常规预算")).not.toBeInTheDocument();
  expect(writes).toEqual([]);
  fireEvent.click(australia);
  fireEvent.click(screen.getByRole("button", { name: "提交变更提案" }));
  await waitFor(() => expect(writes).toHaveLength(2));
  expect(writes[1].body).toEqual({ schema_version: 1, case_revision: 1, proposal: { schema_version: 1, fact_key: "student.preferred_countries", value: ["australia", "japan", "malaysia"] } });
  expect(mutationRoles).toEqual(["student", "student"]);
  expect(sessionEvents).toEqual(["revoke", "bootstrap", "mint:parent", "revoke", "bootstrap", "mint:student"]);
});
