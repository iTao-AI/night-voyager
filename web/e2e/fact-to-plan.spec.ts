import { writeFile } from "node:fs/promises";

import { expect, test, type Locator, type Page } from "@playwright/test";

const proofFile = process.env.FACT_TO_PLAN_PROOF_FILE;
const connectedExecutionProofFile = process.env.FACT_TO_PLAN_CONNECTED_EXECUTION_PROOF_FILE;
const workerReadyFile = process.env.FACT_TO_PLAN_WORKER_READY_FILE;
const workerReadySentinel = process.env.FACT_TO_PLAN_WORKER_READY_SENTINEL;
const presentationLocale = process.env.PRESENTATION_LOCALE === "en" ? "en" : "zh-CN";
const updatePortfolioScreenshots = process.env.UPDATE_PORTFOLIO_SCREENSHOTS === "1";
const portfolioCopy = presentationLocale === "en" ? {
  budget: "CNY 300,000–400,000",
  heading: "Move complex study-abroad planning forward with clarity.",
  primaryAction: "See the advisor workflow",
  secondaryAction: "See route analysis",
  routeDescription: "The current client case has intended field computing and a confirmed planning budget of CNY 300,000–400,000. Australia is recommended with a budget condition, Japan is a conditional alternative, and Malaysia is unavailable.",
  persistedBudget: "CNY 305,500–400,000",
  routes: [
    ["australia", "Australia", "Recommended with budget condition"],
    ["japan", "Japan", "Conditional alternative"],
    ["malaysia", "Malaysia", "Blocked"],
  ],
} : {
  budget: "¥300,000–400,000",
  heading: "让复杂的留学规划，清晰地向前。",
  primaryAction: "查看顾问工作流",
  secondaryAction: "查看方案研判",
  routeDescription: "当前客户档案的意向方向为计算机方向，确认规划预算为 CNY 300,000–400,000。澳大利亚在预算条件下推荐，日本为有条件备选，马来西亚暂不可选。",
  persistedBudget: "¥305,500–400,000",
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
  handoff: "Continue to planning",
  stage: "Current decision stage",
  familyBudget: "Total family budget",
  factVersion: "Information version",
  caseRevision: "Record version",
  createTask: "Create planning task",
  pinMatched: "Runtime Skill pin matched",
  approve: "Approve current plan",
  continueParent: "Continue as parent",
  familyBrief: "Family Decision Brief",
  continueDecision: "Continue family decision",
  receipt: "Family Decision Receipt",
  timeline: "Action timeline",
  continueExecution: "Continue this Case into execution",
} : {
  startParent: "开始家长流程",
  addBudget: "添加已确认预算消息",
  proposeBudget: "提交预算供顾问审核",
  continueAdvisor: "以指定顾问身份继续",
  confirmBudget: "确认家庭预算",
  replan: "需要重新规划",
  handoff: "继续进入规划",
  stage: "当前决策阶段",
  familyBudget: "家庭总预算",
  factVersion: "事实版本",
  caseRevision: "档案版本",
  createTask: "创建规划任务",
  pinMatched: "运行时 Skill pin 已匹配",
  approve: "批准当前计划",
  continueParent: "以家长身份继续",
  familyBrief: "家庭决定简报",
  continueDecision: "继续家庭决定",
  receipt: "家庭决定回执",
  timeline: "行动时间线",
  continueExecution: "继续当前 Case 的执行计划",
};
const executionCopy = presentationLocale === "en" ? {
  student: "Student",
  advisor: "Advisor",
  start: "Start the action plan",
  progress: "Record progress",
  blocked: "Record blocker and stop the current checkpoint",
  reassess: "Request reassessment and stop execution",
  recover: "Revalidate execution authority",
  handoff: "Reassessment handoff",
  pending: "Any next workflow awaits separate future authorization.",
} : {
  student: "学生",
  advisor: "顾问",
  start: "开始执行行动计划",
  progress: "记录进行中",
  blocked: "记录阻塞并停止当前 checkpoint",
  reassess: "请求重新评估并停止执行",
  recover: "重新验证执行 authority",
  handoff: "重新评估交接",
  pending: "后续流程等待未来单独授权。",
};
const rawPublicData = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|schema_version|confirmed_fact_id|candidate_id|request_sha256|night_voyager_(?:api|worker|migrator)|\/Users\/|Traceback|csrf|cookie/i;

