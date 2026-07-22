import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, expect, it, vi } from "vitest";

import { AdvisorLedger } from "../../components/connected-demo/AdvisorLedger";
import { DecisionReceiptTimeline } from "../../components/connected-demo/DecisionReceiptTimeline";
import { FamilyDecisionBrief } from "../../components/connected-demo/FamilyDecisionBrief";
import { RecoveryNotice } from "../../components/connected-demo/RecoveryNotice";
import { JourneyConflictNotice } from "../../components/demo-session/JourneyConflictNotice";
import type { CurrentDecisionBrief, TaskStatus } from "../../lib/connected-demo/contracts";
import { PresentationProvider } from "../../lib/presentation/context";
import { brief as briefFixture, CONFIRMED_FACT, ledger as ledgerFixture } from "./connected-demo-test-data";

function renderPresentation(ui: ReactElement) {
  return render(ui, { wrapper: PresentationProvider });
}

afterEach(() => {
  cleanup();
  localStorage.clear();
});

it("renders Chinese task-ready authority with one primary action and no raw phase", () => {
  const ledger = ledgerFixture("task-ready");
  const { container } = renderPresentation(
    <AdvisorLedger ledger={ledger} onPrimaryAction={() => undefined} />,
  );
  expect(screen.getByRole("heading", { name: "当前决策阶段" })).toBeVisible();
  expect(screen.getByText("可以开始规划")).toBeVisible();
  expect(screen.getByRole("button", { name: "创建规划任务" })).toBeEnabled();
  expect(screen.getByText("Case revision 1")).toBeVisible();
  expect(container).not.toHaveTextContent(/task-ready|lease owner|organization_id|reviewer notes/i);
});

