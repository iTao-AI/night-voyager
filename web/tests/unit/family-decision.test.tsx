import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { FamilyDecisionAction } from "../../components/connected-demo/FamilyDecisionBrief";
import { DecisionReceiptTimeline } from "../../components/connected-demo/DecisionReceiptTimeline";
import { PresentationProvider } from "../../lib/presentation/context";
import * as family from "../../lib/connected-demo/family-decision";
import { loadRecoveryMetadata, saveRecoveryMetadata } from "../../lib/connected-demo/session-storage";
import { useConnectedDemo } from "../../lib/connected-demo/use-connected-demo";
import { CASE_ID, BRIEF_ID, ROUTE_ID, brief, status } from "./connected-demo-test-data";

const choice = { minimumYuan: "300000", maximumYuan: "350000", acknowledgedTradeOffs: ["budget_elasticity"] as ["budget_elasticity"] };
const body = { schema_version: 1, expected_brief_version: 1, selected_route_id: ROUTE_ID, accepted_budget_min_minor: 30_000_000, accepted_budget_max_minor: 35_000_000, currency: "CNY", accepted_trade_offs: ["budget_elasticity"] };
afterEach(() => { cleanup(); sessionStorage.clear(); localStorage.clear(); vi.unstubAllGlobals(); });

it("sends the entered interval and only explicit required acknowledgments", () => {
  expect(family.validateFamilyDecisionDraft(choice, brief())).toEqual({ ok: true, body });
  expect(family.suggestFamilyDecisionDraft(brief())).toEqual({ minimumYuan: "305500", maximumYuan: "400000", acknowledgedTradeOffs: [] });
});
it.each([
  { minimumYuan: "0" }, { minimumYuan: "" }, { minimumYuan: "-1" }, { minimumYuan: "1.2" }, { minimumYuan: "1e5" },
  { maximumYuan: "90071992547410" }, { minimumYuan: "350000", maximumYuan: "300000" },
  { minimumYuan: "310000" }, { maximumYuan: "300000" }, { maximumYuan: "400001" }, { acknowledgedTradeOffs: [] },
])("rejects unsafe, invalid or unacknowledged choice %j", (invalid) => {
  expect(family.validateFamilyDecisionDraft({ ...choice, ...invalid }, brief()).ok).toBe(false);
});
it("keeps trade-off acknowledgment separate from final parent consent", () => {
  const submit = vi.fn();
  function Form() {
    const [draft, setDraft] = useState(family.suggestFamilyDecisionDraft(brief()));
    const [confirmed, setConfirmed] = useState(false);
    return <FamilyDecisionAction brief={brief()} draft={draft} onDraftChange={setDraft} confirmed={confirmed} onConfirm={setConfirmed} onSubmit={submit} />;
  }
  render(<PresentationProvider><Form /></PresentationProvider>);
  expect(screen.getAllByRole("checkbox")).toHaveLength(2);
  screen.getAllByRole("checkbox").forEach((checkbox) => expect(checkbox).not.toBeChecked());
  const button = screen.getByRole("button", { name: "继续家庭决定" });
  fireEvent.click(screen.getByLabelText("我以家长身份确认当前路线、预算区间和已勾选取舍。"));
  expect(button).toBeDisabled();
  fireEvent.click(screen.getByLabelText("我接受：预算弹性"));
  expect(button).toBeEnabled();
  fireEvent.change(screen.getByLabelText("接受预算上限（元）"), { target: { value: "400001" } });
  expect(button).toBeDisabled();
});

