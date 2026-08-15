import { expect, test } from "@playwright/test";

test("shows the advisor workspace portfolio entry without API side effects", async ({ page }) => {
  const apiRequests: string[] = [];
  const eventRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) apiRequests.push(request.url());
    if (request.url().includes("/events?after=")) eventRequests.push(request.url());
  });
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
  const routePreview = page.locator(".portfolio-hero-product .advisor-workspace-preview");
  await expect(routePreview).toBeVisible();
  await expect(page.locator(".portfolio-category")).toHaveText("为留学顾问打造的 AI 协作平台");
  await expect(page.locator(".portfolio-eyebrow")).toHaveText("为留学顾问打造的 AI 协作平台");
  await expect(page.locator(".portfolio-primary-navigation")).not.toContainText(
    /家庭表达|家庭决定|顾问到家庭决策流程/,
  );
  await expect(page.getByRole("link", { name: "Night Voyager" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "让复杂的留学规划，清晰地向前。" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "查看完整咨询流程" })).toHaveAttribute(
    "href",
    "/demo/collaboration",
  );
  await expect(page.getByRole("link", { name: "查看方案研判" })).toHaveAttribute(
    "href",
    "/demo",
  );
  await expect(routePreview.locator(".portfolio-preview-route-list")).toContainText("澳大利亚");
  await expect(routePreview.locator(".portfolio-preview-route-list")).toContainText("日本");
  await expect(routePreview.locator(".portfolio-preview-route-list")).toContainText("马来西亚");
  await expect(page.getByText(/本地合成演示/)).toBeVisible();
  await expect(page.getByText("M0 · Local bootstrap")).toHaveCount(0);
  expect(await page.evaluate(() => sessionStorage.getItem("night-voyager:m5"))).toBeNull();
  expect(apiRequests).toEqual([]);
  expect(eventRequests).toEqual([]);

  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 1024, height: 900 },
    { width: 768, height: 1024 },
    { width: 390, height: 844 },
    { width: 320, height: 720 },
  ]) {
    await page.setViewportSize(viewport);
    await page.evaluate(
      () =>
        new Promise<void>((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
        ),
    );
    await page.waitForFunction(() => {
      const hero = document.querySelector(".portfolio-hero-copy");
      return (
        hero instanceof HTMLElement &&
        hero.getBoundingClientRect().right <=
          document.documentElement.clientWidth + 0.5
      );
    });
    const primaryAction = page.locator("a.portfolio-primary-action[href='/demo/collaboration']");
    await expect(primaryAction).toBeVisible();
    const routeSurface = routePreview.locator(".portfolio-preview-route-list");
    await expect(routeSurface.locator('[data-route-id="australia"]')).toContainText("在预算条件下推荐");
    await expect(routeSurface.locator('[data-route-id="japan"]')).toContainText("有条件备选");
    await expect(routeSurface.locator('[data-route-id="malaysia"]')).toContainText("暂不可选");
    expect(
      await page.evaluate(
        () =>
          document.documentElement.scrollWidth ===
          document.documentElement.clientWidth,
      ),
    ).toBe(true);
    const undersized = await page
      .locator(".portfolio-primary-action:visible, .portfolio-secondary-action:visible, .locale-switch button:visible")
      .evaluateAll(
        (nodes) =>
          nodes.filter((node) => {
            const box = node.getBoundingClientRect();
            return box.width < 44 || box.height < 44;
          }).length,
      );
    expect(undersized).toBe(0);
  }

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "跳到主要内容" })).toBeFocused();
  await expect
    .poll(async () => {
      await page.getByRole("button", { name: "English", exact: true }).click();
      return page.locator("html").getAttribute("lang");
    })
    .toBe("en");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator(".portfolio-category")).toHaveText(
    "An AI collaboration platform built for study-abroad advisors",
  );
  await expect(
    page.getByRole("heading", {
      name: "Move complex study-abroad planning forward with clarity.",
    }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "See the complete consultation flow" })).toHaveAttribute(
    "href",
    "/demo/collaboration",
  );
  await expect(page.getByRole("link", { name: "See route analysis" })).toHaveAttribute(
    "href",
    "/demo",
  );
  expect(apiRequests).toEqual([]);
  expect(eventRequests).toEqual([]);
});
