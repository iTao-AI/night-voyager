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

it("NVPC-P1-001 publishes closed bilingual execution authority labels", () => {
  expect(zhCN.planExecutionMilestoneDocuments).toBe("材料准备");
  expect(zhCN.planExecutionCheckpointInProgress).toBe("进行中");
  expect(zhCN.planExecutionRiskOnTrack).toBe("按计划");
  expect(zhCN.planExecutionActivityAttestation).toBe("家庭状态更新");
  expect(en.planExecutionMilestoneDocuments).toBe("Documents");
  expect(en.planExecutionCheckpointInProgress).toBe("In progress");
  expect(en.planExecutionRiskOnTrack).toBe("On track");
  expect(en.planExecutionActivityAttestation).toBe("Family status update");
});

it("NVPC-P1-003 and NVPC-P2-006 explain handoff and approved-plan context", () => {
  expect(zhCN.planExecutionNextFamily).toContain("负责角色");
  expect(zhCN.planExecutionNextAdvisor).toContain("顾问");
  expect(zhCN.planExecutionApprovedPlanTitle).toContain("已批准");
  expect(en.planExecutionNextFamily).toContain("checkpoint owner");
  expect(en.planExecutionNextAdvisor).toContain("advisor");
  expect(en.planExecutionApprovedPlanTitle).toContain("Approved");
});

it("NVPC-P2-005 discloses the latest-64 retention boundary", () => {
  expect(zhCN.planExecutionActivityLatest64).toContain("最近 64 条");
  expect(en.planExecutionActivityLatest64).toContain("latest 64");
});
