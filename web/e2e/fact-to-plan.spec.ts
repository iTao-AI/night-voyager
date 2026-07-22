import { writeFile } from "node:fs/promises";

import { expect, test, type Locator, type Page } from "@playwright/test";

const proofFile = process.env.FACT_TO_PLAN_PROOF_FILE;
const workerReadyFile = process.env.FACT_TO_PLAN_WORKER_READY_FILE;
const workerReadySentinel = process.env.FACT_TO_PLAN_WORKER_READY_SENTINEL;
const presentationLocale = process.env.PRESENTATION_LOCALE === "en" ? "en" : "zh-CN";
const updatePortfolioScreenshots = process.env.UPDATE_PORTFOLIO_SCREENSHOTS === "1";
const presentationCopy = presentationLocale === "en" ? {
  startParent: "Start parent flow",
  addBudget: "Add confirmed budget message",
  proposeBudget: "Submit the budget for advisor review",
  continueAdvisor: "Continue as assigned advisor",
  confirmBudget: "Confirm family budget",
  replan: "Re-plan required",
  handoff: "Continue to governed planning",
  stage: "Current decision stage",
  familyBudget: "Total family budget",
  createTask: "Create planning task",
  pinMatched: "Runtime Skill pin matched",
  approve: "Approve Australia for family review",
  familyBrief: "Family Decision Brief",
  confirmRoute: "Confirm Australia route",
  receipt: "Family Decision Receipt",
  timeline: "Action timeline",
} : {
  startParent: "开始家长流程",
  addBudget: "添加已确认预算消息",
  proposeBudget: "提交预算供顾问审核",
  continueAdvisor: "以指定顾问身份继续",
  confirmBudget: "确认家庭预算",
  replan: "需要重新规划",
  handoff: "继续进入受治理规划",
  stage: "当前决策阶段",
  familyBudget: "家庭总预算",
  createTask: "创建规划任务",
  pinMatched: "运行时 Skill pin 已匹配",
  approve: "批准澳大利亚进入家庭审核",
  familyBrief: "家庭决定简报",
  confirmRoute: "确认澳大利亚路线",
  receipt: "家庭决定回执",
  timeline: "行动时间线",
};
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

