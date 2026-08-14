import { describe, expect, it } from "vitest";

import { en, getPresentationCopy, zhCN } from "../../lib/presentation/catalog";

describe("presentation catalog contract", () => {
  it("keeps exact key parity and bounded non-empty copy", () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(zhCN).sort());

    for (const catalog of [zhCN, en]) {
      for (const value of Object.values(catalog)) {
        expect(value.trim().length).toBeGreaterThan(0);
        expect(value.length).toBeLessThanOrEqual(360);
      }
    }
  });

  it("keeps the exact advisor workspace promise and canonical product identity", () => {
    expect(zhCN.productPromise).toBe("为留学顾问打造的 AI 协作平台");
    expect(zhCN.productName).toBe("Night Voyager");
    expect(en.productName).toBe("Night Voyager");
  });

  it("freezes the advisor-first portfolio thesis in both locales", () => {
    expect(zhCN.rootTitle).toBe("让复杂的留学规划，清晰地向前。");
    expect(zhCN.rootSummary).toBe(
      "Night Voyager 帮助顾问把散落在对话里的预算、目标、时间和现实条件整理清楚，再据此比较不同路线、说明推荐理由，并推进下一步。AI 协助整理与分析，关键判断仍由顾问完成。",
    );
    expect(en.rootTitle).toBe("Move complex study-abroad planning forward with clarity.");
    expect(en.rootSummary).toBe(
      "Night Voyager helps advisors organize the budgets, goals, timelines, and practical constraints scattered across conversations, then compare routes, explain recommendations, and move the next step forward. AI assists with organization and analysis; the advisor retains every consequential judgment.",
    );
    expect(zhCN.rootPrimaryAction).toBe("查看顾问工作流");
    expect(zhCN.rootSecondaryAction).toBe("GitHub ↗");
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
