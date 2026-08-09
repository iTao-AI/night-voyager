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
    expect(css).toMatch(/\.revision-comparison[\s\S]*overflow-wrap:\s*anywhere/);
    expect(css).toMatch(/\.revision-route-removed[\s\S]*color:/);
    expect(css).toMatch(/@media\s*\(max-width:\s*767px\)[\s\S]*\.revision-comparison-table/);
    expect(css).not.toMatch(/-webkit-line-clamp|line-clamp/);
  });

  it("freezes the presentation audit contrast, target, copy-size, and canonical Compose gate", () => {
    const css = readFileSync(resolve(process.cwd(), "app/styles.css"), "utf8");
    const e2e = readFileSync(resolve(process.cwd(), "e2e/presentation.spec.ts"), "utf8");
    const composeConfig = readFileSync(resolve(process.cwd(), "playwright.compose.config.ts"), "utf8");
    const composeProof = readFileSync(resolve(process.cwd(), "../scripts/verify_compose.sh"), "utf8");
    const currentText = css.match(/--journey-current-text:\s*(#[0-9a-f]{6})/i)?.[1];
    const rgb = (value: string) => value.match(/[0-9a-f]{2}/gi)!.map((channel) => Number.parseInt(channel, 16) / 255);
    const luminance = (value: string) => rgb(value).reduce((sum, channel, index) => {
      const linear = channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
      return sum + linear * [0.2126, 0.7152, 0.0722][index];
    }, 0);
    const contrast = (foreground: string, background: string) => {
      const light = Math.max(luminance(foreground), luminance(background));
      const dark = Math.min(luminance(foreground), luminance(background));
      return (light + 0.05) / (dark + 0.05);
    };

    expect(currentText).toBeDefined();
    expect(contrast(currentText!, "#fffdf8")).toBeGreaterThanOrEqual(4.5);
    expect(css).toMatch(/\.decision-journey-current\s*\{[^}]*font-size:\s*1rem/);
    expect(css).toMatch(/\.decision-journey-current\s+strong\s*\{[^}]*color:\s*var\(--journey-current-text\)/);
    expect(css).toMatch(/\.decision-journey-track li > span:last-child\s*\{[^}]*font-size:\s*1rem/);
    expect(css).toMatch(/\.confirmation-summary input\s*\{[^}]*width:\s*44px[^}]*height:\s*44px/);
    expect(css).toMatch(/\.product-mark\s*\{[^}]*min-height:\s*44px/);
    expect(e2e).toContain("target.height < 44 || target.width < 44");
    expect(composeConfig).toContain("presentation.spec.ts");
    expect(composeProof).toContain("PRESENTATION_AUDIT_OUTPUT_DIR");
    expect(composeProof).toContain("presentation.spec.ts");
  });
});
