import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { continueCollaborationAsAdvisorFamily, loadDemoJourneyEnvelope, loadRecoveryMetadata, saveCollaborationJourney, saveRecoveryMetadata } from "../../lib/connected-demo/session-storage";
import { useConnectedDemo } from "../../lib/connected-demo/use-connected-demo";
import { PresentationProvider, usePresentation } from "../../lib/presentation/context";
import { CASE_ID, BRIEF_ID, CONFIRMED_FACT, CONTINUED_CASE_ID, TASK_ID, brief, ledger, standaloneTask } from "./connected-demo-test-data";

const advisorMetadata = () => ({ schema_version: 2 as const, journey: "advisor-family" as const, role: "advisor" as const, csrf: "csrf", caseId: CASE_ID, taskId: null, briefId: null, cursor: 0, mutations: {} });
const parentMetadata = () => ({ schema_version: 2 as const, journey: "advisor-family" as const, role: "parent" as const, csrf: "csrf", caseId: CASE_ID, taskId: null, briefId: BRIEF_ID, cursor: 0, mutations: {} });
const inspector = (pinStatus: "not_created" | "matched", caseId = CASE_ID) => ({
  schema_version: 1,
  case_id: caseId,
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

afterEach(() => { sessionStorage.clear(); localStorage.clear(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it("keeps business state, calls, idempotency, journey, and EventSource unchanged across a locale switch", async () => {
  saveRecoveryMetadata(advisorMetadata());
  const requests: string[] = [];
  const sources: string[] = [];
  class FakeEventSource {
    constructor(readonly url: string) { sources.push(url); }
    addEventListener() {}
    close() {}
  }
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    requests.push(path);
    if (path.endsWith("/advisor-ledger")) return Response.json(ledger("task-ready"));
    if (path.endsWith("/confirmed-facts")) return Response.json({ schema_version: 1, current: [CONFIRMED_FACT], history: [], next_cursor: null });
    if (path.endsWith("/planning-skill-inspector")) return Response.json(inspector("not_created"));
    if (path.endsWith("/agent-tasks")) return Response.json(standaloneTask(false), { status: 202 });
    throw new Error(`unexpected ${path}`);
  }));

  const { result } = renderHook(() => ({ demo: useConnectedDemo(), presentation: usePresentation() }), { wrapper: PresentationProvider });
  await waitFor(() => expect(result.current.demo.state.value).toBe("advisor_ready"));
  await act(async () => result.current.demo.createTask());
  await waitFor(() => expect(result.current.demo.state.value).toBe("task_streaming"));

  const callsBefore = [...requests];
  const sourcesBefore = [...sources];
  const envelopeBefore = sessionStorage.getItem("night-voyager:m5");
  const stateBefore = JSON.stringify(result.current.demo.state);
  const idempotencyBefore = loadRecoveryMetadata()?.mutations["create-task"];

  act(() => result.current.presentation.setLocale("en"));
  await waitFor(() => expect(result.current.presentation.locale).toBe("en"));

  expect(requests).toEqual(callsBefore);
  expect(sources).toEqual(sourcesBefore);
  expect(sources).toEqual([`/api/demo/tasks/${TASK_ID}/events?after=0`]);
  expect(sessionStorage.getItem("night-voyager:m5")).toBe(envelopeBefore);
  expect(JSON.stringify(result.current.demo.state)).toBe(stateBefore);
  expect(loadRecoveryMetadata()?.mutations["create-task"]).toEqual(idempotencyBefore);
});

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

it("uses the continued non-default Case for authority reads, task creation, and streaming", async () => {
  const continuedLedger = {
    ...ledger("task-ready"),
    case_id: CONTINUED_CASE_ID,
    case_revision: 2,
    case_state: "intake",
    canonical_task_inputs: {
      ...ledger("task-ready").canonical_task_inputs!,
      case_id: CONTINUED_CASE_ID,
      expected_case_revision: 2,
    },
  };
  saveRecoveryMetadata({ ...advisorMetadata(), caseId: CONTINUED_CASE_ID });
  const requests: string[] = [];
  const sources: string[] = [];
  class FakeEventSource {
    constructor(readonly url: string) { sources.push(url); }
    addEventListener() {}
    close() {}
  }
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    requests.push(path);
    if (path.endsWith("/advisor-ledger")) return Response.json(continuedLedger);
    if (path.endsWith("/confirmed-facts")) return Response.json({ schema_version: 1, current: [CONFIRMED_FACT], history: [], next_cursor: null });
    if (path.endsWith("/planning-skill-inspector")) return Response.json(inspector("not_created", CONTINUED_CASE_ID));
    if (path.endsWith("/agent-tasks")) return Response.json(standaloneTask(false), { status: 202 });
    throw new Error(`unexpected ${path}`);
  }));

  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("advisor_ready"));
  await waitFor(() => expect(result.current.currentFacts).toMatchObject({ caseId: CONTINUED_CASE_ID, caseRevision: 2 }));
  expect(result.current.currentFacts?.facts).toEqual([CONFIRMED_FACT]);
  await act(async () => result.current.createTask());
  await waitFor(() => expect(result.current.state.value).toBe("task_streaming"));

  expect(requests).toContain(`/api/demo/cases/${CONTINUED_CASE_ID}/advisor-ledger`);
  expect(requests).toContain(`/api/demo/cases/${CONTINUED_CASE_ID}/confirmed-facts`);
  expect(requests).toContain(`/api/demo/cases/${CONTINUED_CASE_ID}/planning-skill-inspector`);
  expect(requests).toContain(`/api/demo/cases/${CONTINUED_CASE_ID}/agent-tasks`);
  expect(requests.every((path) => !path.includes(CASE_ID))).toBe(true);
  expect(sources).toEqual([`/api/demo/tasks/${TASK_ID}/events?after=0`]);
  expect(loadRecoveryMetadata()).toMatchObject({ caseId: CONTINUED_CASE_ID, taskId: TASK_ID });
});

