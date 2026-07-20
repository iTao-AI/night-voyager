export type CollaborationRole = "advisor" | "student" | "parent";
export type MemoryCandidateState = "pending" | "stale" | "expired" | "confirmed" | "rejected";
export type VerificationDecision = "confirm" | "reject";
export type FactKey =
  | "student.intended_field"
  | "student.preferred_countries"
  | "student.intake"
  | "family.risk_tolerance"
  | "family.japan_risk_accepted"
  | "family.budget";

export interface BudgetValue {
  schema_version: 1;
  currency: "CNY";
  period: "program_total";
  preferred_minor: number | null;
  hard_ceiling_minor: number | null;
  elasticity_bps: number;
  refused: boolean;
}

export type FactValue = string | readonly ("australia" | "japan" | "malaysia")[] | boolean | BudgetValue;

export interface CollaborationThread {
  schema_version: 1;
  thread_id: string;
  case_id: string;
  created_by_actor_id: string;
  created_at: string;
}

export interface CollaborationMessage {
  schema_version: 1;
  message_event_id: string;
  thread_id: string;
  case_id: string;
  sequence_no: number;
  actor_id: string;
  actor_role: CollaborationRole;
  body: string;
  content_sha256: string;
  created_at: string;
}

export interface MessagePage {
  schema_version: 1;
  items: readonly CollaborationMessage[];
  next_after_sequence: number | null;
}

export interface MemoryCandidateParticipant {
  schema_version: 1;
  fact_key: FactKey;
  value: FactValue;
  state: MemoryCandidateState;
  created_at: string;
  expires_at: string;
}

export interface MemoryCandidateAdvisor extends MemoryCandidateParticipant {
  candidate_id: string;
  message_event_id: string;
  source_message_sequence_no: number;
  subject_actor_id: string;
  subject_role: CollaborationRole;
  case_revision: number;
  verification_id: string | null;
  decision: VerificationDecision | null;
  reason: string | null;
  request_sha256: string;
  value_sha256: string;
}

export type MemoryCandidateProjection = MemoryCandidateParticipant | MemoryCandidateAdvisor;

export interface MemoryCandidateVerification {
  schema_version: 1;
  verification_id: string;
  candidate_id: string;
  decision: VerificationDecision;
  result_fact_id: string | null;
  result_revision: number | null;
  replayed: boolean;
}

export interface ConfirmedFactParticipant {
  schema_version: 1;
  fact_key: FactKey;
  value: FactValue;
  fact_version: number;
  confirmed_at: string;
  subject_role: CollaborationRole;
  confirming_advisor_role: "advisor";
}

export interface ConfirmedFactAdvisor extends ConfirmedFactParticipant {
  confirmed_fact_id: string;
  candidate_id: string;
  verification_id: string;
  source_message_event_id: string;
  source_message_sequence_no: number;
  source_message_sha256_prefix: string;
  confirming_advisor_actor_id: string;
  reason: string;
  supersedes_fact_id: string | null;
}

export type ConfirmedFactProjection = ConfirmedFactParticipant | ConfirmedFactAdvisor;
export type ConfirmedFactPage =
  | { schema_version: 1; current: readonly ConfirmedFactParticipant[] }
  | { schema_version: 1; current: readonly ConfirmedFactAdvisor[]; history: readonly ConfirmedFactAdvisor[]; next_cursor: string | null };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const SHA256 = /^[0-9a-f]{64}$/;
const SHA_PREFIX = /^[0-9a-f]{12}$/;
const RFC3339 = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/;
const ROLES = ["advisor", "student", "parent"] as const;
const STATES = ["pending", "stale", "expired", "confirmed", "rejected"] as const;
const DECISIONS = ["confirm", "reject"] as const;
const COUNTRIES = ["australia", "japan", "malaysia"] as const;

