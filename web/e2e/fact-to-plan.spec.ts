import { writeFile } from "node:fs/promises";

import { expect, test, type Locator, type Page } from "@playwright/test";

const proofFile = process.env.FACT_TO_PLAN_PROOF_FILE;
const workerReadyFile = process.env.FACT_TO_PLAN_WORKER_READY_FILE;
const workerReadySentinel = process.env.FACT_TO_PLAN_WORKER_READY_SENTINEL;
const rawPublicData = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|schema_version|confirmed_fact_id|candidate_id|request_sha256|night_voyager_(?:api|worker|migrator)|\/Users\/|Traceback|csrf|cookie/i;

async function expectPublicSurface(page: Page) {
  await expect(page.getByRole("banner")).toBeVisible();
  await expect(page.getByRole("main")).toBeVisible();
  await expect(page.getByRole("contentinfo")).toBeVisible();
  await expect(page.getByRole("main")).not.toContainText(rawPublicData);
}

async function expectResponsiveSurface(page: Page, requiredVisible: readonly Locator[]) {
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 768, height: 900 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    expect(await page.evaluate(() => document.documentElement.scrollWidth === document.documentElement.clientWidth)).toBe(true);
    const undersized = await page.locator("button:visible, a.primary-action:visible").evaluateAll((nodes) => nodes.filter((node) => node.getBoundingClientRect().height < 44).length);
    expect(undersized).toBe(0);
    const controls = await page.getByRole("group", { name: /展示语言|Presentation language/ }).boundingBox();
    expect(controls).not.toBeNull();
    expect((controls?.x ?? 0) + (controls?.width ?? 0)).toBeLessThanOrEqual(viewport.width);
    for (const required of requiredVisible) await expect(required).toBeVisible();
  }
}