function parent() {
  saveRecoveryMetadata({ schema_version: 3, journey: "advisor-family", role: "parent", csrf: "parent-csrf", caseId: CASE_ID, currentRevision: 1, currentTaskId: null, predecessorRunId: null, currentRunId: null, cursor: 0, phase: "family_review", mutations: {} });
}
function transport(options: { ambiguous?: boolean; stale?: boolean } = {}) {
  let currentBrief = brief();
  const requests: Array<{ path: string; body: unknown; key: string; csrf: string }> = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path.endsWith("/journey-status")) return Response.json(status(currentBrief.phase));
    if (path.endsWith("/current-decision-brief")) return Response.json(currentBrief);
    if (path.endsWith("/family-decisions")) {
      const submitted = JSON.parse(String(init?.body));
      requests.push({ path, body: submitted, key: new Headers(init?.headers).get("Idempotency-Key") ?? "", csrf: new Headers(init?.headers).get("X-CSRF-Token") ?? "" });
      if (options.stale) { currentBrief = { ...brief(), brief_version: 2 }; return Response.json({ code: "stale_brief" }, { status: 409 }); }
      if (options.ambiguous) return Response.json({ code: "upstream_unavailable" }, { status: 503 });
      currentBrief = brief("plan_ready");
      currentBrief.receipt = { ...currentBrief.receipt!, accepted_budget_min_minor: submitted.accepted_budget_min_minor, accepted_budget_max_minor: submitted.accepted_budget_max_minor, accepted_trade_offs: submitted.accepted_trade_offs };
      return Response.json({});
    }
    throw new Error(`unexpected ${path}`);
  }));
  return { requests, update: (next = brief()) => { currentBrief = next; } };
}
async function selected(result: { current: ReturnType<typeof useConnectedDemo> }) {
  await waitFor(() => expect(result.current.state.value).toBe("family_review"));
  await act(async () => { result.current.setFamilyDraft(choice); result.current.setConfirmed(true); });
}
it("binds actual choices to parent/current brief and renders immutable receipt values", async () => {
  parent(); const server = transport();
  const { result } = renderHook(() => useConnectedDemo()); await selected(result);
  await act(async () => result.current.decide());
  expect(server.requests[0]).toMatchObject({ path: `/api/demo/decision-briefs/${BRIEF_ID}/family-decisions`, body, csrf: "parent-csrf" });
  expect(server.requests[0].key).toMatch(/^[0-9a-f-]{36}$/);
  expect(result.current.state.value).toBe("plan_ready");
  if (result.current.state.value !== "plan_ready") throw new Error("receipt missing");
  render(<PresentationProvider><DecisionReceiptTimeline brief={result.current.state.brief} /></PresentationProvider>);
  expect(screen.getByText("¥300,000–350,000")).toBeVisible();
});
it("replays an ambiguous submission exactly, including after reload with explicit consent", async () => {
  parent(); const server = transport({ ambiguous: true });
  const first = renderHook(() => useConnectedDemo()); await selected(first.result);
  await act(async () => first.result.current.decide());
  await act(async () => first.result.current.retry());
  expect(server.requests[1]).toEqual(server.requests[0]);
  first.unmount();
  const restored = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(restored.result.current.state.value).toBe("family_review"));
  expect(restored.result.current.familyDraft).toEqual(choice);
  expect(restored.result.current.confirmed).toBe(false);
  await act(async () => restored.result.current.decide());
  expect(server.requests).toHaveLength(2);
  await act(async () => restored.result.current.setConfirmed(true));
  await act(async () => restored.result.current.decide());
  expect(server.requests[2]).toEqual(server.requests[0]);
});
it("makes edited choices a new intention and resets all acceptance on a new brief identity/version", async () => {
  parent(); const server = transport({ ambiguous: true });
  const { result } = renderHook(() => useConnectedDemo()); await selected(result);
  await act(async () => result.current.decide());
  await act(async () => result.current.recover());
  await act(async () => { result.current.setFamilyDraft({ ...choice, maximumYuan: "360000" }); result.current.setConfirmed(true); });
  await act(async () => result.current.decide());
  expect(server.requests[1].key).not.toBe(server.requests[0].key);
  expect(server.requests[1].body).toMatchObject({ accepted_budget_max_minor: 36_000_000 });
  server.update({ ...brief(), brief_id: "81000000-0000-0000-0000-000000000302" });
  await act(async () => result.current.recover());
  expect(result.current.familyDraft).toEqual({ minimumYuan: "305500", maximumYuan: "400000", acknowledgedTradeOffs: [] });
  expect(result.current.confirmed).toBe(false);
  expect(loadRecoveryMetadata()).not.toHaveProperty("familyIntent");
});
it("reloads authority and clears stale choices after an old-version conflict", async () => {
  parent(); const server = transport({ stale: true });
  const { result } = renderHook(() => useConnectedDemo()); await selected(result);
  await act(async () => result.current.decide());
  expect(result.current.state).toMatchObject({ value: "family_review", brief: { brief_version: 2 } });
  expect(result.current.familyDraft.acknowledgedTradeOffs).toEqual([]);
  expect(result.current.confirmed).toBe(false);
  expect(loadRecoveryMetadata()).not.toHaveProperty("familyIntent");
  expect(server.requests).toHaveLength(1);
});
it("does not replay an old intention after authoritative recovery changes the brief", async () => {
  parent(); const server = transport({ ambiguous: true });
  const { result } = renderHook(() => useConnectedDemo()); await selected(result);
  await act(async () => result.current.decide());
  server.update({ ...brief(), brief_version: 2 });
  await act(async () => result.current.recover());
  await act(async () => result.current.retry());
  expect(server.requests).toHaveLength(1);
  expect(result.current.familyDraft.acknowledgedTradeOffs).toEqual([]);
});
it("never submits a missing trade-off, invalid range or wrong-role metadata", async () => {
  parent(); const server = transport();
  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("family_review"));
  for (const draft of [{ ...choice, acknowledgedTradeOffs: [] }, { ...choice, maximumYuan: "400001" }]) {
    await act(async () => { result.current.setFamilyDraft(draft); result.current.setConfirmed(true); });
    await act(async () => result.current.decide());
  }
  await act(async () => { result.current.setFamilyDraft(choice); result.current.setConfirmed(true); });
  saveRecoveryMetadata({ ...loadRecoveryMetadata()!, role: "advisor", phase: "review_required" });
  await act(async () => result.current.decide());
  expect(server.requests).toEqual([]);
});
it("keeps key-only legacy recovery unacknowledged and rejects malformed submitted metadata", async () => {
  parent(); const metadata = loadRecoveryMetadata()!;
  const mutations = { "family-decision": { fingerprint: "a".repeat(64), idempotencyKey: "00000000-0000-4000-8000-000000000001" } };
  saveRecoveryMetadata({ ...metadata, mutations });
  transport(); const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("family_review"));
  expect(result.current.familyDraft.acknowledgedTradeOffs).toEqual([]);
  expect(result.current.confirmed).toBe(false);
  for (const invalid of [
    { ...body, accepted_budget_min_minor: 0 },
    { ...body, accepted_budget_min_minor: 30000001 },
    { ...body, accepted_trade_offs: [] },
    { ...body, currency: "USD" },
    { ...body, unexpected: true },
  ]) {
    sessionStorage.setItem("night-voyager:m5", JSON.stringify({ ...metadata, mutations, familyIntent: { schema_version: 1, briefId: BRIEF_ID, body: invalid } }));
    expect(loadRecoveryMetadata()).toBeNull();
  }
});

it("separates the English receipt milestone label from its unchanged formatted date", async () => {
  localStorage.setItem("night-voyager:presentation-locale:v1", "en");
  render(<PresentationProvider><DecisionReceiptTimeline brief={brief("plan_ready")} /></PresentationProvider>);
  await screen.findByText("Documents");
  expect(screen.getByRole("listitem")).toHaveTextContent("Documents · Sep 1, 2026");
});
