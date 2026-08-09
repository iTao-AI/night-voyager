import { writeFile } from "node:fs/promises";

import {
  expect,
  test,
  type APIResponse,
  type Page,
  type Request,
} from "@playwright/test";

const proofFile = process.env.PLANNING_REVISION_PROOF_FILE;
const workerReadyFile = process.env.PLANNING_REVISION_WORKER_READY_FILE;
const initialSentinel = process.env.PLANNING_REVISION_INITIAL_SENTINEL;
const restartSentinel = process.env.PLANNING_REVISION_RESTART_SENTINEL;
const reviewRoot = process.env.PLANNING_REVISION_REVIEW_ROOT;
const screenshotFile =
  process.env.PLANNING_REVISION_SCREENSHOT_FILE ??
  "/workspace/docs/assets/night-voyager-planning-revision.png";
const locale = process.env.PRESENTATION_LOCALE === "en" ? "en" : "zh-CN";
const updateScreenshot =
  process.env.UPDATE_PLANNING_REVISION_SCREENSHOT === "1";
const ORIGIN = "http://127.0.0.1:3000";
const HAPPY_CASE = "49000000-0000-0000-0000-000000000001";
const BLOCKED_CASE = "49000000-0000-0000-0000-000000000002";

const copy = locale === "en"
  ? {
      requestRevision: "Request revision",
      continueStudent: "Continue as student",
      submitProposal: "Submit change proposal",
      continueAdvisor: "Continue as advisor",
      confirmFact: "Confirm preferred-country change",
      createTask: "Create revised planning task",
      approve: "Approve revised plan",
      continueParent: "Continue as parent",
      familyBrief: "Family Decision Brief",
      continueDecision: "Continue family decision",
      receipt: "Family Decision Receipt",
      timeline: "Action timeline",
      reconnect: "Reconnect advisor flow",
      comparison: "Planning revision comparison",
      blocked: "This revision was blocked by deterministic policy",
      safeExit: "Return to product overview",
    }
  : {
      requestRevision: "请求修订",
      continueStudent: "以学生身份继续",
      submitProposal: "提交变更提案",
      continueAdvisor: "以顾问身份继续",
      confirmFact: "确认意向国家变更",
      createTask: "创建修订规划任务",
      approve: "批准修订计划",
      continueParent: "以家长身份继续",
      familyBrief: "家庭决定简报",
      continueDecision: "继续家庭决定",
      receipt: "家庭决定回执",
      timeline: "行动时间线",
      reconnect: "重新连接顾问流程",
      comparison: "规划修订比较",
      blocked: "此修订已被确定性规则阻止",
      safeExit: "返回产品概览",
    };

type Json = Record<string, unknown>;
type FlowProof = {
  case_id: string;
  request_review_id: string;
  predecessor_run_id: string;
  task_id: string;
  current_run_id: string;
};

async function payload(response: APIResponse): Promise<Json> {
  if (!response.ok()) {
    throw new Error(`request failed status=${response.status()} body=${await response.text()}`);
  }
  return await response.json() as Json;
}

async function mint(page: Page, role: "advisor" | "student" | "parent") {
  const bootstrap = await payload(
    await page.request.get("/api/demo/session-bootstrap"),
  );
  const session = await payload(
    await page.request.post("/api/demo/sessions", {
      headers: {
        Origin: ORIGIN,
        "Content-Type": "application/json",
        "X-CSRF-Token": String(bootstrap.csrf_token),
      },
      data: { demo_actor: role },
    }),
  );
  return String(session.csrf_token);
}

async function rotate(
  page: Page,
  csrf: string,
  role: "advisor" | "student" | "parent",
) {
  const revoked = await page.request.delete("/api/demo/session", {
    headers: { Origin: ORIGIN, "X-CSRF-Token": csrf },
  });
  expect(revoked.ok()).toBe(true);
  return await mint(page, role);
}

async function read(page: Page, path: string): Promise<Json> {
  return await payload(await page.request.get(path));
}

async function mutate(
  page: Page,
  path: string,
  csrf: string,
  key: string,
  data: unknown,
): Promise<Json> {
  return await payload(
    await page.request.post(path, {
      headers: {
        Origin: ORIGIN,
        "Content-Type": "application/json",
        "X-CSRF-Token": csrf,
        "Idempotency-Key": key,
      },
      data,
    }),
  );
}

