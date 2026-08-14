import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, expect, it, vi } from "vitest";

import { CollaborationDemo } from "../../components/collaboration-demo/CollaborationDemo";
import { CollaborationRecoveryNotice } from "../../components/collaboration-demo/CollaborationRecoveryNotice";
import { ConfirmedFactSummary } from "../../components/collaboration-demo/ConfirmedFactSummary";
import { MemoryCandidateCard } from "../../components/collaboration-demo/MemoryCandidateCard";
import { SharedThread } from "../../components/collaboration-demo/SharedThread";
import type { CollaborationErrorCategory } from "../../lib/collaboration-demo/reducer";
import type { MemoryCandidateProjection } from "../../lib/collaboration-demo/contracts";
import { PresentationProvider } from "../../lib/presentation/context";

const CASE = "41000000-0000-0000-0000-000000000001";
const THREAD = "42000000-0000-0000-0000-000000000001";
const MESSAGE = "43000000-0000-0000-0000-000000000001";
const CANDIDATE = "44000000-0000-0000-0000-000000000001";
const FACT = "45000000-0000-0000-0000-000000000001";
const AT = "2026-07-20T01:02:03Z";
const SHA = "a".repeat(64);
const budget = { schema_version: 1 as const, currency: "CNY" as const, period: "program_total" as const, preferred_minor: 30_000_000, hard_ceiling_minor: 40_000_000, elasticity_bps: 1000, refused: false };
const thread = { schema_version: 1 as const, thread_id: THREAD, case_id: CASE, created_by_actor_id: CASE, created_at: AT };
const message = { schema_version: 1 as const, message_event_id: MESSAGE, thread_id: THREAD, case_id: CASE, sequence_no: 1, actor_id: CASE, actor_role: "parent" as const, body: "Our confirmed program budget is 300,000 to 400,000 CNY.", content_sha256: SHA, created_at: AT };
const participantCandidate = { schema_version: 1 as const, fact_key: "family.budget" as const, value: budget, state: "pending" as const, created_at: AT, expires_at: "2026-07-27T01:02:03Z" };
const advisorCandidate = { ...participantCandidate, candidate_id: CANDIDATE, message_event_id: MESSAGE, source_message_sequence_no: 1, subject_actor_id: CASE, subject_role: "parent" as const, case_revision: 1, verification_id: MESSAGE, decision: "confirm" as const, reason: "Confirmed by advisor.", request_sha256: SHA, value_sha256: SHA, state: "confirmed" as const };
const fact = { schema_version: 1 as const, fact_key: "family.budget" as const, value: budget, fact_version: 1, confirmed_at: AT, subject_role: "parent" as const, confirming_advisor_role: "advisor" as const, confirmed_fact_id: FACT, candidate_id: CANDIDATE, verification_id: MESSAGE, source_message_event_id: MESSAGE, source_message_sequence_no: 1, source_message_sha256_prefix: "aaaaaaaaaaaa", confirming_advisor_actor_id: CASE, reason: "Confirmed by advisor.", supersedes_fact_id: null };
const baseContext = { role: "parent" as const, caseId: CASE, thread, messages: [message], candidate: null, fact: null, caseRevision: 1 };

const hook = vi.hoisted(() => ({ current: {} as Record<string, unknown> }));
vi.mock("../../lib/collaboration-demo/use-collaboration-demo", async () => {
  const actual = await vi.importActual<typeof import("../../lib/collaboration-demo/use-collaboration-demo")>("../../lib/collaboration-demo/use-collaboration-demo");
  return { ...actual, useCollaborationDemo: () => hook.current };
});

function setState(state: unknown, journeyConflict: "advisor-family" | null = null) {
  hook.current = { state, inspector: null, journeyConflict, connectParent: vi.fn(), appendMessage: vi.fn(), proposeBudget: vi.fn(), switchToAdvisor: vi.fn(), confirmCandidate: vi.fn(), continueToPlanning: vi.fn(), retry: vi.fn(), endConflictingJourney: vi.fn() };
}

function renderPresentation(ui: ReactElement) {
  return render(ui, { wrapper: PresentationProvider });
}

afterEach(() => { cleanup(); localStorage.clear(); vi.clearAllMocks(); });

it("renders localized empty/loading thread while preserving the user message exactly", () => {
  const { rerender, container } = renderPresentation(<SharedThread messages={[]} />);
  expect(screen.getByRole("heading", { name: "共享 Case 沟通记录" })).toBeVisible();
  expect(screen.getByText("尚无参与者消息。")).toBeVisible();
  rerender(<SharedThread messages={[]} loading />);
  expect(screen.getByRole("status")).toHaveTextContent("正在加载服务器沟通记录");
  rerender(<SharedThread messages={[message]} />);
  expect(screen.getByText(message.body)).toBeVisible();
  expect(screen.getByText("家长 · 消息 1")).toBeVisible();
  expect(container).not.toHaveTextContent(MESSAGE);
});

