import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { parseConnectedDemoScenario } from "../../lib/connected-demo/scenario";
import { useConnectedDemo } from "../../lib/connected-demo/use-connected-demo";
import { loadRecoveryMetadata, saveRecoveryMetadata } from "../../lib/connected-demo/session-storage";
import { CASE_ID, ledger, status } from "./connected-demo-test-data";

const INTAKE_CASE = "49000000-0000-0000-0000-000000000003";
afterEach(() => { cleanup(); sessionStorage.clear(); vi.unstubAllGlobals(); });
function existing(caseId = CASE_ID) {
  saveRecoveryMetadata({ schema_version: 3, journey: "advisor-family", role: "advisor", csrf: "csrf", caseId, currentRevision: 1, currentTaskId: null, predecessorRunId: null, currentRunId: null, cursor: 0, phase: "task_ready", mutations: {} });
}
function fetcher() {
  const calls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input); calls.push(path);
    if (path.endsWith("session-bootstrap")) return Response.json({ csrf_token: "bootstrap" });
    if (path.endsWith("sessions")) return Response.json({ role: "advisor", proof_mode: "synthetic-demo", csrf_token: "csrf" });
    const caseId = path.match(/cases\/([^/]+)/)?.[1] ?? CASE_ID;
    if (path.endsWith("journey-status")) return Response.json(status("task_ready", caseId));
    if (path.endsWith("advisor-ledger")) {
      const value = ledger("task_ready");
      return Response.json({ ...value, case_id: caseId, canonical_task_inputs: { ...value.canonical_task_inputs, case_id: caseId } });
    }
    if (path.endsWith("confirmed-facts")) return Response.json({ schema_version: 1, current: [], history: [], next_cursor: null });
    return Response.json({}, { status: 404 });
  }));
  return calls;
}

it("starts the fixed intake Case only after an explicit fresh action", async () => {
  const calls = fetcher();
  const { result } = renderHook(() => useConnectedDemo("intake-delay" as never));
  expect(calls).toEqual([]);
  await act(() => result.current.connectAdvisor());
  expect(calls).toContain(`/api/demo/cases/${INTAKE_CASE}/advisor-ledger`);
  expect(loadRecoveryMetadata()?.caseId).toBe(INTAKE_CASE);
});

it("does not overwrite or fetch an active different-Case journey from the intake URL", async () => {
  existing();
  const before = loadRecoveryMetadata();
  const calls = fetcher();
  const { result } = renderHook(() => useConnectedDemo("intake-delay" as never));
  await act(async () => { await Promise.resolve(); });
  expect(result.current.journeyConflict).toBe("advisor-family");
  await act(() => result.current.connectAdvisor());
  expect(calls).toEqual([]);
  expect(loadRecoveryMetadata()).toEqual(before);
});

it("keeps bare demo recovery bound to an existing intake journey", async () => {
  existing(INTAKE_CASE);
  const calls = fetcher();
  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("advisor_ready"));
  expect(calls).toContain(`/api/demo/cases/${INTAKE_CASE}/advisor-ledger`);
  expect(calls.some(path => path.includes(`/cases/${CASE_ID}/`))).toBe(false);
});


it.each(["default", "unknown", "", ["intake-delay"], ["intake-delay", "intake-delay"]])("rejects a non-exact controlled scenario %j", (value) => {
  expect(() => parseConnectedDemoScenario(value)).toThrow("invalid demo scenario");
});
it("keeps missing scenario on the original default", () => {
  expect(parseConnectedDemoScenario(undefined)).toBe("default");
  expect(parseConnectedDemoScenario("intake-delay")).toBe("intake-delay");
});
