import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import {
  loadRecoveryMetadata,
  saveRecoveryMetadata,
} from "../../lib/connected-demo/session-storage";
import { useConnectedDemo } from "../../lib/connected-demo/use-connected-demo";
import {
  CASE_ID,
  TASK_ID,
  brief,
  ledger,
  status,
} from "./connected-demo-test-data";

const THREAD_ID = "42000000-0000-0000-0000-000000000001";
const MESSAGE_ID = "43000000-0000-0000-0000-000000000001";
const CANDIDATE_ID = "44000000-0000-0000-0000-000000000001";
const AT = "2026-07-20T01:02:03Z";
const SHA = "a".repeat(64);

const advisorMetadata = (phase: "task_ready" | "review_required" | "revision_task_active" | "revision_blocked" = "task_ready") => ({
  schema_version: 3 as const,
  journey: "advisor-family" as const,
  role: "advisor" as const,
  csrf: "csrf",
  caseId: CASE_ID,
  currentRevision: phase === "revision_task_active" || phase === "revision_blocked" ? 2 : 1,
  currentTaskId: phase === "revision_task_active" || phase === "revision_blocked" ? TASK_ID : null,
  predecessorRunId: phase === "revision_blocked" ? "70000000-0000-0000-0000-000000000001" : null,
  currentRunId: phase === "review_required"
    ? "70000000-0000-0000-0000-000000000001"
    : phase === "revision_blocked"
      ? "70000000-0000-0000-0000-000000000002"
      : null,
  cursor: 0,
  phase,
  mutations: {},
});

const studentMetadata = () => ({
  schema_version: 3 as const,
  journey: "advisor-family" as const,
  role: "student" as const,
  csrf: "student-csrf",
  caseId: CASE_ID,
  currentRevision: 1,
  currentTaskId: null,
  predecessorRunId: null,
  currentRunId: null,
  cursor: 0,
  phase: "revision_requested" as const,
  mutations: {},
});

const parentMetadata = () => ({
  schema_version: 3 as const,
  journey: "advisor-family" as const,
  role: "parent" as const,
  csrf: "parent-csrf",
  caseId: CASE_ID,
  currentRevision: 1,
  currentTaskId: null,
  predecessorRunId: null,
  currentRunId: null,
  cursor: 0,
  phase: "family_review" as const,
  mutations: {},
});

const thread = {
  schema_version: 1,
  thread_id: THREAD_ID,
  case_id: CASE_ID,
  created_by_actor_id: CASE_ID,
  created_at: AT,
};
const preferredFact = {
  schema_version: 1,
  fact_key: "student.preferred_countries",
  value: ["australia", "japan", "malaysia"],
  fact_version: 1,
  confirmed_at: AT,
  subject_role: "student",
  confirming_advisor_role: "advisor",
};
const participantCandidate = {
  schema_version: 1,
  fact_key: "student.preferred_countries",
  value: ["australia", "japan"],
  state: "pending",
  created_at: AT,
  expires_at: "2026-07-27T01:02:03Z",
};
const advisorCandidate = {
  ...participantCandidate,
  candidate_id: CANDIDATE_ID,
  message_event_id: MESSAGE_ID,
  source_message_sequence_no: 1,
  subject_actor_id: CASE_ID,
  subject_role: "student",
  case_revision: 1,
  verification_id: null,
  decision: null,
  reason: null,
  request_sha256: SHA,
  value_sha256: SHA,
};

afterEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it("rejects unsupported v2, malformed v3, and stale identity fields fail closed", () => {
  for (const value of [
    { schema_version: 2, journey: "advisor-family", role: "advisor", csrf: "csrf", caseId: CASE_ID, taskId: null, briefId: null, cursor: 0, mutations: {} },
    { ...advisorMetadata(), schema_version: 4 },
    { ...advisorMetadata(), phase: "revision-requested" },
    { ...advisorMetadata(), currentTaskId: "not-a-uuid" },
    { ...advisorMetadata(), role: "student" },
    { ...studentMetadata(), currentTaskId: TASK_ID },
    { ...parentMetadata(), cursor: 1 },
  ]) {
    sessionStorage.setItem("night-voyager:m5", JSON.stringify(value));
    expect(loadRecoveryMetadata()).toBeNull();
    expect(sessionStorage.getItem("night-voyager:m5")).toBeNull();
  }
});

it("stores only exact same-tab V3 recovery hints", () => {
  saveRecoveryMetadata(advisorMetadata());
  expect(loadRecoveryMetadata()).toEqual(advisorMetadata());
  expect(localStorage.length).toBe(0);
});

