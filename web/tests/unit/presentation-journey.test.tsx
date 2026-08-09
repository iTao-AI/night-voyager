import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { CollaborationDemo } from "../../components/collaboration-demo/CollaborationDemo";
import { EvidenceDisclosure } from "../../components/connected-demo/EvidenceDisclosure";
import { ConnectedDemo } from "../../components/connected-demo/ConnectedDemo";
import { MemoryCandidateCard } from "../../components/collaboration-demo/MemoryCandidateCard";
import { SharedThread } from "../../components/collaboration-demo/SharedThread";
import { PlanExecutionWorkspace } from "../../components/plan-execution/PlanExecutionWorkspace";
import { PresentationProvider } from "../../lib/presentation/context";
import {
  collaborationWorkflowStage,
  connectedWorkflowStage,
  planExecutionWorkflowStage,
} from "../../lib/presentation/journey";
import { en, zhCN } from "../../lib/presentation/catalog";
import type { CollaborationMessage, MemoryCandidateProjection } from "../../lib/collaboration-demo/contracts";
import { brief, ledger as ledgerFixture, status } from "./connected-demo-test-data";

const collaborationHook = vi.hoisted(() => ({ current: null as unknown }));
const connectedHook = vi.hoisted(() => ({ current: null as unknown }));
const planHook = vi.hoisted(() => ({ current: null as unknown }));

vi.mock("../../lib/collaboration-demo/use-collaboration-demo", () => ({
  useCollaborationDemo: () => collaborationHook.current,
}));
vi.mock("../../lib/connected-demo/use-connected-demo", () => ({
  useConnectedDemo: () => connectedHook.current,
}));
vi.mock("../../lib/plan-execution/use-plan-execution", () => ({
  usePlanExecution: () => planHook.current,
}));

const CASE_ID = "41000000-0000-0000-0000-000000000001";
const THREAD_ID = "42000000-0000-0000-0000-000000000001";
const MESSAGE_ID = "43000000-0000-0000-0000-000000000001";
const CANDIDATE_ID = "44000000-0000-0000-0000-000000000001";
const AT = "2026-07-20T01:02:03Z";
const RAW_MESSAGE = "Our confirmed program budget is 300,000 to 400,000 CNY.";
const RAW_REASON = "Confirmed by the assigned advisor. Keep the family ceiling visible.";
const RAW_LIMITATION = "Synthetic only; not live institutional coverage.";

const message: CollaborationMessage = {
  schema_version: 1,
  message_event_id: MESSAGE_ID,
  thread_id: THREAD_ID,
  case_id: CASE_ID,
  sequence_no: 1,
  actor_id: CASE_ID,
  actor_role: "parent",
  body: RAW_MESSAGE,
  content_sha256: "a".repeat(64),
  created_at: AT,
};

const candidate = {
  schema_version: 1,
  fact_key: "family.budget",
  value: {
    schema_version: 1,
    currency: "CNY",
    period: "program_total",
    preferred_minor: 30_000_000,
    hard_ceiling_minor: 40_000_000,
    elasticity_bps: 1000,
    refused: false,
  },
  state: "confirmed",
  created_at: AT,
  expires_at: "2026-07-27T01:02:03Z",
  candidate_id: CANDIDATE_ID,
  message_event_id: MESSAGE_ID,
  source_message_sequence_no: 1,
  subject_actor_id: CASE_ID,
  subject_role: "parent",
  case_revision: 1,
  verification_id: MESSAGE_ID,
  decision: "confirm",
  reason: RAW_REASON,
  request_sha256: "b".repeat(64),
  value_sha256: "c".repeat(64),
} as unknown as MemoryCandidateProjection;

function renderPresentation(ui: React.ReactElement) {
  return render(ui, { wrapper: PresentationProvider });
}

function collaborationState(value: string, role: "parent" | "advisor" = "parent") {
  collaborationHook.current = {
    state: {
      value,
      context: {
        role,
        caseId: CASE_ID,
        thread: { schema_version: 1, thread_id: THREAD_ID, case_id: CASE_ID, created_by_actor_id: CASE_ID, created_at: AT },
        messages: [message],
        candidate: value === "advisor_reviewing" ? candidate : null,
        fact: null,
        caseRevision: 1,
      },
    },
    inspector: null,
    journeyConflict: null,
    connectParent: vi.fn(),
    appendMessage: vi.fn(),
    proposeBudget: vi.fn(),
    switchToAdvisor: vi.fn(),
    confirmCandidate: vi.fn(),
    continueToPlanning: vi.fn(),
    retry: vi.fn(),
    endConflictingJourney: vi.fn(),
  };
}