function ledgerIdentity(ledger: Json) {
  const task = ledger.task as Json | null;
  const run = ledger.planning_run as Json | null;
  const comparison = ledger.comparison as Json | null;
  return {
    currentTaskId: task ? String(task.task_id) : null,
    predecessorRunId: comparison
      ? String(comparison.previous_planning_run_id)
      : null,
    currentRunId: run ? String(run.planning_run_id) : null,
  };
}

async function hydrate(
  page: Page,
  caseId: string,
  role: "advisor" | "student" | "parent",
  csrf: string,
  mutations: Json = {},
) {
  const status = await read(page, `/api/demo/cases/${caseId}/journey-status`);
  const ledger = role === "advisor"
    ? await read(page, `/api/demo/cases/${caseId}/advisor-ledger`)
    : null;
  const identity = ledger
    ? ledgerIdentity(ledger)
    : { currentTaskId: null, predecessorRunId: null, currentRunId: null };
  await page.evaluate(
    ({ envelope }) => {
      sessionStorage.setItem("night-voyager:m5", JSON.stringify(envelope));
    },
    {
      envelope: {
        schema_version: 3,
        journey: "advisor-family",
        role,
        csrf,
        caseId,
        currentRevision: Number(status.current_revision),
        ...identity,
        cursor: 0,
        phase: String(status.phase),
        mutations,
      },
    },
  );
}

async function lostAck(
  page: Page,
  pattern: string,
  operation: string,
  action: () => Promise<void>,
): Promise<{ response: Json; idempotencyKey: string }> {
  expect([
    "request-revision",
    "fact-confirmation",
    "create-task",
  ]).toContain(operation);
  let first = true;
  let captured: Json | null = null;
  let idempotencyKey = "";
  const keys: string[] = [];
  const listener = (request: Request) => {
    if (
      request.method() === "POST" &&
      new URL(request.url()).pathname.match(new RegExp(pattern))
    ) {
      const key = request.headers()["idempotency-key"];
      if (key) keys.push(key);
    }
  };
  page.on("request", listener);
  const matcher = new RegExp(`${pattern}$`);
  await page.route(matcher, async (route) => {
    if (!first) {
      await route.continue();
      return;
    }
    first = false;
    idempotencyKey = route.request().headers()["idempotency-key"] ?? "";
    expect(idempotencyKey).toBeTruthy();
    const response = await route.fetch();
    captured = await response.json() as Json;
    await route.abort();
  });
  await action();
  await expect(page.getByRole("button", { name: copy.reconnect })).toBeVisible();
  await page.getByRole("button", { name: copy.reconnect }).click();
  await expect.poll(() => keys.length).toBeGreaterThanOrEqual(2);
  expect(new Set(keys)).toEqual(new Set([idempotencyKey]));
  page.off("request", listener);
  await page.unroute(matcher);
  expect(captured).not.toBeNull();
  return { response: captured!, idempotencyKey };
}

async function capture(page: Page, state: "happy" | "blocked") {
  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 768, height: 900 },
    { width: 390, height: 844 },
    { width: 320, height: 720 },
  ]) {
    await page.setViewportSize(viewport);
    expect(
      await page.evaluate(
        () =>
          document.documentElement.scrollWidth ===
          document.documentElement.clientWidth,
      ),
    ).toBe(true);
  }
  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    expect(
      await page.evaluate(
        () =>
          document.documentElement.scrollWidth ===
          document.documentElement.clientWidth,
      ),
    ).toBe(true);
    const skipLink = page.locator(".skip-link");
    await expect(skipLink).toHaveCount(1);
    await skipLink.evaluate((node) => node.setAttribute("hidden", ""));
    await expect(skipLink).toBeHidden();
    const filename =
      `planning-revision-${locale}-${viewport.width}-${state}.png`;
    await page.screenshot({
      path: `${reviewRoot}/${filename}`,
      fullPage: true,
    });
    if (
      state === "happy" &&
      locale === "zh-CN" &&
      viewport.width === 1440 &&
      updateScreenshot
    ) {
      await page.screenshot({
        path: screenshotFile,
        fullPage: true,
      });
    }
  }
}

async function requestRevisionDirect(
  page: Page,
  caseId: string,
  csrf: string,
  key: string,
) {
  const ledger = await read(page, `/api/demo/cases/${caseId}/advisor-ledger`);
  const inputs = ledger.review_inputs as Json;
  const result = await mutate(
    page,
    `/api/demo/cases/${caseId}/advisor-reviews`,
    csrf,
    key,
    {
      schema_version: 1,
      planning_run_id: inputs.planning_run_id,
      expected_case_revision: inputs.expected_case_revision,
      action: "request_revision",
      eligible_route_ids: [],
      risk_acceptances: [],
      reviewer_notes: "Bounded synthetic revision proof.",
    },
  );
  return { ledger, result };
}

