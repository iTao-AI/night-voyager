import type { BudgetValue } from "./contracts";

export interface BudgetDraft {
  preferredYuan: string;
  hardCeilingYuan: string;
}

export interface CollaborationBudgetIntent {
  schema_version: 1;
  expected_case_revision: number;
  value: BudgetValue;
}

export type BudgetDraftField = "preferred" | "hard_ceiling" | "form";
export type BudgetValidationCode =
  | "required"
  | "whole_yuan_positive"
  | "safe_integer"
  | "preferred_exceeds_ceiling"
  | "invalid_revision";

export interface BudgetValidationIssue {
  field: BudgetDraftField;
  code: BudgetValidationCode;
}

export type BudgetValidation =
  | { ok: true; intent: Readonly<CollaborationBudgetIntent> }
  | { ok: false; error: BudgetValidationIssue };

export const BUDGET_ELASTICITY_BPS = 1_000;
export const DEFAULT_BUDGET_DRAFT: Readonly<BudgetDraft> = Object.freeze({
  preferredYuan: "300000",
  hardCeilingYuan: "400000",
});
export const TIGHT_BUDGET_DRAFT: Readonly<BudgetDraft> = Object.freeze({
  preferredYuan: "100000",
  hardCeilingYuan: "120000",
});

const MAX_SAFE_BIGINT = BigInt(Number.MAX_SAFE_INTEGER);
const BUDGET_VALUE_KEYS = [
  "schema_version",
  "currency",
  "period",
  "preferred_minor",
  "hard_ceiling_minor",
  "elasticity_bps",
  "refused",
] as const;

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function exact(value: Record<string, unknown>, keys: readonly string[]): boolean {
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  return actual.length === expected.length && actual.every((key, index) => key === expected[index]);
}

function positiveSafeInteger(value: unknown): value is number {
  return Number.isSafeInteger(value) && Number(value) > 0;
}

function parseWholeYuan(raw: string, field: Exclude<BudgetDraftField, "form">): { ok: true; minor: number } | { ok: false; error: BudgetValidationIssue } {
  const normalized = raw.trim();
  if (!normalized) return { ok: false, error: { field, code: "required" } };
  if (!/^\d+$/.test(normalized)) return { ok: false, error: { field, code: "whole_yuan_positive" } };

  const minor = BigInt(normalized) * 100n;
  if (minor <= 0n) return { ok: false, error: { field, code: "whole_yuan_positive" } };
  if (minor > MAX_SAFE_BIGINT) return { ok: false, error: { field, code: "safe_integer" } };
  return { ok: true, minor: Number(minor) };
}

function freeze<T>(value: T): Readonly<T> {
  if (value && typeof value === "object") {
    Object.freeze(value);
    for (const child of Object.values(value as Record<string, unknown>)) freeze(child);
  }
  return value;
}

export function validateBudgetDraft(draft: BudgetDraft, expectedCaseRevision: number): BudgetValidation {
  if (!Number.isSafeInteger(expectedCaseRevision) || expectedCaseRevision <= 0) {
    return { ok: false, error: { field: "form", code: "invalid_revision" } };
  }
  const preferred = parseWholeYuan(draft.preferredYuan, "preferred");
  if (!preferred.ok) return preferred;
  const hardCeiling = parseWholeYuan(draft.hardCeilingYuan, "hard_ceiling");
  if (!hardCeiling.ok) return hardCeiling;
  if (preferred.minor > hardCeiling.minor) {
    return { ok: false, error: { field: "hard_ceiling", code: "preferred_exceeds_ceiling" } };
  }

  return {
    ok: true,
    intent: freeze({
      schema_version: 1 as const,
      expected_case_revision: expectedCaseRevision,
      value: {
        schema_version: 1 as const,
        currency: "CNY" as const,
        period: "program_total" as const,
        preferred_minor: preferred.minor,
        hard_ceiling_minor: hardCeiling.minor,
        elasticity_bps: BUDGET_ELASTICITY_BPS,
        refused: false,
      },
    }),
  };
}

