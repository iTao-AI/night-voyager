import { expect, test, type Page } from "@playwright/test";

const terminalProof = process.env.M5_TERMINAL_PROOF === "1";
const rawPresentation = /recommended_with_condition|synthetic_high_risk_alternative|direct_program_fit_evidence_absent|budget_elasticity|30,550,000|40,000,000/;

async function expectNoRawPresentation(page: Page) {
  await expect(page.getByRole("main")).not.toContainText(rawPresentation);
}

async function expectCollapsedNoTaskInspector(page: Page) {
  const details = page.locator(".skill-inspector details");
  await expect(details.locator("summary")).toBeVisible();
  await expect(details).not.toHaveAttribute("open", "");
  await expect(details).toContainText(/尚未创建规划任务|Planning task not created/);
}

test("connected-demo.spec.ts preserves the native SSE cursor and renders a live terminal task", async ({ page }) => {
  test.skip(!terminalProof, "runs in the worker-paused Compose lane");
  await page.goto("/demo");
  await page.getByRole("button", { name: /开始顾问流程|Start advisor flow/ }).click();
  await expect(page.getByRole("button", { name: /创建规划任务|Create planning task/ })).toBeEnabled();
  await expectCollapsedNoTaskInspector(page);

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
  await page.getByRole("button", { name: /创建规划任务|Create planning task/ }).click();
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
  await expect(page.getByRole("status")).toContainText(/正在准备|Preparing/i);

  const cancelled = await page.evaluate(async () => {
    const metadata: unknown = JSON.parse(sessionStorage.getItem("night-voyager:m5") ?? "{}");
    if (typeof metadata !== "object" || metadata === null) {
      throw new Error("invalid advisor-family recovery metadata");
    }
    const envelope = metadata as Record<string, unknown>;
    const taskId = envelope.currentTaskId;
    const csrf = envelope.csrf;
    if (
      envelope.schema_version !== 3
      || envelope.journey !== "advisor-family"
      || typeof taskId !== "string"
      || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(taskId)
      || typeof csrf !== "string"
      || csrf.length === 0
    ) {
      throw new Error("invalid advisor-family recovery metadata");
    }
    const current = await fetch(`/api/demo/tasks/${taskId}`, { cache: "no-store" });
    const task = await current.json();
    const response = await fetch(`/api/demo/tasks/${taskId}/cancel`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrf,
        "Idempotency-Key": "00000000-0000-4000-8000-000000000777",
      },
      body: JSON.stringify({ schema_version: 1, expected_row_version: task.row_version }),
    });
    return { status: response.status, body: await response.json() };
  });
  expect(cancelled.status).toBe(200);
  await expect(page.getByRole("status")).toContainText(/已取消|Cancelled/i);
  await expect(page.getByText(/规划任务已暂停|Planning task paused/i)).toBeVisible();
});

