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
  await expect(page.locator(".advisor-workspace-preview")).toBeVisible();
  await expect(page.locator(".portfolio-category")).toHaveText("留学顾问的 AI 协作工作台");
  await expect(page.locator(".portfolio-eyebrow")).toHaveText("AI 协作工作台 · 为留学顾问设计");
  await expect(page.locator(".portfolio-primary-navigation")).not.toContainText(
    /家庭表达|家庭决定|顾问到家庭决策流程/,
  );
  await expect(page.getByRole("link", { name: "Night Voyager" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "把零散咨询，整理成可以推进的留学方案" }),
  ).toBeVisible();
  await expect(page.locator(".portfolio-primary-action")).toHaveAttribute(
    "href",
    "/demo/collaboration",
  );
  await expect(page.getByRole("link", { name: "了解方案如何被核对" })).toHaveAttribute(
    "href",
    "/demo",
  );
  await expect(page.locator(".advisor-workspace-preview .workspace-route-list")).toContainText("澳大利亚");
  await expect(page.locator(".advisor-workspace-preview .workspace-route-list")).toContainText("日本");
  await expect(page.locator(".advisor-workspace-preview .workspace-route-list")).toContainText("马来西亚");
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
    const primaryAction = page.locator(".portfolio-primary-action");
    await expect(primaryAction).toBeVisible();
    const routeSurface = page.locator(".advisor-workspace-preview .workspace-route-list");
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
    "AI collaboration workspace for study-abroad advisors",
  );
  await expect(
    page.getByRole("heading", {
      name: "Turn scattered consultations into a client plan you can move forward",
    }),
  ).toBeVisible();
  await expect(page.locator(".portfolio-primary-action")).toHaveAttribute(
    "href",
    "/demo/collaboration",
  );
  await expect(page.getByRole("link", { name: "See how the proposal is verified" })).toHaveAttribute(
    "href",
    "/demo",
  );
  expect(apiRequests).toEqual([]);
  expect(eventRequests).toEqual([]);
});