it.each([
  ["active-task", "task_streaming"],
  ["review-required", "advisor_review"],
  ["terminal-task-failure", "terminal_task_failure"],
] as const)("recovers the continued Case in %s without substituting the standalone seed", async (phase, expectedState) => {
  const projected = {
    ...ledger(phase, phase === "terminal-task-failure" ? "failed" : "preparing"),
    case_id: CONTINUED_CASE_ID,
    case_revision: 2,
  };
  saveRecoveryMetadata({ ...advisorMetadata(), caseId: CONTINUED_CASE_ID, taskId: TASK_ID, cursor: phase === "active-task" ? 7 : 0 });
  const requests: string[] = [];
  class FakeEventSource { addEventListener() {} close() {} }
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    requests.push(path);
    if (path.endsWith("/advisor-ledger")) return Response.json(projected);
    if (path.endsWith("/confirmed-facts")) return Response.json({ schema_version: 1, current: [CONFIRMED_FACT], history: [], next_cursor: null });
    if (path.endsWith("/planning-skill-inspector")) return Response.json(inspector("matched", CONTINUED_CASE_ID));
    throw new Error(`unexpected ${path}`);
  }));

  const { result } = renderHook(() => useConnectedDemo());

  await waitFor(() => expect(result.current.state.value).toBe(expectedState));
  await waitFor(() => expect(result.current.currentFacts?.caseId).toBe(CONTINUED_CASE_ID));
  expect(requests).toContain(`/api/demo/cases/${CONTINUED_CASE_ID}/advisor-ledger`);
  expect(requests).toContain(`/api/demo/cases/${CONTINUED_CASE_ID}/confirmed-facts`);
  expect(requests.every((path) => !path.includes(CASE_ID))).toBe(true);
  expect(loadRecoveryMetadata()).toMatchObject({ caseId: CONTINUED_CASE_ID, taskId: TASK_ID });
});

it.each([
  ["active-task", "task_streaming", 1],
  ["review-required", "advisor_review", 0],
  ["terminal-task-failure", "terminal_task_failure", 0],
] as const)("atomically adopts a %s task created after handoff without posting", async (phase, expectedState, expectedStreams) => {
  const projected = phase === "terminal-task-failure" ? ledger(phase, "failed") : ledger(phase);
  const active = {
    ...projected,
    case_id: CONTINUED_CASE_ID,
    case_revision: 2,
    canonical_task_inputs: projected.canonical_task_inputs ? {
      ...projected.canonical_task_inputs,
      case_id: CONTINUED_CASE_ID,
      expected_case_revision: 2,
    } : null,
    review_inputs: projected.review_inputs ? { ...projected.review_inputs, expected_case_revision: 2 } : null,
  };
  saveRecoveryMetadata({ ...advisorMetadata(), caseId: CONTINUED_CASE_ID });
  const sources: string[] = [];
  const taskPosts: string[] = [];
  class FakeEventSource {
    constructor(readonly url: string) { sources.push(url); }
    addEventListener() {}
    close() {}
  }
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path.endsWith("/agent-tasks") && init?.method === "POST") taskPosts.push(path);
    if (path.endsWith("/advisor-ledger")) return Response.json(active);
    if (path.endsWith("/confirmed-facts")) return Response.json({ schema_version: 1, current: [CONFIRMED_FACT], history: [], next_cursor: null });
    throw new Error(`unexpected ${path}`);
  }));

  const { result } = renderHook(() => useConnectedDemo());

  await waitFor(() => expect(result.current.state.value).toBe(expectedState));
  expect(loadRecoveryMetadata()).toMatchObject({ caseId: CONTINUED_CASE_ID, taskId: TASK_ID, cursor: 0 });
  expect(sources).toHaveLength(expectedStreams);
  if (expectedStreams) expect(sources).toEqual([`/api/demo/tasks/${TASK_ID}/events?after=0`]);
  expect(taskPosts).toEqual([]);
});

