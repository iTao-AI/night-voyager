import { expect, it } from "vitest";

import { en, zhCN } from "../../lib/presentation/catalog";

it("publishes exact bilingual blocked, recovery, and terminal semantics", () => {
  expect(zhCN.planExecutionBlocked).toContain("已阻塞");
  expect(zhCN.planExecutionReassessmentStop).toContain("不会创建新计划");
  expect(zhCN.planExecutionWhoNext).toContain("下一位行动者");
  expect(en.planExecutionBlocked).toContain("blocked");
  expect(en.planExecutionReassessmentStop).toContain("does not create a new plan");
  expect(en.planExecutionWhoNext).toContain("Who acts next");
  expect(zhCN.planExecutionReassessment).not.toContain("PR A");
  expect(en.planExecutionReassessment).not.toContain("PR A");
});
