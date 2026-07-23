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
  it("presents the Chinese-first truthful route without API or session effects", () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    const sessionRead = vi.spyOn(Storage.prototype, "getItem");

    const { container } = render(<PresentationProvider><Home /></PresentationProvider>);

    expect(container.querySelector(".portfolio-night")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "你的留学路线 应该从你出发",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(/为什么适合你/)).toBeInTheDocument();
    expect(screen.getAllByText("澳大利亚").length).toBeGreaterThan(0);
    expect(screen.getAllByText("推荐").length).toBeGreaterThan(0);
    expect(screen.getAllByText("日本").length).toBeGreaterThan(0);
    expect(screen.getAllByText("备选").length).toBeGreaterThan(0);
    expect(screen.getAllByText("马来西亚").length).toBeGreaterThan(0);
    expect(screen.getAllByText("暂不推荐").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "查看示例方案" })).toHaveAttribute(
      "href",
      "/demo/collaboration",
    );
    expect(screen.getByRole("link", { name: "查看路线依据" })).toHaveAttribute(
      "href",
      "#route-atlas",
    );
    const headerNavigation = screen.getByRole("navigation", {
      name: "作品集导航",
    });
    expect(within(headerNavigation).getByRole("link", { name: "决策依据" })).toHaveAttribute(
      "href",
      "/demo",
    );
    expect(
      screen.queryByRole("heading", {
        name: "把家庭事实变成可追溯的留学决策与行动计划",
      }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/M0 · Local bootstrap/)).not.toBeInTheDocument();
    expect(screen.queryByText(/99%|10,000 users|一万用户|节省 80%/i)).not.toBeInTheDocument();
    const picture = container.querySelector(".portfolio-backdrop picture");
    expect(picture?.querySelectorAll("source")).toHaveLength(2);
    expect(picture?.querySelector("source")?.getAttribute("type")).toBe("image/avif");
    expect(picture?.querySelector("source:nth-of-type(2)")?.getAttribute("type")).toBe(
      "image/webp",
    );
    expect(picture?.querySelector("img")).toHaveAttribute("alt", "");
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(sessionRead.mock.calls.some(([key]) => key === "night-voyager:m5")).toBe(false);
  });

  it("offers the same truthful routes in explicit English", () => {
    render(<PresentationProvider><Home /></PresentationProvider>);
    fireEvent.click(screen.getByRole("button", { name: "English" }));

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Your study-abroad route should start with you",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View the example plan" })).toHaveAttribute(
      "href",
      "/demo/collaboration",
    );
    expect(screen.getByRole("link", { name: "View route evidence" })).toHaveAttribute(
      "href",
      "#route-atlas",
    );
    const headerNavigation = screen.getByRole("navigation", {
      name: "Portfolio navigation",
    });
    expect(within(headerNavigation).getByRole("link", { name: "Decision evidence" })).toHaveAttribute(
      "href",
      "/demo",
    );
    expect(screen.getByText(/why a route fits/i)).toBeInTheDocument();
  });
});