it("renders current Case revision and confirmed facts without internal provenance", () => {
  const current = { ...ledgerFixture("task-ready"), case_revision: 2 };
  const { container, rerender } = renderPresentation(
    <AdvisorLedger ledger={current} confirmedFacts={[CONFIRMED_FACT]} onPrimaryAction={() => undefined} />,
  );
  expect(screen.getAllByText("Case revision 2")).toHaveLength(2);
  expect(screen.getByRole("heading", { name: "当前已确认家庭事实" })).toBeVisible();
  expect(screen.getByText("家庭总预算")).toBeVisible();
  expect(screen.getByText("¥300,000–400,000")).toBeVisible();
  expect(screen.getByText("Fact version 1")).toBeVisible();
  expect(container).not.toHaveTextContent(/family\.budget|45000000|44000000|confirmed_fact_id|candidate_id|schema_version|\{"/i);

  rerender(<AdvisorLedger ledger={current} confirmedFacts={[]} onPrimaryAction={() => undefined} />);
  expect(screen.getByText("此 Case revision 尚无已确认事实。")).toBeVisible();
  expect(screen.queryByText("¥300,000–400,000")).toBeNull();

  rerender(<AdvisorLedger ledger={current} confirmedFacts={null} onPrimaryAction={() => undefined} />);
  expect(screen.getByText("服务器事实投影刷新前，当前事实暂不可用。")).toBeVisible();
});

it("orders route outcome, reason, eligibility and uses closed fallbacks", () => {
  const projected = ledgerFixture("review-required");
  projected.routes[2] = {
    ...projected.routes[2],
    required_claims: ["malaysia_program_fit", "raw_claim_secret"],
    known_gaps: ["malaysia_gap", "raw_gap_secret"],
  };
  projected.evidence[0] = { ...projected.evidence[0], claim: "raw_claim_secret" };
  const { container } = renderPresentation(
    <AdvisorLedger ledger={projected} onPrimaryAction={() => undefined} />,
  );

  expect(screen.getAllByText("不符合审核条件").length).toBeGreaterThanOrEqual(2);
  expect(screen.getAllByText("在预算条件下推荐").length).toBeGreaterThan(0);
  expect(screen.getAllByText("有条件备选").length).toBeGreaterThan(0);
  expect(screen.getAllByText("暂不可选").length).toBeGreaterThan(0);
  expect(screen.getAllByText("成本与汇率证据均在已批准边界内").length).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole("button", { name: "马来西亚" }));
  expect(screen.getByText(/缺少马来西亚项目匹配证据/)).toBeVisible();
  expect(screen.getAllByText("缺少直接的项目匹配证据").length).toBeGreaterThan(0);
  expect(screen.getAllByText("状态暂不可用").length).toBeGreaterThan(0);
  expect(container).not.toHaveTextContent(/recommended_with_condition|raw_claim_secret|raw_gap_secret|malaysia_gap|direct_program_fit_evidence_absent/);
});

it("renders an explicit no-route fallback", () => {
  renderPresentation(
    <AdvisorLedger ledger={ledgerFixture("task-ready")} onPrimaryAction={() => undefined} />,
  );
  expect(screen.getByText("路线比较尚未生成。")).toBeVisible();
});

it("renders the same route authority in explicit English", async () => {
  localStorage.setItem("night-voyager:presentation-locale:v1", "en");
  const { container } = renderPresentation(
    <AdvisorLedger ledger={ledgerFixture("review-required")} onPrimaryAction={() => undefined} />,
  );
  await waitFor(() => expect(screen.getAllByText("Recommended with budget condition").length).toBeGreaterThan(0));
  expect(screen.getByRole("button", { name: "Approve Australia for family review" })).toBeEnabled();
  expect(container).not.toHaveTextContent(/review-required|needs_advisor_review/);
});

it.each([
  ["preparing", "正在准备"],
  ["needs_advisor_review", "需要顾问审核"],
  ["ready", "已完成"],
  ["needs_evidence", "需要补充证据"],
  ["timed_out", "已超时"],
  ["failed", "未完成"],
  ["cancelled", "已取消"],
  ["outdated", "已有更新版本"],
] satisfies Array<[TaskStatus, string]>)
("announces localized task status %s outside the collapsed technical trail", (status, visible) => {
  const phase = status === "preparing" ? "active-task" : status === "needs_advisor_review" ? "review-required" : "terminal-task-failure";
  const projected = ledgerFixture(phase, status);
  const { container } = renderPresentation(
    <AdvisorLedger ledger={projected} busy onPrimaryAction={() => undefined} />,
  );
  expect(screen.getByRole("status")).toHaveTextContent(visible);
  expect(screen.getByText("任务记录").closest("details")).not.toHaveAttribute("open");
  expect(container).not.toHaveTextContent(status);
});

it("renders only server-derived family constraints before provenance", () => {
  const { container } = renderPresentation(
    <FamilyDecisionBrief brief={briefFixture("family-review")} confirmed={false} onConfirm={() => undefined} onSubmit={() => undefined} />,
  );
  expect(screen.getByText("¥305,500")).toBeVisible();
  expect(screen.getByText("¥400,000")).toBeVisible();
  expect(screen.getAllByText("预算弹性").length).toBeGreaterThan(0);
  expect(screen.getByRole("button", { name: "确认澳大利亚路线" })).toBeDisabled();
  expect(container).not.toHaveTextContent(/budget_elasticity|30,550,000|40,000,000/);
});

it.each(["invalid_transition", "session_expired", "session_recovery_required", "stale_conflict", "transport_failure"] as const)(
  "shows fail-closed recovery for %s without leaking the raw code",
  (code) => {
    const { container } = renderPresentation(
      <RecoveryNotice code={code} onReconnect={() => undefined} />,
    );
    expect(screen.getByRole("heading", { name: "需要恢复" })).toBeVisible();
    expect(screen.queryByText(/Decision Receipt/i)).toBeNull();
    expect(container).not.toHaveTextContent(code);
  },
);

it("localizes a journey conflict without changing the safe server action", () => {
  const end = vi.fn();
  renderPresentation(
    <JourneyConflictNotice currentJourney="collaboration" returnHref="/demo/collaboration" onEnd={end} />,
  );
  expect(screen.getByRole("heading", { name: "另一个演示流程正在进行" })).toBeVisible();
  expect(screen.getByRole("link", { name: "返回当前流程" })).toHaveAttribute("href", "/demo/collaboration");
  fireEvent.click(screen.getByRole("button", { name: "结束当前流程并继续" }));
  expect(end).toHaveBeenCalledOnce();
});

it("presents the receipt then chronological timeline without internal identifiers", () => {
  const brief = briefFixture("plan-ready") as CurrentDecisionBrief;
  const { container } = renderPresentation(<DecisionReceiptTimeline brief={brief} />);
  expect(screen.getByRole("heading", { name: "家庭决定回执" })).toBeVisible();
  expect(screen.getByText("¥305,500–400,000")).toBeVisible();
  expect(screen.getByText("预算弹性")).toBeVisible();
  expect(screen.getByText("家庭协商确认")).toBeVisible();
  expect(screen.getByText("文件准备")).toBeVisible();
  expect(screen.getByText("2026年9月1日")).toBeVisible();
  expect(container).not.toHaveTextContent(/decision_id|receipt_id|selected_route_id|budget_elasticity|30,550,000|40,000,000|family_consultation|documents/);
});