async function expectPublicSurface(page: Page) {
  await expect(page.getByRole("banner")).toBeVisible();
  await expect(page.getByRole("main")).toBeVisible();
  await expect(page.getByRole("contentinfo")).toBeVisible();
  await expect(page.getByRole("main")).not.toContainText(rawPublicData);
}

async function expectTransitionSurfacesReadable(page: Page, selectors: string, state: string) {
  const measurements = await page.locator(selectors).evaluateAll((elements) => {
    const parse = (value: string) => {
      const channels = (value.match(/[\d.]+/g) ?? []).map(Number);
      const alpha = channels.length >= 4 ? channels[3] : 1;
      return alpha >= 0.99 ? channels.slice(0, 3) : [];
    };
    const luminance = (rgb: number[]) => rgb.reduce((sum, channel, index) => {
      const normalized = channel / 255;
      const linear = normalized <= 0.04045
        ? normalized / 12.92
        : ((normalized + 0.055) / 1.055) ** 2.4;
      return sum + linear * [0.2126, 0.7152, 0.0722][index]!;
    }, 0);
    const contrast = (foreground: number[], background: number[]) => {
      const light = Math.max(luminance(foreground), luminance(background));
      const dark = Math.min(luminance(foreground), luminance(background));
      return (light + 0.05) / (dark + 0.05);
    };
    return elements.map((element) => {
      let surface: HTMLElement | null = element as HTMLElement;
      let background = parse(getComputedStyle(surface).backgroundColor);
      while (surface && background.length < 3) {
        surface = surface.parentElement;
        if (surface) background = parse(getComputedStyle(surface).backgroundColor);
      }
      const foreground = parse(getComputedStyle(element).color);
      const box = element.getBoundingClientRect();
      const frame = element.closest<HTMLElement>(".advisor-product-frame-grid")?.getBoundingClientRect();
      return {
        contrast: foreground.length === 3 && background.length === 3 ? contrast(foreground, background) : 0,
        outsideFrame: frame ? box.left < frame.left - 1 || box.right > frame.right + 1 : false,
      };
    });
  });
  expect(measurements, state).not.toHaveLength(0);
  expect(measurements.filter((measurement) => measurement.contrast < 4.5), state).toEqual([]);
  expect(measurements.filter((measurement) => measurement.outsideFrame), state).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), state).toBe(true);
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
    /为留学顾问打造的 AI 协作平台|An AI collaboration platform built for study-abroad advisors/,
  );
  await expect(page.locator(".portfolio-product-story")).toContainText(
    /客户信息、路线比较|Client information, plan comparisons/,
  );
  await expect(page.locator(".portfolio-workflow-list")).toContainText(
    /执行跟进|Execution follow-up/,
  );
  await expect(
    page.locator("a.portfolio-primary-action[href='/demo/collaboration']"),
  ).toHaveAttribute("href", "/demo/collaboration");
  await expect(
    page.getByRole("link", { name: portfolioCopy.secondaryAction }),
  ).toHaveAttribute("href", "/demo");
  const reducedMotion = await page.evaluate(() => matchMedia("(prefers-reduced-motion: reduce)").matches);
  if (reducedMotion) {
    await expect(page.getByText(portfolioCopy.persistedBudget, { exact: true }).first()).toBeVisible();
  } else {
    await page.locator("[data-story-sentinel][data-story-scene='route']").scrollIntoViewIfNeeded();
    await expect(page.locator("#route-atlas .portfolio-preview-route-description")).toHaveText(
      portfolioCopy.routeDescription,
    );
  }
  await expect(page.getByText(portfolioCopy.budget, { exact: true }).first()).toBeVisible();

  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 1280, height: 1000 },
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
            const intentionalRailOverflow = node.closest(
              ".advisor-product-frame .workflow-rail-list",
            );
            if (intentionalRailOverflow) return false;
            return box.left < -0.5 || box.right > document.documentElement.clientWidth + 0.5;
          }).length,
    );
    expect(clipped).toBe(0);
    if (!reducedMotion) {
      const routeSurface = page.locator("#route-atlas .portfolio-route-list");
      for (const [id, country, outcome] of portfolioCopy.routes) {
        const route = routeSurface.locator(`[data-route-id="${id}"]`);
        await expect(route).toHaveCount(1);
        await expect(route).toContainText(country);
        await expect(route).toContainText(outcome);
      }
    } else {
      const staticSubjects = page.locator(
        ".portfolio-story-static-subject:visible .advisor-workspace-preview",
      );
      await expect(staticSubjects).toHaveCount(3);
      await expect(
        page.locator(
          "[data-story-scene='confirmed'] .portfolio-story-static-subject:visible .advisor-workspace-preview",
        ),
      ).toBeVisible();
      await expect(
        page.locator(
          "[data-story-scene='route'] .portfolio-story-static-subject:visible .advisor-workspace-preview",
        ),
      ).toBeVisible();
      await expect(
        page.locator(
          "[data-story-scene='outcome'] .portfolio-story-static-subject:visible .advisor-workspace-preview",
        ),
      ).toBeVisible();
      const staticSceneOrder = await page.locator(
        ".portfolio-story-static-subject:visible .advisor-workspace-preview",
      ).evaluateAll((nodes) => nodes.map((node) => node.getAttribute("data-preview-scene")));
      expect(staticSceneOrder).toEqual(["confirmed", "route", "outcome"]);
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
  const skipLink = page.locator(".skip-link");
  await expect(skipLink).toHaveCount(1);
  await skipLink.evaluate((node) => node.setAttribute("hidden", ""));
  await expect(skipLink).toBeHidden();
  await page.screenshot({ path: `/workspace/docs/assets/${filename}`, fullPage: true });
}

