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
        name: "把零散咨询，整理成可以推进的留学方案",
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/留学顾问的 AI 协作工作台|为留学顾问设计/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("澳大利亚").length).toBeGreaterThan(0);
    expect(screen.getAllByText("在预算条件下推荐").length).toBeGreaterThan(0);
    expect(screen.getAllByText("日本").length).toBeGreaterThan(0);
    expect(screen.getAllByText("有条件备选").length).toBeGreaterThan(0);
    expect(screen.getAllByText("马来西亚").length).toBeGreaterThan(0);
    expect(screen.getAllByText("暂不可选").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "查看一次完整咨询流程" })[0]).toHaveAttribute(
      "href",
      "/demo/collaboration",
    );
    expect(screen.getAllByRole("link", { name: "了解方案如何被核对" })[0]).toHaveAttribute(
      "href",
      "/demo",
    );
    const headerNavigation = screen.getByRole("navigation", {
      name: "顾问工作台导航",
    });
    expect(within(headerNavigation).getByRole("link", { name: "方案研判" })).toHaveAttribute("href", "#route-atlas");
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
        name: "Turn scattered consultations into a client plan you can move forward",
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Walk through one client case" })[0]).toHaveAttribute(
      "href",
      "/demo/collaboration",
    );
    expect(screen.getByRole("link", { name: "See how the proposal is verified" })).toHaveAttribute(
      "href",
      "/demo",
    );
    const headerNavigation = screen.getByRole("navigation", {
      name: "Advisor workspace navigation",
    });
    expect(within(headerNavigation).getByRole("link", { name: "Route analysis" })).toHaveAttribute("href", "#route-atlas");
    expect(screen.getAllByText(/AI collaboration workspace for study-abroad advisors/i).length).toBeGreaterThan(0);
  });
});