function invalid(): never { throw new Error("invalid response"); }
function object(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function exact(value: Record<string, unknown>, keys: readonly string[]): boolean {
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  return actual.length === expected.length && actual.every((key, index) => key === expected[index]);
}
function member<T extends string>(value: unknown, values: readonly T[]): value is T { return typeof value === "string" && values.includes(value as T); }
function uuid(value: unknown): value is string { return typeof value === "string" && UUID.test(value); }
function sha(value: unknown): value is string { return typeof value === "string" && SHA256.test(value); }
function timestamp(value: unknown): value is string { return typeof value === "string" && RFC3339.test(value) && !Number.isNaN(Date.parse(value)); }
function positive(value: unknown): value is number { return Number.isSafeInteger(value) && Number(value) > 0; }
function nullableUuid(value: unknown): value is string | null { return value === null || uuid(value); }
function bounded(value: unknown, maximumBytes: number): value is string { return typeof value === "string" && new TextEncoder().encode(value).byteLength >= 1 && new TextEncoder().encode(value).byteLength <= maximumBytes; }
function freeze<T>(value: T): Readonly<T> {
  if (value && typeof value === "object") {
    Object.freeze(value);
    for (const child of Object.values(value as Record<string, unknown>)) freeze(child);
  }
  return value;
}

function factValue(factKey: unknown, value: unknown): value is FactValue {
  switch (factKey) {
    case "student.intended_field": return bounded(value, 160);
    case "student.preferred_countries":
      return Array.isArray(value) && value.length > 0 && value.every((item) => member(item, COUNTRIES)) && new Set(value).size === value.length && value.join() === [...value].sort().join();
    case "student.intake": return typeof value === "string" && /^\d{4}-(?:0[1-9]|1[0-2])$/.test(value);
    case "family.risk_tolerance": return member(value, ["low", "medium", "high"] as const);
    case "family.japan_risk_accepted": return typeof value === "boolean";
    case "family.budget": {
      if (!object(value) || !exact(value, ["schema_version", "currency", "period", "preferred_minor", "hard_ceiling_minor", "elasticity_bps", "refused"])) return false;
      if (value.schema_version !== 1 || value.currency !== "CNY" || value.period !== "program_total" || typeof value.refused !== "boolean" || !Number.isSafeInteger(value.elasticity_bps) || Number(value.elasticity_bps) < 0 || Number(value.elasticity_bps) > 2500) return false;
      const preferred = value.preferred_minor;
      const ceiling = value.hard_ceiling_minor;
      if (value.refused) return preferred === null && ceiling === null;
      return positive(preferred) && positive(ceiling) && preferred <= ceiling;
    }
    default: return false;
  }
}

export function parseCollaborationThread(value: unknown): CollaborationThread {
  if (!object(value) || !exact(value, ["schema_version", "thread_id", "case_id", "created_by_actor_id", "created_at"]) || value.schema_version !== 1 || !uuid(value.thread_id) || !uuid(value.case_id) || !uuid(value.created_by_actor_id) || !timestamp(value.created_at)) invalid();
  return freeze(value as unknown as CollaborationThread);
}

export function parseMessageEvent(value: unknown): CollaborationMessage {
  const keys = ["schema_version", "message_event_id", "thread_id", "case_id", "sequence_no", "actor_id", "actor_role", "body", "content_sha256", "created_at"];
  if (!object(value) || !exact(value, keys) || value.schema_version !== 1 || !uuid(value.message_event_id) || !uuid(value.thread_id) || !uuid(value.case_id) || !positive(value.sequence_no) || !uuid(value.actor_id) || !member(value.actor_role, ROLES) || !bounded(value.body, 4096) || !sha(value.content_sha256) || !timestamp(value.created_at)) invalid();
  return freeze(value as unknown as CollaborationMessage);
}

export function parseMessagePage(value: unknown): MessagePage {
  if (!object(value) || !exact(value, ["schema_version", "items", "next_after_sequence"]) || value.schema_version !== 1 || !Array.isArray(value.items) || !(value.next_after_sequence === null || positive(value.next_after_sequence))) invalid();
  const parsed = { schema_version: 1 as const, items: value.items.map(parseMessageEvent), next_after_sequence: value.next_after_sequence as number | null };
  return freeze(parsed);
}

function parseParticipantCandidate(value: unknown): MemoryCandidateParticipant {
  const keys = ["schema_version", "fact_key", "value", "state", "created_at", "expires_at"];
  if (!object(value) || !exact(value, keys) || value.schema_version !== 1 || !factValue(value.fact_key, value.value) || !member(value.state, STATES) || !timestamp(value.created_at) || !timestamp(value.expires_at)) invalid();
  return freeze(value as unknown as MemoryCandidateParticipant);
}

function parseAdvisorCandidate(value: unknown): MemoryCandidateAdvisor {
  const keys = ["schema_version", "fact_key", "value", "state", "created_at", "expires_at", "candidate_id", "message_event_id", "source_message_sequence_no", "subject_actor_id", "subject_role", "case_revision", "verification_id", "decision", "reason", "request_sha256", "value_sha256"];
  if (!object(value) || !exact(value, keys) || value.schema_version !== 1 || !factValue(value.fact_key, value.value) || !member(value.state, STATES) || !timestamp(value.created_at) || !timestamp(value.expires_at) || !uuid(value.candidate_id) || !uuid(value.message_event_id) || !positive(value.source_message_sequence_no) || !uuid(value.subject_actor_id) || !member(value.subject_role, ROLES) || !positive(value.case_revision) || !nullableUuid(value.verification_id) || !(value.decision === null || member(value.decision, DECISIONS)) || !(value.reason === null || bounded(value.reason, 512)) || !sha(value.request_sha256) || !sha(value.value_sha256)) invalid();
  const terminal = value.decision !== null || value.verification_id !== null || value.reason !== null;
  if (terminal && !(value.decision !== null && value.verification_id !== null && value.reason !== null)) invalid();
  return freeze(value as unknown as MemoryCandidateAdvisor);
}

export function parseMemoryCandidate(value: unknown): MemoryCandidateProjection {
  if (!object(value)) invalid();
  return Object.hasOwn(value, "candidate_id") ? parseAdvisorCandidate(value) : parseParticipantCandidate(value);
}

export function parseMemoryCandidateList(value: unknown): readonly MemoryCandidateProjection[] {
  if (!Array.isArray(value) || value.length > 100) invalid();
  return freeze(value.map(parseMemoryCandidate));
}

export function parseMemoryCandidateVerification(value: unknown): MemoryCandidateVerification {
  const keys = ["schema_version", "verification_id", "candidate_id", "decision", "result_fact_id", "result_revision", "replayed"];
  if (!object(value) || !exact(value, keys) || value.schema_version !== 1 || !uuid(value.verification_id) || !uuid(value.candidate_id) || !member(value.decision, DECISIONS) || !nullableUuid(value.result_fact_id) || !(value.result_revision === null || positive(value.result_revision)) || typeof value.replayed !== "boolean") invalid();
  const paired = (value.result_fact_id === null) === (value.result_revision === null);
  if (!paired || (value.decision === "confirm") !== (value.result_fact_id !== null)) invalid();
  return freeze(value as unknown as MemoryCandidateVerification);
}

function parseParticipantFact(value: unknown): ConfirmedFactParticipant {
  const keys = ["schema_version", "fact_key", "value", "fact_version", "confirmed_at", "subject_role", "confirming_advisor_role"];
  if (!object(value) || !exact(value, keys) || value.schema_version !== 1 || !factValue(value.fact_key, value.value) || !positive(value.fact_version) || !timestamp(value.confirmed_at) || !member(value.subject_role, ROLES) || value.confirming_advisor_role !== "advisor") invalid();
  return freeze(value as unknown as ConfirmedFactParticipant);
}

function parseAdvisorFact(value: unknown): ConfirmedFactAdvisor {
  const keys = ["schema_version", "fact_key", "value", "fact_version", "confirmed_at", "subject_role", "confirming_advisor_role", "confirmed_fact_id", "candidate_id", "verification_id", "source_message_event_id", "source_message_sequence_no", "source_message_sha256_prefix", "confirming_advisor_actor_id", "reason", "supersedes_fact_id"];
  if (!object(value) || !exact(value, keys) || value.schema_version !== 1 || !factValue(value.fact_key, value.value) || !positive(value.fact_version) || !timestamp(value.confirmed_at) || !member(value.subject_role, ROLES) || value.confirming_advisor_role !== "advisor" || !uuid(value.confirmed_fact_id) || !uuid(value.candidate_id) || !uuid(value.verification_id) || !uuid(value.source_message_event_id) || !positive(value.source_message_sequence_no) || typeof value.source_message_sha256_prefix !== "string" || !SHA_PREFIX.test(value.source_message_sha256_prefix) || !uuid(value.confirming_advisor_actor_id) || !bounded(value.reason, 512) || !nullableUuid(value.supersedes_fact_id)) invalid();
  return freeze(value as unknown as ConfirmedFactAdvisor);
}

export function parseConfirmedFactPage(value: unknown): ConfirmedFactPage {
  if (!object(value) || value.schema_version !== 1 || !Array.isArray(value.current)) invalid();
  if (Object.hasOwn(value, "history") || Object.hasOwn(value, "next_cursor")) {
    if (!exact(value, ["schema_version", "current", "history", "next_cursor"]) || !Array.isArray(value.history) || !(value.next_cursor === null || bounded(value.next_cursor, 512))) invalid();
    return freeze({ schema_version: 1 as const, current: value.current.map(parseAdvisorFact), history: value.history.map(parseAdvisorFact), next_cursor: value.next_cursor as string | null });
  }
  if (!exact(value, ["schema_version", "current"])) invalid();
  return freeze({ schema_version: 1 as const, current: value.current.map(parseParticipantFact) });
}
