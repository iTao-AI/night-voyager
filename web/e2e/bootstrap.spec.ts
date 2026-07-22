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
  await expect(page.getByText("本地合成演示")).toBeVisible();
  await expect(page.getByText("M0 · Local bootstrap")).toHaveCount(0);
  expect(apiRequests).toEqual([]);
});
