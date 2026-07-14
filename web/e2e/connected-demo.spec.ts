import { expect, test } from "@playwright/test";

test("connected-demo.spec.ts proves the advisor-to-family database flow", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/demo");
  await expect(page.getByRole("heading", { name: "Connected advisor-to-family demo" })).toBeVisible();
  await expect(page.getByRole("banner")).toBeVisible();
  await expect(page.getByRole("main")).toBeVisible();
  await expect(page.getByRole("contentinfo")).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to decision workflow" })).toBeFocused();

  await page.getByRole("button", { name: "Start advisor walkthrough" }).click();
  await expect(page.getByRole("heading", { name: "Advisor Ledger" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Create planning task" })).toBeEnabled();

  await page.getByRole("button", { name: "Create planning task" }).click();
  await expect(page.getByRole("button", { name: "Approve Australia for family review" })).toBeEnabled({ timeout: 60_000 });
  await expect(page.getByRole("button", { name: "Choose Malaysia" })).toBeDisabled();
  await expect(page.getByText(/Accepted synthetic evidence and limitations/i)).toBeVisible();
  await expect(page.locator("[aria-live='polite']")).toBeAttached();

  const sseReplay = await page.evaluate(async () => {
    const metadata = JSON.parse(sessionStorage.getItem("night-voyager:m5") ?? "null") as { taskId?: string } | null;
    const response = await fetch(`/api/demo/tasks/${metadata?.taskId}/events?after=0`, {
      headers: { "Last-Event-ID": "1" },
    });
    return { status: response.status, body: await response.text() };
  });
  expect(sseReplay.status).toBe(200);
  expect(sseReplay.body).not.toMatch(/^id: 1$/m);
  expect(sseReplay.body).toMatch(/^id: [2-9][0-9]*$/m);

  await page.getByRole("button", { name: "Approve Australia for family review" }).click();
  await expect(page.getByRole("heading", { name: "Family Decision Brief" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/budget_elasticity/i)).toBeVisible();
  const advisorDenied = await page.request.get(
    "/api/demo/cases/40000000-0000-0000-0000-000000000002/advisor-ledger",
  );
  expect(advisorDenied.status()).toBe(404);

  await page.getByRole("checkbox").check();
  const decisionRequestPromise = page.waitForRequest(
    (request) => request.method() === "POST" && request.url().includes("/family-decisions"),
  );
  await page.getByRole("button", { name: "Confirm Australia route" }).click();
  const decisionRequest = await decisionRequestPromise;
  const decisionHeaders = await decisionRequest.allHeaders();
  await expect(page.getByRole("heading", { name: "Decision Receipt" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Timeline Plan" })).toBeVisible();

  const decisionPath = new URL(decisionRequest.url()).pathname;
  const replay = await page.request.post(decisionPath, {
    data: decisionRequest.postDataJSON(),
    headers: {
      Origin: "http://127.0.0.1:3000",
      "Content-Type": "application/json",
      "X-CSRF-Token": decisionHeaders["x-csrf-token"],
      "Idempotency-Key": decisionHeaders["idempotency-key"],
    },
  });
  expect(replay.status()).toBe(200);
  const stale = await page.request.post(decisionPath, {
    data: decisionRequest.postDataJSON(),
    headers: {
      Origin: "http://127.0.0.1:3000",
      "Content-Type": "application/json",
      "X-CSRF-Token": decisionHeaders["x-csrf-token"],
      "Idempotency-Key": "00000000-0000-4000-8000-000000000999",
    },
  });
  expect(stale.status()).toBe(409);
  await expect(page.getByRole("heading", { name: "Decision Receipt" })).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { name: "Decision Receipt" })).toBeVisible();
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 768, height: 900 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
  await expect(page.getByRole("main")).toBeVisible();
});