it("recovers advisor status first, then reads only advisor-safe detail", async () => {
  saveRecoveryMetadata(advisorMetadata("review_required"));
  const requests: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    requests.push(path);
    if (path.endsWith("/journey-status")) return Response.json(status("review_required"));
    if (path.endsWith("/advisor-ledger")) return Response.json(ledger("review_required"));
    if (path.endsWith("/confirmed-facts")) return Response.json({ schema_version: 1, current: [], history: [], next_cursor: null });
    if (path.endsWith("/planning-skill-inspector")) return Response.json({ code: "unavailable" }, { status: 404 });
    throw new Error(`unexpected ${path}`);
  }));

  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("advisor_review"));

  expect(requests[0]).toBe(`/api/demo/cases/${CASE_ID}/journey-status`);
  expect(requests[1]).toBe(`/api/demo/cases/${CASE_ID}/advisor-ledger`);
  expect(requests).not.toContain(`/api/demo/cases/${CASE_ID}/current-decision-brief`);
  expect(loadRecoveryMetadata()).toMatchObject({
    phase: "review_required",
    currentRevision: 1,
    currentRunId: "70000000-0000-0000-0000-000000000001",
  });
});

it("restores an exact valid revision-blocked projection without recovery fallback", async () => {
  saveRecoveryMetadata(advisorMetadata("revision_blocked"));
  const requests: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    requests.push(path);
    if (path.endsWith("/journey-status")) return Response.json(status("revision_blocked"));
    if (path.endsWith("/advisor-ledger")) return Response.json(ledger("revision_blocked"));
    if (path.endsWith("/confirmed-facts")) return Response.json({ schema_version: 1, current: [], history: [], next_cursor: null });
    if (path.endsWith("/memory-candidates")) return Response.json([]);
    if (path.endsWith("/collaboration-thread")) return Response.json(thread);
    if (path.includes("/messages?")) return Response.json({ schema_version: 1, items: [], next_after_sequence: null });
    if (path.endsWith("/planning-skill-inspector")) return Response.json({ code: "unavailable" }, { status: 404 });
    throw new Error(`unexpected ${path}`);
  }));

  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("revision_blocked"));

  expect(result.current.state).toMatchObject({
    value: "revision_blocked",
    ledger: { recovery: null },
  });
  expect(requests[0]).toBe(`/api/demo/cases/${CASE_ID}/journey-status`);
  expect(requests[1]).toBe(`/api/demo/cases/${CASE_ID}/advisor-ledger`);
});

it("recovers student status before participant-safe collaboration detail", async () => {
  saveRecoveryMetadata(studentMetadata());
  const requests: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    requests.push(path);
    if (path.endsWith("/journey-status")) return Response.json(status("revision_requested"));
    if (path.endsWith("/collaboration-thread")) return Response.json(thread);
    if (path.endsWith("/confirmed-facts")) return Response.json({ schema_version: 1, current: [preferredFact] });
    if (path.endsWith("/memory-candidates")) return Response.json([]);
    if (path.includes("/messages?")) return Response.json({ schema_version: 1, items: [], next_after_sequence: null });
    throw new Error(`unexpected ${path}`);
  }));

  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("revision_requested"));

  expect(requests[0]).toBe(`/api/demo/cases/${CASE_ID}/journey-status`);
  expect(requests).not.toContain(`/api/demo/cases/${CASE_ID}/advisor-ledger`);
  expect(result.current.revision?.facts).toEqual([preferredFact]);
});

it("recovers parent status before the exact V2 current brief", async () => {
  saveRecoveryMetadata(parentMetadata());
  const requests: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    requests.push(path);
    if (path.endsWith("/journey-status")) return Response.json(status("family_review"));
    if (path.endsWith("/current-decision-brief")) return Response.json(brief("family_review"));
    throw new Error(`unexpected ${path}`);
  }));
  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("family_review"));
  expect(requests).toEqual([
    `/api/demo/cases/${CASE_ID}/journey-status`,
    `/api/demo/cases/${CASE_ID}/current-decision-brief`,
  ]);
});

it("fails closed on status/detail revision or phase mismatch", async () => {
  saveRecoveryMetadata(advisorMetadata());
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    if (path.endsWith("/journey-status")) return Response.json(status("review_required"));
    if (path.endsWith("/advisor-ledger")) return Response.json(ledger("task_ready"));
    throw new Error(`unexpected ${path}`);
  }));
  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state).toMatchObject({
    value: "recoverable_error",
    code: "transport_failure",
  }));
});