test("connected-demo.spec.ts connected golden flow proves the advisor-to-family database flow", async ({ page }) => {
  test.skip(terminalProof, "runs in the normal worker-backed Compose lane");
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/demo");
  await expect(page.getByRole("heading", { name: /让路线分析先通过顾问判断|Put route analysis through advisor review/ })).toBeVisible();
  await expect(page.locator(".advisor-workspace-shell")).toHaveAttribute("data-proof-segment", "connected_same_case");
  await expect(page.locator(".workspace-context-bar")).toContainText(/同一 Case 的连接证明|Connected same-Case proof/);
  await expect(page.locator(".workflow-rail-list")).toHaveCount(1);
  await expect(page.getByRole("banner")).toBeVisible();
  await expect(page.getByRole("main")).toBeVisible();
  await expect(page.getByRole("contentinfo")).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: /跳到主要内容|Skip to main content/ })).toBeFocused();

  await page.getByRole("button", { name: /开始顾问流程|Start advisor flow/ }).click();
  await expect(page.getByRole("heading", { name: /当前工作阶段|Current workflow stage/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /创建规划任务|Create planning task/ })).toBeEnabled();

  const initialSse = page.waitForRequest((request) => request.url().includes("/events?after="));
  await page.getByRole("button", { name: /创建规划任务|Create planning task/ }).click();
  const firstStream = await initialSse;
  expect(new URL(firstStream.url()).searchParams.get("after")).toBe("0");
  await page.reload();
  await expect(page.getByRole("status")).toBeVisible();
  await expect(page.getByRole("button", { name: /批准当前计划|Approve current plan/ })).toBeEnabled({ timeout: 60_000 });
  await expect(page.getByText(/在预算条件下推荐|Recommended with budget condition/).first()).toBeVisible();
  await expect(page.getByText(/成本与汇率证据均在已批准边界内|Cost and FX evidence are within the approved boundary/).first()).toBeVisible();
  await expect(page.getByText(/有条件备选|Conditional alternative/).first()).toBeVisible();
  await expect(page.getByText(/较高风险的合成备选方案|Higher-risk synthetic alternative/).first()).toBeVisible();
  await expect(page.getByText(/暂不可选|Blocked/).first()).toBeVisible();
  await expect(page.getByText(/已接受的合成证据与限制|Accepted synthetic evidence and limitations/i)).toBeVisible();
  await expect(page.getByRole("status")).toContainText(/需要顾问审核|Needs advisor review/i);
  await expect(page.getByText(/运行时 Skill pin 已匹配|Runtime Skill pin matched/)).toBeVisible();
  await expectNoRawPresentation(page);
  await page.setViewportSize({ width: 768, height: 900 });
  await expect(page.getByText(/在预算条件下推荐|Recommended with budget condition/).first()).toBeVisible();
  await expect(page.getByText(/成本与汇率证据均在已批准边界内|Cost and FX evidence are within the approved boundary/).first()).toBeVisible();
  await expectNoRawPresentation(page);
  await page.setViewportSize({ width: 390, height: 844 });
  for (const [country, outcome, reason] of [
    ["澳大利亚", /在预算条件下推荐|Recommended with budget condition/, /成本与汇率证据均在已批准边界内|Cost and FX evidence are within the approved boundary/],
    ["日本", /有条件备选|Conditional alternative/, /较高风险的合成备选方案|Higher-risk synthetic alternative/],
    ["马来西亚", /暂不可选|Blocked/, /缺少直接的项目匹配证据|Program-fit evidence is missing/],
  ] as const) {
    await page.getByRole("button", { name: country, exact: true }).click();
    await expect(page.getByRole("button", { name: country, exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByText(outcome).last()).toBeVisible();
    await expect(page.getByText(reason).last()).toBeVisible();
  }
  await expect(page.getByText(/不符合审核条件|Not eligible for review/, { exact: true }).last()).toBeVisible();
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
  await page.getByRole("button", { name: /批准当前计划|Approve current plan/ }).click();
  await expect(page.getByRole("heading", { name: /需要恢复|Recovery required/ })).toBeVisible();
  await page.getByRole("button", { name: /重新连接顾问流程|Reconnect advisor flow/ }).click();
  await expect(page.getByRole("button", { name: /以家长身份继续|Continue as parent/ })).toBeEnabled();
  await page.getByRole("button", { name: /以家长身份继续|Continue as parent/ }).click();
  await expect(page.getByRole("heading", { name: /家庭决定简报|Family Decision Brief/ })).toBeVisible({ timeout: 30_000 });
  expect(reviewKeys).toHaveLength(2);
  expect(reviewKeys[0]).toBe(reviewKeys[1]);
  await page.unroute("**/api/demo/cases/*/advisor-reviews");
  await expect(page.getByText("¥305,500")).toBeVisible();
  await expect(page.getByText("¥400,000")).toBeVisible();
  await expect(page.getByText(/预算弹性|Budget flexibility/).first()).toBeVisible();
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
  await page.getByRole("button", { name: /继续家庭决定|Continue family decision/ }).click();
  await expect(page.getByRole("heading", { name: /家庭决定回执|Family Decision Receipt/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /行动时间线|Action timeline/ })).toBeVisible();
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
  await expect(page.getByRole("heading", { name: /家庭决定回执|Family Decision Receipt/ })).toBeVisible();
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 768, height: 900 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    await expect(page.getByText("¥305,500–400,000")).toBeVisible();
    await expect(page.getByText(/预算弹性|Budget flexibility/)).toBeVisible();
    await expectNoRawPresentation(page);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
  await expect(page.getByRole("main")).toBeVisible();
});
