import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import Home from "../../app/page";
import { PresentationProvider } from "../../lib/presentation/context";

afterEach(cleanup);

describe("presentation accessibility contract", () => {
  it("keeps one ordered page heading, landmarks, skip target, and native disclosure", () => {
    const { container } = render(<PresentationProvider><Home /></PresentationProvider>);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(3);
    const levels = [...container.querySelectorAll("h1,h2,h3")].map((heading) => Number(heading.tagName.slice(1)));
    expect(levels[0]).toBe(1);
    expect(levels.every((level, index) => index === 0 || level <= levels[index - 1] + 1)).toBe(true);
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "跳到主要内容" })).toHaveAttribute("href", "#main-content");
    expect(container.querySelector("#route-atlas")).toBeInTheDocument();
    expect(container.querySelector("#journey")).toBeInTheDocument();
    expect(container.querySelector("details > summary")).toBeInstanceOf(HTMLElement);
    expect(screen.getByRole("link", { name: "查看示例方案" }).closest("details")).toBeNull();
  });

  it("declares durable focus, target, wrapping, link, CJK, and reduced-motion CSS", () => {
    const css = readFileSync(resolve(process.cwd(), "app/styles.css"), "utf8");
    expect(css).toContain('"PingFang SC"');
    expect(css).toContain('"Microsoft YaHei"');
    expect(css).toContain('"Noto Sans CJK SC"');
    expect(css).toMatch(/:focus-visible/);
    expect(css).toMatch(/min-(?:height|block-size):\s*44px/);
    expect(css).toMatch(/text-decoration:\s*underline/);
    expect(css).toMatch(/overflow-wrap:\s*anywhere/);
    expect(css).toMatch(/@media\s*\(prefers-reduced-motion:\s*reduce\)/);
    expect(css).not.toMatch(/-webkit-line-clamp|line-clamp/);
  });
});
