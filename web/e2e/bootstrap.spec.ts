import { expect, test } from "@playwright/test";

test("shows the Chinese-first portfolio entry without API side effects", async ({ page }) => {
  const apiRequests: string[] = [];
  const eventRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) apiRequests.push(request.url());
    if (request.url().includes("/events?after=")) eventRequests.push(request.url());
  });
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
  await page.waitForFunction(() => {
    const image = document.querySelector(".portfolio-backdrop img");
    return (
      image instanceof HTMLImageElement &&
      image.complete &&
      image.naturalWidth > 0
    );
  });
  expect(
    await page
      .locator(".portfolio-backdrop img")
      .evaluate((image) => (image as HTMLImageElement).currentSrc),
  ).toContain("night-voyager-voyage-1680.avif");
  await expect(page.getByRole("link", { name: "Night Voyager" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "你的留学路线 应该从你出发" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "查看示例方案" })).toHaveAttribute(
    "href",
    "/demo/collaboration",
  );
  await expect(page.getByRole("link", { name: "查看路线依据" })).toHaveAttribute(
    "href",
    "#route-atlas",
  );
  await expect(
    page.locator('.portfolio-atlas-graphic [data-route-stop="australia"]'),
  ).toContainText("澳大利亚");
  await expect(
    page.locator('.portfolio-atlas-graphic [data-route-stop="japan"]'),
  ).toContainText("日本");
  await expect(
    page.locator('.portfolio-atlas-graphic [data-route-stop="malaysia"]'),
  ).toContainText("马来西亚");
  await expect(page.getByText("本地合成演示", { exact: true })).toBeVisible();
  await expect(page.getByText("M0 · Local bootstrap")).toHaveCount(0);
  expect(await page.evaluate(() => sessionStorage.getItem("night-voyager:m5"))).toBeNull();
  expect(apiRequests).toEqual([]);
  expect(eventRequests).toEqual([]);

  for (const viewport of [
    { width: 1440, height: 1000 },
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
    const primaryAction = page.getByRole("link", { name: "查看示例方案" });
    await expect(primaryAction).toBeVisible();
    const routeSurface = page.locator(
      viewport.width >= 1024
        ? ".portfolio-atlas-graphic"
        : ".portfolio-route-summary",
    );
    await expect(routeSurface.locator('[data-route-stop="australia"]')).toContainText(
      "推荐",
    );
    await expect(routeSurface.locator('[data-route-stop="japan"]')).toContainText(
      "备选",
    );
    await expect(routeSurface.locator('[data-route-stop="malaysia"]')).toContainText(
      "暂不推荐",
    );
    expect(
      await page.evaluate(
        () =>
          document.documentElement.scrollWidth ===
          document.documentElement.clientWidth,
      ),
    ).toBe(true);
    const undersized = await page
      .locator(".portfolio-button:visible, .locale-switch button:visible")
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
  await expect(
    page.getByRole("heading", {
      name: "Your study-abroad route should start with you",
    }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "View the example plan" })).toHaveAttribute(
    "href",
    "/demo/collaboration",
  );
  expect(apiRequests).toEqual([]);
  expect(eventRequests).toEqual([]);
});
