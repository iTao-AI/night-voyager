import { writeFile } from "node:fs/promises";

import { expect, test, type Locator, type Page } from "@playwright/test";

const proofFile = process.env.FACT_TO_PLAN_PROOF_FILE;
const workerReadyFile = process.env.FACT_TO_PLAN_WORKER_READY_FILE;
const workerReadySentinel = process.env.FACT_TO_PLAN_WORKER_READY_SENTINEL;
const presentationLocale = process.env.PRESENTATION_LOCALE === "en" ? "en" : "zh-CN";
const updatePortfolioScreenshots = process.env.UPDATE_PORTFOLIO_SCREENSHOTS === "1";
const portfolioCopy = presentationLocale === "en" ? {
  budget: "CNY 340,000–400,000",
  heading: "Turn scattered consultations into a client plan you can move forward",
  primaryAction: "Walk through one client case",
  secondaryAction: "See how the proposal is verified",
  routeDescription: "The current case has intended field computing and a CNY 340,000–400,000 budget. Australia is recommended with a budget condition, Japan is a conditional alternative, and Malaysia is blocked.",
  supersededBudget: "305,500",
  routes: [
    ["australia", "Australia", "Recommended with budget condition"],
    ["japan", "Japan", "Conditional alternative"],
    ["malaysia", "Malaysia", "Blocked"],
  ],
} : {
  budget: "¥340,000–400,000",
  heading: "把零散咨询，整理成可以推进的留学方案",
  primaryAction: "查看一次完整咨询流程",
  secondaryAction: "了解方案如何被核对",
  routeDescription: "当前档案的 intended field 为 computing，预算为 CNY 340,000–400,000。澳大利亚在预算条件下推荐，日本为有条件备选，马来西亚暂不可选。",
  supersededBudget: "30.55",
  routes: [
    ["australia", "澳大利亚", "在预算条件下推荐"],
    ["japan", "日本", "有条件备选"],
    ["malaysia", "马来西亚", "暂不可选"],
  ],
} as const;
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
  approve: "Approve current plan",
  continueParent: "Continue as parent",
  familyBrief: "Family Decision Brief",
  continueDecision: "Continue family decision",
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
  approve: "批准当前计划",
  continueParent: "以家长身份继续",
  familyBrief: "家庭决定简报",
  continueDecision: "继续家庭决定",
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

async function expectPortfolioEntry(page: Page) {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await expect(
    page.getByRole("heading", { level: 1, name: portfolioCopy.heading }),
  ).toBeVisible();
  await expect(page.locator(".portfolio-category")).toContainText(
    /留学顾问的 AI 协作工作台|AI collaboration workspace for study-abroad advisors/,
  );
  await expect(page.locator(".portfolio-workflow")).toContainText(
    /同一 Case|same Case/,
  );
  await expect(
    page.locator(".portfolio-primary-action"),
  ).toHaveAttribute("href", "/demo/collaboration");
  await expect(
    page.getByRole("link", { name: portfolioCopy.secondaryAction }),
  ).toHaveAttribute("href", "/demo");
  await expect(page.locator("#route-atlas .portfolio-section-heading > p:last-child")).toHaveText(
    portfolioCopy.routeDescription,
  );
  await expect(page.getByText(portfolioCopy.budget, { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("main")).not.toContainText(portfolioCopy.supersededBudget);

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
    const clipped = await page
      .locator(
        "main :is(h1, h2, h3, p, li, summary, a, button, strong, em, small):visible",
      )
      .evaluateAll(
        (nodes) =>
          nodes.filter((node) => {
            const box = node.getBoundingClientRect();
            return (
              box.left < -0.5 ||
              box.right > document.documentElement.clientWidth + 0.5
            );
          }).length,
    );
    expect(clipped).toBe(0);
    const routeSurface = page.locator("#route-atlas .portfolio-route-list");
    for (const [id, country, outcome] of portfolioCopy.routes) {
      const route = routeSurface.locator(`[data-route-id="${id}"]`);
      await expect(route).toHaveCount(1);
      await expect(route).toContainText(country);
      await expect(route).toContainText(outcome);
    }
  }
}

async function capturePublicScreenshot(page: Page, filename: string) {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await expectPublicSurface(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth === document.documentElement.clientWidth)).toBe(true);
  const clipped = await page.locator("main :is(h1, h2, h3, p, li, dt, dd, button, a):visible").evaluateAll((nodes) => nodes.filter((node) => {
    const box = node.getBoundingClientRect();
    return box.left < 0 || box.right > document.documentElement.clientWidth + 0.5;
  }).length);
  expect(clipped).toBe(0);
  await page.screenshot({ path: `/workspace/docs/assets/${filename}`, fullPage: true });
}

