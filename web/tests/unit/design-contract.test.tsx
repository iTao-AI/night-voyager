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
    expect(screen.getByRole("heading", { level: 1, name: "让复杂的留学规划，清晰地向前。" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Night Voyager 导航" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看顾问工作流" })).toHaveAttribute("href", "#product");
    expect(screen.getByRole("link", { name: "GitHub ↗" })).toHaveAttribute("href", "https://github.com/iTao-AI/night-voyager");
  });
});
