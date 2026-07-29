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
  expect(screen.getByText(/已阻塞/)).toBeInTheDocument();
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
});