interface FactToPlanAuthoritySnapshot {
  ready: boolean;
  phase: unknown;
  taskStatus: unknown;
  ledgerPhase: unknown;
  problemCode: unknown;
  taskPlanningRunId: unknown;
  ledgerPlanningRunId: unknown;
}

async function readFactToPlanReviewAuthority(
  page: Page,
  caseId: string,
  taskId: string,
): Promise<FactToPlanAuthoritySnapshot> {
  return page.evaluate(async ({ caseId, taskId }) => {
    const read = async (path: string) => {
      const response = await fetch(path, { cache: "no-store" });
      const value: unknown = await response.json().catch(() => null);
      const payload = typeof value === "object" && value !== null && !Array.isArray(value)
        ? value as Record<string, unknown>
        : {};
      return {
        status: response.status,
        payload,
        problemCode: payload.code,
      };
    };
    const [journeyRead, taskRead, ledgerRead] = await Promise.all([
      read(`/api/demo/cases/${caseId}/journey-status`),
      read(`/api/demo/tasks/${taskId}`),
      read(`/api/demo/cases/${caseId}/advisor-ledger`),
    ]);
    const journey = journeyRead.payload;
    const task = taskRead.payload;
    const ledger = ledgerRead.payload;
    const ledgerTask = typeof ledger.task === "object" && ledger.task !== null && !Array.isArray(ledger.task)
      ? ledger.task as Record<string, unknown>
      : {};
    const ledgerRun = typeof ledger.planning_run === "object" && ledger.planning_run !== null && !Array.isArray(ledger.planning_run)
      ? ledger.planning_run as Record<string, unknown>
      : {};
    const reviewInputs = typeof ledger.review_inputs === "object" && ledger.review_inputs !== null && !Array.isArray(ledger.review_inputs)
      ? ledger.review_inputs as Record<string, unknown>
      : {};
    const problemCode = [journeyRead, taskRead, ledgerRead]
      .find((projection) => projection.status !== 200)?.problemCode ?? null;
    const planningRunId = task.planning_run_id;
    return {
      ready:
        journeyRead.status === 200
        && taskRead.status === 200
        && ledgerRead.status === 200
        && journey.case_id === caseId
        && journey.phase === "review_required"
        && journey.active_role === "advisor"
        && task.task_id === taskId
        && task.status === "needs_advisor_review"
        && typeof planningRunId === "string"
        && ledger.case_id === caseId
        && ledger.phase === "review_required"
        && ledgerTask.task_id === taskId
        && ledgerTask.status === "needs_advisor_review"
        && ledgerTask.planning_run_id === planningRunId
        && ledgerRun.planning_run_id === planningRunId
        && reviewInputs.planning_run_id === planningRunId,
      phase: journey.phase,
      taskStatus: task.status,
      ledgerPhase: ledger.phase,
      problemCode,
      taskPlanningRunId: planningRunId,
      ledgerPlanningRunId: ledgerRun.planning_run_id,
    };
  }, { caseId, taskId });
}

