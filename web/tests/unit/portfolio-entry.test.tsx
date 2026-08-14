import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import Home from "../../app/page";
import { PresentationProvider } from "../../lib/presentation/context";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("portfolio entry", () => {
  it("presents the advisor workspace root without API or product-session effects", () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    const sessionRead = vi.spyOn(Storage.prototype, "getItem");

    const { container } = render(<PresentationProvider><Home /></PresentationProvider>);

    expect(container.querySelector(".advisor-portfolio-shell")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "让复杂的留学规划，清晰地向前。",
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("为留学顾问打造的 AI 协作平台").length).toBeGreaterThan(0);
    expect(screen.getAllByText("澳大利亚").length).toBeGreaterThan(0);
    expect(screen.getAllByText("在预算条件下推荐").length).toBeGreaterThan(0);
    expect(screen.getAllByText("日本").length).toBeGreaterThan(0);
    expect(screen.getAllByText("有条件备选").length).toBeGreaterThan(0);
    expect(screen.getAllByText("马来西亚").length).toBeGreaterThan(0);
    expect(screen.getAllByText("暂不可选").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "查看顾问工作流" })).toHaveAttribute(
      "href",
      "#product",
    );
    expect(screen.getByRole("link", { name: "GitHub ↗" })).toHaveAttribute(
      "href",
      "https://github.com/iTao-AI/night-voyager",
    );
    expect(screen.getAllByRole("link", { name: "查看完整咨询流程" })[0]).toHaveAttribute(
      "href",
      "/demo/collaboration",
    );
    expect(screen.getAllByRole("link", { name: "查看方案研判" })[0]).toHaveAttribute(
      "href",
      "/demo",
    );
    const headerNavigation = screen.getByRole("navigation", {
      name: "Night Voyager 导航",
    });
    expect(within(headerNavigation).getByRole("link", { name: "可信推进" })).toHaveAttribute("href", "#route-atlas");
    expect(
      screen.queryByRole("heading", {
        name: "把家庭事实变成可追溯的留学决策与行动计划",
      }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/M0 · Local bootstrap/)).not.toBeInTheDocument();
    expect(screen.queryByText(/99%|10,000 users|一万用户|节省 80%/i)).not.toBeInTheDocument();
    expect(container.querySelector(".advisor-workspace-preview")).toBeInTheDocument();
    expect(container.querySelector("img")).toBeNull();
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(sessionRead.mock.calls.some(([key]) => key === "night-voyager:m5")).toBe(false);
  });

  it("offers the same truthful routes in explicit English", () => {
    render(<PresentationProvider><Home /></PresentationProvider>);
    fireEvent.click(screen.getByRole("button", { name: "English" }));

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Move complex study-abroad planning forward with clarity.",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "See the advisor workflow" })).toHaveAttribute(
      "href",
      "#product",
    );
    expect(screen.getByRole("link", { name: "GitHub ↗" })).toHaveAttribute(
      "href",
      "https://github.com/iTao-AI/night-voyager",
    );
    expect(screen.getAllByRole("link", { name: "See the complete consultation flow" })[0]).toHaveAttribute(
      "href",
      "/demo/collaboration",
    );
    expect(screen.getAllByRole("link", { name: "See route analysis" })[0]).toHaveAttribute(
      "href",
      "/demo",
    );
    const headerNavigation = screen.getByRole("navigation", {
      name: "Night Voyager navigation",
    });
    expect(within(headerNavigation).getByRole("link", { name: "Trusted progress" })).toHaveAttribute("href", "#route-atlas");
    expect(screen.getAllByText(/An AI collaboration platform built for study-abroad advisors/i).length).toBeGreaterThan(0);
  });
});
