import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";

import { PlanExecutionWorkspace } from "../../components/plan-execution/PlanExecutionWorkspace";
import type { PlanExecutionController } from "../../lib/plan-execution/use-plan-execution";
import { PresentationProvider } from "../../lib/presentation/context";
import { PRESENTATION_LOCALE_STORAGE_KEY } from "../../lib/presentation/locales";
import { contextFixture, viewFixture } from "./plan-execution-contracts.test";

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});

function activeController(): PlanExecutionController {
  return {
    state: {
      value: "checkpoint_active" as const,
      context: contextFixture,
      view: viewFixture(),
      receipt: null,
      error: null,
      operation: null,
      safeDisplayState: null,
    },
    busy: false,
    connect: async () => undefined,
    switchRole: async () => undefined,
    start: async () => undefined,
    attest: async () => undefined,
    verify: async () => undefined,
    reassess: async () => undefined,
    recover: async () => undefined,
  };
}

function controllerFor(
  role: "student" | "parent" | "advisor",
  checkpointState: "in_progress" | "awaiting_advisor" | "blocked",
) {
  const controller = activeController();
  controller.state.context = { ...contextFixture, active_role: role };
  controller.state.view = viewFixture(checkpointState);
  controller.state.value = checkpointState === "awaiting_advisor"
    ? "awaiting_advisor"
    : "checkpoint_active";
  return controller;
}

it("renders the current action first without raw hashes or row versions", () => {
  const controller = activeController();
  const { container } = render(
    <PresentationProvider>
      <PlanExecutionWorkspace controller={controller} />
    </PresentationProvider>,
  );
  expect(screen.getByRole("heading", { name: "当前行动" })).toBeInTheDocument();
  expect(container.querySelector("[data-section='current-action']"))
    .toBe(container.querySelector("main section"));
  expect(container.textContent).not.toMatch(/[0-9a-f]{64}/);
  expect(container.textContent).not.toContain("row_version");
  expect(screen.getByRole("button", { name: "记录进行中" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "提交完成状态给顾问" })).toBeInTheDocument();
});

