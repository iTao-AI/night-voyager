import type { PlanExecutionRole } from "./contracts";
import type { PlanExecutionIdempotencyRecord } from "./idempotency";

export interface PlanExecutionEnvelopeV1 {
  schema_version: 1;
  journey: "plan-execution";
  role: PlanExecutionRole;
  caseId: string;
  timelinePlanId: string;
  executionId: string | null;
  executionVersion: number | null;
  checkpointId: string | null;
  checkpointVersion: number | null;
  lastReceiptId: string | null;
  mutations: Partial<Record<"start" | "attest" | "verify" | "reassess", PlanExecutionIdempotencyRecord>>;
}
const KEY = "night-voyager:plan-execution:v1";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const SHA = /^[0-9a-f]{64}$/;
function uuid(value: unknown): value is string { return typeof value === "string" && UUID.test(value); }
function nullableUuid(value: unknown): value is string | null { return value === null || uuid(value); }
function nullableVersion(value: unknown): value is number | null {
  return value === null || (Number.isSafeInteger(value) && Number(value) > 0);
}
function valid(value: unknown): value is PlanExecutionEnvelopeV1 {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const item = value as Record<string, unknown>;
  if (Object.keys(item).sort().join(",") !== "caseId,checkpointId,checkpointVersion,executionId,executionVersion,journey,lastReceiptId,mutations,role,schema_version,timelinePlanId") return false;
  if (item.schema_version !== 1 || item.journey !== "plan-execution"
    || !["advisor", "student", "parent"].includes(String(item.role))
    || !uuid(item.caseId) || !uuid(item.timelinePlanId) || !nullableUuid(item.executionId)
    || !nullableVersion(item.executionVersion) || !nullableUuid(item.checkpointId)
    || !nullableVersion(item.checkpointVersion) || !nullableUuid(item.lastReceiptId)
    || typeof item.mutations !== "object" || item.mutations === null || Array.isArray(item.mutations)) return false;
  return Object.entries(item.mutations).every(([operation, record]) => {
    if (!["start", "attest", "verify", "reassess"].includes(operation)
      || typeof record !== "object" || record === null || Array.isArray(record)) return false;
    const candidate = record as Record<string, unknown>;
    return Object.keys(candidate).sort().join(",") === "fingerprint,idempotencyKey"
      && typeof candidate.fingerprint === "string" && SHA.test(candidate.fingerprint)
      && uuid(candidate.idempotencyKey);
  });
}
export function loadPlanExecutionEnvelope(): PlanExecutionEnvelopeV1 | null {
  const raw = sessionStorage.getItem(KEY);
  if (!raw) return null;
  try {
    const value: unknown = JSON.parse(raw);
    if (!valid(value)) throw new Error("invalid envelope");
    return value;
  } catch {
    sessionStorage.removeItem(KEY);
    return null;
  }
}
export function savePlanExecutionEnvelope(value: PlanExecutionEnvelopeV1): void {
  if (!valid(value)) throw new Error("invalid plan execution envelope");
  sessionStorage.setItem(KEY, JSON.stringify(value));
}
export function clearPlanExecutionEnvelope(): void { sessionStorage.removeItem(KEY); }
