import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { loadRecoveryMetadata, saveRecoveryMetadata } from "../../lib/connected-demo/session-storage";
import { useConnectedDemo } from "../../lib/connected-demo/use-connected-demo";
import { CASE_ID, BRIEF_ID, TASK_ID, brief, ledger } from "./connected-demo-test-data";

const advisorMetadata = () => ({ role: "advisor" as const, csrf: "csrf", caseId: CASE_ID, taskId: null, briefId: null, cursor: 0, mutations: {} });
const parentMetadata = () => ({ role: "parent" as const, csrf: "csrf", caseId: CASE_ID, taskId: null, briefId: BRIEF_ID, cursor: 0, mutations: {} });

afterEach(() => { sessionStorage.clear(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it("validates canonical role-specific recovery metadata", () => {
  expect(loadRecoveryMetadata()).toBeNull();
  sessionStorage.setItem("night-voyager:m5", JSON.stringify({ ...parentMetadata(), taskId: TASK_ID }));
  expect(loadRecoveryMetadata()).toBeNull();
  sessionStorage.setItem("night-voyager:m5", JSON.stringify({ ...advisorMetadata(), briefId: BRIEF_ID }));
  expect(loadRecoveryMetadata()).toBeNull();
  sessionStorage.setItem("night-voyager:m5", JSON.stringify({ ...advisorMetadata(), caseId: "not-a-uuid" }));
  expect(loadRecoveryMetadata()).toBeNull();
});

it("stores only same-tab display and mutation recovery metadata", () => {
  saveRecoveryMetadata(advisorMetadata());
  expect(loadRecoveryMetadata()?.role).toBe("advisor");
  expect(localStorage.length).toBe(0);
});

it("rejects advisor authority paired with forged parent metadata", async () => {
  saveRecoveryMetadata(parentMetadata());
  const fetchMock = vi.fn(async () => Response.json(ledger("plan-ready")));
  vi.stubGlobal("fetch", fetchMock);
  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("recoverable_error"));
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(result.current.state).toMatchObject({ code: "transport_failure" });
});

it("retains metadata on 503 for explicit retry", async () => {
  saveRecoveryMetadata(advisorMetadata());
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({ code: "bff_upstream_unavailable" }, { status: 503 })));
  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("recoverable_error"));
  expect(loadRecoveryMetadata()).not.toBeNull();
  expect(result.current.state).toMatchObject({ code: "transport_failure" });
});

it("clears metadata only on confirmed 401 and permits explicit fresh bootstrap", async () => {
  saveRecoveryMetadata(advisorMetadata());
  let expired = true;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (expired && path.endsWith("/advisor-ledger")) { expired = false; return Response.json({ detail: "authentication failed" }, { status: 401, headers: { "Set-Cookie": "night_voyager_session=; Max-Age=0; Path=/" } }); }
    if (path.endsWith("/session-bootstrap")) return Response.json({ csrf_token: "bootstrap" });
    if (path.endsWith("/sessions") && init?.method === "POST") return Response.json({ role: "advisor", proof_mode: "synthetic-demo", csrf_token: "new-csrf" }, { status: 201 });
    return Response.json(ledger("task-ready"));
  });
  vi.stubGlobal("fetch", fetchMock);
  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state).toMatchObject({ value: "recoverable_error", code: "session_expired" }));
  expect(loadRecoveryMetadata()).toBeNull();
  await act(async () => { await result.current.retry(); });
  await waitFor(() => expect(result.current.state.value).toBe("advisor_ready"));
  expect(loadRecoveryMetadata()?.csrf).toBe("new-csrf");
});

it("never replays a mutation after confirmed 401 and reconnects through fresh bootstrap", async () => {
  saveRecoveryMetadata(advisorMetadata());
  let taskCreates = 0;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path.endsWith("/agent-tasks")) {
      taskCreates += 1;
      return Response.json({ detail: "authentication failed" }, { status: 401 });
    }
    if (path.endsWith("/session-bootstrap")) return Response.json({ csrf_token: "bootstrap" });
    if (path.endsWith("/sessions") && init?.method === "POST") return Response.json({ role: "advisor", proof_mode: "synthetic-demo", csrf_token: "fresh-csrf" }, { status: 201 });
    return Response.json(ledger("task-ready"));
  });
  vi.stubGlobal("fetch", fetchMock);
  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("advisor_ready"));
  await act(async () => { await result.current.createTask(); });
  expect(result.current.state).toMatchObject({ value: "recoverable_error", code: "session_expired" });
  expect(loadRecoveryMetadata()).toBeNull();
  await act(async () => { await result.current.retry(); });
  await waitFor(() => expect(result.current.state.value).toBe("advisor_ready"));
  expect(taskCreates).toBe(1);
  expect(loadRecoveryMetadata()?.csrf).toBe("fresh-csrf");
});

