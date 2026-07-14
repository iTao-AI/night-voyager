import type { IdempotencyRecord } from "./idempotency";

export type MutationOperation = "create-task" | "advisor-review" | "family-decision";
export interface RecoveryMetadata {
  role: "advisor" | "parent";
  csrf: string;
  caseId: string;
  taskId: string | null;
  briefId: string | null;
  cursor: number;
  mutations: Partial<Record<MutationOperation, IdempotencyRecord>>;
}

const KEY = "night-voyager:m5";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const OPERATIONS: MutationOperation[] = ["create-task", "advisor-review", "family-decision"];
function canonicalUuid(value: unknown): value is string { return typeof value === "string" && UUID.test(value); }
function validMutations(value: unknown): value is RecoveryMetadata["mutations"] {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  return Object.entries(value).every(([operation, record]) =>
    OPERATIONS.includes(operation as MutationOperation) &&
    typeof record === "object" && record !== null && !Array.isArray(record) &&
    Object.keys(record).sort().join(",") === "fingerprint,idempotencyKey" &&
    typeof (record as IdempotencyRecord).fingerprint === "string" && /^[0-9a-f]{64}$/.test((record as IdempotencyRecord).fingerprint) &&
    canonicalUuid((record as IdempotencyRecord).idempotencyKey),
  );
}

export function saveRecoveryMetadata(value: RecoveryMetadata): void { sessionStorage.setItem(KEY, JSON.stringify(value)); }
export function clearRecoveryMetadata(): void { sessionStorage.removeItem(KEY); }
export function loadRecoveryMetadata(): RecoveryMetadata | null {
  const raw = sessionStorage.getItem(KEY);
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as Partial<RecoveryMetadata>;
    if (
      Object.keys(value).sort().join(",") !== "briefId,caseId,csrf,cursor,mutations,role,taskId" ||
      !["advisor", "parent"].includes(String(value.role)) || typeof value.csrf !== "string" || !value.csrf ||
      !canonicalUuid(value.caseId) || !(value.taskId === null || canonicalUuid(value.taskId)) ||
      !(value.briefId === null || canonicalUuid(value.briefId)) || !Number.isSafeInteger(value.cursor) || Number(value.cursor) < 0 ||
      !validMutations(value.mutations)
    ) return null;
    if (value.role === "advisor" && value.briefId !== null) return null;
    if (value.role === "parent" && (value.taskId !== null || value.briefId === null || value.cursor !== 0)) return null;
    return value as RecoveryMetadata;
  } catch { return null; }
}

export function withMutation(
  metadata: RecoveryMetadata,
  operation: MutationOperation,
  record: IdempotencyRecord | undefined,
): RecoveryMetadata {
  const mutations = { ...metadata.mutations };
  if (record) mutations[operation] = record;
  else delete mutations[operation];
  return { ...metadata, mutations };
}
