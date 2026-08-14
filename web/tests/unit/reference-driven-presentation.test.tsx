import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import Home from "../../app/page";
import { AdvisorProductFrame } from "../../components/presentation/AdvisorProductFrame";
import { PortfolioStory } from "../../components/presentation/PortfolioStory";
import { PresentationProvider } from "../../lib/presentation/context";
import { en, zhCN } from "../../lib/presentation/catalog";
import { PORTFOLIO_PREVIEW, PERSISTED_OUTCOME } from "../../lib/presentation/portfolio";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("reference-driven presentation contract", () => {
  it("freezes the approved bilingual public story and CTA map", () => {
    expect(zhCN.productPromise).toBe("为留学顾问打造的 AI 协作平台");
    expect(zhCN.rootEyebrow).toBe("为留学顾问打造的 AI 协作平台");
    expect(zhCN.rootTitleLineOne).toBe("让复杂的留学规划，");
    expect(zhCN.rootTitleLineTwo).toBe("清晰地向前。");
    expect(zhCN.rootSummary).toBe(
      "Night Voyager 帮助顾问把散落在对话里的预算、目标、时间和现实条件整理清楚，再据此比较不同路线、说明推荐理由，并推进下一步。AI 协助整理与分析，关键判断仍由顾问完成。",
    );
    expect(zhCN.rootPrimaryAction).toBe("查看顾问工作流");
    expect(zhCN.rootSecondaryAction).toBe("GitHub ↗");
    expect(en.productPromise).toBe("An AI collaboration platform built for study-abroad advisors");
    expect(en.rootTitleLineOne).toBe("Move complex study-abroad planning forward");
    expect(en.rootTitleLineTwo).toBe("with clarity.");
    expect(en.rootSummary).toBe(
      "Night Voyager helps advisors organize the budgets, goals, timelines, and practical constraints scattered across conversations, then compare routes, explain recommendations, and move the next step forward. AI assists with organization and analysis; the advisor retains every consequential judgment.",
    );
    expect(en.rootPrimaryAction).toBe("See the advisor workflow");
    expect(en.rootSecondaryAction).toBe("GitHub ↗");
  });

  it("keeps the connected-story root projection separate from the persisted outcome", () => {
    expect(PORTFOLIO_PREVIEW.intendedField).toBe("computing");
    expect(PORTFOLIO_PREVIEW.budget).toEqual({
      currency: "CNY",
      preferredMinor: 30_000_000,
      hardCeilingMinor: 40_000_000,
    });
    expect(JSON.stringify(PORTFOLIO_PREVIEW)).not.toContain("34000000");
    expect(JSON.stringify(PORTFOLIO_PREVIEW)).not.toContain("¥340,000–400,000");
    expect(zhCN.persistedOutcomeBudget).toBe("¥305,500–400,000");
    expect(en.persistedOutcomeBudget).toBe("CNY 305,500–400,000");
  });

  it("renders a static root with the product anchor, public GitHub CTA, and one boundary", () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    const setItemSpy = vi.spyOn(Storage.prototype, "setItem");

    const { container } = render(<PresentationProvider><Home /></PresentationProvider>);

    expect(screen.getByRole("heading", { level: 1, name: "让复杂的留学规划，清晰地向前。" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看顾问工作流" })).toHaveAttribute("href", "#product");
    expect(screen.getByRole("link", { name: "GitHub ↗" })).toHaveAttribute(
      "href",
      "https://github.com/iTao-AI/night-voyager",
    );
    expect(container.querySelector("#product")).toBeInTheDocument();
    expect(screen.getAllByText(zhCN.publicBoundary, { exact: true })).toHaveLength(1);
    expect(container.querySelector("img")).toBeNull();
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(setItemSpy).not.toHaveBeenCalled();
  });

  it("keeps every home-document id unique and resolves each aria-labelledby reference", () => {
    const { container } = render(<PresentationProvider><Home /></PresentationProvider>);
    const ids = [...container.querySelectorAll<HTMLElement>("[id]")].map((element) => element.id);
    expect(ids).toEqual([...new Set(ids)]);

    for (const element of container.querySelectorAll<HTMLElement>("[aria-labelledby]")) {
      for (const reference of element.getAttribute("aria-labelledby")!.split(/\s+/)) {
        expect(container.ownerDocument.getElementById(reference)).toBeInTheDocument();
      }
    }
  });

  it("authors all three static story subjects in confirmed, route, outcome order", () => {
    const { container } = render(<PresentationProvider><PortfolioStory /></PresentationProvider>);
    expect([...container.querySelectorAll<HTMLElement>(".portfolio-story-static-subject .advisor-workspace-preview")]
      .map((element) => element.dataset.previewScene))
      .toEqual(["confirmed", "route", "outcome"]);
  });

  it("keeps the plain wordmark and candidate status public-neutral", () => {
    const css = ["app/styles.css", "app/portfolio.css", "app/workspace.css"]
      .map((file) => readFileSync(resolve(process.cwd(), file), "utf8"))
      .join("\n");
    const spec = readFileSync(resolve(process.cwd(), "../docs/superpowers/specs/2026-08-14-reference-driven-presentation.md"), "utf8");
    const plan = readFileSync(resolve(process.cwd(), "../docs/superpowers/plans/2026-08-14-reference-driven-presentation.md"), "utf8");

    expect(css).toContain("--font-latin");
    expect(css).toMatch(/\.portfolio-brand[\s\S]*font-size:\s*20px[\s\S]*letter-spacing:\s*-\.035em/);
    expect(css).toMatch(/\.workspace-brand[\s\S]*font-size:\s*20px[\s\S]*letter-spacing:\s*-\.035em/);
    expect(css).not.toContain("brand-mark");
    expect(spec).toContain("Status: `LOCAL CANDIDATE / IN REVIEW`");
    expect(spec).toContain("Publication: `NOT PUSHED / NOT MERGED / NOT RELEASED / NOT DEPLOYED`");
    expect(plan).toContain("Status: `LOCAL CANDIDATE / IN REVIEW`");
    expect(plan).toContain("Publication: `NOT PUSHED / NOT MERGED / NOT RELEASED / NOT DEPLOYED`");
  });

  it("keeps the three public scenes and persisted outcome values typed and bounded", () => {
    expect(PERSISTED_OUTCOME).toEqual({
      route: "australia",
      budget: "¥305,500–400,000",
      tradeoff: "预算弹性",
      source: "客户直接确认",
      intakeMonth: "2027-02",
      timeline: [
        "文件准备 · 2026-09-01 · 学生",
        "提交申请 · 2026-10-15 · 学生",
        "签证准备 · 2026-12-15 · 学生",
        "抵达准备 · 2027-01-20 · 家长",
      ],
    });

    const { container } = render(<PresentationProvider><PortfolioStory /></PresentationProvider>);
    expect([...container.querySelectorAll<HTMLElement>("[data-story-sentinel]")].map((node) => node.dataset.storyScene)).toEqual([
      "confirmed",
      "route",
      "outcome",
    ]);
    const storySource = readFileSync(
      resolve(process.cwd(), "components/presentation/PortfolioStory.tsx"),
      "utf8",
    );
    expect(storySource).toContain("IntersectionObserver");
    expect(storySource).toContain("observer?.disconnect()");
    expect(storySource).not.toMatch(/fetch\s*\(|localStorage|sessionStorage|EventSource|document\.cookie/);
  });

  it("keeps the shared product frame pure and exposes authored mobile reading order", () => {
    const frameSource = readFileSync(
      resolve(process.cwd(), "components/presentation/AdvisorProductFrame.tsx"),
      "utf8",
    );
    expect(frameSource).not.toMatch(/fetch\s*\(|XMLHttpRequest|EventSource|document\.cookie|localStorage|sessionStorage|use[A-Z].*(Controller|Reducer)|api\//);

    const { container } = render(
      <AdvisorProductFrame
        topBand={<p>客户档案 · 档案版本 2</p>}
        workflow={<ol><li>方案研判</li></ol>}
        context={<p>已确认信息</p>}
        currentWork={<h2>当前路线</h2>}
        evidence={<p>路线依据</p>}
        authority={<p>顾问审核</p>}
        technical={<p>Technical evidence</p>}
      />,
    );

    expect(container.querySelector("[data-product-frame]")).toBeInTheDocument();
    expect(container.querySelector("[data-frame-slot='context']")).toHaveAttribute("data-column-span", "2");
    expect(container.querySelector("[data-frame-slot='work']")).toHaveAttribute("data-column-span", "7");
    expect(container.querySelector("[data-frame-slot='authority']")).toHaveAttribute("data-column-span", "3");
    const orderedSlots = [...container.querySelectorAll<HTMLElement>("[data-frame-slot]")]
      .map((element) => element.dataset.frameSlot)
      .filter((slot): slot is string => Boolean(slot));
    expect(orderedSlots).toEqual(["top-band", "workflow", "context", "work", "evidence", "authority", "technical"]);
  });

  it("does not expose technical identifiers in the first-level root story", () => {
    const { container } = render(<PresentationProvider><Home /></PresentationProvider>);
    const firstLayer = container.querySelector("main")?.cloneNode(true) as HTMLElement;
    firstLayer.querySelectorAll("details").forEach((element) => element.remove());
    expect(firstLayer.textContent).not.toMatch(/Case revision|Fact version|DecisionReceipt|TimelinePlan|AgentTask|Skill pin/i);
  });
});