interface ConnectedExecutionContext {
  schema_version: 1;
  journey: "connected-advisor-family";
  case_id: string;
  case_revision: number;
  decision_id: string;
  decision_receipt_id: string;
  timeline_plan_id: string;
  execution_id: string | null;
  active_role: "advisor" | "student" | "parent";
  assignment_status: "assigned";
}

interface ConnectedExecutionReceipt {
  schema_version: 1;
  receipt_id: string;
  operation: "start" | "attest" | "verify" | "reassess";
  result_id: string;
  execution_id: string;
  checkpoint_id: string | null;
}

interface ConnectedExecutionView {
  execution: {
    execution_id: string;
    case_id: string;
    case_revision: number;
    decision_id: string;
    decision_receipt_id: string;
    timeline_plan_id: string;
    state: string;
    row_version: number;
  };
  checkpoints: Array<{
    checkpoint_id: string;
    ordinal: number;
    milestone_key: string;
    state: string;
    row_version: number;
  }>;
  current_checkpoint: {
    checkpoint_id: string;
    ordinal: number;
    milestone_key: string;
    state: string;
    row_version: number;
  } | null;
  reassessment: {
    reassessment_id: string;
    execution_id: string;
    checkpoint_id: string;
    predecessor_case_id: string;
    predecessor_case_revision: number;
    predecessor_decision_id: string;
    predecessor_decision_receipt_id: string;
    predecessor_timeline_plan_id: string;
    predecessor_execution_id: string;
    predecessor_checkpoint_id: string;
    successor_status: string;
  } | null;
}

async function connectedMutate(
  page: Page,
  buttonName: string,
  path: string,
): Promise<{ receipt: ConnectedExecutionReceipt; view: ConnectedExecutionView }> {
  const receiptResponse = page.waitForResponse(
    (response) => response.request().method() === "POST" && response.url().includes(path),
  );
  const viewResponse = page.waitForResponse(
    (response) => response.request().method() === "GET"
      && response.url().includes("/timeline-execution"),
  );
  await page.getByRole("button", { name: buttonName, exact: true }).click();
  const [receiptHttp, viewHttp] = await Promise.all([receiptResponse, viewResponse]);
  expect(receiptHttp.status()).toBe(200);
  expect(viewHttp.status()).toBe(200);
  return {
    receipt: await receiptHttp.json() as ConnectedExecutionReceipt,
    view: await viewHttp.json() as ConnectedExecutionView,
  };
}

