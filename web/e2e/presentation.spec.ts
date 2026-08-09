import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import { expect, test, type Browser, type Locator, type Page } from "@playwright/test";

const AUDIT_OUTPUT = process.env.PRESENTATION_AUDIT_OUTPUT_DIR;
const PUBLIC_EVIDENCE_ROOT = process.env.PRESENTATION_PUBLIC_EVIDENCE_ROOT;
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3000";
const ROUTES = ["/", "/demo/collaboration", "/demo", "/demo/plan"] as const;
const LOCALES = ["zh-CN", "en"] as const;
const WIDTHS = [1440, 1024, 768, 390, 320] as const;
const MOTION_MODES = ["no-preference", "reduce"] as const;
const APPROVED_PUBLIC_EVIDENCE_FILENAMES = [
  "night-voyager-portfolio-entry.png",
  "collaboration-confirmed-fact.png",
  "m5-advisor-ledger.png",
  "m5-family-receipt-timeline.png",
  "night-voyager-planning-revision.png",
  "plan-execution-current-action.png",
  "plan-execution-advisor-review.png",
  "plan-execution-reassessment-mobile.png",
  "plan-execution-recovery-mobile.png",
] as const;

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
  let visibleFocus = false;
  for (let index = 0; index < 12; index += 1) {
    await page.keyboard.press("Tab");
    const step = await page.evaluate(() => {
      const active = document.activeElement as HTMLElement | null;
      if (!active) return { descriptor: "none", visible: false };
      const style = getComputedStyle(active);
      return {
        descriptor: [
          active.tagName.toLowerCase(),
          active.getAttribute("aria-label"),
          active.textContent?.trim().slice(0, 80),
        ].filter(Boolean).join(":"),
        visible: style.outlineStyle !== "none" && style.outlineWidth !== "0px",
      };
    });
    sequence.push(step.descriptor);
    visibleFocus ||= step.visible;
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
  return { focus, keyboard: sequence, visibleFocus };
}

async function activateByKeyboard(
  target: Locator,
  key: "Enter" | "Space" = "Enter",
) {
  await expect(target).toBeEnabled();
  await target.focus();
  await expect(target).toBeFocused();
  await target.press(key);
}

async function keyboardDisclosureEvidence(page: Page) {
  const summary = page.locator("summary").filter({ visible: true }).first();
  if (await summary.count() === 0) return { activated: false, key: null };
  const details = summary.locator("..");
  const initiallyOpen = await details.evaluate((element) => element.hasAttribute("open"));
  await activateByKeyboard(summary, "Enter");
  if (initiallyOpen) await expect(details).not.toHaveAttribute("open");
  else await expect(details).toHaveAttribute("open", "");
  await activateByKeyboard(summary, "Space");
  if (initiallyOpen) await expect(details).toHaveAttribute("open", "");
  else await expect(details).not.toHaveAttribute("open");
  return { activated: true, key: "Enter+Space" };
}