function connectedState(value: string) {
  connectedHook.current = {
    state: value === "family_review"
      ? { value, status: status("family_review"), brief: brief("family_review") }
      : { value, status: status("review_required"), ledger: ledgerFixture("review-required") },
    inspector: null,
    journeyConflict: null,
    confirmed: false,
    setConfirmed: vi.fn(),
    endConflictingJourney: vi.fn(),
    connectAdvisor: vi.fn(),
    recover: vi.fn(),
    retry: vi.fn(),
    createTask: vi.fn(),
    approve: vi.fn(),
    requestRevision: vi.fn(),
    rotateToParent: vi.fn(),
    rotateToStudent: vi.fn(),
    rotateToAdvisor: vi.fn(),
    decide: vi.fn(),
  };
}

function planState(value: string) {
  planHook.current = {
    state: {
      value,
      context: {
        active_role: "student",
        execution_id: null,
      },
      view: null,
      receipt: null,
      error: null,
      operation: null,
      safeDisplayState: null,
    },
    busy: false,
    connect: vi.fn(),
    switchRole: vi.fn(),
    start: vi.fn(),
    attest: vi.fn(),
    verify: vi.fn(),
    reassess: vi.fn(),
    recover: vi.fn(),
  };
}

afterEach(() => {
  cleanup();
  localStorage.clear();
  collaborationHook.current = null;
  connectedHook.current = null;
  planHook.current = null;
  vi.clearAllMocks();
});

it("renders one closed five-stage workflow for each demo route", () => {
  collaborationState("thread_ready");
  const collaboration = renderPresentation(<CollaborationDemo />);
  expect(collaboration.container.querySelectorAll(".workflow-rail-list > li")).toHaveLength(5);
  expect(collaboration.container.querySelector("[data-current-stage='consultation_intake']")).not.toBeNull();
  collaboration.unmount();

  connectedState("family_review");
  const connected = renderPresentation(<ConnectedDemo />);
  expect(connected.container.querySelector("[data-current-stage='client_confirmation']")).not.toBeNull();
  connected.unmount();

  planState("ready_to_start");
  const plan = renderPresentation(<PlanExecutionWorkspace />);
  expect(plan.container.querySelector("[data-current-stage='execution_followup']")).not.toBeNull();
});

it("maps advisor confirmation and route review from existing route state", () => {
  collaborationState("advisor_reviewing", "advisor");
  const collaboration = renderPresentation(<CollaborationDemo />);
  expect(collaboration.container.querySelector("[data-current-stage='client_fact_review']")).not.toBeNull();
  collaboration.unmount();

  connectedState("advisor_review");
  const connected = renderPresentation(<ConnectedDemo />);
  expect(connected.container.querySelector("[data-current-stage='route_analysis']")).not.toBeNull();
  connected.unmount();

  connectedState("task_streaming");
  const routeReview = renderPresentation(<ConnectedDemo />);
  expect(routeReview.container.querySelector("[data-current-stage='route_analysis']")).not.toBeNull();
});

it("retains a known stage through recoverable and role-switching projections", () => {
  expect(collaborationWorkflowStage("recoverable_error", "replan_required")).toBe("route_analysis");
  expect(collaborationWorkflowStage("recoverable_error", "future_state_secret")).toBeNull();
  expect(connectedWorkflowStage("role_switching", { value: "advisor_review" })).toBe("route_analysis");
  expect(connectedWorkflowStage("recoverable_error", { value: "family_review" })).toBe("client_confirmation");
  expect(connectedWorkflowStage("recoverable_error", { value: "future_state_secret" })).toBeNull();
  expect(planExecutionWorkflowStage("recoverable_error")).toBe("execution_followup");
});

it("fails closed for unknown UI state without exposing the raw state", () => {
  collaborationState("future_state_secret");
  const collaboration = renderPresentation(<CollaborationDemo />);
  expect(collaboration.container.querySelector(".workflow-rail-list")).not.toBeNull();
  expect(collaboration.container.querySelector(".workflow-rail-list")?.getAttribute("data-current-stage")).toBeNull();
  expect(collaboration.container).not.toHaveTextContent("future_state_secret");
  collaboration.unmount();

  connectedState("future_state_secret");
  const connected = renderPresentation(<ConnectedDemo />);
  expect(connected.container.querySelector(".workflow-rail-list")).not.toBeNull();
  expect(connected.container.querySelector(".workflow-rail-list")?.getAttribute("data-current-stage")).toBeNull();
  expect(connected.container).not.toHaveTextContent("future_state_secret");
  connected.unmount();

  planState("future_state_secret");
  const plan = renderPresentation(<PlanExecutionWorkspace />);
  expect(plan.container.querySelector(".workflow-rail-list")).not.toBeNull();
  expect(plan.container.querySelector(".workflow-rail-list")?.getAttribute("data-current-stage")).toBeNull();
});

