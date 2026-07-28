import type { IdempotencyRecord } from "./idempotency";
import type { DemoPhaseV2 } from "./contracts";

export type AdvisorFamilyMutationKind =
  | "request-revision" | "fact-proposal-message" | "fact-proposal-candidate"
  | "fact-confirmation"
  | "create-task" | "new-review" | "family-decision";
export type CollaborationMutationKind = "append-message" | "propose-memory-candidate" | "verify-memory-candidate";
export type CollaborationPersistedPhase =
  | "bootstrapping_parent"
  | "thread_ready"
  | "message_submitting"
  | "proposal_pending"
  | "switching_to_advisor"
  | "advisor_reviewing"
  | "confirmation_submitting"
  | "replan_required";

export interface AdvisorFamilyJourneyEnvelopeV3 {
  schema_version: 3;
  journey: "advisor-family";
  role: "advisor" | "student" | "parent";
  csrf: string;
  caseId: string;
  currentRevision: number;
  currentTaskId: string | null;
  predecessorRunId: string | null;
  currentRunId: string | null;
  cursor: number;
  phase: DemoPhaseV2;
  mutations: Partial<Record<AdvisorFamilyMutationKind, IdempotencyRecord>>;
  pendingRole?: "advisor" | "student" | "parent";
}

export interface CollaborationJourneyEnvelopeV2 {
  schema_version: 2;
  journey: "collaboration";
  role: "parent" | "advisor";
  csrf: string;
  caseId: string;
  threadId: string | null;
  messageId: string | null;
  candidateId: string | null;
  phase: CollaborationPersistedPhase;
  mutations: Partial<Record<CollaborationMutationKind, IdempotencyRecord>>;
}

export type DemoJourneyEnvelope = AdvisorFamilyJourneyEnvelopeV3 | CollaborationJourneyEnvelopeV2;
export type RecoveryMetadata = AdvisorFamilyJourneyEnvelopeV3;
export type MutationOperation = AdvisorFamilyMutationKind;
export interface CollaborationAdvisorFamilyAuthority {
  phase: DemoPhaseV2;
  currentRevision: number;
  currentTaskId: string | null;
  predecessorRunId: string | null;
  currentRunId: string | null;
}

const KEY = "night-voyager:m5";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const SHA256 = /^[0-9a-f]{64}$/;
const ADVISOR_OPERATIONS = ["request-revision", "fact-proposal-message", "fact-proposal-candidate", "fact-confirmation", "create-task", "new-review", "family-decision"] as const;
const COLLABORATION_OPERATIONS = ["append-message", "propose-memory-candidate", "verify-memory-candidate"] as const;
const COLLABORATION_PHASES: readonly CollaborationPersistedPhase[] = ["bootstrapping_parent", "thread_ready", "message_submitting", "proposal_pending", "switching_to_advisor", "advisor_reviewing", "confirmation_submitting", "replan_required"];
const PHASES: readonly DemoPhaseV2[] = ["task_ready", "active_task", "review_required", "revision_requested", "revision_fact_pending", "replan_required", "revision_task_active", "revision_review_required", "revision_blocked", "family_review", "plan_ready", "terminal_task_failure"];

function object(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function exact(value: Record<string, unknown>, keys: readonly string[]): boolean { const actual = Object.keys(value).sort(); const expected = [...keys].sort(); return actual.length === expected.length && actual.every((key, index) => key === expected[index]); }
function uuid(value: unknown): value is string { return typeof value === "string" && UUID.test(value); }
function nullableUuid(value: unknown): value is string | null { return value === null || uuid(value); }
function validMutations(value: unknown, operations: readonly string[]): boolean {
  if (!object(value)) return false;
  return Object.entries(value).every(([operation, record]) => operations.includes(operation) && object(record) && exact(record, ["fingerprint", "idempotencyKey"]) && typeof record.fingerprint === "string" && SHA256.test(record.fingerprint) && uuid(record.idempotencyKey));
}

function advisorFamily(value: Record<string, unknown>): value is Record<string, unknown> & AdvisorFamilyJourneyEnvelopeV3 {
  const pendingRole = Object.hasOwn(value, "pendingRole");
  const keys = ["schema_version", "journey", "role", "csrf", "caseId", "currentRevision", "currentTaskId", "predecessorRunId", "currentRunId", "cursor", "phase", "mutations", ...(pendingRole ? ["pendingRole"] : [])];
  if (!exact(value, keys) || value.schema_version !== 3 || value.journey !== "advisor-family" || !["advisor", "student", "parent"].includes(String(value.role)) || typeof value.csrf !== "string" || !value.csrf || !uuid(value.caseId) || !Number.isSafeInteger(value.currentRevision) || Number(value.currentRevision) <= 0 || !nullableUuid(value.currentTaskId) || !nullableUuid(value.predecessorRunId) || !nullableUuid(value.currentRunId) || !Number.isSafeInteger(value.cursor) || Number(value.cursor) < 0 || !PHASES.includes(value.phase as DemoPhaseV2) || !validMutations(value.mutations, ADVISOR_OPERATIONS)) return false;
  const expectedRole = value.phase === "revision_requested" ? "student" : ["family_review", "plan_ready"].includes(String(value.phase)) ? "parent" : "advisor";
  if (pendingRole) {
    if (!["advisor", "student", "parent"].includes(String(value.pendingRole)) || value.pendingRole !== expectedRole || value.pendingRole === value.role) return false;
  } else if (value.role !== expectedRole) return false;
  if (value.role !== "advisor" && (value.currentTaskId !== null || value.cursor !== 0)) return false;
  return true;
}

function collaboration(value: Record<string, unknown>): value is Record<string, unknown> & CollaborationJourneyEnvelopeV2 {
  if (!exact(value, ["schema_version", "journey", "role", "csrf", "caseId", "threadId", "messageId", "candidateId", "phase", "mutations"]) || value.schema_version !== 2 || value.journey !== "collaboration" || !["parent", "advisor"].includes(String(value.role)) || typeof value.csrf !== "string" || !value.csrf || !uuid(value.caseId) || !nullableUuid(value.threadId) || !nullableUuid(value.messageId) || !nullableUuid(value.candidateId) || !COLLABORATION_PHASES.includes(value.phase as CollaborationPersistedPhase) || !validMutations(value.mutations, COLLABORATION_OPERATIONS)) return false;
  const phase = value.phase as CollaborationPersistedPhase;
  if (phase === "bootstrapping_parent") return value.role === "parent" && value.threadId === null && value.messageId === null && value.candidateId === null;
  if (phase === "switching_to_advisor") return value.threadId !== null && value.messageId !== null && value.candidateId === null;
  if (value.threadId === null) return false;
  if (["thread_ready", "message_submitting", "proposal_pending"].includes(phase)) {
    if (value.role !== "parent" || value.candidateId !== null) return false;
    return phase !== "proposal_pending" || value.messageId !== null;
  }
  return value.role === "advisor" && value.messageId !== null && value.candidateId !== null;
}

export function loadDemoJourneyEnvelope(): DemoJourneyEnvelope | null {
  const raw = sessionStorage.getItem(KEY);
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as unknown;
    if (!object(value) || (!advisorFamily(value) && !collaboration(value))) {
      sessionStorage.removeItem(KEY);
      return null;
    }
    return value as DemoJourneyEnvelope;
  } catch {
    sessionStorage.removeItem(KEY);
    return null;
  }
}