async function renderedMetrics(page: Page) {
  return page.evaluate(() => {
    type Color = [number, number, number, number];

    function color(value: string): Color | null {
      const channels = value.match(/[\d.]+/g)?.map(Number);
      if (!channels || channels.length < 3) return null;
      const scale = /^color\(srgb\s/.test(value) ? 255 : 1;
      return [
        channels[0] * scale,
        channels[1] * scale,
        channels[2] * scale,
        channels[3] ?? 1,
      ];
    }
    function composite(foreground: Color, background: Color): Color {
      const alpha = foreground[3] + background[3] * (1 - foreground[3]);
      if (alpha === 0) return [0, 0, 0, 0];
      return [
        (foreground[0] * foreground[3]
          + background[0] * background[3] * (1 - foreground[3])) / alpha,
        (foreground[1] * foreground[3]
          + background[1] * background[3] * (1 - foreground[3])) / alpha,
        (foreground[2] * foreground[3]
          + background[2] * background[3] * (1 - foreground[3])) / alpha,
        alpha,
      ];
    }
    function luminance(channels: Color) {
      const [red, green, blue] = channels.map((value) => {
        const normalized = value / 255;
        return normalized <= 0.04045
          ? normalized / 12.92
          : ((normalized + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
    }
    function contrast(foreground: Color, background: Color) {
      const light = Math.max(luminance(foreground), luminance(background));
      const dark = Math.min(luminance(foreground), luminance(background));
      return (light + 0.05) / (dark + 0.05);
    }
    function backgroundFor(element: Element) {
      let result: Color = [0, 0, 0, 0];
      for (let current: Element | null = element; current; current = current.parentElement) {
        const style = getComputedStyle(current);
        if (style.backgroundImage !== "none" && result[3] < 1) return null;
        const layer = color(style.backgroundColor);
        if (layer) result = composite(result, layer);
        if (result[3] >= 0.999) return result;
      }
      return composite(result, [255, 255, 255, 1]);
    }
    function milliseconds(value: string) {
      return value.split(",").map((entry) => {
        const token = entry.trim();
        return token.endsWith("ms")
          ? Number.parseFloat(token)
          : Number.parseFloat(token) * 1000;
      });
    }
    function maximumTimeline(duration: string, delay: string) {
      const durations = milliseconds(duration);
      const delays = milliseconds(delay);
      return durations.reduce((maximum, value, index) => (
        Math.max(maximum, value + Math.max(0, delays[index % delays.length] ?? 0))
      ), 0);
    }

    const visible = [...document.querySelectorAll<HTMLElement>("body *")].filter((element) => {
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return rect.width > 0
        && rect.height > 0
        && style.visibility !== "hidden"
        && !element.closest("[aria-hidden='true']");
    });
    const contrastSamples = visible
      .filter((element) => element.childElementCount === 0 && Boolean(element.textContent?.trim()))
      .map((element) => {
        const style = getComputedStyle(element);
        const foreground = color(style.color);
        const background = backgroundFor(element);
        const fontSize = Number.parseFloat(style.fontSize);
        const fontWeight = Number.parseInt(style.fontWeight, 10);
        const isLargeText = fontSize >= 24 || (fontSize >= 18.6667 && fontWeight >= 700);
        const requiredRatio = isLargeText ? 3 : 4.5;
        return foreground && background
          ? {
              ratio: contrast(composite(foreground, background), background),
              requiredRatio,
              text: element.textContent!.trim().slice(0, 80),
            }
          : null;
      })
      .filter((sample): sample is {
        ratio: number;
        requiredRatio: number;
        text: string;
      } => sample !== null)
      .sort((left, right) => left.ratio - right.ratio)
    const motion = visible.map((element) => {
      const style = getComputedStyle(element);
      return {
        animationMs: maximumTimeline(style.animationDuration, style.animationDelay),
        name: element.getAttribute("aria-label") ?? element.textContent?.trim().slice(0, 80),
        transitionMs: maximumTimeline(style.transitionDuration, style.transitionDelay),
      };
    });
    const maxMotionMs = motion.reduce(
      (maximum, entry) => Math.max(maximum, entry.animationMs, entry.transitionMs),
      0,
    );
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
    const journeyCopy = visible
      .filter((element) => element.matches(".workflow-rail-label"))
      .map((element) => ({
        fontSize: Number.parseFloat(getComputedStyle(element).fontSize),
        text: element.textContent?.trim().slice(0, 120),
      }));
    const longCopy = visible
      .filter((element) => (
        (element.textContent?.trim().length ?? 0) >= 80
        && (
          element.childElementCount === 0
          || element.matches("p, li, dd, button, summary, [role='status'], [role='alert']")
        )
      ))
      .map((element) => {
        const style = getComputedStyle(element);
        const clips = (value: string) => value === "hidden" || value === "clip";
        const lineClamp = Number.parseInt(style.webkitLineClamp, 10);
        return {
          clipped: (
            clips(style.overflowX) && element.scrollWidth > element.clientWidth + 1
          ) || (
            clips(style.overflowY) && element.scrollHeight > element.clientHeight + 1
          ) || (
            Number.isFinite(lineClamp)
            && lineClamp > 0
            && element.scrollHeight > element.clientHeight + 1
          ),
          text: element.textContent!.trim().slice(0, 120),
        };
      });

    return {
      contrast: contrastSamples,
      headings: visible
        .filter((element) => /^H[1-6]$/.test(element.tagName))
        .map((element) => ({ level: element.tagName, text: element.textContent?.trim() })),
      journeyCopy,
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
      maxMotionMs,
      motionOffenders: motion.filter(
        (entry) => entry.animationMs > 10 || entry.transitionMs > 10,
      ),
      overflow: {
        clientWidth: document.documentElement.clientWidth,
        horizontal: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
        scrollWidth: document.documentElement.scrollWidth,
      },
      reducedMotion: matchMedia("(prefers-reduced-motion: reduce)").matches,
      scrollBehavior: getComputedStyle(document.documentElement).scrollBehavior,
      targets,
    };
  });
}

async function assertSemanticPresentation(page: Page) {
  const metrics = await renderedMetrics(page);
  expect(metrics.overflow.horizontal).toBe(false);
  expect(
    metrics.contrast.filter((sample) => sample.ratio < sample.requiredRatio),
  ).toEqual([]);
  expect(metrics["long-copy"].filter((entry) => entry.clipped)).toEqual([]);
  expect(metrics.headings.filter((heading) => heading.level === "H1")).toHaveLength(1);
  expect(metrics.landmarks).toContain("main");
  expect(metrics.targets.filter((target) => target.height < 44 || target.width < 44)).toEqual([]);
  expect(metrics.journeyCopy.filter((copy) => copy.fontSize < 16)).toEqual([]);
  const journeyStage = page.url().includes("/demo/collaboration")
    ? "consultation_intake"
    : page.url().includes("/demo/plan")
      ? "execution_followup"
      : page.url().includes("/demo")
        ? "route_analysis"
        : null;
  if (journeyStage) {
    await expect(page.locator(".workflow-rail-list > li")).toHaveCount(5);
    await expect(page.locator(`.workflow-rail-list[data-current-stage='${journeyStage}']`)).toBeVisible();
  }
  const shell = page.locator(".advisor-workspace-shell");
  if (page.url().endsWith("/") || new URL(page.url()).pathname === "/") {
    await expect(page.locator(".portfolio-category")).toContainText(
      /AI collaboration workspace for study-abroad advisors|留学顾问的 AI 协作工作台/,
    );
    await expect(page.locator(".advisor-workspace-preview")).toContainText(
      /澳大利亚|Australia/,
    );
  } else {
    await expect(shell).toBeVisible();
    await expect(page.locator(".workspace-category")).toContainText(
      /AI collaboration workspace for study-abroad advisors|留学顾问的 AI 协作工作台/,
    );
    const expectedProofSegment = page.url().includes("/demo/plan")
      ? "independent_execution_scenario"
      : "connected_same_case";
    await expect(shell).toHaveAttribute("data-proof-segment", expectedProofSegment);
    await expect(page.locator(".workflow-rail")).toBeVisible();
    expect(await page.locator("[data-primary-action='true']:visible").count()).toBeLessThanOrEqual(1);
    expect((await page.locator(
      ".workspace-header, .workspace-context-bar, .workflow-rail, .workspace-route-heading",
    ).allTextContents()).join("\n")).not.toMatch(
      /家庭表达|家庭决定|顾问到家庭决策流程|Family input|Family decision|Advisor-to-family decision flow/,
    );
  }
  if (metrics.reducedMotion) {
    expect(metrics.maxMotionMs).toBeLessThanOrEqual(10);
    expect(metrics.motionOffenders).toEqual([]);
    expect(metrics.scrollBehavior).not.toBe("smooth");
  }
  if (page.url().includes("/demo/plan")) {
    await expect(page.locator("body")).not.toContainText(
      /\b(documents|application|visa|arrival|on_track|due_soon|in_progress|attestation_recorded|verification_recorded)\b/,
    );
    expect(metrics.liveRegions).toHaveLength(1);
  }
  return metrics;
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
  key: "Enter" | "Space" = "Enter",
) {
  const response = page.waitForResponse((candidate) =>
    candidate.request().method() === "POST"
    && candidate.url().endsWith("/api/demo/sessions"));
  const button = page.getByRole("button", {
    exact: true,
    name: PLAN_COPY[locale][role],
  });
  await activateByKeyboard(button, key);
  expect((await response).status()).toBe(201);
  await expect(button).toHaveAttribute("aria-pressed", "true");
}

async function mutation(
  page: Page,
  name: string,
  key: "Enter" | "Space" = "Enter",
) {
  const receipt = page.waitForResponse((response) =>
    response.request().method() === "POST"
    && !response.url().endsWith("/api/demo/sessions"));
  const freshRead = page.waitForResponse((response) =>
    response.request().method() === "GET"
    && response.url().includes("/timeline-execution"));
  await activateByKeyboard(page.getByRole("button", { exact: true, name }), key);
  expect((await receipt).status()).toBe(200);
  expect((await freshRead).status()).toBe(200);
  await expect(page.locator(".plan-execution-hero > h3")).toBeFocused();
}

async function captureState(page: Page, name: string) {
  const publicFilename = {
    "plan-state-current-action-zh-CN-1440": "plan-execution-current-action.png",
    "plan-state-advisor-review-zh-CN-1440": "plan-execution-advisor-review.png",
    "plan-state-reassessment-en-390": "plan-execution-reassessment-mobile.png",
    "plan-state-recovery-zh-CN-390": "plan-execution-recovery-mobile.png",
  }[name];
  if (name.includes("-en-")) {
    await expect(page.getByText("Local synthetic demo", { exact: true })).toBeVisible();
  } else {
    await expect(page.getByText("本地合成演示", { exact: true })).toBeVisible();
  }
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
    window.scrollTo({ left: 0, top: 0 });
  });
  await page.screenshot({
    animations: "disabled",
    fullPage: true,
    path: path.join(AUDIT_OUTPUT!, `${name}.png`),
  });
  if (PUBLIC_EVIDENCE_ROOT && publicFilename) {
    expect(APPROVED_PUBLIC_EVIDENCE_FILENAMES).toContain(publicFilename);
    await mkdir(PUBLIC_EVIDENCE_ROOT, { mode: 0o755, recursive: true });
    await page.screenshot({
      animations: "disabled",
      fullPage: true,
      path: path.join(PUBLIC_EVIDENCE_ROOT, publicFilename),
    });
  }
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
          const keyboardEvidence = await keyboardAndFocusEvidence(page);
          const evidence = {
            cell,
            ...keyboardEvidence,
            metrics: await assertSemanticPresentation(page),
          };
          expect(keyboardEvidence.keyboard.some((item) => item !== "none")).toBe(true);
          expect(keyboardEvidence.visibleFocus).toBe(true);
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
          const evidence = { cell, metrics: await assertSemanticPresentation(page) };
          expect(evidence.metrics.reducedMotion).toBe(motion === "reduce");
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
        const evidence = {
          cell: zoomCell,
          metrics: await assertSemanticPresentation(page),
        };
        await writeFile(
          path.join(AUDIT_OUTPUT!, `${slug(zoomCell)}-zoom.json`),
          `${JSON.stringify(evidence, null, 2)}\n`,
          { encoding: "utf8", mode: 0o600 },
        );
        await context.close();
      });
    }
  }

  test("completes the happy governed keyboard journey and captures its states", async ({
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
    await rotateRole(page, locale, "student", "Enter");
    await mutation(page, labels.start, "Space");
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
    await activateByKeyboard(
      page.getByRole("button", { exact: true, name: labels.progress }),
      "Enter",
    );
    await expect(page.getByRole("button", { exact: true, name: labels.recover })).toBeVisible();
    await page.setViewportSize({ width: 390, height: 760 });
    await captureState(page, "plan-state-recovery-zh-CN-390");
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.unroute("**/checkpoint-attestations");
    await mutation(page, labels.recover, "Space");

    await mutation(page, labels.completion, "Enter");
    await captureState(page, "plan-state-awaiting-advisor-zh-CN-1440");
    await rotateRole(page, locale, "advisor", "Space");
    await captureState(page, "plan-state-advisor-review-zh-CN-1440");
    await mutation(page, labels.verify, "Enter");

    for (const [index, role] of (["student", "student", "parent"] as const).entries()) {
      await rotateRole(page, locale, role, index % 2 === 0 ? "Space" : "Enter");
      await mutation(page, labels.completion, index % 2 === 0 ? "Enter" : "Space");
      await rotateRole(page, locale, "advisor", index % 2 === 0 ? "Space" : "Enter");
      await mutation(page, labels.verify, index % 2 === 0 ? "Enter" : "Space");
    }
    await expect(page.getByText("行动计划已完成。", { exact: true }).last()).toBeVisible();
    await expect(page.locator(".approved-plan-steps > li[data-state='verified']")).toHaveCount(4);
    expect((await keyboardDisclosureEvidence(page)).activated).toBe(true);
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