export function createBudgetIntent(draft: BudgetDraft, expectedCaseRevision: number): Readonly<CollaborationBudgetIntent> {
  const result = validateBudgetDraft(draft, expectedCaseRevision);
  if (!result.ok) throw new Error(`invalid budget intent: ${result.error.code}`);
  return result.intent;
}

export function isBudgetValue(value: unknown): value is BudgetValue {
  if (!object(value) || !exact(value, BUDGET_VALUE_KEYS)) return false;
  if (
    value.schema_version !== 1
    || value.currency !== "CNY"
    || value.period !== "program_total"
    || typeof value.refused !== "boolean"
    || !Number.isSafeInteger(value.elasticity_bps)
    || Number(value.elasticity_bps) < 0
    || Number(value.elasticity_bps) > 2_500
  ) return false;
  if (value.refused) return value.preferred_minor === null && value.hard_ceiling_minor === null;
  return positiveSafeInteger(value.preferred_minor)
    && positiveSafeInteger(value.hard_ceiling_minor)
    && value.preferred_minor <= value.hard_ceiling_minor;
}

export function isBudgetIntent(value: unknown): value is CollaborationBudgetIntent {
  if (
    !object(value)
    || !exact(value, ["schema_version", "expected_case_revision", "value"])
    || value.schema_version !== 1
    || !positiveSafeInteger(value.expected_case_revision)
    || !isBudgetValue(value.value)
  ) return false;
  return !value.value.refused
    && value.value.preferred_minor !== null
    && value.value.hard_ceiling_minor !== null
    && value.value.preferred_minor % 100 === 0
    && value.value.hard_ceiling_minor % 100 === 0;
}

export function budgetValueMatchesIntent(value: unknown, intent: CollaborationBudgetIntent | null): boolean {
  if (!intent || !isBudgetIntent(intent) || !isBudgetValue(value)) return false;
  return value.schema_version === intent.value.schema_version
    && value.currency === intent.value.currency
    && value.period === intent.value.period
    && value.preferred_minor === intent.value.preferred_minor
    && value.hard_ceiling_minor === intent.value.hard_ceiling_minor
    && value.elasticity_bps === intent.value.elasticity_bps
    && value.refused === intent.value.refused;
}

export function budgetDraftFromIntent(intent: CollaborationBudgetIntent): BudgetDraft {
  if (!isBudgetIntent(intent) || intent.value.preferred_minor === null || intent.value.hard_ceiling_minor === null) {
    throw new Error("invalid budget intent");
  }
  return {
    preferredYuan: String(intent.value.preferred_minor / 100),
    hardCeilingYuan: String(intent.value.hard_ceiling_minor / 100),
  };
}

function formatWholeYuan(minor: number): string {
  if (!Number.isSafeInteger(minor) || minor <= 0 || minor % 100 !== 0) throw new Error("invalid whole-yuan budget");
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0, useGrouping: true }).format(minor / 100);
}

export function renderBudgetMessage(intent: CollaborationBudgetIntent): string {
  if (!isBudgetIntent(intent) || intent.value.preferred_minor === null || intent.value.hard_ceiling_minor === null) throw new Error("invalid budget intent");
  return `Our confirmed program budget is ${formatWholeYuan(intent.value.preferred_minor)} to ${formatWholeYuan(intent.value.hard_ceiling_minor)} CNY.`;
}

export function messageRequestForBudget(intent: CollaborationBudgetIntent) {
  return { schema_version: 1 as const, body: renderBudgetMessage(intent) };
}

export function proposalRequestForBudget(intent: CollaborationBudgetIntent) {
  return {
    schema_version: 1 as const,
    case_revision: intent.expected_case_revision,
    proposal: {
      schema_version: 1 as const,
      fact_key: "family.budget" as const,
      value: intent.value,
    },
  };
}

export function defaultBudgetIntent(expectedCaseRevision = 1): Readonly<CollaborationBudgetIntent> {
  return createBudgetIntent(DEFAULT_BUDGET_DRAFT, expectedCaseRevision);
}
