import { expect, test, type Locator, type Page } from "@playwright/test";

const ROUTES = [
  ["australia", "澳大利亚", "在预算条件下推荐"],
  ["japan", "日本", "有条件备选"],
  ["malaysia", "马来西亚", "暂不可选"],
] as const;

function relativeLuminance(rgb: readonly number[]) {
  const [red, green, blue] = rgb.map((value) => {
    const channel = value / 255;
    return channel <= 0.04045
      ? channel / 12.92
      : ((channel + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

function contrastRatio(foreground: readonly number[], background: readonly number[]) {
  const foregroundLuminance = relativeLuminance(foreground);
  const backgroundLuminance = relativeLuminance(background);
  return (
    (Math.max(foregroundLuminance, backgroundLuminance) + 0.05) /
    (Math.min(foregroundLuminance, backgroundLuminance) + 0.05)
  );
}

async function expectReadable(locator: Locator) {
  const measurements = await locator.evaluateAll((elements) =>
    elements.map((element) => {
      const style = getComputedStyle(element);
      const parseRgb = (value: string) =>
        (value.match(/[\d.]+/g) ?? []).slice(0, 3).map(Number);
      return {
        foreground: parseRgb(style.color),
        background: parseRgb(style.backgroundColor),
      };
    }),
  );

  expect(measurements.length).toBeGreaterThan(0);
  for (const measurement of measurements) {
    expect(measurement.foreground).toHaveLength(3);
    expect(measurement.background).toHaveLength(3);
    expect(contrastRatio(measurement.foreground, measurement.background)).toBeGreaterThanOrEqual(4.5);
  }
}

async function expectRootRows(page: Page, locale: "zh-CN" | "en") {
  const routePreview = page.locator(".portfolio-hero-product .advisor-workspace-preview");
  const routeRows = routePreview.locator(".portfolio-preview-route-list > li[data-route-id]");
  await expect(routeRows).toHaveCount(3);
  for (const [id, zhCountry, zhOutcome] of ROUTES) {
    const row = routePreview.locator(`.portfolio-preview-route-list > li[data-route-id="${id}"]`);
    await expect(row).toHaveCount(1);
    await expect(row).toContainText(locale === "zh-CN" ? zhCountry : id === "australia" ? "Australia" : id === "japan" ? "Japan" : "Malaysia");
    await expect(row).toContainText(
      locale === "zh-CN"
        ? zhOutcome
        : id === "australia"
          ? "Recommended with budget condition"
          : id === "japan"
            ? "Conditional alternative"
            : "Blocked",
    );
  }
}

test("keeps the primary portfolio action readable in both locales", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");

  for (const locale of ["zh-CN", "en"] as const) {
    if (locale === "en") {
      await page.getByRole("button", { name: "English", exact: true }).click();
      await expect(page.locator("html")).toHaveAttribute("lang", "en");
    }
    await expectReadable(page.locator(".portfolio-primary-action"));
  }
});

test("keeps the advisor workspace identity and route-analysis preview in the first surface", async ({ page }) => {
  await page.goto("/");
  const routePreview = page.locator(".portfolio-hero-product .advisor-workspace-preview");
  await expect(page.locator(".portfolio-category")).toHaveText("为留学顾问打造的 AI 协作平台");
  await expect(page.locator(".portfolio-eyebrow")).toHaveText("为留学顾问打造的 AI 协作平台");
  await expect(routePreview).toHaveAttribute("data-preview-scene", "route");
  await expect(routePreview.locator(".workspace-top-band-grid")).toContainText("当前客户档案 · 档案版本 2");
  await expect(routePreview.getByRole("heading", { name: "方案比较" })).toBeVisible();
  await expect(page.locator(".portfolio-primary-navigation")).not.toContainText(
    /家庭表达|家庭决定|顾问到家庭决策流程/,
  );

  await page.getByRole("button", { name: "English", exact: true }).click();
  await expect(page.locator(".portfolio-category")).toHaveText(
    "An AI collaboration platform built for study-abroad advisors",
  );
  await expect(page.locator(".portfolio-eyebrow")).toHaveText(
    "An AI collaboration platform built for study-abroad advisors",
  );
  await expect(routePreview.locator(".workspace-top-band-grid")).toContainText("Current client case · Record version 2");
  await expect(routePreview.getByRole("heading", { name: "Plan comparison" })).toBeVisible();
  await expect(page.locator(".portfolio-primary-navigation")).not.toContainText(
    /Family input|Family decision|Advisor-to-family decision flow/,
  );
});

test("keeps the coded route preview readable and ordered at the review widths", async ({ page }) => {
  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 1280, height: 1000 },
    { width: 1024, height: 900 },
    { width: 768, height: 1024 },
    { width: 390, height: 844 },
    { width: 320, height: 720 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto("/");
    await expect(page.locator(".portfolio-hero-product .advisor-workspace-preview")).toBeVisible();
    await expectRootRows(page, "zh-CN");
    await expectReadable(page.locator(".portfolio-hero-product .advisor-workspace-preview .workspace-status-pill"));
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth === document.documentElement.clientWidth,
      ),
    ).toBe(true);
  }
});

test("keeps the product frame at 2/7/3 on desktop and uses an authored static sequence on reflow", async ({ page }) => {
  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 1280, height: 1000 },
  ]) {
    await page.setViewportSize(viewport);
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await page.goto("/");
    const geometry = await page.locator(".portfolio-hero-product .advisor-product-frame").evaluate((frame) => {
      const grid = frame.querySelector<HTMLElement>(".advisor-product-frame-grid")!;
      const context = frame.querySelector<HTMLElement>("[data-frame-slot='context']")!;
      const work = frame.querySelector<HTMLElement>("[data-frame-slot='work']")!;
      const authority = frame.querySelector<HTMLElement>("[data-frame-slot='authority']")!;
      const workflow = frame.querySelector<HTMLElement>("[data-frame-slot='workflow']")!;
      const rect = (element: HTMLElement) => {
        const box = element.getBoundingClientRect();
        return { left: box.left, right: box.right, top: box.top, bottom: box.bottom, width: box.width, height: box.height };
      };
      const authorityDescendants = [...authority.querySelectorAll<HTMLElement>("*")]
        .filter((element) => getComputedStyle(element).display !== "none")
        .map(rect)
        .filter((box) => box.width > 0 && box.height > 0);
      const workflowDescendants = [...workflow.querySelectorAll<HTMLElement>("*")]
        .filter((element) => getComputedStyle(element).display !== "none")
        .map(rect)
        .filter((box) => box.width > 0 && box.height > 0);
      const contextDescendants = [...context.querySelectorAll<HTMLElement>("*")]
        .filter((element) => getComputedStyle(element).display !== "none")
        .map(rect)
        .filter((box) => box.width > 0 && box.height > 0);
      return {
        context: rect(context),
        contextDescendants,
        grid: rect(grid),
        authority: rect(authority),
        authorityDescendants,
        workflowDescendants,
        work: rect(work),
        workflow: rect(workflow),
        workflowDirection: getComputedStyle(workflow.querySelector<HTMLElement>(".workflow-rail-list")!).flexDirection,
        labelWritingMode: getComputedStyle(workflow.querySelector<HTMLElement>(".workflow-rail-label")!).writingMode,
        labelWidth: workflow.querySelector<HTMLElement>(".workflow-rail-label")!.getBoundingClientRect().width,
        labelOverflow: workflow.querySelector<HTMLElement>(".workflow-rail-label")!.scrollWidth > workflow.querySelector<HTMLElement>(".workflow-rail-label")!.clientWidth + 1,
      };
    });

    expect(geometry.context.width / geometry.grid.width).toBeCloseTo(2 / 12, 2);
    expect(geometry.work.width / geometry.grid.width).toBeCloseTo(7 / 12, 2);
    expect(geometry.authority.width / geometry.grid.width).toBeCloseTo(3 / 12, 2);
    expect(geometry.workflow.width).toBeLessThanOrEqual(geometry.context.width + 1);
    expect(geometry.workflowDirection).toBe("column");
    expect(geometry.labelWritingMode).toBe("horizontal-tb");
    expect(geometry.labelWidth).toBeGreaterThanOrEqual(80);
    expect(geometry.labelOverflow).toBe(false);
    for (const box of geometry.workflowDescendants) {
      expect(box.left).toBeGreaterThanOrEqual(geometry.context.left - 1);
      expect(box.right).toBeLessThanOrEqual(geometry.context.right + 1);
    }
    for (const box of geometry.contextDescendants) {
      expect(box.left).toBeGreaterThanOrEqual(geometry.context.left - 1);
      expect(box.right).toBeLessThanOrEqual(geometry.context.right + 1);
    }
    for (const box of geometry.authorityDescendants) {
      expect(box.left).toBeGreaterThanOrEqual(geometry.authority.left - 1);
      expect(box.right).toBeLessThanOrEqual(geometry.authority.right + 1);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }

  for (const width of [768, 390, 320]) {
    await page.setViewportSize({ width, height: width >= 768 ? 1000 : 844 });
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await page.goto("/");
    const staticSubjects = page.locator(".portfolio-story-static-subject:visible .advisor-workspace-preview");
    await expect(staticSubjects).toHaveCount(3);
    await expect(staticSubjects.nth(0)).toHaveAttribute("data-preview-scene", "confirmed");
    await expect(staticSubjects.nth(1)).toHaveAttribute("data-preview-scene", "route");
    await expect(staticSubjects.nth(2)).toHaveAttribute("data-preview-scene", "outcome");
    await expect(page.locator(".portfolio-story-frame:visible")).toHaveCount(0);
    const reflow = await page.locator(".portfolio-hero-product .advisor-product-frame").evaluate((frame) => {
      const topBand = frame.querySelector<HTMLElement>(".workspace-top-band-grid")!;
      const rail = frame.querySelector<HTMLElement>(".advisor-product-frame-workflow .workflow-rail-list")!;
      const items = [...rail.querySelectorAll<HTMLElement>(":scope > li")];
      const boxes = items.map((item) => item.getBoundingClientRect());
      return {
        topBandColumns: new Set([...topBand.children].map((child) => Math.round(child.getBoundingClientRect().left))).size,
        railWidth: rail.getBoundingClientRect().width,
        railScrollWidth: rail.scrollWidth,
        railDirection: getComputedStyle(rail).flexDirection,
        itemHeights: boxes.map((box) => box.height),
        itemTops: boxes.map((box) => Math.round(box.top)),
      };
    });
    expect(reflow.topBandColumns).toBe(2);
    expect(reflow.railDirection).toBe("row");
    expect(new Set(reflow.itemTops).size).toBe(1);
    expect(reflow.itemHeights.every((height) => height >= 64)).toBe(true);
    if (width <= 560) expect(reflow.railScrollWidth).toBeGreaterThan(reflow.railWidth);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.locator(".portfolio-story-static-subject:visible .advisor-workspace-preview")).toHaveCount(3);
  await expect(page.locator(".portfolio-story-frame:visible")).toHaveCount(0);
  expect(await page.locator(".portfolio-story-frame, .portfolio-story-chapter, .portfolio-product-preview").evaluateAll((elements) =>
    elements.filter((element) => {
      const style = getComputedStyle(element);
      return style.position === "sticky" || style.transform !== "none";
    }).length,
  )).toBe(0);
});