export function saveRecoveryMetadata(value: AdvisorFamilyJourneyEnvelopeV3): void { sessionStorage.setItem(KEY, JSON.stringify(value)); }
export function saveCollaborationJourney(value: CollaborationJourneyEnvelopeV2): void { sessionStorage.setItem(KEY, JSON.stringify(value)); }
export function clearDemoJourneyEnvelope(): void { sessionStorage.removeItem(KEY); }
export const clearRecoveryMetadata = clearDemoJourneyEnvelope;
export function loadRecoveryMetadata(): AdvisorFamilyJourneyEnvelopeV3 | null { const value = loadDemoJourneyEnvelope(); return value?.journey === "advisor-family" ? value : null; }

export function continueCollaborationAsAdvisorFamily(
  current: CollaborationJourneyEnvelopeV2,
  authority: CollaborationAdvisorFamilyAuthority,
): AdvisorFamilyJourneyEnvelopeV3 {
  const authorityKeys = ["phase", "currentRevision", "currentTaskId", "predecessorRunId", "currentRunId"];
  if (
    !object(current)
    || !collaboration(current)
    || current.role !== "advisor"
    || current.phase !== "replan_required"
    || Object.keys(current.mutations).length !== 0
    || !object(authority)
    || !exact(authority, authorityKeys)
    || !Number.isSafeInteger(authority.currentRevision)
    || authority.currentRevision <= 0
    || !nullableUuid(authority.currentTaskId)
    || !nullableUuid(authority.predecessorRunId)
    || !nullableUuid(authority.currentRunId)
    || authority.predecessorRunId !== null
  ) {
    throw new Error("invalid collaboration handoff");
  }
  const taskReady = authority.phase === "task_ready"
    && authority.currentTaskId === null
    && authority.currentRunId === null;
  const active = authority.phase === "active_task"
    && authority.currentTaskId !== null
    && authority.currentRunId === null;
  const review = authority.phase === "review_required"
    && authority.currentTaskId !== null
    && authority.currentRunId !== null;
  const terminal = authority.phase === "terminal_task_failure"
    && authority.currentTaskId !== null
    && authority.currentRunId === null;
  if (!taskReady && !active && !review && !terminal) {
    throw new Error("invalid collaboration handoff");
  }
  return {
    schema_version: 3,
    journey: "advisor-family",
    role: "advisor",
    csrf: current.csrf,
    caseId: current.caseId,
    currentRevision: authority.currentRevision,
    currentTaskId: authority.currentTaskId,
    predecessorRunId: authority.predecessorRunId,
    currentRunId: authority.currentRunId,
    cursor: 0,
    phase: authority.phase,
    mutations: {},
  };
}

export function withMutation(metadata: AdvisorFamilyJourneyEnvelopeV3, operation: AdvisorFamilyMutationKind, record: IdempotencyRecord | undefined): AdvisorFamilyJourneyEnvelopeV3 {
  const mutations = { ...metadata.mutations };
  if (record) mutations[operation] = record; else delete mutations[operation];
  return { ...metadata, mutations };
}

export function withCollaborationMutation(metadata: CollaborationJourneyEnvelopeV2, operation: CollaborationMutationKind, record: IdempotencyRecord | undefined): CollaborationJourneyEnvelopeV2 {
  const mutations = { ...metadata.mutations };
  if (record) mutations[operation] = record; else delete mutations[operation];
  return { ...metadata, mutations };
}
