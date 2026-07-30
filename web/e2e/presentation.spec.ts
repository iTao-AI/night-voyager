import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import { expect, test, type Browser, type Page } from "@playwright/test";

const AUDIT_OUTPUT = process.env.PRESENTATION_AUDIT_OUTPUT_DIR;
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3000";
const ROUTES = ["/", "/demo/collaboration", "/demo", "/demo/plan"] as const;
const LOCALES = ["zh-CN", "en"] as const;
const WIDTHS = [1440, 768, 390, 320] as const;
const MOTION_MODES = ["no-preference", "reduce"] as const;

type AuditCell = {
  route: (typeof ROUTES)[number];
  locale: (typeof LOCALES)[number];
  width: (typeof WIDTHS)[number];
  motion: (typeof MOTION_MODES)[number];
  zoom: "default" | "200%";
};

function slug(cell: AuditCell) {
  const route = cell.route === "/" ? "root" : cell.route.slice(1).replaceAll("/", "-");
  return `${route}-${cell.locale}-${cell.width}-${cell.motion}-${cell.zoom.replace("%", "pct")}`;
}

async function openCell(browser: Browser, cell: AuditCell) {
  const context = await browser.newContext({
    baseURL: BASE_URL,
    deviceScaleFactor: 1,
    locale: cell.locale,
    reducedMotion: cell.motion,
    viewport: { width: cell.width, height: cell.width >= 768 ? 900 : 760 },
  });
  await context.addInitScript((locale) => {
    const key = "night-voyager:presentation-locale:v1";
    if (locale === "en") localStorage.setItem(key, locale);
    else localStorage.removeItem(key);
  }, cell.locale);
  const page = await context.newPage();
  await page.goto(cell.route, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  if (cell.zoom === "200%") {
    await page.evaluate(() => {
      document.documentElement.style.zoom = "2";
    });
  }
  return { context, page };
}

async function keyboardAndFocusEvidence(page: Page) {
  const sequence: string[] = [];
  for (let index = 0; index < 12; index += 1) {
    await page.keyboard.press("Tab");
    sequence.push(await page.evaluate(() => {
      const active = document.activeElement as HTMLElement | null;
      if (!active) return "none";
      return [
        active.tagName.toLowerCase(),
        active.getAttribute("aria-label"),
        active.textContent?.trim().slice(0, 80),
      ].filter(Boolean).join(":");
    }));
  }
  const focus = await page.evaluate(() => {
    const active = document.activeElement as HTMLElement | null;
    if (!active) return null;
    const style = getComputedStyle(active);
    return {
      outlineStyle: style.outlineStyle,
      outlineWidth: style.outlineWidth,
      boxShadow: style.boxShadow,
    };
  });
  return { focus, keyboard: sequence };
}

async function renderedMetrics(page: Page) {
  return page.evaluate(() => {
    function rgb(value: string) {
      const channels = value.match(/[\d.]+/g)?.slice(0, 3).map(Number);
      return channels?.length === 3 ? channels : null;
    }
    function luminance(channels: number[]) {
      const [red, green, blue] = channels.map((value) => {
        const normalized = value / 255;
        return normalized <= 0.04045
          ? normalized / 12.92
          : ((normalized + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
    }
    function contrast(foreground: number[], background: number[]) {
      const light = Math.max(luminance(foreground), luminance(background));
      const dark = Math.min(luminance(foreground), luminance(background));
      return (light + 0.05) / (dark + 0.05);
    }
    function backgroundFor(element: Element) {
      for (let current: Element | null = element; current; current = current.parentElement) {
        const value = getComputedStyle(current).backgroundColor;
        if (value !== "rgba(0, 0, 0, 0)" && value !== "transparent") return value;
      }
      return "rgb(255, 255, 255)";
    }

    const visible = [...document.querySelectorAll<HTMLElement>("body *")].filter((element) => {
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden";
    });
    const contrastSamples = visible
      .filter((element) => element.childElementCount === 0 && Boolean(element.textContent?.trim()))
      .map((element) => {
        const foreground = rgb(getComputedStyle(element).color);
        const background = rgb(backgroundFor(element));
        return foreground && background
          ? { ratio: contrast(foreground, background), text: element.textContent!.trim().slice(0, 80) }
          : null;
      })
      .filter((sample): sample is { ratio: number; text: string } => sample !== null)
      .sort((left, right) => left.ratio - right.ratio)
      .slice(0, 20);
    const targets = visible
      .filter((element) => element.matches("a, button, input, select, summary"))
      .map((element) => {
        const rect = element.getBoundingClientRect();
        return {
          height: rect.height,
          name: element.getAttribute("aria-label") ?? element.textContent?.trim().slice(0, 80),
          width: rect.width,
        };
      });
    const longCopy = visible
      .filter((element) => (element.textContent?.trim().length ?? 0) >= 80)
      .map((element) => ({
        clipped: element.scrollWidth > element.clientWidth + 1,
        text: element.textContent!.trim().slice(0, 120),
      }));

    return {
      contrast: contrastSamples,
      headings: visible
        .filter((element) => /^H[1-6]$/.test(element.tagName))
        .map((element) => ({ level: element.tagName, text: element.textContent?.trim() })),
      landmarks: visible
        .filter((element) => element.matches("header, nav, main, aside, footer, [role='main'], [role='navigation']"))
        .map((element) => element.getAttribute("role") ?? element.tagName.toLowerCase()),
      "latest-64": {
        disclosureVisible: visible.some((element) => /64/.test(element.textContent ?? "")),
      },
      liveRegions: visible
        .filter((element) => element.hasAttribute("aria-live") || element.getAttribute("role") === "status")
        .map((element) => element.textContent?.trim().slice(0, 120)),
      "long-copy": longCopy,
      overflow: {
        clientWidth: document.documentElement.clientWidth,
        horizontal: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
        scrollWidth: document.documentElement.scrollWidth,
      },
      reducedMotion: matchMedia("(prefers-reduced-motion: reduce)").matches,
      targets,
    };
  });
}

const PLAN_COPY = {
  "zh-CN": {
    advisor: "顾问",
    blocked: "记录阻塞并停止当前 checkpoint",
    completion: "提交完成状态给顾问",
    parent: "家长",
    progress: "记录进行中",
    reassess: "请求重新评估并停止执行",
    recover: "重新验证执行 authority",
    start: "开始执行行动计划",
    student: "学生",
    verify: "验证并继续",
  },
  en: {
    advisor: "Advisor",
    blocked: "Record blocker and stop the current checkpoint",
    completion: "Submit completion to advisor",
    parent: "Parent",
    progress: "Record progress",
    reassess: "Request reassessment and stop execution",
    recover: "Revalidate execution authority",
    start: "Start the action plan",
    student: "Student",
    verify: "Verify and continue",
  },
} as const;

async function rotateRole(
  page: Page,
  locale: keyof typeof PLAN_COPY,
  role: "student" | "parent" | "advisor",
) {
  const response = page.waitForResponse((candidate) =>
    candidate.request().method() === "POST"
    && candidate.url().endsWith("/api/demo/sessions"));
  const button = page.getByRole("button", {
    exact: true,
    name: PLAN_COPY[locale][role],
  });
  await button.click();
  expect((await response).status()).toBe(201);
  await expect(button).toHaveAttribute("aria-pressed", "true");
}

async function mutation(page: Page, name: string) {
  const receipt = page.waitForResponse((response) =>
    response.request().method() === "POST"
    && !response.url().endsWith("/api/demo/sessions"));
  const freshRead = page.waitForResponse((response) =>
    response.request().method() === "GET"
    && response.url().includes("/timeline-execution"));
  await page.getByRole("button", { exact: true, name }).click();
  expect((await receipt).status()).toBe(200);
  expect((await freshRead).status()).toBe(200);
}

async function captureState(page: Page, name: string) {
  await page.screenshot({
    animations: "disabled",
    fullPage: true,
    path: path.join(AUDIT_OUTPUT!, `${name}.png`),
  });
  await writeFile(
    path.join(AUDIT_OUTPUT!, `${name}.json`),
    `${JSON.stringify(await renderedMetrics(page), null, 2)}\n`,
    { encoding: "utf8", mode: 0o600 },
  );
}

test.describe("provider-free governed presentation audit", () => {
  test.skip(!AUDIT_OUTPUT, "requires the private presentation audit output root");

  for (const route of ROUTES) {
    for (const locale of LOCALES) {
      for (const width of WIDTHS) {
        const cell: AuditCell = {
          route,
          locale,
          width,
          motion: "no-preference",
          zoom: "default",
        };
        test(`${slug(cell)} rendered baseline`, async ({ browser }) => {
          const { context, page } = await openCell(browser, cell);
          const evidence = {
            cell,
            ...(await keyboardAndFocusEvidence(page)),
            metrics: await renderedMetrics(page),
          };
          await mkdir(AUDIT_OUTPUT!, { mode: 0o700, recursive: true });
          await page.screenshot({
            animations: "disabled",
            fullPage: true,
            path: path.join(AUDIT_OUTPUT!, `${slug(cell)}.png`),
          });
          await writeFile(
            path.join(AUDIT_OUTPUT!, `${slug(cell)}.json`),
            `${JSON.stringify(evidence, null, 2)}\n`,
            { encoding: "utf8", mode: 0o600 },
          );
          await context.close();
        });
      }

      for (const motion of MOTION_MODES) {
        const cell: AuditCell = {
          route,
          locale,
          width: 390,
          motion,
          zoom: "default",
        };
        test(`${slug(cell)} motion baseline`, async ({ browser }) => {
          const { context, page } = await openCell(browser, cell);
          const evidence = { cell, metrics: await renderedMetrics(page) };
          await writeFile(
            path.join(AUDIT_OUTPUT!, `${slug(cell)}-motion.json`),
            `${JSON.stringify(evidence, null, 2)}\n`,
            { encoding: "utf8", mode: 0o600 },
          );
          await context.close();
        });
      }

      const zoomCell: AuditCell = {
        route,
        locale,
        width: 768,
        motion: "no-preference",
        zoom: "200%",
      };
      test(`${slug(zoomCell)} zoom baseline`, async ({ browser }) => {
        const { context, page } = await openCell(browser, zoomCell);
        const evidence = { cell: zoomCell, metrics: await renderedMetrics(page) };
        await writeFile(
          path.join(AUDIT_OUTPUT!, `${slug(zoomCell)}-zoom.json`),
          `${JSON.stringify(evidence, null, 2)}\n`,
          { encoding: "utf8", mode: 0o600 },
        );
        await context.close();
      });
    }
  }

  test("captures the happy current, waiting, recovery, and completed states", async ({
    browser,
  }) => {
    const locale = "zh-CN";
    const labels = PLAN_COPY[locale];
    const { context, page } = await openCell(browser, {
      locale,
      motion: "no-preference",
      route: "/demo/plan?scenario=happy" as "/demo/plan",
      width: 1440,
      zoom: "default",
    });
    await rotateRole(page, locale, "student");
    await mutation(page, labels.start);
    await captureState(page, "plan-state-current-action-zh-CN-1440");

    let dropOnce = true;
    await page.route("**/checkpoint-attestations", async (route) => {
      if (!dropOnce) {
        await route.continue();
        return;
      }
      dropOnce = false;
      await route.fetch();
      await route.abort("failed");
    });
    await page.getByRole("button", { exact: true, name: labels.progress }).click();
    await expect(page.getByRole("button", { exact: true, name: labels.recover })).toBeVisible();
    await captureState(page, "plan-state-recovery-zh-CN-1440");
    await page.unroute("**/checkpoint-attestations");
    await mutation(page, labels.recover);

    await mutation(page, labels.completion);
    await captureState(page, "plan-state-awaiting-advisor-zh-CN-1440");
    await rotateRole(page, locale, "advisor");
    await captureState(page, "plan-state-advisor-review-zh-CN-1440");
    await mutation(page, labels.verify);

    for (const role of ["student", "student", "parent"] as const) {
      await rotateRole(page, locale, role);
      await mutation(page, labels.completion);
      await rotateRole(page, locale, "advisor");
      await mutation(page, labels.verify);
    }
    await captureState(page, "plan-state-completed-zh-CN-1440");
    await context.close();
  });

  test("captures the blocked and reassessment states", async ({ browser }) => {
    const locale = "en";
    const labels = PLAN_COPY[locale];
    const { context, page } = await openCell(browser, {
      locale,
      motion: "reduce",
      route: "/demo/plan?scenario=blocked" as "/demo/plan",
      width: 390,
      zoom: "default",
    });
    await rotateRole(page, locale, "student");
    await mutation(page, labels.start);
    await mutation(page, labels.blocked);
    await rotateRole(page, locale, "advisor");
    await captureState(page, "plan-state-blocked-en-390");
    await mutation(page, labels.reassess);
    await captureState(page, "plan-state-reassessment-en-390");
    await context.close();
  });
});