test("uses one plain 20px wordmark without a glyph across all four routes", async ({ page }) => {
  for (const route of ["/", "/demo/collaboration", "/demo", "/demo/plan"]) {
    await page.goto(route);
    const wordmark = page.locator(".portfolio-brand, .workspace-brand");
    await expect(wordmark).toHaveCount(1);
    await expect(wordmark).toHaveText("Night Voyager");
    await expect(wordmark.locator("svg, img, .portfolio-brand-mark, .workspace-brand-mark")).toHaveCount(0);
    await expect.poll(() => wordmark.evaluate((element) => {
      const style = getComputedStyle(element);
      return `${style.fontSize}|${style.letterSpacing}|${style.fontFamily}`;
    })).toMatch(/^20px\|-0\.7px\|.*Avenir Next/i);
  }
});

test("keeps every home id unique and every labelled-by reference resolvable in Chromium", async ({ page }) => {
  await page.goto("/");
  const report = await page.evaluate(() => {
    const ids = [...document.querySelectorAll<HTMLElement>("[id]")].map((element) => element.id);
    const unresolved = [...document.querySelectorAll<HTMLElement>("[aria-labelledby]")].flatMap((element) =>
      element.getAttribute("aria-labelledby")!.split(/\s+/).filter((reference) => !document.getElementById(reference)),
    );
    return { duplicateIds: ids.filter((id, index) => ids.indexOf(id) !== index), unresolved };
  });
  expect(report.duplicateIds).toEqual([]);
  expect(report.unresolved).toEqual([]);
});

test("keeps the English route preview truthful without runtime image dependencies", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await page.getByRole("button", { name: "English", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByRole("heading", { level: 1 })).toHaveAttribute(
    "aria-label",
    "Move complex study-abroad planning forward with clarity.",
  );
  await expectRootRows(page, "en");
  await expect(page.locator("main img")).toHaveCount(0);
});
