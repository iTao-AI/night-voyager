import { expect, test, type Page } from "@playwright/test";

const terminalProof = process.env.M5_TERMINAL_PROOF === "1";
const rawPresentation = /recommended_with_condition|synthetic_high_risk_alternative|direct_program_fit_evidence_absent|budget_elasticity|30,550,000|40,000,000/;

async function expectNoRawPresentation(page: Page) {
  await expect(page.getByRole("main")).not.toContainText(rawPresentation);
}

test("connected-demo.spec.ts preserves the native SSE cursor and renders a live terminal task", async ({ page }) => {
  test.skip(!terminalProof, "runs in the worker-paused Compose lane");
  await page.goto("/demo");
  await page.getByRole("button", { name: "Start advisor walkthrough" }).click();
  await expect(page.getByRole("button", { name: "Create planning task" })).toBeEnabled();
  await expect(page.getByText("No planning task created")).toBeVisible();

  let closedFirstStream = false;
  await page.route("**/api/demo/tasks/*/events?after=0", async (route) => {
    if (closedFirstStream) { await route.fallback(); return; }
    closedFirstStream = true;
    await route.fulfill({
      status: 200,
      headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-store" },
      body: 'id: 1\nevent: queued\ndata: {"status":"preparing"}\n\n',
    });
  });
  const initialSse = page.waitForRequest((request) => request.url().includes("/events?after="));
  const nativeReconnect = page.waitForRequest((request) => request.url().includes("/events?") && Boolean(request.headers()["last-event-id"]));
  await page.getByRole("button", { name: "Create planning task" }).click();
  expect(new URL((await initialSse).url()).searchParams.get("after")).toBe("0");
  await page.waitForFunction(() => {
    const stored = sessionStorage.getItem("night-voyager:m5");
    return stored !== null && Number(JSON.parse(stored).cursor) > 0;
  });
  const storedCursor = await page.evaluate(() => Number(JSON.parse(sessionStorage.getItem("night-voyager:m5") ?? "{}").cursor));

  expect((await nativeReconnect).headers()["last-event-id"]).toBe(String(storedCursor));
  await page.unroute("**/api/demo/tasks/*/events?after=0");

  const reloadSse = page.waitForRequest((request) => request.url().includes("/events?after="));
  await page.reload();
  expect(new URL((await reloadSse).url()).searchParams.get("after")).toBe(String(storedCursor));
  await expect(page.getByRole("status")).toContainText(/preparing/i);

  const cancelled = await page.evaluate(async () => {
    const metadata = JSON.parse(sessionStorage.getItem("night-voyager:m5") ?? "{}");
    const current = await fetch(`/api/demo/tasks/${metadata.taskId}`, { cache: "no-store" });
    const task = await current.json();
    const response = await fetch(`/api/demo/tasks/${metadata.taskId}/cancel`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": metadata.csrf,
        "Idempotency-Key": "00000000-0000-4000-8000-000000000777",
      },
      body: JSON.stringify({ schema_version: 1, expected_row_version: task.row_version }),
    });
    return { status: response.status, body: await response.json() };
  });
  expect(cancelled.status).toBe(200);
  await expect(page.getByRole("status")).toContainText(/cancelled/i);
  await expect(page.getByText(/terminal-task-failure/i)).toBeVisible();
});