it("reuses the request-bound idempotency key after a lost mutation response", async () => {
  saveRecoveryMetadata(advisorMetadata());
  const keys: string[] = [];
  let createAttempts = 0;
  class FakeEventSource { addEventListener() {} close() {} }
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path.endsWith("/advisor-ledger")) return Response.json(ledger("task-ready"));
    if (path.endsWith("/agent-tasks")) {
      keys.push(new Headers(init?.headers).get("Idempotency-Key") ?? "");
      createAttempts += 1;
      if (createAttempts === 1) return Response.json({ code: "bff_upstream_unavailable" }, { status: 503 });
      return Response.json({ schema_version: 1, task_id: TASK_ID, row_version: 1, status: "preparing", public_code: null, attempt_count: 0, planning_run_id: null, created_at: "2026-07-14T00:00:00Z", updated_at: "2026-07-14T00:00:00Z", replayed: true }, { status: 202 });
    }
    throw new Error(`unexpected ${path}`);
  }));
  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("advisor_ready"));
  await act(async () => { await result.current.createTask(); });
  expect(result.current.state.value).toBe("recoverable_error");
  await act(async () => { await result.current.retry(); });
  await waitFor(() => expect(result.current.state.value).toBe("task_streaming"));
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
  expect(loadRecoveryMetadata()?.mutations["create-task"]?.idempotencyKey).toBe(keys[0]);
});

it("keeps one EventSource and coalesces out-of-order refreshes with a monotonic cursor", async () => {
  saveRecoveryMetadata({ ...advisorMetadata(), taskId: TASK_ID, cursor: 4 });
  const listeners = new Map<string, (event: Event) => void>();
  const sources: Array<{ url: string; closed: boolean }> = [];
  class FakeEventSource {
    closed = false;
    constructor(public readonly url: string) { sources.push(this); }
    addEventListener(code: string, listener: (event: Event) => void) { listeners.set(code, listener); }
    close() { this.closed = true; }
  }
  vi.stubGlobal("EventSource", FakeEventSource);
  let resolveFirst: ((value: Response) => void) | undefined;
  let resolveSecond: ((value: Response) => void) | undefined;
  let calls = 0;
  vi.stubGlobal("fetch", vi.fn(async () => {
    calls += 1;
    if (calls === 1) return Response.json(ledger("active-task"));
    return await new Promise<Response>((resolve) => { if (calls === 2) resolveFirst = resolve; else resolveSecond = resolve; });
  }));
  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("task_streaming"));
  expect(sources).toHaveLength(1);
  expect(sources[0].url).toContain(`/${TASK_ID}/events?after=4`);
  act(() => {
    listeners.get("heartbeat_recorded")?.({ lastEventId: "9" } as MessageEvent);
    listeners.get("heartbeat_recorded")?.({ lastEventId: "6" } as MessageEvent);
  });
  expect(calls).toBe(2);
  await act(async () => { resolveFirst?.(Response.json(ledger("active-task"))); });
  await waitFor(() => expect(calls).toBe(3));
  await act(async () => { resolveSecond?.(Response.json(ledger("review-required"))); });
  await waitFor(() => expect(result.current.state.value).toBe("advisor_review"));
  expect(loadRecoveryMetadata()?.cursor).toBe(9);
  expect(sources).toHaveLength(1);
});

it("refreshes a real stale decision conflict and requires renewed confirmation", async () => {
  saveRecoveryMetadata(parentMetadata());
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path.endsWith("/advisor-ledger")) return Response.json({ code: "resource_unavailable" }, { status: 404 });
    if (path.includes("/family-decisions") && init?.method === "POST") return Response.json({ code: "stale_case_revision" }, { status: 409 });
    return Response.json(brief("family-review"));
  }));
  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("family_review"));
  act(() => result.current.setConfirmed(true));
  await waitFor(() => expect(result.current.confirmed).toBe(true));
  await act(async () => { await result.current.decide(); });
  await waitFor(() => expect(result.current.state.value).toBe("family_review"));
  expect(result.current.confirmed).toBe(false);
  expect(loadRecoveryMetadata()?.mutations["family-decision"]).toBeUndefined();
});