function expectConnectedExecutionIdentity(
  view: ConnectedExecutionView,
  context: ConnectedExecutionContext,
  executionId?: string,
) {
  expect(view.execution.case_id).toBe(context.case_id);
  expect(view.execution.case_revision).toBe(context.case_revision);
  expect(view.execution.decision_id).toBe(context.decision_id);
  expect(view.execution.decision_receipt_id).toBe(context.decision_receipt_id);
  expect(view.execution.timeline_plan_id).toBe(context.timeline_plan_id);
  if (executionId) expect(view.execution.execution_id).toBe(executionId);
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
  test.skip(
    !proofFile || !connectedExecutionProofFile || !workerReadyFile || !workerReadySentinel,
    "runs only in the isolated fact-to-plan Compose lane",
  );
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
  await expect(page.locator(".portfolio-hero-product .advisor-workspace-preview")).toBeVisible();
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
  await expect(page.locator("html")).toHaveCSS("scroll-behavior", "auto");
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
  const confirmedRecord = page.locator("[data-confirmed-record]");
  await expect(confirmedRecord).toHaveAttribute("data-fact-version", "1");
  await expect(confirmedRecord).toHaveAttribute("data-case-revision", "2");
  await expect(confirmedRecord.getByText(presentationCopy.factVersion, { exact: true })).toBeVisible();
  await expect(confirmedRecord.getByText(presentationCopy.caseRevision, { exact: true })).toBeVisible();
  await expectTransitionSurfacesReadable(
    page,
    ".message-list li, [data-confirmed-record] .collaboration-facts > div",
    "confirmed fact transition",
  );
  await page.reload();
  await expect(page.getByRole("heading", { name: presentationCopy.replan })).toBeFocused();
  await expectResponsiveSurface(page, [
    page.getByRole("heading", { name: presentationCopy.replan }),
    confirmedRecord,
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
  await expect(page.locator("[data-frame-slot='top-band']")).toContainText(/同一 Case 的连接证明|Connected same-Case proof/);
  await expect(page.getByRole("heading", { name: presentationCopy.stage })).toBeVisible();
  await expect(page.getByText(presentationCopy.familyBudget)).toBeVisible();
  await expect(page.getByText(`${presentationCopy.caseRevision} 2`, { exact: true }).first()).toBeVisible();
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
  await expectTransitionSurfacesReadable(
    page,
    ".advisor-ledger .table-wrap table, .advisor-ledger .current-stage",
    "advisor review transition",
  );
  const technicalEvidence = page.locator("[data-frame-slot='technical']");
  await technicalEvidence.locator(":scope > summary").click();
  await expect(technicalEvidence.getByText(presentationCopy.pinMatched)).toBeVisible();
  const reloadEventStart = eventRequests.length;
  await page.reload();
  await expect(page.getByRole("button", { name: presentationCopy.approve })).toBeEnabled();
  await technicalEvidence.locator(":scope > summary").click();
  await expect(technicalEvidence.getByText(presentationCopy.pinMatched)).toBeVisible();
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
  await expectTransitionSurfacesReadable(
    page,
    "[data-persisted-result] .decision-requirements > div, [data-persisted-result] .timeline",
    "persisted receipt transition",
  );
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

  const briefResponse = await page.request.get(
    `/api/demo/cases/${caseId}/current-decision-brief?contract_version=2`,
  );
  expect(briefResponse.status()).toBe(200);
  const brief = await briefResponse.json() as {
    case_id: string;
    revision_context: { current_case_revision: number };
    receipt: { decision_id: string; receipt_id: string };
    timeline: { country: string };
  };
  expect(brief.case_id).toBe(caseId);
  expect(brief.revision_context.current_case_revision).toBe(2);
  expect(brief.receipt).toBeTruthy();
  expect(brief.timeline).toBeTruthy();

  await expect(
    page.getByRole("link", { name: presentationCopy.continueExecution, exact: true }),
  ).toHaveAttribute("href", `/demo/plan?case_id=${caseId}`);
  await page.getByRole("link", {
    name: presentationCopy.continueExecution,
    exact: true,
  }).click();
  await page.waitForURL(`**/demo/plan?case_id=${caseId}`);
  await expect(page.locator(".advisor-workspace-shell")).toHaveAttribute(
    "data-proof-segment",
    "connected_same_case",
  );
  await expect(page.locator("[data-frame-slot='top-band']")).toContainText(
    /当前 Case 的执行延续|Continuation of this Case/,
  );

  const wrongCaseId = "40000000-0000-0000-0000-000000000001";
  const wrongCaseResponse = await page.request.get(
    `/api/demo/cases/${wrongCaseId}/plan-execution-context`,
  );
  expect(wrongCaseResponse.status()).toBe(404);
  expect(await wrongCaseResponse.json()).toMatchObject({
    code: "plan_execution_context_unavailable",
  });

  await page.getByRole("button", { name: executionCopy.student, exact: true }).click();
  await expect(page.getByRole("button", {
    name: executionCopy.student,
    exact: true,
  })).toHaveAttribute("aria-pressed", "true");
  const contextResponse = await page.request.get(
    `/api/demo/cases/${caseId}/plan-execution-context`,
  );
  expect(contextResponse.status()).toBe(200);
  const context = await contextResponse.json() as ConnectedExecutionContext;
  expect(Object.keys(context).sort()).toEqual([
    "active_role",
    "assignment_status",
    "case_id",
    "case_revision",
    "decision_id",
    "decision_receipt_id",
    "execution_id",
    "journey",
    "schema_version",
    "timeline_plan_id",
  ].sort());
  expect(context).toMatchObject({
    schema_version: 1,
    journey: "connected-advisor-family",
    case_id: caseId,
    case_revision: 2,
    decision_id: brief.receipt.decision_id,
    decision_receipt_id: brief.receipt.receipt_id,
    execution_id: null,
    active_role: "student",
    assignment_status: "assigned",
  });

  const acceptedReceiptIds: string[] = [];
  const checkpointIds: string[] = [];
  const started = await connectedMutate(page, executionCopy.start, "/executions");
  acceptedReceiptIds.push(started.receipt.receipt_id);
  checkpointIds.push(...started.view.checkpoints.map((checkpoint) => checkpoint.checkpoint_id));
  expect(checkpointIds).toHaveLength(4);
  expect(started.view.current_checkpoint?.milestone_key).toBe("documents");
  expectConnectedExecutionIdentity(started.view, context, started.receipt.execution_id);
  const startedContextResponse = await page.request.get(
    `/api/demo/cases/${caseId}/plan-execution-context`,
  );
  expect(startedContextResponse.status()).toBe(200);
  expect((await startedContextResponse.json() as ConnectedExecutionContext).execution_id)
    .toBe(started.receipt.execution_id);

  await page.reload();
  await expect(page.getByRole("button", {
    name: executionCopy.progress,
    exact: true,
  })).toBeVisible();
  const reloadedContextResponse = await page.request.get(
    `/api/demo/cases/${caseId}/plan-execution-context`,
  );
  expect(reloadedContextResponse.status()).toBe(200);
  const reloadedContext = await reloadedContextResponse.json() as ConnectedExecutionContext;
  expect(reloadedContext).toMatchObject({
    ...context,
    execution_id: started.receipt.execution_id,
  });

  let lostReceipt: ConnectedExecutionReceipt | null = null;
  let dropOnce = true;
  await page.route("**/checkpoint-attestations", async (route) => {
    if (!dropOnce) {
      await route.continue();
      return;
    }
    dropOnce = false;
    const upstream = await route.fetch();
    lostReceipt = await upstream.json() as ConnectedExecutionReceipt;
    await route.abort("failed");
  });
  await page.getByRole("button", { name: executionCopy.progress, exact: true }).click();
  await expect(page.getByRole("button", {
    name: executionCopy.recover,
    exact: true,
  })).toBeVisible();
  await page.unroute("**/checkpoint-attestations");
  const recoveredReceiptResponse = page.waitForResponse(
    (response) => response.request().method() === "POST"
      && response.url().includes("/checkpoint-attestations"),
  );
  const recoveredViewResponse = page.waitForResponse(
    (response) => response.request().method() === "GET"
      && response.url().includes("/timeline-execution"),
  );
  await page.getByRole("button", { name: executionCopy.recover, exact: true }).click();
  const [recoveredReceiptHttp, recoveredViewHttp] = await Promise.all([
    recoveredReceiptResponse,
    recoveredViewResponse,
  ]);
  expect(recoveredReceiptHttp.status()).toBe(200);
  expect(recoveredViewHttp.status()).toBe(200);
  const recoveredReceipt = await recoveredReceiptHttp.json() as ConnectedExecutionReceipt;
  const recoveredView = await recoveredViewHttp.json() as ConnectedExecutionView;
  expect(lostReceipt).not.toBeNull();
  expect(recoveredReceipt.receipt_id).toBe(lostReceipt!.receipt_id);
  acceptedReceiptIds.push(lostReceipt!.receipt_id);
  expectConnectedExecutionIdentity(recoveredView, context, started.receipt.execution_id);

  const blocked = await connectedMutate(page, executionCopy.blocked, "/checkpoint-attestations");
  acceptedReceiptIds.push(blocked.receipt.receipt_id);
  expect(blocked.view.current_checkpoint?.state).toBe("blocked");
  expectConnectedExecutionIdentity(blocked.view, context, started.receipt.execution_id);

  const advisorSessionResponse = page.waitForResponse(
    (response) => response.request().method() === "POST"
      && response.url().endsWith("/api/demo/sessions"),
  );
  await page.getByRole("button", { name: executionCopy.advisor, exact: true }).click();
  expect((await advisorSessionResponse).status()).toBe(201);
  await expect(page.getByRole("button", {
    name: executionCopy.reassess,
    exact: true,
  })).toBeVisible();
  const reassessed = await connectedMutate(page, executionCopy.reassess, "/reassessments");
  acceptedReceiptIds.push(reassessed.receipt.receipt_id);
  expect(reassessed.view.execution.state).toBe("reassessment_required");
  expect(reassessed.view.reassessment).toMatchObject({
    execution_id: started.receipt.execution_id,
    checkpoint_id: checkpointIds[0],
    predecessor_case_id: caseId,
    predecessor_case_revision: 2,
    predecessor_decision_id: context.decision_id,
    predecessor_decision_receipt_id: context.decision_receipt_id,
    predecessor_timeline_plan_id: context.timeline_plan_id,
    predecessor_execution_id: started.receipt.execution_id,
    predecessor_checkpoint_id: checkpointIds[0],
    successor_status: "pending_future_authorization",
  });
  await expect(page.getByRole("heading", { name: executionCopy.handoff })).toBeVisible();
  await expect(page.getByText(executionCopy.pending)).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: executionCopy.handoff })).toBeVisible();
  await expect(page.getByText(executionCopy.pending)).toBeVisible();
  await expectPublicSurface(page);

  await writeFile(connectedExecutionProofFile!, `${JSON.stringify({
    schema_version: 1,
    locale: presentationLocale,
    case_id: caseId,
    case_revision: 2,
    task_id: taskId,
    decision_id: context.decision_id,
    decision_receipt_id: context.decision_receipt_id,
    timeline_plan_id: context.timeline_plan_id,
    execution_id: started.receipt.execution_id,
    lost_ack_receipt_id: lostReceipt!.receipt_id,
    blocked_attestation_id: blocked.receipt.result_id,
    reassessment_request_id: reassessed.receipt.result_id,
    accepted_receipt_ids: acceptedReceiptIds,
    checkpoint_ids: checkpointIds,
  })}\n`, { encoding: "utf8", mode: 0o600 });
});