it("fails closed when recovery metadata already names a different task", async () => {
  const otherTask = "70000000-0000-0000-0000-000000000002";
  saveRecoveryMetadata({ ...advisorMetadata(), taskId: otherTask });
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    if (path.endsWith("/advisor-ledger")) return Response.json(ledger("active-task"));
    if (path.endsWith("/confirmed-facts")) return Response.json({ schema_version: 1, current: [], history: [], next_cursor: null });
    throw new Error(`unexpected ${path}`);
  }));

  const { result } = renderHook(() => useConnectedDemo());

  await waitFor(() => expect(result.current.state.value).toBe("recoverable_error"));
  expect(loadRecoveryMetadata()?.taskId).toBe(otherTask);
});

it.each(["unavailable", "malformed"] as const)("does not present confirmed facts as empty when the projection is %s", async (kind) => {
  saveRecoveryMetadata(advisorMetadata());
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    if (path.endsWith("/advisor-ledger")) return Response.json(ledger("task-ready"));
    if (path.endsWith("/confirmed-facts")) {
      return kind === "unavailable"
        ? Response.json({ code: "bff_upstream_unavailable" }, { status: 503 })
        : Response.json({ schema_version: 1, current: "not-an-array" });
    }
    if (path.endsWith("/planning-skill-inspector")) return Response.json(inspector("not_created"));
    throw new Error(`unexpected ${path}`);
  }));

  const { result } = renderHook(() => useConnectedDemo());

  await waitFor(() => expect(result.current.state.value).toBe("advisor_ready"));
  expect(result.current.currentFacts).toBeNull();
});

it("re-reads facts until the ledger revision is stable across the projection", async () => {
  const atRevision = (revision: number) => ({
    ...ledger("task-ready"),
    case_revision: revision,
    canonical_task_inputs: { ...ledger("task-ready").canonical_task_inputs!, expected_case_revision: revision },
  });
  const advancedFact = { ...CONFIRMED_FACT, fact_version: 2 };
  saveRecoveryMetadata(advisorMetadata());
  let ledgerReads = 0;
  let factReads = 0;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    if (path.endsWith("/advisor-ledger")) {
      ledgerReads += 1;
      return Response.json(atRevision(ledgerReads === 1 ? 2 : 3));
    }
    if (path.endsWith("/confirmed-facts")) {
      factReads += 1;
      return Response.json({ schema_version: 1, current: [factReads === 1 ? CONFIRMED_FACT : advancedFact], history: [], next_cursor: null });
    }
    if (path.endsWith("/planning-skill-inspector")) return Response.json(inspector("not_created"));
    throw new Error(`unexpected ${path}`);
  }));

  const { result } = renderHook(() => useConnectedDemo());

  await waitFor(() => expect(result.current.currentFacts?.caseRevision).toBe(3));
  expect(result.current.state).toMatchObject({ value: "advisor_ready", ledger: { case_revision: 3 } });
  expect(result.current.currentFacts?.facts).toEqual([advancedFact]);
  expect(ledgerReads).toBe(3);
  expect(factReads).toBe(2);
});

it("recovers the continued parent brief after role rotation without reading the seed Case", async () => {
  saveRecoveryMetadata({ ...parentMetadata(), caseId: CONTINUED_CASE_ID });
  const continuedBrief = { ...brief("family-review"), case_id: CONTINUED_CASE_ID };
  const requests: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    requests.push(path);
    if (path.endsWith("/advisor-ledger")) return Response.json({ code: "resource_unavailable" }, { status: 404 });
    if (path.endsWith("/current-decision-brief")) return Response.json(continuedBrief);
    throw new Error(`unexpected ${path}`);
  }));

  const { result } = renderHook(() => useConnectedDemo());

  await waitFor(() => expect(result.current.state.value).toBe("family_review"));
  expect(requests).toEqual([
    `/api/demo/cases/${CONTINUED_CASE_ID}/advisor-ledger`,
    `/api/demo/cases/${CONTINUED_CASE_ID}/current-decision-brief`,
  ]);
  expect(requests.every((path) => !path.includes(CASE_ID))).toBe(true);
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
  let ledgerCalls = 0;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    if (path.endsWith("/confirmed-facts")) return Response.json({ schema_version: 1, current: [], history: [], next_cursor: null });
    if (path.endsWith("/planning-skill-inspector")) return Response.json(inspector("matched"));
    ledgerCalls += 1;
    if (ledgerCalls <= 2) return Response.json(ledger("active-task"));
    if (ledgerCalls <= 4) return await new Promise<Response>((resolve) => { if (ledgerCalls === 3) resolveFirst = resolve; else resolveSecond = resolve; });
    return Response.json(ledger("review-required"));
  }));
  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("task_streaming"));
  expect(sources).toHaveLength(1);
  expect(sources[0].url).toContain(`/${TASK_ID}/events?after=4`);
  act(() => {
    listeners.get("heartbeat_recorded")?.({ lastEventId: "9" } as MessageEvent);
    listeners.get("heartbeat_recorded")?.({ lastEventId: "6" } as MessageEvent);
  });
  expect(ledgerCalls).toBe(3);
  await act(async () => { resolveFirst?.(Response.json(ledger("active-task"))); });
  await waitFor(() => expect(ledgerCalls).toBe(4));
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
