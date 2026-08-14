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
  const routeRows = page.locator(".advisor-workspace-preview .workspace-route-row");
  await expect(routeRows).toHaveCount(3);
  for (const [id, zhCountry, zhOutcome] of ROUTES) {
    const row = page.locator(`.advisor-workspace-preview .workspace-route-row[data-route-id="${id}"]`);
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
  await expect(page.locator(".portfolio-category")).toHaveText("为留学顾问打造的 AI 协作平台");
  await expect(page.locator(".portfolio-eyebrow")).toHaveText("为留学顾问打造的 AI 协作平台");
  await expect(page.locator(".advisor-workspace-preview")).toContainText("当前客户档案 · 方案研判");
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
  await expect(page.locator(".portfolio-primary-navigation")).not.toContainText(
    /Family input|Family decision|Advisor-to-family decision flow/,
  );
});

test("keeps the coded route preview readable and ordered at the review widths", async ({ page }) => {
  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 1024, height: 900 },
    { width: 768, height: 1024 },
    { width: 390, height: 844 },
    { width: 320, height: 720 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto("/");
    await expect(page.locator(".advisor-workspace-preview")).toBeVisible();
    await expectRootRows(page, "zh-CN");
    await expectReadable(page.locator(".advisor-workspace-preview .workspace-status-pill"));
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth === document.documentElement.clientWidth,
      ),
    ).toBe(true);
  }
});

test("keeps the English route preview truthful without runtime image dependencies", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await page.getByRole("button", { name: "English", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Move complex study-abroad planning forward with clarity.",
  );
  await expectRootRows(page, "en");
  await expect(page.locator("main img")).toHaveCount(0);
});
