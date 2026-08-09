import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, expect, it, vi } from "vitest";

import { ConnectedDemo } from "../../components/connected-demo/ConnectedDemo";
import { AdvisorLedger } from "../../components/connected-demo/AdvisorLedger";
import { DecisionReceiptTimeline } from "../../components/connected-demo/DecisionReceiptTimeline";
import { FamilyDecisionBrief } from "../../components/connected-demo/FamilyDecisionBrief";
import { PlanningRevisionComparison } from "../../components/connected-demo/PlanningRevisionComparison";
import { RecoveryNotice } from "../../components/connected-demo/RecoveryNotice";
import { RevisionFactEditor } from "../../components/connected-demo/RevisionFactEditor";
import { JourneyConflictNotice } from "../../components/demo-session/JourneyConflictNotice";
import type {
  ConfirmedFactAdvisor,
  FactKey,
  FactValue,
} from "../../lib/collaboration-demo/contracts";
import type { CurrentDecisionBrief, TaskStatus } from "../../lib/connected-demo/contracts";
import { PresentationProvider } from "../../lib/presentation/context";
import { brief as briefFixture, comparison as comparisonFixture, CONFIRMED_FACT, ledger as ledgerFixture, status as statusFor } from "./connected-demo-test-data";

const connectedHook = vi.hoisted(() => ({ current: {} as Record<string, unknown> }));
vi.mock("../../lib/connected-demo/use-connected-demo", async () => {
  const actual = await vi.importActual<typeof import("../../lib/connected-demo/use-connected-demo")>("../../lib/connected-demo/use-connected-demo");
  return { ...actual, useConnectedDemo: () => connectedHook.current };
});

function renderPresentation(ui: ReactElement) {
  return render(ui, { wrapper: PresentationProvider });
}

function confirmedFact(
  factKey: FactKey,
  value: FactValue,
  factVersion: number,
): ConfirmedFactAdvisor {
  return { ...CONFIRMED_FACT, fact_key: factKey, value, fact_version: factVersion };
}

const mixedConfirmedFacts = [
  confirmedFact("student.intended_field", "Computer Science", 1),
  confirmedFact("student.preferred_countries", ["australia", "japan"], 2),
  confirmedFact("student.intake", "2027-02", 3),
  confirmedFact("family.risk_tolerance", "medium", 4),
  confirmedFact("family.japan_risk_accepted", true, 5),
  confirmedFact("family.budget", CONFIRMED_FACT.value, 6),
] satisfies readonly ConfirmedFactAdvisor[];

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.clearAllMocks();
});

function setConnectedDemo(state: unknown, journeyConflict: "collaboration" | null = null) {
  connectedHook.current = {
    state,
    confirmed: false,
    setConfirmed: vi.fn(),
    inspector: null,
    currentFacts: { caseId: ledgerFixture("review-required").case_id, caseRevision: 1, facts: [CONFIRMED_FACT] },
    revision: null,
    journeyConflict,
    endConflictingJourney: vi.fn(),
    connectAdvisor: vi.fn(),
    recover: vi.fn(),
    retry: vi.fn(),
    createTask: vi.fn(),
    createRevisionTask: vi.fn(),
    approve: vi.fn(),
    requestRevision: vi.fn(),
    rotateToStudent: vi.fn(),
    submitPreferredCountries: vi.fn(),
    rotateToAdvisor: vi.fn(),
    confirmPreferredCountries: vi.fn(),
    approveRevision: vi.fn(),
    rotateToParent: vi.fn(),
    decide: vi.fn(),
  };
}

it("presents connected route analysis inside the advisor workspace shell", () => {
  const ledger = ledgerFixture("review-required");
  setConnectedDemo({ value: "advisor_review", status: { ...statusFor("review_required"), active_role: "advisor" }, ledger });
  const { container } = renderPresentation(<ConnectedDemo />);

  expect(screen.getByRole("heading", { level: 1, name: "让路线分析先通过顾问判断" })).toBeVisible();
  expect(screen.getAllByText("方案研判与客户确认").length).toBeGreaterThanOrEqual(1);
  expect(screen.getByText("同一 Case 的连接证明")).toBeVisible();
  expect(screen.getByRole("list", { name: "顾问工作流阶段" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "批准当前计划" })).toHaveAttribute("data-primary-action", "true");
  expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  expect(container.querySelectorAll('[role="status"]').length).toBeLessThanOrEqual(1);
  expect(container.querySelector(".workspace-supporting-evidence")).toBeInTheDocument();
  expect(container.querySelector(".workspace-technical-evidence:not([open])")).toBeInTheDocument();
  expect(screen.queryByText("顾问到家庭决策流程")).toBeNull();
});

