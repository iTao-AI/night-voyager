import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import DemoPage from "../../app/demo/page";
import Home from "../../app/page";
import { PresentationProvider } from "../../lib/presentation/context";

afterEach(cleanup);

describe("M5 connected demo design contract", () => {
  it("starts fail closed with one connected advisor action", () => {
    render(<PresentationProvider><DemoPage /></PresentationProvider>);

    expect(screen.getByText("本地合成演示")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "让路线分析先通过顾问判断" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "开始顾问流程" })).toBeEnabled();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("keeps the root on the split advisor presentation foundation", () => {
    const layout = readFileSync(resolve(process.cwd(), "app/layout.tsx"), "utf8");
    expect(layout).toContain('import "./styles.css"');
    expect(layout).toContain('import "./portfolio.css"');
    expect(layout).toContain('import "./workspace.css"');

    render(<PresentationProvider><Home /></PresentationProvider>);
    expect(screen.getByRole("heading", { level: 1, name: "把零散咨询，整理成可以推进的留学方案" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "顾问工作台导航" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "查看一次完整咨询流程" })[0]).toHaveAttribute("href", "/demo/collaboration");
    expect(screen.getByRole("link", { name: "了解方案如何被核对" })).toHaveAttribute("href", "/demo");
  });
});
