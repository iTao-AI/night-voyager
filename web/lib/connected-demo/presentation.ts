const OUTCOME_COPY = new Map<string, string>([
  ["recommended_with_condition", "Recommended with budget condition"],
  ["conditional", "Conditional alternative"],
  ["blocked", "Blocked"],
]);

const REASON_COPY = new Map<string, string>([
  [
    "complete_cost_and_fx_within_boundary",
    "Cost and FX evidence are within the approved boundary",
  ],
  ["synthetic_high_risk_alternative", "Higher-risk synthetic alternative"],
  ["direct_program_fit_evidence_absent", "Program-fit evidence is missing"],
]);

const TRADE_OFF_COPY = new Map<string, string>([
  ["budget_elasticity", "Budget flexibility"],
]);

function requireCnyMinor(minor: unknown, currency: unknown): number {
  if (
    currency !== "CNY"
    || typeof minor !== "number"
    || !Number.isSafeInteger(minor)
    || minor <= 0
  ) {
    throw new Error("unsupported_money_presentation");
  }
  return minor;
}

function groupDigits(value: bigint): string {
  return value.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function cnyValue(minor: number): string {
  const exact = BigInt(minor);
  const units = groupDigits(exact / 100n);
  const remainder = exact % 100n;
  return remainder === 0n ? units : `${units}.${remainder.toString().padStart(2, "0")}`;
}

function present(code: unknown, copy: ReadonlyMap<string, string>): string {
  if (typeof code !== "string") throw new Error("unsupported_presentation_code");
  const value = copy.get(code);
  if (value === undefined) throw new Error("unsupported_presentation_code");
  return value;
}

export function formatCnyMinor(minor: unknown, currency: unknown): string {
  return `${cnyValue(requireCnyMinor(minor, currency))} CNY`;
}

export function formatCnyRange(
  minimumMinor: unknown,
  maximumMinor: unknown,
  currency: unknown,
): string {
  const minimum = requireCnyMinor(minimumMinor, currency);
  const maximum = requireCnyMinor(maximumMinor, currency);
  if (minimum > maximum) throw new Error("unsupported_money_presentation");
  return `${cnyValue(minimum)}–${cnyValue(maximum)} CNY`;
}

export function presentRouteOutcome(code: unknown): string {
  return present(code, OUTCOME_COPY);
}

export function presentRouteReason(code: unknown): string {
  return present(code, REASON_COPY);
}

export function presentTradeOff(code: unknown): string {
  return present(code, TRADE_OFF_COPY);
}