test("fact-to-plan.spec.ts proves one governed same-Case browser-to-database journey", async ({ page }) => {
  test.skip(!proofFile || !workerReadyFile || !workerReadySentinel, "runs only in the isolated fact-to-plan Compose lane");
  let storageReplacements = 0;
  await page.exposeFunction("recordFactToPlanStorageWrite", () => { storageReplacements += 1; });
  await page.addInitScript(() => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = function setItem(key: string, value: string) {
      if (this === sessionStorage && key === "night-voyager:m5") void (window as typeof window & { recordFactToPlanStorageWrite: () => Promise<void> }).recordFactToPlanStorageWrite();
      return original.call(this, key, value);
    };
  });
  const mutations: string[] = [];
  const eventRequests: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST") mutations.push(new URL(request.url()).pathname);
    if (request.url().includes("/events?after=")) eventRequests.push(request.url());
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/demo/collaboration");
  await expectPublicSurface(page);
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "跳到主要内容" })).toBeFocused();
  await page.getByRole("button", { name: "开始家长流程" }).click();
  await page.getByRole("button", { name: "添加已确认预算消息" }).click();
  await page.getByRole("button", { name: "提交预算供顾问审核" }).click();
  await page.getByRole("button", { name: "以指定顾问身份继续" }).click();
  await page.getByRole("button", { name: "确认家庭预算" }).click();
  await expect(page.getByRole("heading", { name: "需要重新规划" })).toBeFocused();
  await expect(page.getByText("Fact version 1")).toBeVisible();
  await expect(page.getByText("Case revision 2")).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "需要重新规划" })).toBeFocused();
  await expectResponsiveSurface(page, [
    page.getByRole("heading", { name: "需要重新规划" }),
    page.getByText("Fact version 1"),
    page.getByText("Case revision 2"),
  ]);
  await page.setViewportSize({ width: 1440, height: 900 });

  const caseId = await page.evaluate(() => JSON.parse(sessionStorage.getItem("night-voyager:m5") ?? "null").caseId as string);
  const taskPostsForCase = (continuedCaseId: string) => mutations.filter((path) => path === `/api/demo/cases/${continuedCaseId}/agent-tasks`);
  expect(taskPostsForCase(caseId)).toHaveLength(0);
  const handoffReads: string[] = [];
  const readListener = (request: import("@playwright/test").Request) => {
    const path = new URL(request.url()).pathname;
    if (request.method() === "GET" && ["memory-candidates", "confirmed-facts", "advisor-ledger", "planning-skill-inspector"].some((suffix) => path.endsWith(`/${suffix}`))) handoffReads.push(path);
  };
  page.on("request", readListener);
  storageReplacements = 0;
  const eventsBeforeHandoff = eventRequests.length;
  let planningNavigations = 0;
  let planningNavigationSeen = false;
  page.on("framenavigated", (frame) => {
    if (frame === page.mainFrame() && new URL(frame.url()).pathname === "/demo" && !planningNavigationSeen) {
      planningNavigationSeen = true;
      planningNavigations += 1;
      page.off("request", readListener);
    }
  });
  await page.getByRole("button", { name: "继续进入受治理规划" }).click();
  await page.waitForURL("**/demo");
  await expect(page.getByRole("heading", { name: "当前决策阶段" })).toBeVisible();
  await expect(page.getByText("家庭总预算")).toBeVisible();
  await expect(page.getByText("Case revision 2").first()).toBeVisible();
  expect(handoffReads).toEqual([
    `/api/demo/cases/${caseId}/memory-candidates`,
    `/api/demo/cases/${caseId}/confirmed-facts`,
    `/api/demo/cases/${caseId}/advisor-ledger`,
    `/api/demo/cases/${caseId}/planning-skill-inspector`,
  ]);
  expect(taskPostsForCase(caseId)).toHaveLength(0);
  expect(eventRequests).toHaveLength(eventsBeforeHandoff);
  expect(storageReplacements).toBe(1);
  expect(planningNavigations).toBe(1);

  const firstStream = page.waitForRequest((request) => request.url().includes("/events?after=0"));
  await page.getByRole("button", { name: "创建规划任务" }).click();
  await firstStream;
  await writeFile(workerReadyFile!, `${workerReadySentinel}\n`, { encoding: "utf8", mode: 0o600 });
  await page.waitForFunction(() => Number(JSON.parse(sessionStorage.getItem("night-voyager:m5") ?? "{}").cursor) > 0);
  const storedCursor = await page.evaluate(() => Number(JSON.parse(sessionStorage.getItem("night-voyager:m5") ?? "{}").cursor));
  const reloadStream = page.waitForRequest((request) => request.url().includes("/events?after="));
  await page.reload();
  expect(new URL((await reloadStream).url()).searchParams.get("after")).toBe(String(storedCursor));
  await expect(page.getByRole("button", { name: "批准澳大利亚进入家庭审核" })).toBeEnabled({ timeout: 60_000 });
  await expect(page.getByText("运行时 Skill pin 已匹配")).toBeVisible();
  await expect(page.getByRole("button", { name: "批准澳大利亚进入家庭审核" })).toBeEnabled();
  expect(taskPostsForCase(caseId)).toHaveLength(1);
  expect(eventRequests.filter((url) => new URL(url).searchParams.get("after") === "0")).toHaveLength(1);
  const taskId = await page.evaluate(() => JSON.parse(sessionStorage.getItem("night-voyager:m5") ?? "null").taskId as string);

  await page.getByRole("button", { name: "批准澳大利亚进入家庭审核" }).click();
  await expect(page.getByRole("heading", { name: "家庭决定简报" })).toBeVisible({ timeout: 30_000 });
  await page.reload();
  await expect(page.getByRole("heading", { name: "家庭决定简报" })).toBeVisible();
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "确认澳大利亚路线" }).click();
  await expect(page.getByRole("heading", { name: "家庭决定回执" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "行动时间线" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "家庭决定回执" })).toBeVisible();
  await expectResponsiveSurface(page, [
    page.getByRole("heading", { name: "家庭决定回执" }),
    page.getByRole("heading", { name: "行动时间线" }),
  ]);
  await expectPublicSurface(page);

  await writeFile(proofFile!, `${JSON.stringify({ schema_version: 1, case_id: caseId, case_revision: 2, task_id: taskId })}\n`, { encoding: "utf8", mode: 0o600 });
});