async function capturePublicScreenshot(page: Page, filename: string) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await expectPublicSurface(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth === document.documentElement.clientWidth)).toBe(true);
  const clipped = await page.locator("main :is(h1, h2, h3, p, li, dt, dd, button, a):visible").evaluateAll((nodes) => nodes.filter((node) => {
    const box = node.getBoundingClientRect();
    return box.left < 0 || box.right > document.documentElement.clientWidth + 0.5;
  }).length);
  expect(clipped).toBe(0);
  await page.screenshot({ path: `/workspace/docs/assets/${filename}`, fullPage: true });
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
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
  await expectPublicSurface(page);
  expect(mutations).toHaveLength(0);
  expect(eventRequests).toHaveLength(0);
  expect(await page.evaluate(() => sessionStorage.getItem("night-voyager:m5"))).toBeNull();
  if (presentationLocale === "en") {
    await page.getByRole("button", { name: "English", exact: true }).click();
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
    expect(await page.evaluate(() => localStorage.getItem("night-voyager:presentation-locale:v1"))).toBe("en");
    expect(mutations).toHaveLength(0);
    expect(eventRequests).toHaveLength(0);
    expect(await page.evaluate(() => sessionStorage.getItem("night-voyager:m5"))).toBeNull();
  } else if (updatePortfolioScreenshots) {
    await capturePublicScreenshot(page, "night-voyager-portfolio-entry.png");
  }

  await page.goto("/demo/collaboration");
  await expectPublicSurface(page);
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: presentationLocale === "en" ? "Skip to main content" : "跳到主要内容" })).toBeFocused();
  await page.getByRole("button", { name: presentationCopy.startParent }).click();
  await page.getByRole("button", { name: presentationCopy.addBudget }).click();
  await page.getByRole("button", { name: presentationCopy.proposeBudget }).click();
  await page.getByRole("button", { name: presentationCopy.continueAdvisor }).click();
  await page.getByRole("button", { name: presentationCopy.confirmBudget }).click();
  await expect(page.getByRole("heading", { name: presentationCopy.replan })).toBeFocused();
  await expect(page.getByText("Fact version 1")).toBeVisible();
  await expect(page.getByText("Case revision 2")).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: presentationCopy.replan })).toBeFocused();
  await expectResponsiveSurface(page, [
    page.getByRole("heading", { name: presentationCopy.replan }),
    page.getByText("Fact version 1"),
    page.getByText("Case revision 2"),
  ]);
  await page.setViewportSize({ width: 1440, height: 900 });
  if (presentationLocale === "zh-CN" && updatePortfolioScreenshots) {
    await capturePublicScreenshot(page, "collaboration-confirmed-fact.png");
  }

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
  await page.getByRole("button", { name: presentationCopy.handoff }).click();
  await page.waitForURL("**/demo");
  await expect(page.getByRole("heading", { name: presentationCopy.stage })).toBeVisible();
  await expect(page.getByText(presentationCopy.familyBudget)).toBeVisible();
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
  await page.getByRole("button", { name: presentationCopy.createTask }).click();
  await firstStream;
  await writeFile(workerReadyFile!, `${workerReadySentinel}\n`, { encoding: "utf8", mode: 0o600 });
  await page.waitForFunction(() => Number(JSON.parse(sessionStorage.getItem("night-voyager:m5") ?? "{}").cursor) > 0);
  const storedCursor = await page.evaluate(() => Number(JSON.parse(sessionStorage.getItem("night-voyager:m5") ?? "{}").cursor));
  const reloadStream = page.waitForRequest((request) => request.url().includes("/events?after="));
  await page.reload();
  expect(new URL((await reloadStream).url()).searchParams.get("after")).toBe(String(storedCursor));
  await expect(page.getByRole("button", { name: presentationCopy.approve })).toBeEnabled({ timeout: 60_000 });
  await expect(page.getByText(presentationCopy.pinMatched)).toBeVisible();
  await expect(page.getByRole("button", { name: presentationCopy.approve })).toBeEnabled();
  expect(taskPostsForCase(caseId)).toHaveLength(1);
  expect(eventRequests.filter((url) => new URL(url).searchParams.get("after") === "0")).toHaveLength(1);
  const taskId = await page.evaluate(() => JSON.parse(sessionStorage.getItem("night-voyager:m5") ?? "null").taskId as string);
  if (presentationLocale === "zh-CN" && updatePortfolioScreenshots) {
    await capturePublicScreenshot(page, "m5-advisor-ledger.png");
  }

  await page.getByRole("button", { name: presentationCopy.approve }).click();
  await expect(page.getByRole("heading", { name: presentationCopy.familyBrief })).toBeVisible({ timeout: 30_000 });
  await page.reload();
  await expect(page.getByRole("heading", { name: presentationCopy.familyBrief })).toBeVisible();
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: presentationCopy.confirmRoute }).click();
  await expect(page.getByRole("heading", { name: presentationCopy.receipt })).toBeVisible();
  await expect(page.getByRole("heading", { name: presentationCopy.timeline })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: presentationCopy.receipt })).toBeVisible();
  await expectResponsiveSurface(page, [
    page.getByRole("heading", { name: presentationCopy.receipt }),
    page.getByRole("heading", { name: presentationCopy.timeline }),
  ]);
  await expectPublicSurface(page);
  if (presentationLocale === "zh-CN" && updatePortfolioScreenshots) {
    await capturePublicScreenshot(page, "m5-family-receipt-timeline.png");
  }

  await writeFile(proofFile!, `${JSON.stringify({ schema_version: 1, case_id: caseId, case_revision: 2, task_id: taskId })}\n`, { encoding: "utf8", mode: 0o600 });
});