it("labels the receipt handoff as an independent execution scenario", () => {
  const brief = briefFixture("plan-ready");
  setConnectedDemo({ value: "plan_ready", status: { ...statusFor("plan_ready"), active_role: "parent" }, brief });
  renderPresentation(<ConnectedDemo />);

  expect(screen.getByRole("heading", { level: 1, name: "让路线分析先通过顾问判断" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "家庭决定回执" })).toBeVisible();
  expect(screen.getByRole("link", { name: /执行跟进使用独立播种/ })).toHaveAttribute("href", "/demo/plan");
  expect(screen.getByText(/不承接当前 Case 或 session/)).toBeVisible();
});

it("focuses the current-work heading after an accepted connected transition", async () => {
  setConnectedDemo({ value: "bootstrapping" });
  const view = renderPresentation(<ConnectedDemo />);
  fireEvent.click(screen.getByRole("button", { name: "开始顾问流程" }));

  setConnectedDemo({
    value: "advisor_ready",
    status: { ...statusFor("task_ready"), active_role: "advisor" },
    ledger: ledgerFixture("task-ready"),
  });
  view.rerender(<ConnectedDemo />);

  await waitFor(() =>
    expect(screen.getByRole("heading", { level: 2, name: "当前工作阶段" })).toHaveFocus(),
  );
});

it("focuses connected conflict and recovery headings on state entry", async () => {
  setConnectedDemo({ value: "bootstrapping" }, "collaboration");
  const conflict = renderPresentation(<ConnectedDemo />);
  await waitFor(() =>
    expect(screen.getByRole("heading", { level: 2, name: "另一个演示流程正在进行" })).toHaveFocus(),
  );
  conflict.unmount();

  const retained = {
    value: "advisor_ready",
    status: { ...statusFor("task_ready"), active_role: "advisor" },
    ledger: ledgerFixture("task-ready"),
  };
  setConnectedDemo({ value: "recoverable_error", code: "transport_failure", prior: retained });
  renderPresentation(<ConnectedDemo />);
  await waitFor(() =>
    expect(screen.getByRole("heading", { level: 3, name: "需要恢复" })).toHaveFocus(),
  );
});