test("connected-demo.spec.ts connected golden flow proves the advisor-to-family database flow", async ({ page }) => {
  test.skip(terminalProof, "runs in the normal worker-backed Compose lane");
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

  const initialSse = page.waitForRequest((request) => request.url().includes("/events?after="));
  await page.getByRole("button", { name: "Create planning task" }).click();
  const firstStream = await initialSse;
  expect(new URL(firstStream.url()).searchParams.get("after")).toBe("0");
  await page.reload();
  await expect(page.getByRole("status")).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve Australia for family review" })).toBeEnabled({ timeout: 60_000 });
  await expect(page.getByText("Recommended with budget condition").first()).toBeVisible();
  await expect(page.getByText("Cost and FX evidence are within the approved boundary").first()).toBeVisible();
  await expect(page.getByText("Conditional alternative").first()).toBeVisible();
  await expect(page.getByText("Higher-risk synthetic alternative").first()).toBeVisible();
  await expect(page.getByText("Blocked").first()).toBeVisible();
  await expect(page.getByText(/Accepted synthetic evidence and limitations/i)).toBeVisible();
  await expect(page.getByRole("status")).toContainText(/needs_advisor_review/i);
  await expect(page.getByText("Pinned execution matched")).toBeVisible();
  await expectNoRawPresentation(page);
  await page.setViewportSize({ width: 768, height: 900 });
  await expect(page.getByText("Recommended with budget condition").first()).toBeVisible();
  await expect(page.getByText("Cost and FX evidence are within the approved boundary").first()).toBeVisible();
  await expectNoRawPresentation(page);
  await page.setViewportSize({ width: 390, height: 844 });
  for (const [country, outcome, reason] of [
    ["Australia", "Recommended with budget condition", "Cost and FX evidence are within the approved boundary"],
    ["Japan", "Conditional alternative", "Higher-risk synthetic alternative"],
    ["Malaysia", "Blocked", "Program-fit evidence is missing"],
  ] as const) {
    await page.getByRole("button", { name: country, exact: true }).click();
    await expect(page.getByRole("button", { name: country, exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByText(outcome).last()).toBeVisible();
    await expect(page.getByText(reason).last()).toBeVisible();
  }
  await expect(page.getByText("Not eligible", { exact: true }).last()).toBeVisible();
  await expectNoRawPresentation(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.setViewportSize({ width: 1440, height: 900 });
  if (process.env.UPDATE_M5_SCREENSHOTS === "1") {
    await page.screenshot({ path: "/workspace/docs/assets/m5-advisor-ledger.png", fullPage: true });
  }

  const reviewKeys: string[] = [];
  let reviewAttempt = 0;
  await page.route("**/api/demo/cases/*/advisor-reviews", async (route) => {
    reviewAttempt += 1;
    reviewKeys.push(route.request().headers()["idempotency-key"] ?? "");
    if (reviewAttempt === 1) {
      const committed = await route.fetch();
      expect(committed.status()).toBe(200);
      await route.abort("failed");
      return;
    }
    await route.continue();
  });
  await page.getByRole("button", { name: "Approve Australia for family review" }).click();
  await expect(page.getByRole("heading", { name: "Recovery required" })).toBeVisible();
  await page.getByRole("button", { name: "Reconnect advisor walkthrough" }).click();
  await expect(page.getByRole("heading", { name: "Family Decision Brief" })).toBeVisible({ timeout: 30_000 });
  expect(reviewKeys).toHaveLength(2);
  expect(reviewKeys[0]).toBe(reviewKeys[1]);
  await page.unroute("**/api/demo/cases/*/advisor-reviews");
  await expect(page.getByText("305,500 CNY")).toBeVisible();
  await expect(page.getByText("400,000 CNY")).toBeVisible();
  await expect(page.getByText("Budget flexibility").first()).toBeVisible();
  await expectNoRawPresentation(page);
  const advisorDenied = await page.request.get(
    "/api/demo/cases/40000000-0000-0000-0000-000000000002/advisor-ledger",
  );
  expect(advisorDenied.status()).toBe(404);

  await page.getByRole("checkbox").check();
  let staleObserved = false;
  await page.route("**/api/demo/decision-briefs/*/family-decisions", async (route) => {
    const request = route.request();
    const headers = request.headers();
    const committed = await page.request.post(request.url(), {
      data: request.postDataJSON(),
      headers: {
        Origin: "http://127.0.0.1:3000",
        "Content-Type": "application/json",
        "X-CSRF-Token": headers["x-csrf-token"],
        "Idempotency-Key": "00000000-0000-4000-8000-000000000999",
      },
    });
    expect(committed.status()).toBe(200);
    const stale = await route.fetch();
    expect(stale.status()).toBe(409);
    staleObserved = true;
    await route.fulfill({ response: stale });
  });
  await page.getByRole("button", { name: "Confirm Australia route" }).click();
  await expect(page.getByRole("heading", { name: "Decision Receipt" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Timeline Plan" })).toBeVisible();
  expect(staleObserved).toBe(true);
  await expect(page.getByRole("checkbox")).toHaveCount(0);
  await page.unroute("**/api/demo/decision-briefs/*/family-decisions");
  if (process.env.UPDATE_M5_SCREENSHOTS === "1") {
    await page.screenshot({
      path: "/workspace/docs/assets/m5-family-receipt-timeline.png",
      fullPage: true,
    });
  }

  await page.reload();
  await expect(page.getByRole("heading", { name: "Decision Receipt" })).toBeVisible();
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 768, height: 900 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    await expect(page.getByText("305,500–400,000 CNY")).toBeVisible();
    await expect(page.getByText("Budget flexibility")).toBeVisible();
    await expectNoRawPresentation(page);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
  await expect(page.getByRole("main")).toBeVisible();
});
