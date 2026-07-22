import { expect, test } from "@playwright/test";

test("shows the Chinese-first portfolio entry without API side effects", async ({ page }) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) apiRequests.push(request.url());
  });
  await page.goto("/");
  await expect(page.getByRole("link", { name: "Night Voyager" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "把家庭事实变成可追溯的留学决策与行动计划" })).toBeVisible();
  await expect(page.getByRole("link", { name: "体验完整决策流程" })).toHaveAttribute("href", "/demo/collaboration");
  await expect(page.getByText("本地合成演示", { exact: true })).toBeVisible();
  await expect(page.getByText("M0 · Local bootstrap")).toHaveCount(0);
  expect(apiRequests).toEqual([]);

  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 768, height: 900 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    const primaryAction = page.getByRole("link", { name: "体验完整决策流程" });
    await expect(primaryAction).toBeVisible();
    await expect(page.getByText("当前目的", { exact: true })).toBeVisible();
    await expect(page.getByText("为什么可信", { exact: true })).toBeVisible();
    await expect(page.getByText("下一步", { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth === document.documentElement.clientWidth)).toBe(true);
    if (viewport.width === 390) {
      const box = await primaryAction.boundingBox();
      expect(box).not.toBeNull();
      expect((box?.y ?? viewport.height) + (box?.height ?? 0)).toBeLessThanOrEqual(viewport.height);
    }
  }
});
