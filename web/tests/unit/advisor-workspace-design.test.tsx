import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import Home from "../../app/page";
import { AdvisorWorkspacePreview } from "../../components/presentation/AdvisorWorkspacePreview";
import { AdvisorWorkspaceShell } from "../../components/presentation/AdvisorWorkspaceShell";
import { PresentationProvider } from "../../lib/presentation/context";
import {
  WORKFLOW_STAGES,
  collaborationWorkflowStage,
  connectedWorkflowStage,
  planExecutionWorkflowStage,
} from "../../lib/presentation/journey";
import { en, zhCN } from "../../lib/presentation/catalog";
import { PORTFOLIO_PREVIEW } from "../../lib/presentation/portfolio";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("advisor workspace presentation contract", () => {
  it("freezes the approved advisor-first metadata and hero copy", () => {
    expect(zhCN.documentTitle).toBe("Night Voyager｜留学顾问的 AI 协作工作台");
    expect(zhCN.documentDescription).toBe(
      "把分散在聊天、资料和研究中的信息，整理成可核对、可沟通、可推进的留学方案。",
    );
    expect(zhCN.rootEyebrow).toBe("AI 协作工作台 · 为留学顾问设计");
    expect(zhCN.rootTitle).toBe("把零散咨询，整理成可以推进的留学方案");
    expect(zhCN.rootSummary).toBe(
      "Night Voyager 帮助顾问整理客户信息、核对证据、比较留学路线并推进后续计划。AI 负责研究与草拟，关键判断仍由顾问确认。",
    );
    expect(zhCN.rootPrimaryAction).toBe("查看一次完整咨询流程");
    expect(zhCN.rootSecondaryAction).toBe("了解方案如何被核对");

    expect(en.documentTitle).toBe(
      "Night Voyager | AI Collaboration Workspace for Study-Abroad Advisors",
    );
    expect(en.documentDescription).toBe(
      "Turn fragmented conversations, evidence, and route research into a reviewable client plan.",
    );
    expect(en.rootEyebrow).toBe(
      "AI collaboration workspace for study-abroad advisors",
    );
    expect(en.rootTitle).toBe(
      "Turn scattered consultations into a client plan you can move forward",
    );
    expect(en.rootSummary).toBe(
      "Night Voyager helps advisors organize client facts, review evidence, compare study routes, and carry the decision into execution. AI researches and drafts; the advisor keeps professional judgment.",
    );
    expect(en.rootPrimaryAction).toBe("Walk through one client case");
    expect(en.rootSecondaryAction).toBe("See how the proposal is verified");
  });

  it("uses the closed five-stage workflow and fails closed for unknown state", () => {
    expect(WORKFLOW_STAGES).toEqual([
      "consultation_intake",
      "client_fact_review",
      "route_analysis",
      "client_confirmation",
      "execution_followup",
    ]);
    expect(collaborationWorkflowStage("bootstrapping_parent")).toBe("consultation_intake");
    expect(collaborationWorkflowStage("proposal_pending")).toBe("client_fact_review");
    expect(collaborationWorkflowStage("replan_required")).toBe("route_analysis");
    expect(collaborationWorkflowStage("recoverable_error", "replan_required")).toBe("route_analysis");
    expect(collaborationWorkflowStage("recoverable_error", "future_state_secret")).toBeNull();
    expect(connectedWorkflowStage("revision_requested")).toBe("client_fact_review");
    expect(connectedWorkflowStage("task_streaming")).toBe("route_analysis");
    expect(connectedWorkflowStage("advisor_review")).toBe("route_analysis");
    expect(connectedWorkflowStage("family_review")).toBe("client_confirmation");
    expect(connectedWorkflowStage("plan_ready")).toBe("execution_followup");
    expect(connectedWorkflowStage("role_switching", { value: "advisor_review" })).toBe("route_analysis");
    expect(connectedWorkflowStage("recoverable_error", { value: "family_review" })).toBe("client_confirmation");
    expect(connectedWorkflowStage("active_task")).toBeNull();
    expect(connectedWorkflowStage("review_required")).toBeNull();
    expect(connectedWorkflowStage("recoverable_error", { value: "future_state_secret" })).toBeNull();
    expect(planExecutionWorkflowStage("ready_to_start")).toBe("execution_followup");
    expect(planExecutionWorkflowStage("recoverable_error")).toBe("execution_followup");
    expect(planExecutionWorkflowStage("future_state_secret")).toBeNull();
  });

  it("freezes proof-segment labels and deterministic root preview facts", () => {
    expect(PORTFOLIO_PREVIEW.proofSegment).toBe("connected_same_case");
    expect(PORTFOLIO_PREVIEW.syntheticBoundary).toBe(true);
    expect(PORTFOLIO_PREVIEW.intendedField).toBe("computing");
    expect(PORTFOLIO_PREVIEW.budget).toEqual({
      currency: "CNY",
      preferredMinor: 34_000_000,
      hardCeilingMinor: 40_000_000,
    });
    expect(PORTFOLIO_PREVIEW.routes.map(({ id }) => id)).toEqual([
      "australia",
      "japan",
      "malaysia",
    ]);
    expect(PORTFOLIO_PREVIEW.routes.map(({ outcome }) => outcome)).toEqual([
      "recommended_with_condition",
      "conditional",
      "blocked",
    ]);
    expect(PORTFOLIO_PREVIEW.nextAction).toBe("review_routes");
    expect(JSON.stringify(PORTFOLIO_PREVIEW)).not.toMatch(
      /Synthetic (Australia|Japan|Malaysia) Institution|Synthetic Demo Publisher|40000000-0000|51000000-0000|2026-07-01/i,
    );
    expect(zhCN.workflowStageConsultationIntake).toBe("咨询接入");
    expect(zhCN.workflowStageClientFactReview).toBe("信息核验");
    expect(zhCN.workflowStageRouteAnalysis).toBe("方案研判");
    expect(zhCN.workflowStageClientConfirmation).toBe("客户确认");
    expect(zhCN.workflowStageExecutionFollowup).toBe("执行跟进");
    expect(en.workflowStageConsultationIntake).toBe("Consultation intake");
    expect(en.workflowStageClientFactReview).toBe("Client fact review");
    expect(en.workflowStageRouteAnalysis).toBe("Route analysis");
    expect(en.workflowStageClientConfirmation).toBe("Client confirmation");
    expect(en.workflowStageExecutionFollowup).toBe("Execution follow-up");
  });

  it("keeps the canonical preview as the only production route model", () => {
    const source = readFileSync(resolve(process.cwd(), "lib/presentation/portfolio.ts"), "utf8");

    expect(source).not.toContain("PORTFOLIO_ROUTE_STOPS");
    expect(source).not.toContain("PortfolioRouteStop");
  });

  it("renders the root as an advisor workspace and keeps the root static", () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    const storageRead = vi.spyOn(Storage.prototype, "getItem");
    const { container } = render(<PresentationProvider><Home /></PresentationProvider>);

    expect(screen.getByRole("heading", { level: 1, name: zhCN.rootTitle })).toBeInTheDocument();
    expect(screen.getByText(zhCN.rootEyebrow)).toBeInTheDocument();
    expect(screen.getAllByText(/留学顾问的 AI 协作工作台/).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: zhCN.rootPrimaryAction })[0]).toHaveAttribute(
      "href",
      "/demo/collaboration",
    );
    expect(screen.getAllByRole("link", { name: zhCN.rootSecondaryAction })[0]).toHaveAttribute(
      "href",
      "/demo",
    );
    const workflow = container.querySelector<HTMLElement>(".portfolio-workflow-list")!;
    expect(within(workflow).getByText("咨询接入")).toBeInTheDocument();
    expect(within(workflow).getByText("信息核验")).toBeInTheDocument();
    expect(within(workflow).getByText("方案研判")).toBeInTheDocument();
    expect(within(workflow).getByText("客户确认")).toBeInTheDocument();
    expect(within(workflow).getByText("执行跟进")).toBeInTheDocument();

    const navigation = screen.getByRole("navigation", { name: zhCN.rootNavigationLabel });
    expect(withinText(navigation)).not.toMatch(/家庭表达|家庭决定|顾问到家庭决策流程/);
    expect(withinText(document.querySelector("main")!)).not.toMatch(/家庭表达|家庭决定|顾问到家庭决策流程/);
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(storageRead.mock.calls.some(([key]) => key === "night-voyager:m5")).toBe(false);
  });

  it("keeps the public root hierarchy advisor-first in both locales", () => {
    const { container } = render(<PresentationProvider><Home /></PresentationProvider>);
    const assertAdvisorFirst = (locale: "zh-CN" | "en") => {
      const navigation = screen.getByRole("navigation", {
        name: locale === "zh-CN" ? zhCN.rootNavigationLabel : en.rootNavigationLabel,
      });
      const headings = container.querySelectorAll(".advisor-portfolio-shell h1, .advisor-portfolio-shell h2, .advisor-portfolio-shell h3");
      expect(withinText(navigation)).not.toMatch(/家庭表达|家庭决定|顾问到家庭决策流程|Family input|Family decision|Advisor-to-family decision flow/i);
      expect([...headings].map((heading) => heading.textContent ?? "").join(" ")).not.toMatch(
        /家庭表达|家庭决定|顾问到家庭决策流程|Family input|Family decision|Advisor-to-family decision flow/i,
      );
    };

    assertAdvisorFirst("zh-CN");
    fireEvent.click(screen.getByRole("button", { name: "English" }));
    assertAdvisorFirst("en");
  });

  it("keeps the shared shell presentation-only and exposes one route heading", () => {
    const sourcePaths = [
      "components/presentation/AdvisorWorkspaceShell.tsx",
      "components/presentation/WorkflowRail.tsx",
      "components/presentation/AdvisorWorkspacePreview.tsx",
    ];
    for (const relativePath of sourcePaths) {
      const source = readFileSync(resolve(process.cwd(), relativePath), "utf8");
      expect(source).not.toMatch(/fetch\s*\(|XMLHttpRequest|EventSource|localStorage\.setItem|sessionStorage\.setItem|document\.cookie|createTask|mutation/i);
    }

    render(
      <PresentationProvider>
        <AdvisorWorkspaceShell
          activeRole="advisor"
          contextKey="contextPortfolio"
          currentStage="route_analysis"
          mainId="shell-main"
          proofSegment="independent_execution_scenario"
          status={<p>Current route analysis</p>}
          titleKey="rootTitle"
        >
          <p>Current work</p>
        </AdvisorWorkspaceShell>
      </PresentationProvider>,
    );
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByText(zhCN.proofSegmentIndependentExecutionScenario)).toBeInTheDocument();
    expect(screen.getByRole("list", { name: zhCN.workflowRailLabel })).toBeInTheDocument();
    expect(screen.getAllByRole("listitem").filter((item) => item.getAttribute("aria-current") === "step")).toHaveLength(1);
  });

  it("keeps a filled primary action singular in the preview and labels plan as separate", () => {
    const { container } = render(
      <PresentationProvider>
        <AdvisorWorkspacePreview />
      </PresentationProvider>,
    );
    expect(container.querySelectorAll("[data-primary-action='true']")).toHaveLength(1);
    expect(container.querySelectorAll("[data-proof-segment='independent_execution_scenario']")).toHaveLength(0);
    expect(screen.getAllByText(/澳大利亚|Australia/).length).toBeGreaterThan(0);
    expect(zhCN.separateExecutionScenario).toMatch(/单独|独立/);
    expect(en.separateExecutionScenario).toMatch(/separate|independent/i);
  });
});

function withinText(element: Element): string {
  return element.textContent ?? "";
}
