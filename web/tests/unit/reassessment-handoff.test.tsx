import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import { parsePlanExecutionContext, parseTimelineExecutionView } from "../../lib/plan-execution/contracts";
import { buildReassessmentHandoff } from "../../lib/plan-execution/reassessment-handoff";
import { handoffFixture, handoffId } from "../fixtures/reassessment-handoff";
import { PlanExecutionWorkspace } from "../../components/plan-execution/PlanExecutionWorkspace";
import type { PlanExecutionController } from "../../lib/plan-execution/use-plan-execution";
import { PresentationProvider } from "../../lib/presentation/context";

afterEach(() => {
  cleanup(); window.localStorage.clear(); vi.restoreAllMocks();
  Object.defineProperty(navigator, "clipboard", { configurable: true, value: undefined });
});

it("consumes complete accepted read DTOs and exports saved source identities without actors", () => {
  const { context, view } = handoffFixture();
  const summary = buildReassessmentHandoff(
    parsePlanExecutionContext(context), parseTimelineExecutionView(view), "zh-CN",
  );
  expect(summary?.text).toContain("申请提交");
  expect(summary?.text).toContain("缺少必需输入");
  expect(summary?.text).toContain("2026-10-15");
  expect(summary?.text).toContain("保存时的数据库日期：2026-10-07");
  expect(summary?.text).toContain("当前视图所见日期：2026-10-09");
  expect(summary?.text).toContain(handoffId(1));
  expect(summary?.text).toContain(handoffId(4));
  expect(summary?.text).toContain(handoffId(5));
  expect(summary?.text).toContain(handoffId(11));
  expect(summary?.text).toContain(handoffId(30));
  expect(summary?.text).toContain("pending_future_authorization");
  expect(summary?.text).not.toMatch(/actor|csrf|token|cookie|header/i);
  expect(summary?.text).not.toContain(handoffId(90));
  expect(summary?.text).not.toContain(handoffId(91));
});

it("uses the saved checkpoint rather than the independently projected current checkpoint", () => {
  const { context, view } = handoffFixture();
  view.current_checkpoint = view.checkpoints[0];
  view.current_action = { ...view.current_action, checkpoint_id: view.checkpoints[0].checkpoint_id };
  const summary = buildReassessmentHandoff(context, parseTimelineExecutionView(view), "en");
  expect(summary?.facts).toContainEqual({ label: "Saved checkpoint", value: "Application" });
  expect(summary?.facts).toContainEqual({ label: "Due date", value: "2026-10-15" });
  expect(summary?.text).not.toContain("2026-09-01");
});

it.each(["reference", "checkpoint", "execution", "kind", "missing"] as const)(
  "does not attribute a blocker reason from a %s mismatch", (mismatch) => {
    const { context, view } = handoffFixture();
    if (mismatch === "missing") view.latest_attestation = null;
    else if (mismatch === "reference") view.latest_attestation!.attestation_id = handoffId(99);
    else if (mismatch === "checkpoint") view.latest_attestation!.checkpoint_id = handoffId(10);
    else if (mismatch === "execution") view.latest_attestation!.execution_id = handoffId(99);
    else view.latest_attestation!.attestation_kind = "progress";
    const summary = buildReassessmentHandoff(context, view, "en");
    expect(summary?.text).toContain("Matching blocked attestation details are unavailable in this view.");
    expect(summary?.text).not.toContain("Missing required input");
  },
);

it("reports saved deadline acceptance and both server dates without attributing an unrelated blocker", () => {
  const { context, view } = handoffFixture("deadline_elapsed");
  view.latest_attestation = handoffFixture().view.latest_attestation;
  const summary = buildReassessmentHandoff(context, parseTimelineExecutionView(view), "en");
  expect(summary?.text).toContain("Accepted database date: 2026-10-16");
  expect(summary?.text).toContain("View observed date: 2026-10-20");
  expect(summary?.text).toContain("The server accepted the saved checkpoint's elapsed deadline. No further reason was provided.");
  expect(summary?.text).not.toContain("Missing required input");
  expect(summary?.text).toContain("Saved projection reference only; the browser has not revalidated the trigger.");
});

it.each(["case_id", "case_revision", "decision_id", "decision_receipt_id", "timeline_plan_id", "execution_id"] as const)(
  "removes the summary when the current context changes %s", (field) => {
    const { context, view } = handoffFixture();
    const changed = { ...context, [field]: field === "case_revision" ? 3 : handoffId(99) };
    expect(buildReassessmentHandoff(changed, view, "en")).toBeNull();
  },
);

it("does not export an active execution or unsaved reassessment", () => {
  const { context, view } = handoffFixture();
  view.execution.state = "active";
  expect(buildReassessmentHandoff(context, view, "en")).toBeNull();
  view.execution.state = "reassessment_required";
  view.reassessment = null;
  expect(buildReassessmentHandoff(context, view, "en")).toBeNull();
});

function controllerFixture(): PlanExecutionController {
  const { context, view } = handoffFixture();
  return {
    state: { value: "reassessment_required", context, view, receipt: null,
      error: null, operation: null, safeDisplayState: null },
    busy: false, connect: async () => {}, switchRole: async () => {},
    start: async () => {}, attest: async () => {}, verify: async () => {},
    reassess: async () => {}, recover: async () => {},
  };
}
function workspace(controller: PlanExecutionController) {
  return <PresentationProvider><PlanExecutionWorkspace controller={controller} /></PresentationProvider>;
}
function clipboard(writeText: (text: string) => Promise<void>) {
  Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
}

