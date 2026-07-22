import { describe, expect, it } from "vitest";

import { en, getPresentationCopy, zhCN } from "../../lib/presentation/catalog";

describe("presentation catalog contract", () => {
  it("keeps exact key parity and bounded non-empty copy", () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(zhCN).sort());

    for (const catalog of [zhCN, en]) {
      for (const value of Object.values(catalog)) {
        expect(value.trim().length).toBeGreaterThan(0);
        expect(value.length).toBeLessThanOrEqual(240);
      }
    }
  });

  it("keeps the exact approved Chinese promise and canonical product identity", () => {
    expect(zhCN.productPromise).toBe("把家庭事实变成可追溯的留学决策与行动计划");
    expect(zhCN.productName).toBe("Night Voyager");
    expect(en.productName).toBe("Night Voyager");
  });

  it("does not use raw contract codes as visible copy", () => {
    const forbidden = [
      "recommended_with_condition",
      "needs_advisor_review",
      "expired_or_terminal",
      "legacy_unpinned",
    ];
    for (const value of [...Object.values(zhCN), ...Object.values(en)]) {
      expect(forbidden).not.toContain(value);
    }
  });

  it("returns copy only through the closed locale and key contract", () => {
    expect(getPresentationCopy("zh-CN", "statusUnavailable")).toBe("状态暂不可用");
    expect(getPresentationCopy("en", "statusUnavailable")).toBe("Status unavailable");
  });
});
