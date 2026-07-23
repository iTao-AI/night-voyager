import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PresentationShell } from "../../components/presentation/PresentationShell";
import { PresentationProvider } from "../../lib/presentation/context";

afterEach(cleanup);

describe("PresentationShell", () => {
  it("keeps the cinematic shell root-only and both governed demos on PresentationShell", () => {
    const rootPage = readFileSync(resolve(process.cwd(), "app/page.tsx"), "utf8");
    const connectedDemo = readFileSync(
      resolve(process.cwd(), "components/connected-demo/ConnectedDemo.tsx"),
      "utf8",
    );
    const collaborationDemo = readFileSync(
      resolve(process.cwd(), "components/collaboration-demo/CollaborationDemo.tsx"),
      "utf8",
    );

    expect(rootPage).toContain("PortfolioShell");
    expect(rootPage).not.toContain("PresentationShell");
    expect(connectedDemo).toContain("PresentationShell");
    expect(collaborationDemo).toContain("PresentationShell");
  });

  it("provides one shared landmark shell, skip link, synthetic boundary, and selected locale", () => {
    render(
      <PresentationProvider>
        <PresentationShell contextKey="contextPortfolio">
          <h1 id="main-heading">把家庭事实变成计划</h1>
        </PresentationShell>
      </PresentationProvider>,
    );

    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "跳到主要内容" })).toHaveAttribute("href", "#main-content");
    expect(screen.getByText("本地合成演示")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "中文" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "English" })).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(screen.getByRole("button", { name: "English" }));
    expect(screen.getByRole("link", { name: "Skip to main content" })).toBeInTheDocument();
    expect(screen.getByText("Local synthetic demo")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "English" })).toHaveAttribute("aria-pressed", "true");
  });

  it("supports a route-owned main target without changing landmark order", () => {
    render(
      <PresentationProvider>
        <PresentationShell contextKey="contextAdvisorFamily" mainId="demo-main">
          <h1>当前决策阶段</h1>
        </PresentationShell>
      </PresentationProvider>,
    );
    expect(screen.getByRole("link", { name: "跳到主要内容" })).toHaveAttribute("href", "#demo-main");
    expect(screen.getByRole("main")).toHaveAttribute("id", "demo-main");
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });
});
