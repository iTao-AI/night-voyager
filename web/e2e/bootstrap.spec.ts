import { expect, test } from "@playwright/test";

test("shows the M0 bootstrap page", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Night Voyager" })).toBeVisible();
  await expect(page.getByText("M0 · Local bootstrap")).toBeVisible();
});
