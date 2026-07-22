import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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

    render(<PresentationProvider><Home /></PresentationProvider>);

    expect(screen.getByRole("heading", { name: "把家庭事实变成可追溯的留学决策与行动计划" })).toBeInTheDocument();
    expect(screen.getByText(/消息不是事实/)).toBeInTheDocument();
    expect(screen.getByText(/本地合成数据/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "体验完整决策流程" })).toHaveAttribute("href", "/demo/collaboration");
    expect(screen.getByRole("link", { name: "直接查看顾问到家庭流程" })).toHaveAttribute("href", "/demo");
    expect(screen.queryByText(/M0 · Local bootstrap/)).not.toBeInTheDocument();
    expect(screen.queryByText(/99%|10,000 users|一万用户|节省 80%/i)).not.toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(sessionRead.mock.calls.some(([key]) => key === "night-voyager:m5")).toBe(false);
  });

  it("offers the same truthful routes in explicit English", () => {
    render(<PresentationProvider><Home /></PresentationProvider>);
    fireEvent.click(screen.getByRole("button", { name: "English" }));

    expect(screen.getByRole("heading", { name: "Turn family facts into a traceable study-abroad decision and action plan" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Experience the complete decision flow" })).toHaveAttribute("href", "/demo/collaboration");
    expect(screen.getByRole("link", { name: "Go directly to the advisor-to-family flow" })).toHaveAttribute("href", "/demo");
    expect(screen.getByText(/local synthetic data/i)).toBeInTheDocument();
  });
});