it.each([
  ["pending", "等待顾问确认"],
  ["stale", "所依据的档案版本已更新"],
  ["expired", "候选事实已过期"],
  ["confirmed", "已确认进入事实记录"],
  ["rejected", "未被采纳"],
] as const)("presents candidate state %s without raw codes or identifiers", (state, visible) => {
  const candidate = { ...advisorCandidate, state } as MemoryCandidateProjection;
  const { container } = renderPresentation(<MemoryCandidateCard candidate={candidate} />);
  expect(screen.getByRole("heading", { name: "预算事实提案" })).toBeVisible();
  expect(screen.getByText("¥300,000–400,000")).toBeVisible();
  expect(screen.getByText(visible)).toBeVisible();
  expect(screen.queryByText(state, { exact: true })).toBeNull();
  expect(container).not.toHaveTextContent(new RegExp(`candidate_id|schema_version|${CANDIDATE}`, "i"));
});

it("uses a bounded fallback for an additive candidate state", () => {
  const raw = "future_state_secret";
  const candidate = { ...participantCandidate, state: raw } as unknown as MemoryCandidateProjection;
  const { container } = renderPresentation(<MemoryCandidateCard candidate={candidate} />);
  expect(screen.getByText("状态暂不可用")).toBeVisible();
  expect(container).not.toHaveTextContent(raw);
});

it("presents confirmed fact, versions, and server-authored reason without internal IDs", () => {
  const { container } = renderPresentation(<ConfirmedFactSummary fact={fact} caseRevision={2} />);
  expect(screen.getByRole("heading", { name: "已确认家庭事实" })).toBeVisible();
  expect(screen.getByText("¥300,000–400,000")).toBeVisible();
  expect(screen.getByText("事实版本").closest("div")).toHaveTextContent("1");
  expect(screen.getByText("档案版本").closest("div")).toHaveTextContent("2");
  expect(screen.queryByText("Fact version", { exact: true })).toBeNull();
  expect(screen.queryByText("Case revision", { exact: true })).toBeNull();
  expect(screen.getByText("Confirmed by advisor.")).toBeVisible();
  expect(container).not.toHaveTextContent(/family\.budget|confirmed_fact_id|candidate_id|schema_version|45000000/i);
});

it("presents consultation intake inside the advisor workspace shell", () => {
  setState({ value: "thread_ready", context: baseContext });
  const { container } = renderPresentation(<CollaborationDemo />);

  expect(screen.getByRole("banner")).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 1, name: "把咨询记录核验为客户档案" })).toBeVisible();
  expect(screen.getByRole("list", { name: "顾问工作流阶段" })).toBeInTheDocument();
  expect(screen.getAllByText("咨询接入与信息核验").length).toBeGreaterThanOrEqual(1);
  expect(screen.getByText("同一 Case 的连接证明")).toBeVisible();
  expect(container.querySelector("[data-frame-slot='work'] .shared-thread")).toBeInTheDocument();
  expect(container.querySelector("[data-frame-slot='authority'] [data-primary-action='true']")).toBeInTheDocument();
  expect(container.querySelector("[data-frame-slot='evidence'] .shared-thread")).toBeNull();
  expect(screen.queryByRole("heading", { level: 1, name: "家庭协作与事实确认" })).toBeNull();
  expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  expect(container.querySelectorAll('[data-primary-action="true"]')).toHaveLength(1);
  expect(container.querySelectorAll('[role="status"]').length).toBeLessThanOrEqual(1);
});

it("keeps a journey conflict in the route hierarchy and focuses its h2 on entry", async () => {
  setState({ value: "thread_ready", context: baseContext }, "advisor-family");
  renderPresentation(<CollaborationDemo />);

  expect(screen.getByRole("heading", { level: 1, name: "把咨询记录核验为客户档案" })).toBeVisible();
  expect(screen.getByRole("heading", { level: 2, name: "另一个演示流程正在进行" })).toHaveAttribute("tabindex", "-1");
  await waitFor(() => expect(screen.getByRole("heading", { level: 2, name: "另一个演示流程正在进行" })).toHaveFocus());
  expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  expect(screen.getByRole("alert")).toBeInTheDocument();
});

