import { describe, expect, it } from "vitest";

import {
  formatCnyMinor,
  formatCnyRange,
} from "../../lib/presentation/format";
import {
  presentRouteOutcome,
  presentRouteReason,
  presentTradeOff,
} from "../../lib/presentation/codes";

describe("connected demo presentation contract", () => {
  it("formats CNY minor units with exact integer arithmetic", () => {
    expect(formatCnyMinor("en", 30_550_000, "CNY")).toBe("CNY 305,500");
    expect(formatCnyMinor("en", Number.MAX_SAFE_INTEGER - 1, "CNY")).toBe(
      "CNY 90,071,992,547,409.90",
    );
    expect(formatCnyMinor("en", Number.MAX_SAFE_INTEGER, "CNY")).toBe(
      "CNY 90,071,992,547,409.91",
    );
    expect(formatCnyRange("en", 30_550_000, 40_000_000, "CNY")).toBe(
      "CNY 305,500–400,000",
    );
  });

  it.each([
    [-1, "CNY"],
    [1.5, "CNY"],
    [Number.MAX_SAFE_INTEGER + 1, "CNY"],
    [100, "USD"],
  ])("rejects unsupported money presentation: %s %s", (minor, currency) => {
    expect(formatCnyMinor("en", minor, currency)).toBe("Status unavailable");
  });

  it("rejects a reversed CNY range", () => {
    expect(formatCnyRange("en", 40_000_000, 30_550_000, "CNY")).toBe(
      "Status unavailable",
    );
  });

  it.each([
    ["recommended_with_condition", "Recommended with budget condition"],
    ["conditional", "Conditional alternative"],
    ["blocked", "Blocked"],
  ])("presents route outcome %s", (code, copy) => {
    expect(presentRouteOutcome("en", code)).toBe(copy);
  });

  it.each([
    [
      "complete_cost_and_fx_within_boundary",
      "Cost and FX evidence are within the approved boundary",
    ],
    ["synthetic_high_risk_alternative", "Higher-risk synthetic alternative"],
    ["direct_program_fit_evidence_absent", "Program-fit evidence is missing"],
  ])("presents route reason %s", (code, copy) => {
    expect(presentRouteReason("en", code)).toBe(copy);
  });

  it("presents the approved trade-off", () => {
    expect(presentTradeOff("en", "budget_elasticity")).toBe("Budget flexibility");
  });

  it.each([
    () => presentRouteOutcome("en", "unknown"),
    () => presentRouteReason("en", "__proto__"),
    () => presentTradeOff("en", "unknown"),
  ])("fails closed for unknown presentation codes", (present) => {
    expect(present()).toBe("Status unavailable");
  });
});
