import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PresentationShell } from "../../components/presentation/PresentationShell";
import { PresentationProvider } from "../../lib/presentation/context";

afterEach(cleanup);

describe("PresentationShell", () => {
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
});
