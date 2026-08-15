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
    expect(screen.getAllByRole("heading", { level: 2 }).length).toBeGreaterThanOrEqual(4);
    const levels = [...container.querySelectorAll("h1,h2,h3")].map((heading) => Number(heading.tagName.slice(1)));
    expect(levels[0]).toBe(1);
    expect(levels.every((level, index) => index === 0 || level <= levels[index - 1] + 1)).toBe(true);
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "跳到主要内容" })).toHaveAttribute("href", "#main-content");
    expect(container.querySelector("#route-atlas")).toBeInTheDocument();
    expect(container.querySelector("#journey")).toBeInTheDocument();
    expect(container.querySelector(".advisor-workspace-preview")).toBeInTheDocument();
    expect(container.querySelector(".portfolio-route-list")).toBeInTheDocument();
    expect(container.querySelector("details > summary")).toBeInstanceOf(HTMLElement);
    expect(screen.getAllByRole("link", { name: "查看完整咨询流程" })[0].closest("details")).toBeNull();
  });

  it("declares durable focus, target, wrapping, link, CJK, and reduced-motion CSS", () => {
    const css = ["app/styles.css", "app/portfolio.css", "app/workspace.css"]
      .map((file) => readFileSync(resolve(process.cwd(), file), "utf8"))
      .join("\n");
    expect(css).toContain('"PingFang SC"');
    expect(css).toContain('"Microsoft YaHei"');
    expect(css).toContain('"Noto Sans CJK SC"');
    expect(css).toMatch(/:focus-visible/);
    expect(css).toMatch(/min-(?:height|block-size):\s*44px/);
    expect(css).toMatch(/text-decoration:\s*underline/);
    expect(css).toMatch(/overflow-wrap:\s*anywhere/);
    expect(css).toMatch(/@media\s*\(prefers-reduced-motion:\s*reduce\)/);
    expect(css).toContain("--nv-environment: #061117");
    expect(css).toContain("--nv-work-surface: #fcfdfc");
    expect(css).toContain("--nv-action: #2b7486");
    expect(css).toContain("--nv-intervention: #ce765f");
    expect(css).toMatch(/\.workflow-rail-item\[data-state="current"\][\s\S]*border/);
    expect(css).toMatch(/\.portfolio-primary-action[\s\S]*min-block-size:\s*48px/);
    expect(css).toMatch(/@media\s*\(max-width:\s*767px\)[\s\S]*\.portfolio-workflow-list/);
    expect(css).not.toMatch(/-webkit-line-clamp|line-clamp/);
  });

  it("freezes the presentation audit contrast, target, copy-size, and canonical Compose gate", () => {
    const css = ["app/styles.css", "app/portfolio.css", "app/workspace.css"]
      .map((file) => readFileSync(resolve(process.cwd(), file), "utf8"))
      .join("\n");
    const e2e = readFileSync(resolve(process.cwd(), "e2e/presentation.spec.ts"), "utf8");
    const composeConfig = readFileSync(resolve(process.cwd(), "playwright.compose.config.ts"), "utf8");
    const composeProof = readFileSync(resolve(process.cwd(), "../scripts/verify_compose.sh"), "utf8");
    const currentText = css.match(/--nv-intervention:\s*(#[0-9a-f]{6})/i)?.[1];
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
    expect(contrast(currentText!, "#061117")).toBeGreaterThanOrEqual(4.5);
    expect(css).toMatch(/\.workflow-rail-item\[data-state="current"\]\s*\{[^}]*border-left-color:/);
    expect(css).toMatch(/\.portfolio-brand[\s\S]*min-block-size:\s*44px/);
    expect(css).toMatch(/\.workspace-context-facts[\s\S]*grid-template-columns/);
    expect(css).toMatch(/\.portfolio-primary-action[\s\S]*min-block-size:\s*48px/);
    expect(css).toContain("@media (max-width: 1023px)");
    expect(css).toContain("@media (min-width: 1280px)");
    expect(css).toMatch(
      /@media \(max-width: 560px\)[\s\S]*\.advisor-product-frame \.workflow-rail-list\s*\{[\s\S]*display:\s*flex;[\s\S]*flex-direction:\s*row;[\s\S]*overflow-x:\s*auto;/,
    );
    expect(css).toMatch(/\.advisor-product-frame \.workflow-rail-item[\s\S]*min-block-size:\s*4rem/);
    expect(css).toContain("200% zoom");
    expect(css).toMatch(/backdrop-filter/);
    expect(css).toMatch(/max-width:\s*560px[\s\S]*backdrop-filter:\s*none/);
    expect(e2e).toContain("target.height < 44 || target.width < 44");
    expect(e2e).toContain("visibleBlurSurfaces");
    expect(e2e).toContain("backdrop-filter: none !important");
    expect(e2e).toContain("storySticky");
    expect(e2e).toContain("storyTransforms");
    expect(composeConfig).toContain("presentation.spec.ts");
    expect(composeProof).toContain("PRESENTATION_AUDIT_OUTPUT_DIR");
    expect(composeProof).toContain("presentation.spec.ts");
  });
});
