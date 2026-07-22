import { getPresentationCopy } from "./catalog";
import { presentCode } from "./codes";
import { formatCnyRange } from "./format";
import type { PresentationLocale } from "./locales";

const COUNTRIES = ["australia", "japan", "malaysia"] as const;
const BUDGET_KEYS = [
  "schema_version",
  "currency",
  "period",
  "preferred_minor",
  "hard_ceiling_minor",
  "elasticity_bps",
  "refused",
] as const;

function unavailable(locale: PresentationLocale): string {
  return getPresentationCopy(locale, "statusUnavailable");
}

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function exact(value: Record<string, unknown>, keys: readonly string[]): boolean {
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  return actual.length === expected.length
    && actual.every((key, index) => key === expected[index]);
}

function bounded(value: unknown, maximumBytes: number): value is string {
  return typeof value === "string"
    && new TextEncoder().encode(value).byteLength >= 1
    && new TextEncoder().encode(value).byteLength <= maximumBytes;
}

function positive(value: unknown): value is number {
  return Number.isSafeInteger(value) && Number(value) > 0;
}

function preferredCountries(value: unknown): value is readonly (typeof COUNTRIES)[number][] {
  return Array.isArray(value)
    && value.length > 0
    && value.every((item) => typeof item === "string" && COUNTRIES.includes(item as (typeof COUNTRIES)[number]))
    && new Set(value).size === value.length
    && value.join() === [...value].sort().join();
}

function budget(locale: PresentationLocale, value: unknown): string | null {
  if (!object(value) || !exact(value, BUDGET_KEYS)) return null;
  if (
    value.schema_version !== 1
    || value.currency !== "CNY"
    || value.period !== "program_total"
    || typeof value.refused !== "boolean"
    || !Number.isSafeInteger(value.elasticity_bps)
    || Number(value.elasticity_bps) < 0
    || Number(value.elasticity_bps) > 2500
  ) return null;
  if (value.refused) {
    return value.preferred_minor === null && value.hard_ceiling_minor === null
      ? getPresentationCopy(locale, "factValueBudgetRefused")
      : null;
  }
  if (
    !positive(value.preferred_minor)
    || !positive(value.hard_ceiling_minor)
    || value.preferred_minor > value.hard_ceiling_minor
  ) return null;
  return formatCnyRange(locale, value.preferred_minor, value.hard_ceiling_minor, value.currency);
}

export function presentConfirmedFactValue(
  locale: PresentationLocale,
  factKey: unknown,
  value: unknown,
): string {
  switch (factKey) {
    case "student.intended_field":
      return bounded(value, 160) ? value : unavailable(locale);
    case "student.preferred_countries":
      return preferredCountries(value)
        ? value.map((country) => presentCode(locale, "country", country)).join(locale === "zh-CN" ? "、" : ", ")
        : unavailable(locale);
    case "student.intake":
      return typeof value === "string" && /^\d{4}-(?:0[1-9]|1[0-2])$/.test(value)
        ? value
        : unavailable(locale);
    case "family.risk_tolerance":
      return presentCode(locale, "riskTolerance", value);
    case "family.japan_risk_accepted":
      return typeof value === "boolean"
        ? getPresentationCopy(locale, value ? "factValueAccepted" : "factValueNotAccepted")
        : unavailable(locale);
    case "family.budget":
      return budget(locale, value) ?? unavailable(locale);
    default:
      return unavailable(locale);
  }
}
