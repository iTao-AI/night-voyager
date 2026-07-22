import { afterEach, expect, it } from "vitest";

import {
  clearDemoJourneyEnvelope,
  continueCollaborationAsAdvisorFamily,
  loadDemoJourneyEnvelope,
  loadRecoveryMetadata,
  saveCollaborationJourney,
  saveRecoveryMetadata,
} from "../../lib/connected-demo/session-storage";

const CASE = "41000000-0000-0000-0000-000000000001";
const THREAD = "42000000-0000-0000-0000-000000000001";
const MESSAGE = "43000000-0000-0000-0000-000000000001";
const CANDIDATE = "44000000-0000-0000-0000-000000000001";

afterEach(() => sessionStorage.clear());

const collaboration = () => ({ schema_version: 2 as const, journey: "collaboration" as const, role: "parent" as const, csrf: "csrf", caseId: CASE, threadId: THREAD, messageId: MESSAGE, candidateId: null, phase: "proposal_pending" as const, mutations: {} });
const confirmedCollaboration = () => ({ ...collaboration(), role: "advisor" as const, candidateId: CANDIDATE, phase: "replan_required" as const });

it("converts one exact confirmed collaboration envelope without mutating it", () => {
  const current = confirmedCollaboration();
  const snapshot = structuredClone(current);

  expect(continueCollaborationAsAdvisorFamily(current, null)).toEqual({
    schema_version: 2,
    journey: "advisor-family",
    role: "advisor",
    csrf: current.csrf,
    caseId: current.caseId,
    taskId: null,
    briefId: null,
    cursor: 0,
    mutations: {},
  });
  expect(current).toEqual(snapshot);
  expect(continueCollaborationAsAdvisorFamily(current, CANDIDATE)).toMatchObject({ taskId: CANDIDATE });
});

it("rejects every non-terminal role/phase and malformed conversion input", () => {
  const current = confirmedCollaboration();
  for (const phase of [
    "bootstrapping_parent", "thread_ready", "message_submitting", "proposal_pending",
    "switching_to_advisor", "advisor_reviewing", "confirmation_submitting",
  ] as const) {
    expect(() => continueCollaborationAsAdvisorFamily({ ...current, phase } as unknown as typeof current, null)).toThrow();
  }
  for (const invalid of [
    { ...current, role: "parent" },
    { ...current, csrf: "" },
    { ...current, caseId: "not-a-uuid" },
    { ...current, extra: true },
    { ...current, cursor: 1 },
    { ...current, briefId: CANDIDATE },
    { ...current, mutations: { "verify-memory-candidate": { fingerprint: "0".repeat(64), idempotencyKey: CANDIDATE } } },
  ]) {
    expect(() => continueCollaborationAsAdvisorFamily(invalid as typeof current, null)).toThrow();
  }
  for (const taskId of ["", "partial", `${CANDIDATE}0`]) {
    expect(() => continueCollaborationAsAdvisorFamily(current, taskId)).toThrow();
  }
});

it("stores and restores the exact schema-v2 journey union", () => {
  saveCollaborationJourney(collaboration());
  expect(loadDemoJourneyEnvelope()).toEqual(collaboration());
  expect(loadRecoveryMetadata()).toBeNull();
  expect(sessionStorage.getItem("night-voyager:m5")).toContain('"schema_version":2');
  clearDemoJourneyEnvelope();
  expect(loadDemoJourneyEnvelope()).toBeNull();
});

it("preserves a valid other journey and clears malformed or legacy envelopes", () => {
  saveCollaborationJourney(collaboration());
  expect(loadDemoJourneyEnvelope()?.journey).toBe("collaboration");
  expect(sessionStorage.getItem("night-voyager:m5")).not.toBeNull();
  for (const value of [
    { ...collaboration(), schema_version: 1 },
    { ...collaboration(), extra: true },
    { ...collaboration(), caseId: "bad" },
    { ...collaboration(), role: "advisor", phase: "advisor_reviewing", candidateId: null },
    { ...collaboration(), candidateId: CANDIDATE },
  ]) {
    sessionStorage.setItem("night-voyager:m5", JSON.stringify(value));
    expect(loadDemoJourneyEnvelope()).toBeNull();
    expect(sessionStorage.getItem("night-voyager:m5")).toBeNull();
  }
  sessionStorage.setItem("night-voyager:m5", "{");
  expect(loadDemoJourneyEnvelope()).toBeNull();
  expect(sessionStorage.getItem("night-voyager:m5")).toBeNull();
});

it("enforces collaboration phase, role, and server-ID cross-field invariants", () => {
  const validAdvisor = { ...collaboration(), role: "advisor" as const, phase: "advisor_reviewing" as const, candidateId: CANDIDATE };
  saveCollaborationJourney(validAdvisor);
  expect(loadDemoJourneyEnvelope()).toEqual(validAdvisor);
  for (const invalid of [
    { ...collaboration(), phase: "thread_ready", threadId: null },
    { ...collaboration(), phase: "replan_required", role: "advisor", candidateId: null },
    { ...collaboration(), phase: "recoverable_error" },
    { ...collaboration(), role: "advisor", candidateId: CANDIDATE, phase: "handoff_validating" },
    { ...collaboration(), phase: "switching_to_advisor", candidateId: CANDIDATE },
  ]) {
    sessionStorage.setItem("night-voyager:m5", JSON.stringify(invalid));
    expect(loadDemoJourneyEnvelope()).toBeNull();
  }
});

it("keeps advisor-family metadata exact and request-bound", () => {
  const advisor = { schema_version: 2 as const, journey: "advisor-family" as const, role: "advisor" as const, csrf: "csrf", caseId: CASE, taskId: null, briefId: null, cursor: 0, mutations: {} };
  saveRecoveryMetadata(advisor);
  expect(loadRecoveryMetadata()).toEqual(advisor);
  sessionStorage.setItem("night-voyager:m5", JSON.stringify({ ...advisor, mutations: { "create-task": { fingerprint: "0".repeat(64), idempotencyKey: "bad" } } }));
  expect(loadDemoJourneyEnvelope()).toBeNull();
});