it("keeps business vocabulary and exact contract terms in the intended layers", () => {
  expect(zhCN.workflowStageConsultationIntake).toBe("咨询接入");
  expect(zhCN.workflowStageClientFactReview).toBe("信息核验");
  expect(zhCN.workflowStageRouteAnalysis).toBe("方案研判");
  expect(zhCN.workflowStageClientConfirmation).toBe("客户确认");
  expect(zhCN.workflowStageExecutionFollowup).toBe("执行跟进");
  expect(zhCN.typedProposalLabel).toBe("结构化事实提案");
  expect(zhCN.caseRevisionDisclosureLabel).toBe("档案版本");
  expect(zhCN.factVersionDisclosureLabel).toBe("事实版本");
  expect(zhCN.skillPinDisclosureLabel).toBe("规划能力版本");
  expect(zhCN.checkpointDisclosureLabel).toBe("行动节点");
  expect(en.typedProposalLabel).toBe("typed proposal");
  expect(en.caseRevisionDisclosureLabel).toBe("Case revision");
  expect(en.factVersionDisclosureLabel).toBe("Fact version");
  expect(en.skillPinDisclosureLabel).toBe("Skill pin");
  expect(en.checkpointDisclosureLabel).toBe("checkpoint");
  expect(en.messageOriginalLabel).toBe("Original message");
  expect(en.advisorReasonOriginalLabel).toBe("Original advisor confirmation");
  expect(en.workflowStageConsultationIntake).toBe("Consultation intake");
  expect(en.workflowStageClientFactReview).toBe("Client fact review");
  expect(en.workflowStageRouteAnalysis).toBe("Route analysis");
  expect(en.workflowStageClientConfirmation).toBe("Client confirmation");
  expect(en.workflowStageExecutionFollowup).toBe("Execution follow-up");
});

it("keeps English workflow labels and technical facts secondary", async () => {
  planState("ready_to_start");
  localStorage.setItem("night-voyager:presentation-locale:v1", "en");
  const plan = renderPresentation(<PlanExecutionWorkspace />);
  await waitFor(() => expect(plan.container.querySelector(".workflow-rail-list")).toHaveAttribute("data-current-stage", "execution_followup"));
  expect(plan.container.querySelector(".workflow-rail-label")).toHaveTextContent("Consultation intake");
  plan.unmount();

  collaborationState("thread_ready");
  const collaboration = renderPresentation(<CollaborationDemo />);
  const workflow = collaboration.container.querySelector(".workflow-rail");
  const thread = collaboration.container.querySelector(".shared-thread");
  const technical = collaboration.container.querySelector(".workspace-technical-evidence");
  expect(workflow).not.toBeNull();
  expect(thread).not.toBeNull();
  expect(technical).not.toBeNull();
  expect(technical?.querySelectorAll(".authority-steps > li")).toHaveLength(6);
  expect(workflow!.compareDocumentPosition(thread!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(thread!.compareDocumentPosition(technical!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

it("preserves server-owned message, advisor reason, and evidence limitation exactly", () => {
  const thread = renderPresentation(<SharedThread messages={[message]} />);
  expect(screen.getByText("消息原文")).toBeVisible();
  expect(screen.getByText(RAW_MESSAGE)).toBeVisible();
  thread.unmount();

  const candidateView = renderPresentation(<MemoryCandidateCard candidate={candidate} />);
  expect(screen.getByText("顾问确认原文")).toBeVisible();
  expect(screen.getByText(RAW_REASON)).toBeVisible();
  candidateView.unmount();

  const evidence = ledgerFixture("review-required").evidence.map((item) => ({
    ...item,
    limitation: RAW_LIMITATION,
  }));
  const evidenceView = renderPresentation(<EvidenceDisclosure evidence={evidence} />);
  const disclosure = evidenceView.container.querySelector("details");
  if (disclosure) disclosure.open = true;
  expect(screen.getByText("证据限制")).toBeVisible();
  expect(screen.getByText(RAW_LIMITATION)).toBeVisible();
});

it("keeps the shared journey presentational and side-effect free", () => {
  const file = resolve(process.cwd(), "components/presentation/WorkflowRail.tsx");
  const source = readFileSync(file, "utf8");
  expect(source).not.toMatch(/fetch\s*\(|localStorage|sessionStorage|document\.|window\.|EventSource|mutation|switchRole|useEffect|useState/);
});
