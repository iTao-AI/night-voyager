import { isIntakeMonth } from "./intake";
import { isBudgetValue, validateBudgetDraft, type BudgetDraft } from "../collaboration-demo/budget";
import type { BudgetValue, ConfirmedFactProjection, MemoryCandidateAdvisor } from "../collaboration-demo/contracts";
import type { CurrentFactsProjection } from "./use-connected-demo";
import type { Country } from "./contracts";

export const REVISION_COUNTRIES: readonly Country[] = ["australia", "japan", "malaysia"];
export type RevisionFactKey = "student.preferred_countries" | "family.budget" | "student.intake";
export type RevisionIntent =
  | { expectedCaseRevision: number; factKey: "student.preferred_countries"; value: readonly Country[] }
  | { expectedCaseRevision: number; factKey: "family.budget"; value: BudgetValue }
  | { expectedCaseRevision: number; factKey: "student.intake"; value: string };
export type RevisionValidation =
  | { ok: true; intent: RevisionIntent }
  | { ok: false; code: "stale" | "unavailable" | "invalid" | "unchanged" };

export function revisionFact(facts: readonly ConfirmedFactProjection[], key: RevisionFactKey): ConfirmedFactProjection | null {
  const matches = facts.filter((fact) => fact.fact_key === key);
  return matches.length === 1 ? matches[0] : null;
}

export function isRevisionCountries(value: unknown): value is readonly Country[] {
  return Array.isArray(value) && value.length > 0
    && value.every((country) => REVISION_COUNTRIES.includes(country))
    && new Set(value).size === value.length;
}

function editableBudget(value: unknown): value is BudgetValue {
  return isBudgetValue(value) && !value.refused
    && value.preferred_minor !== null && value.hard_ceiling_minor !== null;
}

export function isRevisionIntent(value: unknown): value is RevisionIntent {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  if (Object.keys(record).sort().join() !== "expectedCaseRevision,factKey,value"
    || !Number.isSafeInteger(record.expectedCaseRevision) || Number(record.expectedCaseRevision) <= 0) return false;
  if (record.factKey === "student.intake") return isIntakeMonth(record.value);
  return record.factKey === "student.preferred_countries"
    ? isRevisionCountries(record.value)
    : record.factKey === "family.budget" && editableBudget(record.value)
      && record.value.preferred_minor! % 100 === 0 && record.value.hard_ceiling_minor! % 100 === 0;
}

export function validateRevisionIntent(intent: RevisionIntent, current: CurrentFactsProjection | null): RevisionValidation {
  if (!current) return { ok: false, code: "unavailable" };
  if (intent.expectedCaseRevision !== current.caseRevision) return { ok: false, code: "stale" };
  if (!isRevisionIntent(intent)) return { ok: false, code: "invalid" };
  const fact = revisionFact(current.facts, intent.factKey);
  if (!fact) return { ok: false, code: "unavailable" };
  if (intent.factKey === "student.intake") {
    if (fact.subject_role !== "student" || !isIntakeMonth(fact.value)) return { ok: false, code: "unavailable" };
    if (intent.value === fact.value) return { ok: false, code: "unchanged" };
    return { ok: true, intent: { ...intent } };
  }
  if (intent.factKey === "student.preferred_countries") {
    if (!isRevisionCountries(fact.value)) return { ok: false, code: "unavailable" };
    const value = [...intent.value].sort();
    if (value.join() === [...fact.value].sort().join()) return { ok: false, code: "unchanged" };
    return { ok: true, intent: { ...intent, value } };
  }
  if (!editableBudget(fact.value)) return { ok: false, code: "unavailable" };
  const budget = fact.value;
  const proposed = intent.value;
  if (proposed.schema_version !== budget.schema_version || proposed.currency !== budget.currency
    || proposed.period !== budget.period || proposed.elasticity_bps !== budget.elasticity_bps
    || proposed.refused !== budget.refused) return { ok: false, code: "invalid" };
  if (proposed.preferred_minor === budget.preferred_minor && proposed.hard_ceiling_minor === budget.hard_ceiling_minor) return { ok: false, code: "unchanged" };
  return { ok: true, intent: { ...intent, value: { ...proposed } } };
}

export function validateBudgetRevision(draft: BudgetDraft, expectedCaseRevision: number, current: CurrentFactsProjection | null): RevisionValidation {
  const parsed = validateBudgetDraft(draft, expectedCaseRevision);
  if (!parsed.ok) return { ok: false, code: "invalid" };
  const budget = current ? revisionFact(current.facts, "family.budget")?.value : null;
  if (!editableBudget(budget)) return { ok: false, code: "unavailable" };
  return validateRevisionIntent({ expectedCaseRevision, factKey: "family.budget", value: { ...budget, preferred_minor: parsed.intent.value.preferred_minor, hard_ceiling_minor: parsed.intent.value.hard_ceiling_minor } }, current);
}

export function pendingRevisionCandidate(candidates: readonly MemoryCandidateAdvisor[], expectedCaseRevision: number): MemoryCandidateAdvisor | null {
  const matches = candidates.filter((candidate) => candidate.state === "pending"
    && candidate.case_revision === expectedCaseRevision
    && ["student.preferred_countries", "family.budget", "student.intake"].includes(candidate.fact_key));
  if (matches.length !== 1) return null;
  const candidate = matches[0];
  const valid = candidate.fact_key === "student.intake"
    ? candidate.subject_role === "student" && isIntakeMonth(candidate.value)
    : candidate.fact_key === "student.preferred_countries"
    ? isRevisionCountries(candidate.value)
    : editableBudget(candidate.value);
  return valid ? candidate : null;
}

export function revisionProposalBody(intent: RevisionIntent) {
  return { schema_version: 1 as const, case_revision: intent.expectedCaseRevision, proposal: { schema_version: 1 as const, fact_key: intent.factKey, value: intent.value } };
}

export function revisionMessageBody(intent: RevisionIntent) {
  return { schema_version: 1 as const, body: `For this synthetic revision ${intent.expectedCaseRevision}, I propose ${intent.factKey}: ${JSON.stringify(intent.value)}.` };
}

export function validRevisionReason(reason: string): boolean {
  const bytes = new TextEncoder().encode(reason.trim()).byteLength;
  return bytes > 0 && bytes <= 512;
}