it("uses status to recover a pending explicit role rotation without reading wrong-role detail", async () => {
  saveRecoveryMetadata(advisorMetadata("review_required"));
  const requests: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    requests.push(path);
    if (path.endsWith("/journey-status")) return Response.json(status("revision_requested"));
    throw new Error(`unexpected ${path}`);
  }));
  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state).toMatchObject({
    value: "role_switching",
    targetRole: "student",
  }));
  expect(requests).toEqual([`/api/demo/cases/${CASE_ID}/journey-status`]);
});

it("recovers the exact target role when bootstrap fails after revoke", async () => {
  saveRecoveryMetadata(advisorMetadata("review_required"));
  const mintedRoles: string[] = [];
  const detailReads: string[] = [];
  let targetProjected = false;
  let revoked = false;
  let revokeAttempts = 0;
  let targetBootstrapAttempts = 0;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path.endsWith("/journey-status")) {
      return Response.json(status(targetProjected ? "revision_requested" : "review_required"));
    }
    if (path.endsWith("/advisor-ledger")) {
      detailReads.push("advisor");
      return Response.json(ledger("review_required"));
    }
    if (path.endsWith("/confirmed-facts")) {
      detailReads.push(revoked ? "student" : "advisor");
      return Response.json(revoked
        ? { schema_version: 1, current: [preferredFact] }
        : { schema_version: 1, current: [], history: [], next_cursor: null });
    }
    if (path.endsWith("/memory-candidates")) {
      detailReads.push("student");
      return Response.json([]);
    }
    if (path.endsWith("/collaboration-thread")) {
      detailReads.push("student");
      return Response.json(thread);
    }
    if (path.includes("/messages?")) {
      detailReads.push("student");
      return Response.json({ schema_version: 1, items: [], next_after_sequence: null });
    }
    if (path.endsWith("/planning-skill-inspector")) return Response.json({ code: "unavailable" }, { status: 404 });
    if (path.endsWith("/session") && init?.method === "DELETE") {
      revokeAttempts += 1;
      if (revokeAttempts > 1) {
        return Response.json({ code: "session_revoke_failed" }, { status: 401 });
      }
      revoked = true;
      return new Response(null, { status: 204 });
    }
    if (path.endsWith("/session-bootstrap")) {
      targetBootstrapAttempts += 1;
      return targetBootstrapAttempts === 1
        ? Response.json({ code: "bff_upstream_unavailable" }, { status: 503 })
        : Response.json({ csrf_token: "bootstrap" });
    }
    if (path.endsWith("/sessions")) {
      const role = JSON.parse(String(init?.body)).demo_actor;
      mintedRoles.push(role);
      return Response.json({
        role,
        proof_mode: "synthetic-demo",
        csrf_token: `${role}-csrf`,
      }, { status: 201 });
    }
    throw new Error(`unexpected ${path}`);
  }));

  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("advisor_review"));
  detailReads.length = 0;
  targetProjected = true;

  await act(async () => result.current.rotateToStudent(CASE_ID));
  expect(result.current.state.value).toBe("recoverable_error");
  await act(async () => result.current.retry());
  await waitFor(() => expect(result.current.state.value).toBe("revision_requested"));

  expect(mintedRoles).toEqual(["student"]);
  expect(revokeAttempts).toBe(2);
  expect(detailReads).not.toContain("advisor");
  expect(loadRecoveryMetadata()).toMatchObject({
    schema_version: 3,
    role: "student",
    csrf: "student-csrf",
    caseId: CASE_ID,
    phase: "revision_requested",
  });
  expect(loadRecoveryMetadata()).not.toHaveProperty("pendingRole");
});