async function blockedFlow(page: Page, advisorCsrf: string): Promise<FlowProof> {
  const requested = await requestRevisionDirect(
    page,
    BLOCKED_CASE,
    advisorCsrf,
    "00000000-0000-4000-8000-000000000711",
  );
  const predecessor = String(
    (requested.ledger.planning_run as Json).planning_run_id,
  );
  const parentCsrf = await rotate(page, advisorCsrf, "parent");
  const thread = await read(
    page,
    `/api/demo/cases/${BLOCKED_CASE}/collaboration-thread`,
  );
  const message = await mutate(
    page,
    `/api/demo/collaboration-threads/${thread.thread_id}/messages`,
    parentCsrf,
    "00000000-0000-4000-8000-000000000712",
    {
      schema_version: 1,
      body: "Our synthetic family budget is capped below the Australia route.",
    },
  );
  await mutate(
    page,
    `/api/demo/messages/${message.message_event_id}/memory-candidates`,
    parentCsrf,
    "00000000-0000-4000-8000-000000000713",
    {
      schema_version: 1,
      case_revision: 1,
      proposal: {
        schema_version: 1,
        fact_key: "family.budget",
        value: {
          schema_version: 1,
          currency: "CNY",
          period: "program_total",
          preferred_minor: 20000000,
          hard_ceiling_minor: 25000000,
          elasticity_bps: 0,
          refused: false,
        },
      },
    },
  );
  const nextAdvisorCsrf = await rotate(page, parentCsrf, "advisor");
  const candidates = await payload(
    await page.request.get(
      `/api/demo/cases/${BLOCKED_CASE}/memory-candidates`,
    ),
  ) as unknown as Json[];
  const candidate = candidates.find(
    (item) =>
      item.fact_key === "family.budget" &&
      item.state === "pending",
  );
  expect(candidate).toBeTruthy();
  await mutate(
    page,
    `/api/demo/memory-candidates/${candidate!.candidate_id}/verification-decisions`,
    nextAdvisorCsrf,
    "00000000-0000-4000-8000-000000000714",
    {
      schema_version: 1,
      expected_case_revision: 1,
      decision: "confirm",
      reason: "Confirm the bounded synthetic budget counterfactual.",
    },
  );
  const replan = await read(
    page,
    `/api/demo/cases/${BLOCKED_CASE}/advisor-ledger`,
  );
  const inputs = replan.canonical_task_inputs as Json;
  const task = await mutate(
    page,
    `/api/demo/cases/${BLOCKED_CASE}/agent-tasks`,
    nextAdvisorCsrf,
    "00000000-0000-4000-8000-000000000715",
    {
      schema_version: 1,
      operation: inputs.operation,
      expected_case_revision: inputs.expected_case_revision,
      source_pack_id: inputs.source_pack_id,
      source_pack_version: inputs.source_pack_version,
      policy_version: inputs.policy_version,
    },
  );
  await expect.poll(async () => {
    const status = await read(
      page,
      `/api/demo/cases/${BLOCKED_CASE}/journey-status`,
    );
    return status.phase;
  }, { timeout: 90_000 }).toBe("revision_blocked");
  const blockedLedger = await read(
    page,
    `/api/demo/cases/${BLOCKED_CASE}/advisor-ledger`,
  );
  const rejected = await page.request.post(
    `/api/demo/cases/${BLOCKED_CASE}/advisor-reviews`,
    {
      headers: {
        Origin: ORIGIN,
        "Content-Type": "application/json",
        "X-CSRF-Token": nextAdvisorCsrf,
        "Idempotency-Key": "00000000-0000-4000-8000-000000000716",
      },
      data: {
        schema_version: 1,
        planning_run_id: (blockedLedger.planning_run as Json).planning_run_id,
        expected_case_revision: 2,
        action: "approve_for_consultation",
        eligible_route_ids: [],
        risk_acceptances: [],
      },
    },
  );
  expect(rejected.ok()).toBe(false);
  await hydrate(page, BLOCKED_CASE, "advisor", nextAdvisorCsrf);
  await page.goto("/demo");
  await expect(page.locator(".advisor-workspace-shell")).toHaveAttribute("data-proof-segment", "connected_same_case");
  await expect(page.locator(".workspace-context-bar")).toContainText(/同一 Case 的连接证明|Connected same-Case proof/);
  await expect(page.getByRole("heading", { name: copy.blocked })).toBeVisible();
  await expect(page.getByRole("link", { name: copy.safeExit })).toBeVisible();
  await expect(
    page.getByRole("button", { name: copy.approve }),
  ).toHaveCount(0);
  await capture(page, "blocked");
  const comparison = blockedLedger.comparison as Json;
  expect(comparison.current_run_state).toBe("blocked");
  expect(comparison.approval_eligible).toBe(false);
  return {
    case_id: BLOCKED_CASE,
    request_review_id: String(requested.result.review_id),
    predecessor_run_id: predecessor,
    task_id: String(task.task_id),
    current_run_id: String(
      (blockedLedger.planning_run as Json).planning_run_id,
    ),
  };
}