it("renders Chinese task-ready authority with one primary action and no raw phase", () => {
  const ledger = ledgerFixture("task-ready");
  const { container } = renderPresentation(
    <AdvisorLedger ledger={ledger} onPrimaryAction={() => undefined} />,
  );
  expect(screen.getByRole("heading", { name: "当前决策阶段" })).toBeVisible();
  expect(screen.getByText("可以开始规划")).toBeVisible();
  expect(screen.getByRole("button", { name: "创建规划任务" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "创建规划任务" }).closest("details")).toBeNull();
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

it("renders every exact confirmed-fact type in one Chinese mixed projection", () => {
  const current = { ...ledgerFixture("task-ready"), case_revision: 7 };
  const { container } = renderPresentation(
    <AdvisorLedger ledger={current} confirmedFacts={mixedConfirmedFacts} onPrimaryAction={() => undefined} />,
  );

  for (const visible of [
    "Computer Science",
    "澳大利亚、日本",
    "2027-02",
    "中等",
    "已接受",
    "¥300,000–400,000",
  ]) expect(screen.getByText(visible)).toBeVisible();
  for (const version of [1, 2, 3, 4, 5, 6]) {
    expect(screen.getByText(`Fact version ${version}`)).toBeVisible();
  }
  expect(screen.getAllByText("Case revision 7")).toHaveLength(7);
  expect(container).not.toHaveTextContent(/student\.|family\.|confirmed_fact_id|candidate_id|schema_version|\{"/i);
});

it("renders every exact confirmed-fact type in one explicit English mixed projection", async () => {
  localStorage.setItem("night-voyager:presentation-locale:v1", "en");
  const current = { ...ledgerFixture("task-ready"), case_revision: 7 };
  const { container } = renderPresentation(
    <AdvisorLedger ledger={current} confirmedFacts={mixedConfirmedFacts} onPrimaryAction={() => undefined} />,
  );

  await waitFor(() => expect(screen.getByText("Australia, Japan")).toBeVisible());
  for (const visible of [
    "Computer Science",
    "2027-02",
    "Medium",
    "Accepted",
    "CNY 300,000–400,000",
  ]) expect(screen.getByText(visible)).toBeVisible();
  for (const version of [1, 2, 3, 4, 5, 6]) {
    expect(screen.getByText(`Fact version ${version}`)).toBeVisible();
  }
  expect(screen.getAllByText("Case revision 7")).toHaveLength(7);
  expect(container).not.toHaveTextContent(/student\.|family\.|confirmed_fact_id|candidate_id|schema_version|\{"/i);
});

it("fails closed for malformed current facts without exposing raw values", () => {
  const malformed = [
    { ...CONFIRMED_FACT, fact_key: "student.intended_field", value: { raw: "raw-field-secret" } },
    { ...CONFIRMED_FACT, fact_key: "student.preferred_countries", value: ["australia", "raw-country-secret"] },
    { ...CONFIRMED_FACT, fact_key: "family.risk_tolerance", value: "raw-risk-secret" },
  ] as unknown as readonly ConfirmedFactAdvisor[];
  const current = { ...ledgerFixture("task-ready"), case_revision: 2 };
  const { container } = renderPresentation(
    <AdvisorLedger ledger={current} confirmedFacts={malformed} onPrimaryAction={() => undefined} />,
  );

  expect(screen.getAllByText("状态暂不可用")).toHaveLength(3);
  expect(container).not.toHaveTextContent(/raw-field-secret|raw-country-secret|raw-risk-secret|\{"/i);
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
  expect(screen.getAllByText(/缺少马来西亚项目匹配证据/).length).toBeGreaterThan(0);
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
  expect(screen.getByRole("button", { name: "Approve current plan" })).toBeEnabled();
  expect(container).not.toHaveTextContent(/review-required|needs_advisor_review/);
});

it("renders a bilingual server-owned revision comparison without identifiers", async () => {
  const comparison = comparisonFixture();
  const { container } = renderPresentation(
    <PlanningRevisionComparison comparison={comparison} />,
  );
  expect(screen.getByRole("heading", { name: "规划修订比较" })).toBeVisible();
  expect(screen.getByText("保留的上一版计划")).toBeVisible();
  expect(screen.getByText("当前修订计划")).toBeVisible();
  expect(screen.getAllByText("已从修订计划中移除").length).toBeGreaterThan(0);
  expect(screen.getByRole("table", { name: "规划修订比较" })).toBeVisible();
  expect(screen.getByRole("group", { name: "选择要比较的国家" })).toBeInTheDocument();
  expect(container.querySelector(".revision-country-card dl")).toBeInTheDocument();
  expect(container.querySelector("tr.revision-route-removed")).toHaveTextContent("马来西亚");
  expect(container).not.toHaveTextContent(
    /40000000|70000000|previous_planning_run_id|current_planning_run_id|student\.preferred_countries/,
  );

  cleanup();
  localStorage.setItem("night-voyager:presentation-locale:v1", "en");
  renderPresentation(<PlanningRevisionComparison comparison={comparison} />);
  await waitFor(() => expect(screen.getByRole("heading", { name: "Planning revision comparison" })).toBeVisible());
  expect(screen.getByText("Previous plan retained for history")).toBeVisible();
  expect(screen.getByText("Current revised plan")).toBeVisible();
  expect(screen.getAllByText("Removed from the revised plan").length).toBeGreaterThan(0);
  expect(document.body).not.toHaveTextContent(/规划|修订|上一版|当前/);
});

it("submits only the approved preferred-country revision and fails closed otherwise", () => {
  const submit = vi.fn();
  const preferred = confirmedFact(
    "student.preferred_countries",
    ["australia", "japan", "malaysia"],
    1,
  );
  const projection = { caseId: "40000000-0000-0000-0000-000000000002", caseRevision: 1, facts: [preferred] };
  const { rerender } = renderPresentation(
    <RevisionFactEditor currentFacts={projection} expectedCaseRevision={1} onSubmit={submit} />,
  );
  expect(screen.getByRole("group", { name: "修改意向国家" })).toBeInTheDocument();
  expect(screen.getByText("澳大利亚、日本、马来西亚")).toBeVisible();
  expect(screen.getByText("澳大利亚、日本")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "提交变更提案" }));
  expect(submit).toHaveBeenCalledOnce();

  rerender(
    <RevisionFactEditor
      currentFacts={{ ...projection, facts: [{ ...preferred, value: ["japan", "australia", "malaysia"] }] }}
      expectedCaseRevision={1}
      onSubmit={submit}
    />,
  );
  expect(screen.getByRole("button", { name: "提交变更提案" })).toBeDisabled();
  expect(screen.getByText("当前服务器事实不符合此合成修订的安全基线。")).toBeVisible();
});

it("shows renewed server authorization in the family-safe revised brief", () => {
  const revised = briefFixture("family-review");
  revised.revision_context = {
    schema: "night-voyager.family-revision-context.v1",
    current_case_revision: 2,
    planning_version: "revised",
    advisor_authorization: "renewed_for_current_revision",
  };
  renderPresentation(
    <FamilyDecisionBrief brief={revised} confirmed onConfirm={() => undefined} onSubmit={() => undefined} />,
  );
  expect(screen.getByText("当前 Case revision 2")).toBeVisible();
  expect(screen.getByText("顾问已为当前修订重新授权")).toBeVisible();
  expect(screen.getByRole("button", { name: "继续家庭决定" })).toBeEnabled();
});

it("offers revision only on the initial review and no business action when blocked", () => {
  const approve = vi.fn();
  const revise = vi.fn();
  const { rerender } = renderPresentation(
    <AdvisorLedger
      ledger={ledgerFixture("review_required")}
      onPrimaryAction={approve}
      onSecondaryAction={revise}
    />,
  );
  expect(screen.getByRole("button", { name: "批准当前计划" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "请求修订" })).toBeEnabled();

  rerender(
    <AdvisorLedger
      ledger={ledgerFixture("revision_review_required")}
      onPrimaryAction={approve}
      onSecondaryAction={revise}
    />,
  );
  expect(screen.getByRole("button", { name: "批准修订计划" })).toBeEnabled();
  expect(screen.queryByRole("button", { name: "请求修订" })).toBeNull();

  rerender(
    <AdvisorLedger
      ledger={ledgerFixture("revision_blocked")}
      onPrimaryAction={approve}
      onSecondaryAction={revise}
    />,
  );
  expect(screen.getByText("此修订已被确定性规则阻止")).toBeVisible();
  expect(screen.queryByRole("button", { name: /批准|请求|创建/ })).toBeNull();
  expect(screen.getByRole("link", { name: "返回产品概览" })).toHaveAttribute("href", "/");
});

it.each([
  ["task_ready", "创建规划任务"],
  ["active_task", null],
  ["revision_fact_pending", "确认意向国家变更"],
  ["replan_required", "创建修订规划任务"],
  ["revision_task_active", null],
  ["revision_review_required", "批准修订计划"],
  ["revision_blocked", null],
  ["terminal_task_failure", null],
] as const)("binds advisor phase %s to exactly one or zero business actions", (phase, action) => {
  renderPresentation(
    <AdvisorLedger
      ledger={ledgerFixture(phase)}
      onPrimaryAction={() => undefined}
      onSecondaryAction={() => undefined}
    />,
  );
  const business = screen.queryAllByRole("button").filter((button) =>
    /创建|确认意向|批准|请求修订/.test(button.textContent ?? ""),
  );
  if (action) {
    expect(business).toHaveLength(1);
    expect(business[0]).toHaveAccessibleName(action);
  } else {
    expect(business).toHaveLength(0);
  }
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
  expect(screen.getByRole("button", { name: "继续家庭决定" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "继续家庭决定" }).closest("details")).toBeNull();
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