it("recovers a server-projected target role when bootstrap starts without an envelope", async () => {
  const mintedRoles: string[] = [];
  const detailReads: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path.endsWith("/session-bootstrap")) return Response.json({ csrf_token: "bootstrap" });
    if (path.endsWith("/sessions")) {
      const role = JSON.parse(String(init?.body)).demo_actor;
      mintedRoles.push(role);
      return Response.json({
        role,
        proof_mode: "synthetic-demo",
        csrf_token: `${role}-csrf`,
      }, { status: 201 });
    }
    if (path.endsWith("/session") && init?.method === "DELETE") return new Response(null, { status: 204 });
    if (path.endsWith("/journey-status")) return Response.json(status("revision_requested"));
    if (path.endsWith("/collaboration-thread")) {
      detailReads.push("student");
      return Response.json(thread);
    }
    if (path.endsWith("/confirmed-facts")) {
      detailReads.push("student");
      return Response.json({ schema_version: 1, current: [preferredFact] });
    }
    if (path.endsWith("/memory-candidates")) {
      detailReads.push("student");
      return Response.json([]);
    }
    if (path.includes("/messages?")) {
      detailReads.push("student");
      return Response.json({ schema_version: 1, items: [], next_after_sequence: null });
    }
    if (path.endsWith("/advisor-ledger")) {
      detailReads.push("advisor");
      return Response.json(ledger("review_required"));
    }
    throw new Error(`unexpected ${path}`);
  }));

  const { result } = renderHook(() => useConnectedDemo());
  await act(async () => result.current.connectAdvisor());
  await waitFor(() => expect(result.current.state).toMatchObject({
    value: "role_switching",
    targetRole: "student",
  }));

  await act(async () => result.current.retry());
  await waitFor(() => expect(result.current.state.value).toBe("revision_requested"));

  expect(mintedRoles).toEqual(["advisor", "student"]);
  expect(detailReads).toEqual(["student", "student", "student", "student"]);
  expect(loadRecoveryMetadata()).toMatchObject({
    schema_version: 3,
    role: "student",
    csrf: "student-csrf",
    caseId: CASE_ID,
    phase: "revision_requested",
  });
  expect(loadRecoveryMetadata()).not.toHaveProperty("pendingRole");
});

it("reuses the request-revision key after a committed response is lost", async () => {
  saveRecoveryMetadata(advisorMetadata("review_required"));
  const keys: string[] = [];
  let reviewAttempts = 0;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path.endsWith("/journey-status")) {
      return Response.json(reviewAttempts === 0 ? status("review_required") : status("revision_requested"));
    }
    if (path.endsWith("/advisor-ledger")) return Response.json(ledger("review_required"));
    if (path.endsWith("/confirmed-facts")) return Response.json({ schema_version: 1, current: [], history: [], next_cursor: null });
    if (path.endsWith("/planning-skill-inspector")) return Response.json({ code: "unavailable" }, { status: 404 });
    if (path.endsWith("/advisor-reviews")) {
      reviewAttempts += 1;
      keys.push(new Headers(init?.headers).get("Idempotency-Key") ?? "");
      return reviewAttempts === 1
        ? Response.json({ code: "bff_upstream_unavailable" }, { status: 503 })
        : Response.json({});
    }
    throw new Error(`unexpected ${path}`);
  }));

  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("advisor_review"));
  await act(async () => result.current.requestRevision());
  expect(result.current.state.value).toBe("recoverable_error");
  await act(async () => result.current.retry());
  await waitFor(() => expect(result.current.state.value).toBe("role_switching"));
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
  expect(loadRecoveryMetadata()?.mutations["request-revision"]?.idempotencyKey).toBe(keys[0]);
});

it("submits the bounded student proposal and reconciles status before role rotation", async () => {
  saveRecoveryMetadata(studentMetadata());
  const calls: Array<{ path: string; init?: RequestInit }> = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    calls.push({ path, init });
    if (path.endsWith("/journey-status")) {
      const proposed = calls.some((call) => call.path.endsWith("/memory-candidates") && call.init?.method === "POST");
      return Response.json(status(proposed ? "revision_fact_pending" : "revision_requested"));
    }
    if (path.endsWith("/collaboration-thread")) return Response.json(thread);
    if (path.endsWith("/confirmed-facts")) return Response.json({ schema_version: 1, current: [preferredFact] });
    if (path.endsWith("/memory-candidates") && init?.method !== "POST") return Response.json([]);
    if (path.includes("/messages?")) return Response.json({ schema_version: 1, items: [], next_after_sequence: null });
    if (path.endsWith("/messages") && init?.method === "POST") return Response.json({
      schema_version: 1,
      message_event_id: MESSAGE_ID,
      thread_id: THREAD_ID,
      case_id: CASE_ID,
      sequence_no: 1,
      actor_id: CASE_ID,
      actor_role: "student",
      body: JSON.parse(String(init.body)).body,
      content_sha256: SHA,
      created_at: AT,
    });
    if (path.endsWith("/memory-candidates") && init?.method === "POST") return Response.json(participantCandidate);
    throw new Error(`unexpected ${path}`);
  }));

  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("revision_requested"));
  await act(async () => result.current.submitPreferredCountries());
  await waitFor(() => expect(result.current.state.value).toBe("role_switching"));

  const proposal = calls.find((call) => call.path.endsWith("/memory-candidates") && call.init?.method === "POST");
  expect(JSON.parse(String(proposal?.init?.body))).toEqual({
    schema_version: 1,
    case_revision: 1,
    proposal: {
      schema_version: 1,
      fact_key: "student.preferred_countries",
      value: ["australia", "japan"],
    },
  });
  expect(calls.at(-1)?.path).toBe(`/api/demo/cases/${CASE_ID}/journey-status`);
});

