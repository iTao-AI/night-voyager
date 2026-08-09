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

  it("keeps the exact advisor workspace promise and canonical product identity", () => {
    expect(zhCN.productPromise).toBe("留学顾问的 AI 协作工作台");
    expect(zhCN.productName).toBe("Night Voyager");
    expect(en.productName).toBe("Night Voyager");
  });

  it("freezes the advisor-first portfolio thesis in both locales", () => {
    expect(zhCN.rootTitle).toBe("把零散咨询，整理成可以推进的留学方案");
    expect(zhCN.rootSummary).toBe(
      "Night Voyager 帮助顾问整理客户信息、核对证据、比较留学路线并推进后续计划。AI 负责研究与草拟，关键判断仍由顾问确认。",
    );
    expect(en.rootTitle).toBe("Turn scattered consultations into a client plan you can move forward");
    expect(en.rootSummary).toMatch(/organize.*evidence.*compare.*advisor/i);
    expect(zhCN.rootPrimaryAction).toBe("查看一次完整咨询流程");
    expect(zhCN.rootSecondaryAction).toBe("了解方案如何被核对");
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

  it("freezes the bilingual revision journey vocabulary", () => {
    expect(zhCN.requestRevisionAction).toBe("请求修订");
    expect(zhCN.submitRevisionProposalAction).toBe("提交变更提案");
    expect(zhCN.previousPlanLabel).toBe("保留的上一版计划");
    expect(zhCN.currentRevisedPlanLabel).toBe("当前修订计划");
    expect(zhCN.continueFamilyDecisionAction).toBe("继续家庭决定");
    expect(en.requestRevisionAction).toBe("Request revision");
    expect(en.submitRevisionProposalAction).toBe("Submit change proposal");
    expect(en.previousPlanLabel).toBe("Previous plan retained for history");
    expect(en.currentRevisedPlanLabel).toBe("Current revised plan");
    expect(en.continueFamilyDecisionAction).toBe("Continue family decision");
  });
});