it("copies the visible saved facts only on user action, keeping source identities collapsed", async () => {
  const write = vi.fn().mockResolvedValue(undefined);
  clipboard(write);
  render(workspace(controllerFixture()));
  const handoff = screen.getByRole("region", { name: "重新评估交接" });
  expect(within(handoff).getByText("申请提交")).toBeVisible();
  expect(within(handoff).getByText("缺少必需输入")).toBeVisible();
  expect(within(handoff).getByText(handoffId(30))).not.toBeVisible();
  expect(write).not.toHaveBeenCalled();
  fireEvent.click(within(handoff).getByRole("button", { name: "复制交接摘要" }));
  await waitFor(() => expect(within(handoff).getByText("交接摘要已复制。")).toBeVisible());
  expect(write).toHaveBeenCalledTimes(1);
  expect(write.mock.calls[0][0]).toContain("保存的行动节点：申请提交");
  expect(write.mock.calls[0][0]).toContain("已知原因：缺少必需输入");
  expect(write.mock.calls[0][0]).toContain("不会创建新计划");
  expect(write.mock.calls[0][0]).not.toContain(handoffId(91));
  expect(screen.getAllByRole("status")).toHaveLength(1);
});

it.each(["rejected", "unavailable"] as const)(
  "offers selected current plain text when clipboard is %s", async (kind) => {
    if (kind === "rejected") clipboard(vi.fn().mockRejectedValue(new Error("denied")));
    render(workspace(controllerFixture()));
    fireEvent.click(screen.getByRole("button", { name: "复制交接摘要" }));
    const text = await screen.findByRole("textbox", { name: "可选择的交接摘要" });
    expect(text).toHaveAttribute("readonly");
    expect(text).toHaveFocus();
    expect((text as HTMLTextAreaElement).value).toContain("当前视图所见日期：2026-10-09");
    expect((text as HTMLTextAreaElement).selectionEnd).toBe((text as HTMLTextAreaElement).value.length);
    expect(screen.getByText("无法复制，请选择下方文本手动复制。")).toBeVisible();
  },
);

it.each(["loading", "mutation_in_flight", "session_changed", "recoverable_error"] as const)(
  "removes the old copyable summary during %s", async (state) => {
    clipboard(vi.fn().mockRejectedValue(new Error("denied")));
    const controller = controllerFixture();
    const rendered = render(workspace(controller));
    fireEvent.click(screen.getByRole("button", { name: "复制交接摘要" }));
    await screen.findByRole("textbox", { name: "可选择的交接摘要" });
    controller.state = { ...controller.state, value: state };
    rendered.rerender(workspace(controller));
    expect(screen.queryByRole("textbox", { name: "可选择的交接摘要" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "复制交接摘要" })).not.toBeInTheDocument();
  },
);

it("removes copy while busy even if the last settled state is retained", () => {
  const controller = controllerFixture();
  const rendered = render(workspace(controller));
  expect(screen.getByRole("button", { name: "复制交接摘要" })).toBeEnabled();
  controller.busy = true;
  rendered.rerender(workspace(controller));
  expect(screen.queryByRole("button", { name: "复制交接摘要" })).not.toBeInTheDocument();
});

it("drops fallback and delayed feedback on a new context rather than exporting old facts", async () => {
  let rejectCopy!: (error: Error) => void;
  clipboard(() => new Promise<void>((_resolve, reject) => { rejectCopy = reject; }));
  const controller = controllerFixture();
  const rendered = render(workspace(controller));
  fireEvent.click(screen.getByRole("button", { name: "复制交接摘要" }));
  const next = handoffFixture("deadline_elapsed", 100);
  controller.state = { ...controller.state, context: next.context, view: next.view };
  rendered.rerender(workspace(controller));
  await act(async () => rejectCopy(new Error("late denial")));
  expect(screen.queryByRole("textbox", { name: "可选择的交接摘要" })).not.toBeInTheDocument();
  expect(screen.queryByText("无法复制，请选择下方文本手动复制。")).not.toBeInTheDocument();
  clipboard(vi.fn().mockRejectedValue(new Error("denied")));
  fireEvent.click(screen.getByRole("button", { name: "复制交接摘要" }));
  const fallback = await screen.findByRole("textbox", { name: "可选择的交接摘要" });
  expect((fallback as HTMLTextAreaElement).value).toContain("保存时的数据库日期：2026-10-16");
  expect((fallback as HTMLTextAreaElement).value).not.toContain("缺少必需输入");
  expect((fallback as HTMLTextAreaElement).value).not.toContain(handoffId(1));
  expect((fallback as HTMLTextAreaElement).value).toContain(handoffId(101));
});

it.each(["role", "locale"] as const)("clears the old fallback on a %s change", async (change) => {
  clipboard(vi.fn().mockRejectedValue(new Error("denied")));
  const controller = controllerFixture();
  const rendered = render(workspace(controller));
  fireEvent.click(screen.getByRole("button", { name: "复制交接摘要" }));
  await screen.findByRole("textbox", { name: "可选择的交接摘要" });
  if (change === "role") {
    controller.state.context = { ...controller.state.context!, active_role: "parent" };
    rendered.rerender(workspace(controller));
  } else fireEvent.click(screen.getByRole("button", { name: "English" }));
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: change === "locale" ? "Copy handoff summary" : "复制交接摘要" })).toBeEnabled();
});

it("rejects a changed requested connected Case before an old controller can be copied", () => {
  const controller = controllerFixture();
  render(<PresentationProvider><PlanExecutionWorkspace controller={controller}
    authority={{ kind: "connected", caseId: handoffId(99) }} /></PresentationProvider>);
  expect(screen.queryByRole("button", { name: "复制交接摘要" })).not.toBeInTheDocument();
});