it("reuses both student proposal keys after the candidate response is lost", async () => {
  saveRecoveryMetadata(studentMetadata());
  const messageKeys: string[] = [];
  const candidateKeys: string[] = [];
  const durableMessages = new Set<string>();
  const durableCandidates = new Set<string>();
  let candidateAttempts = 0;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path.endsWith("/journey-status")) {
      return Response.json(status(durableCandidates.size === 0 ? "revision_requested" : "revision_fact_pending"));
    }
    if (path.endsWith("/collaboration-thread")) return Response.json(thread);
    if (path.endsWith("/confirmed-facts")) return Response.json({ schema_version: 1, current: [preferredFact] });
    if (path.endsWith("/memory-candidates") && init?.method !== "POST") return Response.json([]);
    if (path.includes("/messages?")) return Response.json({ schema_version: 1, items: [], next_after_sequence: null });
    if (path.endsWith("/messages") && init?.method === "POST") {
      const key = new Headers(init.headers).get("Idempotency-Key") ?? "";
      messageKeys.push(key);
      durableMessages.add(key);
      return Response.json({
        schema_version: 1,
        message_event_id: MESSAGE_ID,
        thread_id: THREAD_ID,
        case_id: CASE_ID,
        sequence_no: 1,
        actor_id: CASE_ID,
        actor_role: "student",
        body: JSON.parse(String(init.body)).body,
        content_sha256: SHA,
        created_at: AT,
      });
    }
    if (path.endsWith("/memory-candidates") && init?.method === "POST") {
      const key = new Headers(init.headers).get("Idempotency-Key") ?? "";
      candidateKeys.push(key);
      durableCandidates.add(key);
      candidateAttempts += 1;
      return candidateAttempts === 1
        ? Response.json({ code: "bff_upstream_unavailable" }, { status: 503 })
        : Response.json(participantCandidate);
    }
    throw new Error(`unexpected ${path}`);
  }));

  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("revision_requested"));

  await act(async () => result.current.submitPreferredCountries());
  expect(result.current.state.value).toBe("recoverable_error");
  await act(async () => result.current.retry());
  await waitFor(() => expect(result.current.state).toMatchObject({
    value: "role_switching",
    targetRole: "advisor",
  }));

  expect(messageKeys).toHaveLength(2);
  expect(messageKeys[0]).toBe(messageKeys[1]);
  expect(candidateKeys).toHaveLength(2);
  expect(candidateKeys[0]).toBe(candidateKeys[1]);
  expect(durableMessages.size).toBe(1);
  expect(durableCandidates.size).toBe(1);
  expect(loadRecoveryMetadata()?.mutations).toMatchObject({
    "fact-proposal-message": { idempotencyKey: messageKeys[0] },
    "fact-proposal-candidate": { idempotencyKey: candidateKeys[0] },
  });
});

it("confirms only the exact pending preferred-country candidate", async () => {
  saveRecoveryMetadata({
    ...advisorMetadata(),
    phase: "revision_fact_pending",
  });
  let verified = false;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    if (path.endsWith("/journey-status")) {
      return Response.json(status(verified ? "replan_required" : "revision_fact_pending"));
    }
    if (path.endsWith("/advisor-ledger")) return Response.json(ledger(verified ? "replan_required" : "revision_fact_pending"));
    if (path.endsWith("/confirmed-facts")) return Response.json({ schema_version: 1, current: [], history: [], next_cursor: null });
    if (path.endsWith("/collaboration-thread")) return Response.json(thread);
    if (path.endsWith("/memory-candidates")) return Response.json([advisorCandidate]);
    if (path.includes("/messages?")) return Response.json({ schema_version: 1, items: [], next_after_sequence: null });
    if (path.includes("/verification-decisions")) {
      verified = true;
      return Response.json({
        schema_version: 1,
        verification_id: MESSAGE_ID,
        candidate_id: CANDIDATE_ID,
        decision: "confirm",
        result_fact_id: MESSAGE_ID,
        result_revision: 2,
        replayed: false,
      });
    }
    if (path.endsWith("/planning-skill-inspector")) return Response.json({ code: "unavailable" }, { status: 404 });
    throw new Error(`unexpected ${path}`);
  }));
  const { result } = renderHook(() => useConnectedDemo());
  await waitFor(() => expect(result.current.state.value).toBe("revision_fact_pending"));
  await act(async () => result.current.confirmPreferredCountries());
  await waitFor(() => expect(result.current.state.value).toBe("replan_required"));
});