async function waitForFactToPlanReviewAuthority(
  page: Page,
  caseId: string,
  taskId: string,
): Promise<void> {
  let latest: FactToPlanAuthoritySnapshot | null = null;
  try {
    await expect.poll(async () => {
      latest = await readFactToPlanReviewAuthority(page, caseId, taskId);
      return latest.ready;
    }, {
      intervals: [250, 500, 1_000],
      timeout: 120_000,
    }).toBe(true);
  } catch (error) {
    console.error("fact-to-plan approval convergence diagnostic", JSON.stringify(latest));
    throw error;
  }
}

async function captureFactToPlanApprovalDiagnostic(
  page: Page,
  caseId: string,
  taskId: string,
): Promise<void> {
  const [authority, ui] = await Promise.all([
    readFactToPlanReviewAuthority(page, caseId, taskId),
    page.evaluate(() => {
      const stored: unknown = JSON.parse(sessionStorage.getItem("night-voyager:m5") ?? "{}");
      const envelope = typeof stored === "object" && stored !== null && !Array.isArray(stored)
        ? stored as Record<string, unknown>
        : {};
      return {
        pathname: window.location.pathname,
        headings: Array.from(document.querySelectorAll("h1, h2, h3"))
          .filter((node) => (node as HTMLElement).offsetParent !== null)
          .map((node) => node.textContent?.trim() ?? "")
          .filter(Boolean),
        actions: Array.from(document.querySelectorAll("button, a"))
          .filter((node) => (node as HTMLElement).offsetParent !== null)
          .map((node) => node.textContent?.trim() ?? "")
          .filter(Boolean),
        envelope: {
          schemaVersion: envelope.schema_version,
          journey: envelope.journey,
          role: envelope.role,
          caseId: envelope.caseId,
          currentRevision: envelope.currentRevision,
          currentTaskId: envelope.currentTaskId,
          currentRunId: envelope.currentRunId,
          cursor: envelope.cursor,
          phase: envelope.phase,
        },
      };
    }),
  ]);
  console.error(
    "fact-to-plan approval convergence diagnostic",
    JSON.stringify({ authority, ui }),
  );
}