it("focuses the route recovery heading when collaboration enters a recoverable error", async () => {
  setState({
    value: "recoverable_error",
    category: "stale",
    resumePhase: "replan_required",
    context: { ...baseContext, role: "advisor", candidate: advisorCandidate, fact, caseRevision: 2 },
  });
  renderPresentation(<CollaborationDemo />);

  await waitFor(() =>
    expect(screen.getByRole("heading", { level: 2, name: "协作流程已安全暂停" })).toHaveFocus(),
  );
  expect(screen.getByRole("alert")).toBeInTheDocument();
});

it("renders the governed human gates and no task or generic-chat affordance", async () => {
  setState({ value: "bootstrapping_parent", context: { ...baseContext, thread: null, messages: [] } });
  const view = renderPresentation(<CollaborationDemo />);
  expect(screen.getByRole("heading", { level: 1, name: "把咨询记录核验为客户档案" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "开始家长流程" }));
  expect(hook.current.connectParent).toHaveBeenCalledOnce();

  setState({ value: "thread_ready", context: baseContext });
  view.rerender(<CollaborationDemo />);
  expect(screen.getByText("当前角色：家长")).toBeVisible();
  expect(screen.getByRole("button", { name: "提交预算供顾问审核" })).toBeEnabled();

  setState({ value: "proposal_pending", context: { ...baseContext, candidate: participantCandidate } });
  view.rerender(<CollaborationDemo />);
  expect(screen.getByRole("button", { name: "以指定顾问身份继续" })).toBeEnabled();

  setState({ value: "advisor_reviewing", context: { ...baseContext, role: "advisor", candidate: { ...advisorCandidate, state: "pending", verification_id: null, decision: null, reason: null } } });
  view.rerender(<CollaborationDemo />);
  expect(screen.getByText("当前角色：顾问")).toBeVisible();
  expect(screen.getByRole("button", { name: "确认家庭预算" })).toBeEnabled();
  await waitFor(() => expect(screen.getByRole("heading", { name: "顾问确认" })).toHaveFocus());

  setState({ value: "replan_required", context: { ...baseContext, role: "advisor", candidate: advisorCandidate, fact, caseRevision: 2 } });
  view.rerender(<CollaborationDemo />);
  expect(screen.getByRole("heading", { name: "需要重新规划" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "继续进入规划" }));
  expect(hook.current.continueToPlanning).toHaveBeenCalledOnce();
  expect(screen.queryByRole("button", { name: /创建.*任务/ })).toBeNull();
  expect(screen.queryByText(/chat|agenttask|eventsource|schema_version|41000000/i)).toBeNull();
});

it("keeps confirmed fact visible during one disabled handoff validation", async () => {
  setState({ value: "handoff_validating", context: { ...baseContext, role: "advisor", candidate: advisorCandidate, fact, caseRevision: 2 } });
  renderPresentation(<CollaborationDemo />);
  expect(screen.getByText("事实版本").closest("[data-confirmed-record]")).toBeVisible();
  const technicalFactVersion = screen.getByText("Fact version", { exact: true }).closest("details");
  expect(technicalFactVersion).toBeInTheDocument();
  expect(technicalFactVersion).toHaveTextContent("1");
  expect(screen.getAllByText("¥300,000–400,000").some((element) => element.closest("[data-frame-slot='work']"))).toBe(true);
  expect(screen.getByRole("button", { name: "正在验证当前信息…" }).closest("[data-frame-slot='authority']")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "正在验证规划信息" })).toHaveFocus();
  expect(screen.getByRole("button", { name: "正在验证当前信息…" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "正在验证当前信息…" }).closest("details")).toBeNull();
  expect(screen.queryByRole("button", { name: "继续进入规划" })).toBeNull();
});

it.each([
  "stale", "expired_or_terminal", "active_task_blocked", "unsafe_or_unsupported",
  "wrong_role_or_not_found", "session_recovery_required", "transport_unavailable_or_timeout",
] satisfies CollaborationErrorCategory[])("renders bounded recovery category %s without its raw value", (category) => {
  const retry = vi.fn();
  const { container } = renderPresentation(<CollaborationRecoveryNotice category={category} onRetry={retry} />);
  expect(screen.getByRole("heading", { level: 2, name: "协作流程已安全暂停" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "重新载入协作信息" }));
  expect(retry).toHaveBeenCalledOnce();
  expect(container).not.toHaveTextContent(category);
});

it("offers the same authority chain in explicit English", async () => {
  localStorage.setItem("night-voyager:presentation-locale:v1", "en");
  setState({ value: "thread_ready", context: baseContext });
  renderPresentation(<CollaborationDemo />);
  await waitFor(() => expect(screen.getByRole("heading", { level: 1, name: "Verify consultation records into a client case" })).toBeVisible());
  expect(screen.getByRole("button", { name: "Submit the budget for advisor review" })).toBeEnabled();
  expect(screen.getByText(message.body)).toBeVisible();
});
