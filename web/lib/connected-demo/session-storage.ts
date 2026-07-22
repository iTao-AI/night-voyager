import type { IdempotencyRecord } from "./idempotency";

export type AdvisorFamilyMutationKind = "create-task" | "advisor-review" | "family-decision";
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

export interface AdvisorFamilyJourneyEnvelopeV2 {
  schema_version: 2;
  journey: "advisor-family";
  role: "advisor" | "parent";
  csrf: string;
  caseId: string;
  taskId: string | null;
  briefId: string | null;
  cursor: number;
  mutations: Partial<Record<AdvisorFamilyMutationKind, IdempotencyRecord>>;
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

export type DemoJourneyEnvelopeV2 = AdvisorFamilyJourneyEnvelopeV2 | CollaborationJourneyEnvelopeV2;
export type RecoveryMetadata = AdvisorFamilyJourneyEnvelopeV2;
export type MutationOperation = AdvisorFamilyMutationKind;

const KEY = "night-voyager:m5";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const SHA256 = /^[0-9a-f]{64}$/;
const ADVISOR_OPERATIONS = ["create-task", "advisor-review", "family-decision"] as const;
const COLLABORATION_OPERATIONS = ["append-message", "propose-memory-candidate", "verify-memory-candidate"] as const;
const COLLABORATION_PHASES: readonly CollaborationPersistedPhase[] = ["bootstrapping_parent", "thread_ready", "message_submitting", "proposal_pending", "switching_to_advisor", "advisor_reviewing", "confirmation_submitting", "replan_required"];

function object(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function exact(value: Record<string, unknown>, keys: readonly string[]): boolean { const actual = Object.keys(value).sort(); const expected = [...keys].sort(); return actual.length === expected.length && actual.every((key, index) => key === expected[index]); }
function uuid(value: unknown): value is string { return typeof value === "string" && UUID.test(value); }
function nullableUuid(value: unknown): value is string | null { return value === null || uuid(value); }
function validMutations(value: unknown, operations: readonly string[]): boolean {
  if (!object(value)) return false;
  return Object.entries(value).every(([operation, record]) => operations.includes(operation) && object(record) && exact(record, ["fingerprint", "idempotencyKey"]) && typeof record.fingerprint === "string" && SHA256.test(record.fingerprint) && uuid(record.idempotencyKey));
}

function advisorFamily(value: Record<string, unknown>): value is Record<string, unknown> & AdvisorFamilyJourneyEnvelopeV2 {
  if (!exact(value, ["schema_version", "journey", "role", "csrf", "caseId", "taskId", "briefId", "cursor", "mutations"]) || value.schema_version !== 2 || value.journey !== "advisor-family" || !["advisor", "parent"].includes(String(value.role)) || typeof value.csrf !== "string" || !value.csrf || !uuid(value.caseId) || !nullableUuid(value.taskId) || !nullableUuid(value.briefId) || !Number.isSafeInteger(value.cursor) || Number(value.cursor) < 0 || !validMutations(value.mutations, ADVISOR_OPERATIONS)) return false;
  if (value.role === "advisor") return value.briefId === null;
  return value.taskId === null && value.briefId !== null && value.cursor === 0;
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

export function loadDemoJourneyEnvelope(): DemoJourneyEnvelopeV2 | null {
  const raw = sessionStorage.getItem(KEY);
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as unknown;
    if (!object(value) || (!advisorFamily(value) && !collaboration(value))) {
      sessionStorage.removeItem(KEY);
      return null;
    }
    return value as DemoJourneyEnvelopeV2;
  } catch {
    sessionStorage.removeItem(KEY);
    return null;
  }
}

export function saveRecoveryMetadata(value: AdvisorFamilyJourneyEnvelopeV2): void { sessionStorage.setItem(KEY, JSON.stringify(value)); }
export function saveCollaborationJourney(value: CollaborationJourneyEnvelopeV2): void { sessionStorage.setItem(KEY, JSON.stringify(value)); }
export function clearDemoJourneyEnvelope(): void { sessionStorage.removeItem(KEY); }
export const clearRecoveryMetadata = clearDemoJourneyEnvelope;
export function loadRecoveryMetadata(): AdvisorFamilyJourneyEnvelopeV2 | null { const value = loadDemoJourneyEnvelope(); return value?.journey === "advisor-family" ? value : null; }

export function continueCollaborationAsAdvisorFamily(
  current: CollaborationJourneyEnvelopeV2,
  taskId: string | null,
): AdvisorFamilyJourneyEnvelopeV2 {
  if (
    !object(current)
    || !collaboration(current)
    || current.role !== "advisor"
    || current.phase !== "replan_required"
    || Object.keys(current.mutations).length !== 0
    || !nullableUuid(taskId)
  ) {
    throw new Error("invalid collaboration handoff");
  }
  return {
    schema_version: 2,
    journey: "advisor-family",
    role: "advisor",
    csrf: current.csrf,
    caseId: current.caseId,
    taskId,
    briefId: null,
    cursor: 0,
    mutations: {},
  };
}

export function withMutation(metadata: AdvisorFamilyJourneyEnvelopeV2, operation: AdvisorFamilyMutationKind, record: IdempotencyRecord | undefined): AdvisorFamilyJourneyEnvelopeV2 {
  const mutations = { ...metadata.mutations };
  if (record) mutations[operation] = record; else delete mutations[operation];
  return { ...metadata, mutations };
}

export function withCollaborationMutation(metadata: CollaborationJourneyEnvelopeV2, operation: CollaborationMutationKind, record: IdempotencyRecord | undefined): CollaborationJourneyEnvelopeV2 {
  const mutations = { ...metadata.mutations };
  if (record) mutations[operation] = record; else delete mutations[operation];
  return { ...metadata, mutations };
}
