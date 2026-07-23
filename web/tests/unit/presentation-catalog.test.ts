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
    expect(zhCN.productPromise).toBe("你的留学路线应该从你出发");
    expect(zhCN.productName).toBe("Night Voyager");
    expect(en.productName).toBe("Night Voyager");
  });

  it("freezes the student-first portfolio thesis in both locales", () => {
    expect(zhCN.rootTitleLineOne).toBe("你的留学路线");
    expect(zhCN.rootTitleLineTwo).toBe("应该从你出发");
    expect(zhCN.rootSummary).toBe(
      "不只告诉你去哪留学，更要说清为什么适合你。看懂不同路线的理由与取舍，再把选择变成一份可以执行的计划。",
    );
    expect(en.rootTitleLineOne).toBe("Your study-abroad route");
    expect(en.rootTitleLineTwo).toBe("should start with you");
    expect(en.rootSummary).toMatch(/why.*fits.*trade-offs.*actionable plan/i);
    expect(zhCN.rootPrimaryAction).toBe("查看示例方案");
    expect(zhCN.rootSecondaryAction).toBe("查看路线依据");
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
