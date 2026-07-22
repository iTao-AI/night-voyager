import { describe, expect, it } from "vitest";

import { presentConfirmedFactValue } from "../../lib/presentation/facts";

const refusedBudget = {
  schema_version: 1,
  currency: "CNY",
  period: "program_total",
  preferred_minor: null,
  hard_ceiling_minor: null,
  elasticity_bps: 0,
  refused: true,
};

describe("closed confirmed-fact presentation", () => {
  it.each([
    ["zh-CN", "家庭选择不提供预算", "未接受"],
    ["en", "The family chose not to provide a budget", "Not accepted"],
  ] as const)("presents valid refusal and false values in %s", (locale, budget, accepted) => {
    expect(presentConfirmedFactValue(locale, "family.budget", refusedBudget)).toBe(budget);
    expect(presentConfirmedFactValue(locale, "family.japan_risk_accepted", false)).toBe(accepted);
  });

  it.each(["zh-CN", "en"] as const)("does not expose unknown or malformed values in %s", (locale) => {
    const unknown = presentConfirmedFactValue(locale, "family.raw-secret", "raw-value-secret");
    const malformed = presentConfirmedFactValue(locale, "family.budget", {
      ...refusedBudget,
      raw: "raw-budget-secret",
    });
    const fallback = locale === "zh-CN" ? "状态暂不可用" : "Status unavailable";

    expect(unknown).toBe(fallback);
    expect(malformed).toBe(fallback);
    expect(`${unknown}${malformed}`).not.toMatch(/raw-value-secret|raw-budget-secret|family\.raw-secret/);
  });
});
