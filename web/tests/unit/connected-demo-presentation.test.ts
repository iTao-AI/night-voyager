import { describe, expect, it } from "vitest";

import {
  formatCnyMinor,
  formatCnyRange,
  presentRouteOutcome,
  presentRouteReason,
  presentTradeOff,
} from "../../lib/connected-demo/presentation";

describe("connected demo presentation contract", () => {
  it("formats CNY minor units with exact integer arithmetic", () => {
    expect(formatCnyMinor(30_550_000, "CNY")).toBe("305,500 CNY");
    expect(formatCnyMinor(Number.MAX_SAFE_INTEGER - 1, "CNY")).toBe(
      "90,071,992,547,409.90 CNY",
    );
    expect(formatCnyMinor(Number.MAX_SAFE_INTEGER, "CNY")).toBe(
      "90,071,992,547,409.91 CNY",
    );
    expect(formatCnyRange(30_550_000, 40_000_000, "CNY")).toBe(
      "305,500–400,000 CNY",
    );
  });

  it.each([
    [0, "CNY"],
    [-1, "CNY"],
    [1.5, "CNY"],
    [Number.MAX_SAFE_INTEGER + 1, "CNY"],
    [100, "USD"],
  ])("rejects unsupported money presentation: %s %s", (minor, currency) => {
    expect(() => formatCnyMinor(minor, currency)).toThrowError(
      "unsupported_money_presentation",
    );
  });

  it("rejects a reversed CNY range", () => {
    expect(() => formatCnyRange(40_000_000, 30_550_000, "CNY")).toThrowError(
      "unsupported_money_presentation",
    );
  });

  it.each([
    ["recommended_with_condition", "Recommended with budget condition"],
    ["conditional", "Conditional alternative"],
    ["blocked", "Blocked"],
  ])("presents route outcome %s", (code, copy) => {
    expect(presentRouteOutcome(code)).toBe(copy);
  });

  it.each([
    [
      "complete_cost_and_fx_within_boundary",
      "Cost and FX evidence are within the approved boundary",
    ],
    ["synthetic_high_risk_alternative", "Higher-risk synthetic alternative"],
    ["direct_program_fit_evidence_absent", "Program-fit evidence is missing"],
  ])("presents route reason %s", (code, copy) => {
    expect(presentRouteReason(code)).toBe(copy);
  });

  it("presents the approved trade-off", () => {
    expect(presentTradeOff("budget_elasticity")).toBe("Budget flexibility");
  });

  it.each([
    () => presentRouteOutcome("unknown"),
    () => presentRouteReason("__proto__"),
    () => presentTradeOff("unknown"),
  ])("fails closed for unknown presentation codes", (present) => {
    expect(present).toThrowError("unsupported_presentation_code");
  });
});