it("routes every core execution control through the English catalog", async () => {
  window.localStorage.setItem(PRESENTATION_LOCALE_STORAGE_KEY, "en");
  render(
    <PresentationProvider>
      <PlanExecutionWorkspace controller={activeController()} />
    </PresentationProvider>,
  );
  await waitFor(() => {
    expect(screen.getByRole("heading", { name: "Current action" })).toBeInTheDocument();
  });
  expect(screen.getByRole("button", { name: "Record progress" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Submit completion to advisor" })).toBeInTheDocument();
  expect(screen.getByText("Due date")).toBeInTheDocument();
  expect(screen.getByText("Owner role")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Activity" })).toBeInTheDocument();
  expect(screen.queryByText("记录进行中")).not.toBeInTheDocument();
  expect(screen.queryByText("负责角色")).not.toBeInTheDocument();
});

it("offers only closed blocked values to the accountable family role", () => {
  render(
    <PresentationProvider>
      <PlanExecutionWorkspace controller={controllerFor("student", "in_progress")} />
    </PresentationProvider>,
  );
  expect(screen.getByRole("combobox", { name: "阻塞原因" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "缺少必需输入" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "外部依赖暂不可用" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "截止日期存在风险" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "记录阻塞并停止当前 checkpoint" })).toBeInTheDocument();
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
});

it("shows reassessment only to the advisor for server-blocked authority", () => {
  const student = render(
    <PresentationProvider>
      <PlanExecutionWorkspace controller={controllerFor("student", "blocked")} />
    </PresentationProvider>,
  );
  expect(screen.getAllByText(/已阻塞/).length).toBeGreaterThan(0);
  expect(screen.queryByRole("button", { name: "请求重新评估并停止执行" })).not.toBeInTheDocument();
  student.unmount();

  render(
    <PresentationProvider>
      <PlanExecutionWorkspace controller={controllerFor("advisor", "blocked")} />
    </PresentationProvider>,
  );
  expect(screen.getByRole("button", { name: "请求重新评估并停止执行" })).toBeInTheDocument();
  expect(screen.getByText(/不会创建新计划/)).toBeInTheDocument();
});

it("renders terminal handoff without any resume or mutation action", () => {
  const controller = controllerFor("advisor", "blocked");
  controller.state.value = "reassessment_required";
  controller.state.view!.execution.state = "reassessment_required";
  controller.state.view!.reassessment = {
    schema_version: 1,
    reassessment_id: "10000000-0000-0000-0000-000000000020",
    execution_id: controller.state.view!.execution.execution_id,
    checkpoint_id: controller.state.view!.current_checkpoint!.checkpoint_id,
    advisor_actor_id: "10000000-0000-0000-0000-000000000021",
    trigger: "blocked_attestation",
    trigger_reference_id: "10000000-0000-0000-0000-000000000010",
    accepted_database_date: "2026-07-29",
    accepted_trigger_projection_sha256: "a".repeat(64),
    handoff_schema_version: 1,
    predecessor_case_id: contextFixture.case_id,
    predecessor_case_revision: 1,
    predecessor_decision_id: contextFixture.decision_id,
    predecessor_decision_receipt_id: contextFixture.decision_receipt_id,
    predecessor_timeline_plan_id: contextFixture.timeline_plan_id,
    predecessor_execution_id: controller.state.view!.execution.execution_id,
    predecessor_checkpoint_id: controller.state.view!.current_checkpoint!.checkpoint_id,
    owner_role: "advisor",
    successor_status: "pending_future_authorization",
    created_at: "2026-07-29T00:00:00Z",
  };
  render(
    <PresentationProvider>
      <PlanExecutionWorkspace controller={controller} />
    </PresentationProvider>,
  );
  expect(screen.getByRole("heading", { name: "重新评估交接" })).toBeInTheDocument();
  expect(screen.getByText(/等待未来单独授权/)).toBeInTheDocument();
  expect(screen.queryByText(/恢复执行/)).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "请求重新评估并停止执行" })).not.toBeInTheDocument();
  expect(screen.getByText("阻塞状态已由顾问接受为重新评估触发条件。")).toBeInTheDocument();
  expect(screen.queryByText("blocked_attestation")).not.toBeInTheDocument();
});

it("renders the deadline trigger through the English catalog without raw codes", async () => {
  window.localStorage.setItem(PRESENTATION_LOCALE_STORAGE_KEY, "en");
  const controller = controllerFor("advisor", "blocked");
  controller.state.value = "reassessment_required";
  controller.state.view!.execution.state = "reassessment_required";
  controller.state.view!.reassessment = {
    schema_version: 1,
    reassessment_id: "10000000-0000-0000-0000-000000000020",
    execution_id: controller.state.view!.execution.execution_id,
    checkpoint_id: controller.state.view!.current_checkpoint!.checkpoint_id,
    advisor_actor_id: "10000000-0000-0000-0000-000000000021",
    trigger: "deadline_elapsed",
    trigger_reference_id: null,
    accepted_database_date: "2026-07-29",
    accepted_trigger_projection_sha256: "a".repeat(64),
    handoff_schema_version: 1,
    predecessor_case_id: contextFixture.case_id,
    predecessor_case_revision: 1,
    predecessor_decision_id: contextFixture.decision_id,
    predecessor_decision_receipt_id: contextFixture.decision_receipt_id,
    predecessor_timeline_plan_id: contextFixture.timeline_plan_id,
    predecessor_execution_id: controller.state.view!.execution.execution_id,
    predecessor_checkpoint_id: controller.state.view!.current_checkpoint!.checkpoint_id,
    owner_role: "advisor",
    successor_status: "pending_future_authorization",
    created_at: "2026-07-29T00:00:00Z",
  };
  render(
    <PresentationProvider>
      <PlanExecutionWorkspace controller={controller} />
    </PresentationProvider>,
  );

  await waitFor(() => {
    expect(screen.getByText(
      "The server-owned deadline condition was accepted as the reassessment trigger.",
    )).toBeInTheDocument();
  });
  expect(screen.queryByText("deadline_elapsed")).not.toBeInTheDocument();
});

it("NVPC-P1-001 localizes checkpoint and activity authority without raw codes", () => {
  const controller = activeController();
  controller.state.view!.activity = [{
    schema_version: 1,
    kind: "attestation_recorded",
    durable_id: "10000000-0000-0000-0000-000000000090",
    execution_id: controller.state.view!.execution.execution_id,
    checkpoint_id: controller.state.view!.current_checkpoint!.checkpoint_id,
    created_at: "2026-07-29T00:00:00Z",
  }];
  controller.state.view!.activity_total = 1;
  const { container } = render(
    <PresentationProvider>
      <PlanExecutionWorkspace controller={controller} />
    </PresentationProvider>,
  );

  expect(screen.getAllByText("材料准备").length).toBeGreaterThan(0);
  expect(screen.getAllByText("学生").length).toBeGreaterThan(0);
  expect(screen.getByText("按计划")).toBeInTheDocument();
  expect(screen.getByText("家庭状态更新")).toBeInTheDocument();
  expect(container.textContent).not.toMatch(
    /documents|student|on_track|attestation_recorded/,
  );
});

it("NVPC-P1-002 leaves only reassessment in the blocked advisor action region", () => {
  const controller = controllerFor("advisor", "blocked");
  const { container } = render(
    <PresentationProvider>
      <PlanExecutionWorkspace controller={controller} />
    </PresentationProvider>,
  );
  const action = container.querySelector("[data-section='current-action']");
  expect(action).not.toBeNull();
  expect(action!.textContent).not.toContain("记录进行中");
  expect(action!.textContent).not.toContain("提交完成状态给顾问");
  expect(action!.textContent).not.toContain("记录阻塞并停止当前 checkpoint");
  expect(action!.textContent).toContain("请求重新评估并停止执行");
});

it("NVPC-P1-003 puts authority summary and next handoff before the action", () => {
  const { container } = render(
    <PresentationProvider>
      <PlanExecutionWorkspace controller={activeController()} />
    </PresentationProvider>,
  );
  const region = container.querySelector("[data-section='current-action']");
  const summary = region?.querySelector("[data-plan-authority-summary]");
  const action = region?.querySelector("[data-current-action-controls]");
  expect(summary).not.toBeNull();
  expect(action).not.toBeNull();
  expect(summary!.compareDocumentPosition(action!))
    .toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  expect(region!.textContent).toContain("下一位行动者");
  expect(screen.getByRole("group", { name: "checkpoint 状态证明" })).toBeInTheDocument();
});

it("NVPC-P1-004 moves focus and announces one accepted state transition", async () => {
  const controller = activeController();
  const rendered = render(
    <PresentationProvider>
      <PlanExecutionWorkspace controller={controller} />
    </PresentationProvider>,
  );
  const heading = screen.getByRole("heading", { name: "当前行动" });

  controller.state = {
    ...controller.state,
    value: "awaiting_advisor",
    view: viewFixture("awaiting_advisor"),
  };
  rendered.rerender(
    <PresentationProvider>
      <PlanExecutionWorkspace controller={controller} />
    </PresentationProvider>,
  );

  await waitFor(() => expect(heading).toHaveFocus());
  expect(screen.getAllByRole("status")).toHaveLength(1);
  expect(screen.getByRole("status")).toHaveTextContent("等待已分配顾问验证");
});

it("NVPC-P2-005 keeps localized activity in a secondary disclosure", () => {
  const controller = activeController();
  controller.state.view!.activity = [{
    schema_version: 1,
    kind: "mutation_receipt_recorded",
    durable_id: "10000000-0000-0000-0000-000000000091",
    execution_id: controller.state.view!.execution.execution_id,
    checkpoint_id: controller.state.view!.current_checkpoint!.checkpoint_id,
    created_at: "2026-07-29T00:00:00Z",
  }];
  controller.state.view!.activity_total = 67;
  controller.state.view!.activity_truncated = true;
  render(
    <PresentationProvider>
      <PlanExecutionWorkspace controller={controller} />
    </PresentationProvider>,
  );

  expect(screen.getByText("操作回执")).toBeInTheDocument();
  expect(screen.getByText(/最近 64 条/)).toBeInTheDocument();
  expect(screen.getByText("活动记录")).toBeInTheDocument();
  expect(screen.queryByText("mutation_receipt_recorded")).not.toBeInTheDocument();
});

it("NVPC-P2-006 renders the immutable four-step approved plan", () => {
  render(
    <PresentationProvider>
      <PlanExecutionWorkspace controller={activeController()} />
    </PresentationProvider>,
  );
  const plan = screen.getByRole("region", { name: "已批准的行动计划" });
  expect(plan).toBeInTheDocument();
  expect(plan.querySelectorAll("li")).toHaveLength(4);
  expect(plan).toHaveTextContent("材料准备");
  expect(plan).toHaveTextContent("申请提交");
  expect(plan).toHaveTextContent("签证准备");
  expect(plan).toHaveTextContent("抵达安排");
});