test("fact-to-plan.spec.ts proves one governed same-Case browser-to-database journey", async ({ page }) => {
  test.skip(!proofFile || !workerReadyFile || !workerReadySentinel, "runs only in the isolated fact-to-plan Compose lane");
  const storageReplacements: Array<{
    pathname: string;
    schemaVersion: 3;
    journey: "advisor-family";
    phase: string;
    currentRevision: number;
    hasCurrentTask: boolean;
  }> = [];
  await page.exposeFunction("recordFactToPlanStorageWrite", (record: typeof storageReplacements[number]) => {
    storageReplacements.push(record);
  });
  await page.addInitScript(() => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = function setItem(key: string, value: string) {
      if (this === sessionStorage && key === "night-voyager:m5") {
        try {
          const parsed: unknown = JSON.parse(value);
          if (typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)) {
            const envelope = parsed as Record<string, unknown>;
            const exactKeys = [
              "schema_version", "journey", "role", "csrf", "caseId", "currentRevision",
              "currentTaskId", "predecessorRunId", "currentRunId", "cursor", "phase", "mutations",
            ].sort();
            const keys = Object.keys(envelope).sort();
            if (
              keys.length === exactKeys.length
              && keys.every((entry, index) => entry === exactKeys[index])
              && envelope.schema_version === 3
              && envelope.journey === "advisor-family"
              && typeof envelope.phase === "string"
              && Number.isSafeInteger(envelope.currentRevision)
              && Number(envelope.currentRevision) > 0
              && (envelope.currentTaskId === null || typeof envelope.currentTaskId === "string")
            ) {
              void (window as typeof window & {
                recordFactToPlanStorageWrite: (record: {
                  pathname: string;
                  schemaVersion: 3;
                  journey: "advisor-family";
                  phase: string;
                  currentRevision: number;
                  hasCurrentTask: boolean;
                }) => Promise<void>;
              }).recordFactToPlanStorageWrite({
                pathname: window.location.pathname,
                schemaVersion: 3,
                journey: "advisor-family",
                phase: envelope.phase,
                currentRevision: Number(envelope.currentRevision),
                hasCurrentTask: envelope.currentTaskId !== null,
              });
            }
          }
        } catch {
          // Closed V3 advisor-family writes are the only records relevant to this proof.
        }
      }
      return original.call(this, key, value);
    };
  });
  const mutations: string[] = [];
  const eventRequests: string[] = [];
  const rootApiRequests: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST") mutations.push(new URL(request.url()).pathname);
    if (request.url().includes("/events?after=")) eventRequests.push(request.url());
    if (new URL(request.url()).pathname.startsWith("/api/")) {
      rootApiRequests.push(request.url());
    }
  });

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
  await expect(page.locator(".advisor-workspace-preview")).toBeVisible();
  await expectPublicSurface(page);
  expect(mutations).toHaveLength(0);
  expect(eventRequests).toHaveLength(0);
  expect(await page.evaluate(() => sessionStorage.getItem("night-voyager:m5"))).toBeNull();
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", {
      name: "跳到主要内容",
    }),
  ).toBeFocused();
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  if (presentationLocale === "en") {
    await expect
      .poll(async () => {
        await page.getByRole("button", { name: "English", exact: true }).click();
        return page.locator("html").getAttribute("lang");
      })
      .toBe("en");
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
    expect(await page.evaluate(() => localStorage.getItem("night-voyager:presentation-locale:v1"))).toBe("en");
    expect(mutations).toHaveLength(0);
    expect(eventRequests).toHaveLength(0);
    expect(await page.evaluate(() => sessionStorage.getItem("night-voyager:m5"))).toBeNull();
  }
  await expectPortfolioEntry(page);
  expect(rootApiRequests).toHaveLength(0);
  expect(storageReplacements).toHaveLength(0);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.reload();
  await expectPortfolioEntry(page);
  await expect(page.locator(".portfolio-route-path").first()).toHaveCSS(
    "stroke-dashoffset",
    "0px",
  );
  expect(rootApiRequests).toHaveLength(0);
  expect(storageReplacements).toHaveLength(0);
  if (presentationLocale === "zh-CN" && updatePortfolioScreenshots) {
    await capturePublicScreenshot(page, "night-voyager-portfolio-entry.png");
  }
  await page.emulateMedia({ reducedMotion: "no-preference" });

  await page.goto("/demo/collaboration");
  await expectPublicSurface(page);
  await expect(page.locator(".advisor-workspace-shell")).toHaveAttribute("data-proof-segment", "connected_same_case");
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
  expect(storageReplacements).toHaveLength(0);
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
  await expect(page.locator(".advisor-workspace-shell")).toHaveAttribute("data-proof-segment", "connected_same_case");
  await expect(page.locator(".workspace-context-bar")).toContainText(/同一 Case 的连接证明|Connected same-Case proof/);
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
  await expect.poll(() => storageReplacements.length).toBe(2);
  expect(storageReplacements).toEqual([
    {
      pathname: "/demo/collaboration",
      schemaVersion: 3,
      journey: "advisor-family",
      phase: "task_ready",
      currentRevision: 2,
      hasCurrentTask: false,
    },
    {
      pathname: "/demo",
      schemaVersion: 3,
      journey: "advisor-family",
      phase: "task_ready",
      currentRevision: 2,
      hasCurrentTask: false,
    },
  ]);
  expect(planningNavigations).toBe(1);

  const firstStream = page.waitForRequest((request) => request.url().includes("/events?after=0"));
  await page.getByRole("button", { name: presentationCopy.createTask }).click();
  await firstStream;
  await writeFile(workerReadyFile!, `${workerReadySentinel}\n`, { encoding: "utf8", mode: 0o600 });
  await page.waitForFunction(() => Number(JSON.parse(sessionStorage.getItem("night-voyager:m5") ?? "{}").cursor) > 0);
  const beforeReload = await page.evaluate(() => {
    const metadata: unknown = JSON.parse(sessionStorage.getItem("night-voyager:m5") ?? "{}");
    if (typeof metadata !== "object" || metadata === null) {
      throw new Error("invalid advisor-family recovery metadata");
    }
    const envelope = metadata as Record<string, unknown>;
    const caseId = envelope.caseId;
    const currentTaskId = envelope.currentTaskId;
    const cursor = envelope.cursor;
    if (
      envelope.schema_version !== 3
      || envelope.journey !== "advisor-family"
      || typeof caseId !== "string"
      || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(caseId)
      || typeof currentTaskId !== "string"
      || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(currentTaskId)
      || !Number.isSafeInteger(cursor)
      || Number(cursor) < 0
    ) {
      throw new Error("invalid advisor-family recovery metadata");
    }
    return {
      caseId,
      taskId: currentTaskId,
      cursor: Number(cursor),
    };
  });
  expect(beforeReload.caseId).toBe(caseId);
  expect(beforeReload.taskId).toBeTruthy();
  await waitForFactToPlanReviewAuthority(page, beforeReload.caseId, beforeReload.taskId);
  try {
    await expect(page.getByRole("button", { name: presentationCopy.approve })).toBeEnabled({ timeout: 15_000 });
  } catch (error) {
    await captureFactToPlanApprovalDiagnostic(page, beforeReload.caseId, beforeReload.taskId);
    throw error;
  }
  await expect(page.getByText(presentationCopy.pinMatched)).toBeVisible();
  const reloadEventStart = eventRequests.length;
  await page.reload();
  await expect(page.getByRole("button", { name: presentationCopy.approve })).toBeEnabled();
  await expect(page.getByText(presentationCopy.pinMatched)).toBeVisible();
  const afterReload = await page.evaluate(() => {
    const metadata: unknown = JSON.parse(sessionStorage.getItem("night-voyager:m5") ?? "{}");
    if (typeof metadata !== "object" || metadata === null) {
      throw new Error("invalid advisor-family recovery metadata");
    }
    const envelope = metadata as Record<string, unknown>;
    const caseId = envelope.caseId;
    const currentTaskId = envelope.currentTaskId;
    const cursor = envelope.cursor;
    if (
      envelope.schema_version !== 3
      || envelope.journey !== "advisor-family"
      || typeof caseId !== "string"
      || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(caseId)
      || typeof currentTaskId !== "string"
      || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(currentTaskId)
      || !Number.isSafeInteger(cursor)
      || Number(cursor) < 0
    ) {
      throw new Error("invalid advisor-family recovery metadata");
    }
    return {
      caseId,
      taskId: currentTaskId,
      cursor: Number(cursor),
    };
  });
  expect(afterReload).toMatchObject({ caseId: beforeReload.caseId, taskId: beforeReload.taskId });
  expect(afterReload.cursor).toBeGreaterThanOrEqual(beforeReload.cursor);
  const reloadEvents = eventRequests.slice(reloadEventStart);
  expect(reloadEvents.length).toBeLessThanOrEqual(1);
  if (reloadEvents[0]) {
    expect(new URL(reloadEvents[0]).searchParams.get("after")).toBe(String(beforeReload.cursor));
  }
  expect(taskPostsForCase(caseId)).toHaveLength(1);
  expect(eventRequests.filter((url) => new URL(url).searchParams.get("after") === "0")).toHaveLength(1);
  const taskId = afterReload.taskId;
  if (presentationLocale === "zh-CN" && updatePortfolioScreenshots) {
    await capturePublicScreenshot(page, "m5-advisor-ledger.png");
  }

  await page.getByRole("button", { name: presentationCopy.approve }).click();
  await expect(page.getByRole("button", { name: presentationCopy.continueParent })).toBeEnabled();
  await page.getByRole("button", { name: presentationCopy.continueParent }).click();
  await expect(page.getByRole("heading", { name: presentationCopy.familyBrief })).toBeVisible({ timeout: 30_000 });
  await page.reload();
  await expect(page.getByRole("heading", { name: presentationCopy.familyBrief })).toBeVisible();
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: presentationCopy.continueDecision }).click();
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
