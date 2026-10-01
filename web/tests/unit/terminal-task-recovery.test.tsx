import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { parseLedger } from "../../lib/connected-demo/contracts";
import { createConnectedDemoApi } from "../../lib/connected-demo/api";
import { useConnectedDemo } from "../../lib/connected-demo/use-connected-demo";
import { loadRecoveryMetadata, saveRecoveryMetadata } from "../../lib/connected-demo/session-storage";
import { AdvisorLedgerAction } from "../../components/connected-demo/AdvisorLedger";
import { PresentationProvider } from "../../lib/presentation/context";
import { CASE_ID, TASK_ID, ledger, standaloneTask, status } from "./connected-demo-test-data";

function recoverable() {
  const value = ledger("terminal_task_failure", "failed");
  value.task = { ...value.task!, public_code: "transport_interrupted", planning_run_id: null, row_version: 9 };
  value.recovery = { code: "transport_interrupted", retry_allowed: true, guidance: "Start a fresh task with consent." };
  value.canonical_task_inputs = ledger("task_ready").canonical_task_inputs;
  return value;
}
afterEach(() => { cleanup(); sessionStorage.clear(); localStorage.clear(); vi.unstubAllGlobals(); });

it("requires terminal input authority and matching recoverable failure identity", () => {
  const good = recoverable();
  expect(parseLedger(good)).toEqual(good);
  for (const invalid of [
    { ...good, canonical_task_inputs: null },
    { ...good, case_state: "intake" },
    { ...good, task: { ...good.task!, public_code: "invalid_schema" } },
    { ...good, canonical_task_inputs: { ...good.canonical_task_inputs!, expected_case_revision: 2 } },
    { ...good, recovery: { ...good.recovery!, retry_allowed: false } },
  ]) expect(() => parseLedger(invalid)).toThrow("invalid response");
});

it("sends only expected versions to the source-specific retry endpoint", async () => {
  const calls: RequestInit[] = [];
  vi.stubGlobal("fetch", vi.fn(async (path: string, init: RequestInit) => { expect(path).toBe(`/api/demo/tasks/${TASK_ID}/retry`); calls.push(init); return Response.json(standaloneTask()); }));
  const api = createConnectedDemoApi();
  expect(typeof api.retryTask).toBe("function");
  await api.retryTask(TASK_ID, { schema_version: 1, expected_row_version: 9, expected_case_revision: 1 }, "csrf", "consent-key");
  expect(JSON.parse(String(calls[0].body))).toEqual({ schema_version: 1, expected_row_version: 9, expected_case_revision: 1 });
  expect(new Headers(calls[0].headers).get("Idempotency-Key")).toBe("consent-key");
});

it("requires explicit advisor consent and hides recovery for ineligible failures", () => {
  const run = vi.fn();
  const { unmount, rerender } = render(<PresentationProvider><AdvisorLedgerAction ledger={recoverable()} onPrimaryAction={run} /></PresentationProvider>);
  const button = screen.getByRole("button", { name: "创建新的规划任务" });
  expect(button).toBeDisabled();
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(button);
  expect(run).toHaveBeenCalledOnce();
  const next = recoverable();
  next.task!.task_id = "61000000-0000-0000-0000-000000000002";
  rerender(<PresentationProvider><AdvisorLedgerAction ledger={next} onPrimaryAction={run} /></PresentationProvider>);
  expect(screen.getByRole("button", { name: "创建新的规划任务" })).toBeDisabled();
  expect(screen.getByRole("checkbox")).not.toBeChecked();
  unmount();
  render(<PresentationProvider><AdvisorLedgerAction ledger={ledger("terminal_task_failure", "cancelled")} onPrimaryAction={run} /></PresentationProvider>);
  expect(screen.queryByRole("checkbox")).toBeNull();
});

it("persists one consent body/key across network loss and reload, then adopts authoritative successor", async () => {
  saveRecoveryMetadata({ schema_version: 3, journey: "advisor-family", role: "advisor", csrf: "csrf", caseId: CASE_ID, currentRevision: 1, currentTaskId: TASK_ID, predecessorRunId: null, currentRunId: null, cursor: 0, phase: "terminal_task_failure", mutations: {} });
  let committed = false;
  const successor = "61000000-0000-0000-0000-000000000002";
  const mutations: Array<{ body: string; key: string | null }> = [];
  vi.stubGlobal("EventSource", class { addEventListener() {} close() {} });
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path.endsWith("/retry")) {
      mutations.push({ body: String(init?.body), key: new Headers(init?.headers).get("Idempotency-Key") });
      if (mutations.length === 1) throw new Error("network lost");
      committed = true;
      return Response.json({ ...standaloneTask(true), task_id: successor });
    }
    if (path.endsWith("/journey-status")) return Response.json(status(committed ? "active_task" : "terminal_task_failure"));
    if (path.endsWith("/advisor-ledger")) { const value = committed ? ledger("active_task") : recoverable(); if (committed) value.task!.task_id = successor; return Response.json(value); }
    if (path.endsWith("/confirmed-facts")) return Response.json({ schema_version: 1, current: [], history: [], next_cursor: null });
    return Response.json({ code: "unavailable" }, { status: 404 });
  }));
  const first = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(first.result.current.state.value).toBe("terminal_task_failure"));
  expect(typeof first.result.current.retryTerminalTask).toBe("function");
  await act(() => first.result.current.retryTerminalTask());
  expect(first.result.current.state.value).toBe("recoverable_error");
  expect(loadRecoveryMetadata()?.retryIntent).toEqual({ taskId: TASK_ID, expectedRowVersion: 9, expectedCaseRevision: 1 });
  first.unmount();
  const second = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(second.result.current.state.value).toBe("task_streaming"));
  expect(mutations).toHaveLength(2);
  expect(mutations[1]).toEqual(mutations[0]);
  expect(loadRecoveryMetadata()?.currentTaskId).toBe(successor);
  expect(loadRecoveryMetadata()?.retryIntent).toBeUndefined();
});

it("creates a fresh consent key for a later failed source", async () => {
  const previousKey = "61000000-0000-0000-0000-000000000099";
  saveRecoveryMetadata({ schema_version: 3, journey: "advisor-family", role: "advisor", csrf: "csrf", caseId: CASE_ID, currentRevision: 1, currentTaskId: TASK_ID, predecessorRunId: null, currentRunId: null, cursor: 0, phase: "terminal_task_failure", mutations: { "retry-task": { fingerprint: "a".repeat(64), idempotencyKey: previousKey } } });
  const keys: Array<string | null> = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path.endsWith("/retry")) { keys.push(new Headers(init?.headers).get("Idempotency-Key")); throw new Error("network lost"); }
    if (path.endsWith("/journey-status")) return Response.json(status("terminal_task_failure"));
    if (path.endsWith("/advisor-ledger")) return Response.json(recoverable());
    if (path.endsWith("/confirmed-facts")) return Response.json({ schema_version: 1, current: [], history: [], next_cursor: null });
    return Response.json({ code: "unavailable" }, { status: 404 });
  }));
  const hook = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(hook.result.current.state.value).toBe("terminal_task_failure"));
  await act(() => hook.result.current.retryTerminalTask());
  expect(keys).toHaveLength(1);
  expect(keys[0]).toBeTruthy();
  expect(keys[0]).not.toBe(previousKey);
  expect(loadRecoveryMetadata()?.mutations["retry-task"]?.idempotencyKey).toBe(keys[0]);
});
