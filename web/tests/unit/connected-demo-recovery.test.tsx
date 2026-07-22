import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { continueCollaborationAsAdvisorFamily, loadDemoJourneyEnvelope, loadRecoveryMetadata, saveCollaborationJourney, saveRecoveryMetadata } from "../../lib/connected-demo/session-storage";
import { useConnectedDemo } from "../../lib/connected-demo/use-connected-demo";
import { CASE_ID, BRIEF_ID, TASK_ID, brief, ledger, standaloneTask } from "./connected-demo-test-data";

const advisorMetadata = () => ({ schema_version: 2 as const, journey: "advisor-family" as const, role: "advisor" as const, csrf: "csrf", caseId: CASE_ID, taskId: null, briefId: null, cursor: 0, mutations: {} });
const parentMetadata = () => ({ schema_version: 2 as const, journey: "advisor-family" as const, role: "parent" as const, csrf: "csrf", caseId: CASE_ID, taskId: null, briefId: BRIEF_ID, cursor: 0, mutations: {} });
const inspector = (pinStatus: "not_created" | "matched") => ({
  schema_version: 1,
  case_id: CASE_ID,
  operation: pinStatus === "matched" ? "generate_planning_run_v1" : null,
  active_skill_key: "study-destination-compare",
  active_version: "1.0.0",
  activation_sequence: 1,
  evaluator_id: "night-voyager.deterministic-skill-evaluator",
  evaluator_version: "v1",
  evaluation_dataset_id: "night-voyager.study-destination-compare.eval",
  evaluation_dataset_version: "1.0.0",
  task_request_sha256_prefix: pinStatus === "matched" ? "222222222222" : null,
  version_content_sha256_prefix: "111111111111",
  runtime_binding_sha256_prefix: "abcdef123456",
  adapter_id: pinStatus === "matched" ? "deterministic_planning" : null,
  adapter_version: pinStatus === "matched" ? "m4a-v1" : null,
  pin_status: pinStatus,
});

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

it("preserves a valid collaboration journey instead of bootstrapping over it", async () => {
  saveCollaborationJourney({ schema_version: 2, journey: "collaboration", role: "parent", csrf: "csrf", caseId: "41000000-0000-0000-0000-000000000001", threadId: "42000000-0000-0000-0000-000000000001", messageId: null, candidateId: null, phase: "thread_ready", mutations: {} });
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.journeyConflict).toBe("collaboration"));
  expect(fetchMock).not.toHaveBeenCalled();
  expect(loadDemoJourneyEnvelope()?.journey).toBe("collaboration");
});

it("recognizes the exact converted journey envelope as advisor-family recovery metadata", () => {
  const collaboration = {
    schema_version: 2 as const,
    journey: "collaboration" as const,
    role: "advisor" as const,
    csrf: "continued-csrf",
    caseId: CASE_ID,
    threadId: "42000000-0000-0000-0000-000000000001",
    messageId: "43000000-0000-0000-0000-000000000001",
    candidateId: "44000000-0000-0000-0000-000000000001",
    phase: "replan_required" as const,
    mutations: {},
  };
  saveRecoveryMetadata(continueCollaborationAsAdvisorFamily(collaboration, TASK_ID));
  expect(loadRecoveryMetadata()).toEqual({
    schema_version: 2,
    journey: "advisor-family",
    role: "advisor",
    csrf: "continued-csrf",
    caseId: CASE_ID,
    taskId: TASK_ID,
    briefId: null,
    cursor: 0,
    mutations: {},
  });
});

it("classifies a residual-cookie bootstrap guard as session recovery without minting", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    expect(input).toBe("/api/demo/session-bootstrap");
    return Response.json(
      { code: "bff_session_recovery_required" },
      { status: 409 },
    );
  });
  vi.stubGlobal("fetch", fetchMock);
  const { result } = renderHook(() => useConnectedDemo());

  await act(async () => { await result.current.connectAdvisor(); });

  expect(result.current.state).toMatchObject({
    value: "recoverable_error",
    code: "session_recovery_required",
  });
  expect(fetchMock).toHaveBeenCalledTimes(1);
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
      return Response.json(standaloneTask(true), { status: 202 });
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

it("streams through one EventSource after the exact PR B create response", async () => {
  saveRecoveryMetadata(advisorMetadata());
  const sources: string[] = [];
  class FakeEventSource {
    constructor(public readonly url: string) { sources.push(url); }
    addEventListener() {}
    close() {}
  }
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    if (path.endsWith("/advisor-ledger")) return Response.json(ledger("task-ready"));
    if (path.endsWith("/agent-tasks")) return Response.json(standaloneTask(false), { status: 202 });
    throw new Error(`unexpected ${path}`);
  }));

  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("advisor_ready"));
  await act(async () => { await result.current.createTask(); });
  await waitFor(() => expect(result.current.state.value).toBe("task_streaming"));

  expect(sources).toEqual([`/api/demo/tasks/${TASK_ID}/events?after=0`]);
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

it("commits only the latest inspector request when responses complete out of order", async () => {
  saveRecoveryMetadata(advisorMetadata());
  const inspectors: Array<(response: Response) => void> = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    if (path.endsWith("/advisor-ledger")) return Response.json(ledger("task-ready"));
    if (path.endsWith("/planning-skill-inspector")) return await new Promise<Response>((resolve) => inspectors.push(resolve));
    throw new Error(`unexpected ${path}`);
  }));
  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(inspectors).toHaveLength(1));
  await act(async () => result.current.recover());
  await waitFor(() => expect(inspectors).toHaveLength(2));
  await act(async () => inspectors[1](Response.json(inspector("matched"))));
  await waitFor(() => expect(result.current.inspector?.pin_status).toBe("matched"));
  await act(async () => inspectors[0](Response.json(inspector("not_created"))));
  expect(result.current.inspector?.pin_status).toBe("matched");
});

it("invalidates a committed inspector projection while the post-create projection is pending", async () => {
  saveRecoveryMetadata(advisorMetadata());
  class FakeEventSource { addEventListener() {} close() {} }
  vi.stubGlobal("EventSource", FakeEventSource);
  let inspectorCalls = 0;
  let resolveMatched: ((response: Response) => void) | undefined;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    if (path.endsWith("/advisor-ledger")) return Response.json(ledger("task-ready"));
    if (path.endsWith("/agent-tasks")) return Response.json(standaloneTask(false), { status: 202 });
    if (path.endsWith("/planning-skill-inspector")) {
      inspectorCalls += 1;
      if (inspectorCalls === 1) return Response.json(inspector("not_created"));
      return await new Promise<Response>((resolve) => { resolveMatched = resolve; });
    }
    throw new Error(`unexpected ${path}`);
  }));
  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.inspector?.pin_status).toBe("not_created"));

  await act(async () => result.current.createTask());
  await waitFor(() => expect(result.current.state.value).toBe("task_streaming"));
  await waitFor(() => expect(inspectorCalls).toBe(2));
  expect(result.current.inspector).toBeNull();

  await act(async () => resolveMatched?.(Response.json(inspector("matched"))));
  await waitFor(() => expect(result.current.inspector?.pin_status).toBe("matched"));
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