test(
  "planning-revision.spec.ts proves revision recovery, restart, comparison, and blocked counterfactual",
  async ({ page }) => {
    test.setTimeout(300_000);
    test.skip(
      !proofFile ||
        !workerReadyFile ||
        !initialSentinel ||
        !restartSentinel ||
        !reviewRoot,
      "runs only in the isolated planning revision Compose lane",
    );
    await page.goto("/");
    if (locale === "en") {
      await page.evaluate(() => {
        localStorage.setItem("night-voyager:presentation-locale:v1", "en");
      });
    }
    let csrf = await mint(page, "advisor");
    await hydrate(page, HAPPY_CASE, "advisor", csrf);
    await page.goto("/demo");
    await expect(page.locator(".advisor-workspace-shell")).toHaveAttribute("data-proof-segment", "connected_same_case");
    await expect(page.locator(".workspace-context-bar")).toContainText(/同一 Case 的连接证明|Connected same-Case proof/);
    const initialLedger = await read(
      page,
      `/api/demo/cases/${HAPPY_CASE}/advisor-ledger`,
    );
    const predecessor = String(
      (initialLedger.planning_run as Json).planning_run_id,
    );

    const reviewLost = await lostAck(
      page,
      `/api/demo/cases/${HAPPY_CASE}/advisor-reviews`,
      "request-revision",
      async () => {
        await page.getByRole("button", { name: copy.requestRevision }).click();
      },
    );
    await expect(
      page.getByRole("button", { name: copy.continueStudent }),
    ).toBeVisible();
    await page.getByRole("button", { name: copy.continueStudent }).click();
    csrf = String(
      await page.evaluate(() => {
        const value = JSON.parse(
          sessionStorage.getItem("night-voyager:m5") ?? "{}",
        );
        return value.csrf;
      }),
    );
    await page.getByRole("button", { name: copy.submitProposal }).click();
    await page.getByRole("button", { name: copy.continueAdvisor }).click();
    csrf = String(
      await page.evaluate(() => {
        const value = JSON.parse(
          sessionStorage.getItem("night-voyager:m5") ?? "{}",
        );
        return value.csrf;
      }),
    );

    await lostAck(
      page,
      `/api/demo/memory-candidates/.*/verification-decisions`,
      "fact-confirmation",
      async () => {
        await page.getByRole("button", { name: copy.confirmFact }).click();
      },
    );
    const eventRequest = page.waitForRequest(
      (request) => request.url().includes("events?after=0"),
    );
    const taskLost = await lostAck(
      page,
      `/api/demo/cases/${HAPPY_CASE}/agent-tasks`,
      "create-task",
      async () => {
        await page.getByRole("button", { name: copy.createTask }).click();
      },
    );
    await eventRequest;
    await writeFile(workerReadyFile!, `${initialSentinel}\n`, {
      encoding: "utf8",
      mode: 0o600,
    });
    const taskId = String(taskLost.response.task_id);
    await expect.poll(async () => {
      const task = await read(page, `/api/demo/tasks/${taskId}`);
      return task.attempt_count;
    }, { timeout: 90_000 }).toBe(1);
    await writeFile(
      workerReadyFile!,
      `${initialSentinel}\n${restartSentinel}\n`,
      { encoding: "utf8", mode: 0o600 },
    );
    await page.waitForFunction(() => {
      const value = JSON.parse(
        sessionStorage.getItem("night-voyager:m5") ?? "{}",
      );
      return Number(value.cursor) > 0;
    });
    const cursorBeforeReload = Number(
      await page.evaluate(() => {
        const value = JSON.parse(
          sessionStorage.getItem("night-voyager:m5") ?? "{}",
        );
        return value.cursor;
      }),
    );
    await page.reload();
    await expect.poll(async () => {
      const status = await read(
        page,
        `/api/demo/cases/${HAPPY_CASE}/journey-status`,
      );
      return status.phase;
    }, { timeout: 150_000 }).toBe("revision_review_required");
    await page.reload();
    await expect(
      page.getByRole("heading", { name: copy.comparison }),
    ).toBeVisible();
    const finalLedger = await read(
      page,
      `/api/demo/cases/${HAPPY_CASE}/advisor-ledger`,
    );
    const comparison = finalLedger.comparison as Json;
    expect((comparison.changed_fact as Json).previous_value).toEqual([
      "australia",
      "japan",
      "malaysia",
    ]);
    expect((comparison.changed_fact as Json).current_value).toEqual([
      "australia",
      "japan",
    ]);
    const malaysia = (comparison.countries as Json[]).find(
      (country) => country.country === "malaysia",
    );
    expect(malaysia?.delta).toBe("removed");
    expect(
      await page.evaluate(() => {
        const value = JSON.parse(
          sessionStorage.getItem("night-voyager:m5") ?? "{}",
        );
        return Number(value.cursor);
      }),
    ).toBeGreaterThanOrEqual(cursorBeforeReload);
    await capture(page, "happy");

    await page.getByRole("button", { name: copy.approve }).click();
    await page.getByRole("button", { name: copy.continueParent }).click();
    await expect(
      page.getByRole("heading", { name: copy.familyBrief }),
    ).toBeVisible();
    const brief = await read(
      page,
      `/api/demo/cases/${HAPPY_CASE}/current-decision-brief`,
    );
    expect(
      (brief.revision_context as Json).advisor_authorization,
    ).toBe("renewed_for_current_revision");
    const decisionPath =
      `/api/demo/decision-briefs/${String(brief.brief_id)}/family-decisions`;
    const decisionResponsePromise = page.waitForResponse((response) => {
      const request = response.request();
      return (
        request.method() === "POST" &&
        new URL(response.url()).pathname === decisionPath
      );
    });
    await page.getByRole("checkbox").check();
    await page.getByRole("button", { name: copy.continueDecision }).click();
    const decisionResponse = await decisionResponsePromise;
    const decisionStatus = decisionResponse.status();
    const decisionBody = (await decisionResponse.text())
      .replace(/\s+/g, " ")
      .slice(0, 1_000);
    if (decisionStatus < 200 || decisionStatus >= 300) {
      throw new Error(
        `family-decision HTTP boundary status=${decisionStatus} body=${decisionBody}`,
      );
    }
    let durablePhase = "";
    try {
      await expect.poll(async () => {
        const status = await read(
          page,
          `/api/demo/cases/${HAPPY_CASE}/journey-status`,
        );
        durablePhase = String(status.phase);
        return durablePhase;
      }).toBe("plan_ready");
    } catch (error) {
      throw new Error(
        `family-decision server/read-model boundary status=${decisionStatus} ` +
        `body=${decisionBody} durable_phase=${durablePhase}`,
        { cause: error },
      );
    }
    try {
      await expect(
        page.getByRole("heading", { name: copy.receipt }),
      ).toBeVisible();
      await expect(
        page.getByRole("heading", { name: copy.timeline }),
      ).toBeVisible();
    } catch (error) {
      throw new Error(
        `family-decision frontend state recovery defect status=${decisionStatus} ` +
        `body=${decisionBody} durable_phase=${durablePhase}`,
        { cause: error },
      );
    }
    console.log(
      `family-decision authority status=${decisionStatus} ` +
      `durable_phase=${durablePhase} receipt=visible timeline=visible`,
    );

    const happy: FlowProof = {
      case_id: HAPPY_CASE,
      request_review_id: String(reviewLost.response.review_id),
      predecessor_run_id: predecessor,
      task_id: taskId,
      current_run_id: String(
        (finalLedger.planning_run as Json).planning_run_id,
      ),
    };
    csrf = String(
      await page.evaluate(() => {
        const value = JSON.parse(
          sessionStorage.getItem("night-voyager:m5") ?? "{}",
        );
        return value.csrf;
      }),
    );
    csrf = await rotate(page, csrf, "advisor");
    const blocked = await blockedFlow(page, csrf);
    await writeFile(
      proofFile!,
      `${JSON.stringify({ schema_version: 1, locale, happy, blocked })}\n`,
      { encoding: "utf8", mode: 0o600 },
    );
  },
);
