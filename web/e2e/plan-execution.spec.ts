import { writeFile } from "node:fs/promises";
import {
  expect,
  test,
  type Page,
  type Response,
} from "@playwright/test";

const proofFile = process.env.PLAN_EXECUTION_PROOF_FILE;
const recoveryProofFile = process.env.PLAN_EXECUTION_RECOVERY_PROOF_FILE;
const scenario = process.env.PLAN_EXECUTION_SCENARIO;
const locale = process.env.PRESENTATION_LOCALE === "en" ? "en" : "zh-CN";
const ORIGIN = "http://127.0.0.1:3000";

type Receipt = {
  receipt_id: string;
  result_id: string;
  execution_id: string;
  checkpoint_id: string | null;
};

type View = {
  execution: { execution_id: string; state: string; row_version: number };
  checkpoints: { checkpoint_id: string; milestone_key: string; row_version: number }[];
  current_checkpoint: {
    checkpoint_id: string;
    milestone_key: string;
    row_version: number;
  } | null;
  reassessment: { reassessment_id: string } | null;
  activity: { durable_id: string }[];
  activity_total: number;
};

const copy = {
  "zh-CN": {
    student: "学生", parent: "家长", advisor: "顾问",
    start: "开始执行行动计划", progress: "记录进行中",
    completion: "提交完成状态给顾问", requestUpdate: "请求更新",
    verify: "验证并继续", blocked: "记录阻塞并停止当前 checkpoint",
    reassess: "请求重新评估并停止执行", recover: "重新验证执行 authority",
    completed: "行动计划已完成。", handoff: "重新评估交接", activity: "活动记录",
    currentAction: "当前行动", documents: "材料准备", attestation: "checkpoint 状态证明",
  },
  en: {
    student: "Student", parent: "Parent", advisor: "Advisor",
    start: "Start the action plan", progress: "Record progress",
    completion: "Submit completion to advisor", requestUpdate: "Request update",
    verify: "Verify and continue", blocked: "Record blocker and stop the current checkpoint",
    reassess: "Request reassessment and stop execution", recover: "Revalidate execution authority",
    completed: "The action plan is complete.", handoff: "Reassessment handoff", activity: "Activity",
    currentAction: "Current action", documents: "Documents", attestation: "Checkpoint attestation",
  },
} as const;

async function mutate(
  page: Page,
  buttonName: string,
  path: string,
): Promise<{ receipt: Receipt; view: View }> {
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
    receipt: (await receiptHttp.json()) as Receipt,
    view: (await viewHttp.json()) as View,
  };
}

async function rotate(page: Page, role: keyof typeof copy.en): Promise<string> {
  const sessionResponse = page.waitForResponse(
    (response) => response.request().method() === "POST"
      && response.url().endsWith("/api/demo/sessions"),
  );
  const button = page.getByRole("button", { name: copy[locale][role], exact: true });
  await button.click();
  const response = await sessionResponse;
  expect(response.status()).toBe(201);
  await expect(button).toHaveAttribute("aria-pressed", "true");
  return String((await response.json() as { csrf_token: string }).csrf_token);
}

async function expectLiveAndVisibleCopy(page: Page, message: string) {
  await expect(page.getByRole("status")).toHaveText(message);
  await expect(page.locator(".workspace-status-copy")).toHaveText(message);
}

async function progress(
  page: Page,
  context: { case_id: string },
  view: View,
  csrf: string,
  key: string,
): Promise<View> {
  const checkpoint = view.current_checkpoint;
  expect(checkpoint).not.toBeNull();
  const response = await page.request.post(
    `/api/demo/timeline-executions/${view.execution.execution_id}/checkpoint-attestations`,
    {
      headers: {
        Origin: ORIGIN,
        "Content-Type": "application/json",
        "X-CSRF-Token": csrf,
        "Idempotency-Key": key,
      },
      data: {
        schema_version: 1,
        case_id: context.case_id,
        checkpoint_id: checkpoint!.checkpoint_id,
        expected_execution_version: view.execution.row_version,
        expected_checkpoint_version: checkpoint!.row_version,
        attestation_kind: "progress",
        status_code: "work_in_progress",
        attestation_code: `${checkpoint!.milestone_key}_status_confirmed`,
        reason_code: "not_applicable",
      },
    },
  );
  expect(response.status()).toBe(200);
  const fresh = await page.request.get(
    `/api/demo/cases/${context.case_id}/timeline-execution`,
  );
  expect(fresh.status()).toBe(200);
  return await fresh.json() as View;
}

test("complete governed plan execution browser-to-database proof", async ({ page }) => {
  test.skip(
    !proofFile || !["happy", "blocked"].includes(String(scenario)),
    "runs only in an isolated governed execution proof lane",
  );
  const labels = copy[locale];
  const acceptedReceiptIds: string[] = [];
  const checkpointIds: string[] = [];
  const responseOrder: string[] = [];
  const observe = (response: Response) => {
    if (response.request().method() === "POST") responseOrder.push("receipt");
    if (response.request().method() === "GET"
      && response.url().includes("/timeline-execution")) responseOrder.push("fresh-read");
  };
  page.on("response", observe);

  if (locale === "en") {
    await page.addInitScript(() => {
      localStorage.setItem("night-voyager:presentation-locale:v1", "en");
    });
  }
  await page.goto(`/demo/plan?scenario=${scenario}`);
  await expect(page.locator(".advisor-workspace-shell")).toHaveAttribute(
    "data-proof-segment",
    "independent_execution_scenario",
  );
  await expect(page.locator(".workspace-context-bar")).toContainText(
    /独立的确定性执行场景|Independent deterministic execution scenario/,
  );
  await rotate(page, "student");
  const contextResponse = await page.request.get("/api/demo/plan-execution-context");
  expect(contextResponse.status()).toBe(200);
  const context = await contextResponse.json() as {
    case_id: string; timeline_plan_id: string; execution_id: string | null;
  };
  expect(context.execution_id).toBeNull();

  const started = await mutate(page, labels.start, "/executions");
  acceptedReceiptIds.push(started.receipt.receipt_id);
  expect(started.view.current_checkpoint?.milestone_key).toBe("documents");
  checkpointIds.push(...started.view.checkpoints.map((item) => item.checkpoint_id));
  await expect(page.locator(".plan-execution-hero > h3")).toBeFocused();
  const authoritySummary = page.locator("[data-plan-authority-summary]");
  await expect(authoritySummary).toContainText(labels.documents);
  await expect(authoritySummary).not.toContainText("documents");
  await expect(page.locator(".approved-plan-steps > li")).toHaveCount(4);

  if (scenario === "blocked") {
    const blocked = await mutate(page, labels.blocked, "/checkpoint-attestations");
    acceptedReceiptIds.push(blocked.receipt.receipt_id);
    await rotate(page, "advisor");
    const reassessed = await mutate(page, labels.reassess, "/reassessments");
    acceptedReceiptIds.push(reassessed.receipt.receipt_id);
    expect(reassessed.view.execution.state).toBe("reassessment_required");
    await expect(page.getByRole("heading", { name: labels.handoff })).toBeVisible();
    await expect(page.getByRole("button", { name: labels.verify, exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: labels.completion, exact: true })).toHaveCount(0);
    await expect(page.getByRole("group", { name: labels.attestation })).toHaveCount(0);
    await writeFile(proofFile!, `${JSON.stringify({
      schema_version: 1,
      locale,
      scenario,
      case_id: context.case_id,
      timeline_plan_id: context.timeline_plan_id,
      execution_id: reassessed.receipt.execution_id,
      accepted_receipt_ids: acceptedReceiptIds,
      checkpoint_ids: checkpointIds,
      reassessment_request_id: reassessed.receipt.result_id,
    })}\n`, { encoding: "utf8", mode: 0o600 });
    return;
  }

  let lostReceipt: Receipt | null = null;
  let dropOnce = true;
  await page.route("**/checkpoint-attestations", async (route) => {
    if (!dropOnce) {
      await route.continue();
      return;
    }
    dropOnce = false;
    const upstream = await route.fetch();
    lostReceipt = await upstream.json() as Receipt;
    await route.abort("failed");
  });
  await page.getByRole("button", { name: labels.progress, exact: true }).click();
  await expect(page.getByRole("button", { name: labels.recover, exact: true })).toBeVisible();
  await page.unroute("**/checkpoint-attestations");
  const recoveredResponse = page.waitForResponse(
    (response) => response.request().method() === "POST"
      && response.url().includes("/checkpoint-attestations"),
  );
  await page.getByRole("button", { name: labels.recover, exact: true }).click();
  const recovered = await recoveredResponse;
  expect(recovered.status()).toBe(200);
  expect((await recovered.json() as Receipt).receipt_id).toBe(lostReceipt!.receipt_id);
  acceptedReceiptIds.push(lostReceipt!.receipt_id);

  let completed = await mutate(page, labels.completion, "/checkpoint-attestations");
  acceptedReceiptIds.push(completed.receipt.receipt_id);
  await rotate(page, "advisor");
  const update = await mutate(page, labels.requestUpdate, "/checkpoint-verifications");
  acceptedReceiptIds.push(update.receipt.receipt_id);
  await rotate(page, "student");
  completed = await mutate(page, labels.completion, "/checkpoint-attestations");
  acceptedReceiptIds.push(completed.receipt.receipt_id);
  await rotate(page, "advisor");
  let verified = await mutate(page, labels.verify, "/checkpoint-verifications");
  acceptedReceiptIds.push(verified.receipt.receipt_id);

  for (const [milestone, role] of [
    ["application", "student"],
    ["visa", "student"],
    ["arrival", "parent"],
  ] as const) {
    await rotate(page, role);
    expect(verified.view.current_checkpoint?.milestone_key).toBe(milestone);
    completed = await mutate(page, labels.completion, "/checkpoint-attestations");
    acceptedReceiptIds.push(completed.receipt.receipt_id);
    await rotate(page, "advisor");
    verified = await mutate(page, labels.verify, "/checkpoint-verifications");
    acceptedReceiptIds.push(verified.receipt.receipt_id);
  }
  expect(verified.view.execution.state).toBe("completed");
  await expectLiveAndVisibleCopy(page, labels.completed);
  await page.reload();
  await expectLiveAndVisibleCopy(page, labels.completed);
  expect(responseOrder.indexOf("receipt")).toBeLessThan(responseOrder.lastIndexOf("fresh-read"));
  page.off("response", observe);
  await writeFile(proofFile!, `${JSON.stringify({
    schema_version: 1,
    locale,
    scenario,
    case_id: context.case_id,
    timeline_plan_id: context.timeline_plan_id,
    execution_id: verified.receipt.execution_id,
    accepted_receipt_ids: acceptedReceiptIds,
    checkpoint_ids: checkpointIds,
    reassessment_request_id: null,
  })}\n`, { encoding: "utf8", mode: 0o600 });
});

test("prove stale tab, shared session, envelope, and bounded activity", async ({
  browser,
  page,
}) => {
  test.skip(
    !recoveryProofFile,
    "runs only in the isolated plan execution recovery proof lane",
  );

  await page.goto("/demo/plan?scenario=happy");
  let primaryCsrf = await rotate(page, "student");
  const initialContext = await page.request.get(
    "/api/demo/plan-execution-context",
  );
  expect(initialContext.status()).toBe(200);
  const context = await initialContext.json() as {
    case_id: string;
    timeline_plan_id: string;
    execution_id: string | null;
  };
  expect(context.execution_id).toBeNull();

  const staleContext = await browser.newContext({ baseURL: ORIGIN });
  const stalePage = await staleContext.newPage();
  await stalePage.goto("/demo/plan?scenario=happy");
  await rotate(stalePage, "student");

  const started = await mutate(page, copy["zh-CN"].start, "/executions");
  context.execution_id = started.receipt.execution_id;
  let current = started.view;

  const staleRecoverySession = stalePage.waitForResponse(
    (response) => response.request().method() === "POST"
      && response.url().endsWith("/api/demo/sessions"),
  );
  await stalePage.reload();
  expect((await staleRecoverySession).status()).toBe(201);
  await expect(stalePage.getByRole("button", {
    name: copy["zh-CN"].progress,
    exact: true,
  })).toBeVisible();

  const firstProgress = await mutate(
    page,
    copy["zh-CN"].progress,
    "/checkpoint-attestations",
  );
  current = firstProgress.view;

  // stale second tab: its old row versions are rejected, then it closes to a fresh read.
  const staleRejection = stalePage.waitForResponse(
    (response) => response.request().method() === "POST"
      && response.url().includes("/checkpoint-attestations"),
  );
  await stalePage.getByRole("button", {
    name: copy["zh-CN"].progress,
    exact: true,
  }).click();
  const staleResponse = await staleRejection;
  expect(staleResponse.status()).toBe(409);
  const staleProblem = await staleResponse.json() as { code: string };
  expect(staleProblem.code).toBe("stale_execution_version");
  await expect(stalePage.getByRole("button", {
    name: copy["zh-CN"].progress,
    exact: true,
  })).toBeEnabled();

  for (let index = 0; index < 32; index += 1) {
    current = await progress(
      page,
      context,
      current,
      primaryCsrf,
      `00000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
    );
  }
  expect(current.activity_total).toBe(67);
  expect(current.activity).toHaveLength(64);

  const activityRecoverySession = page.waitForResponse(
    (response) => response.request().method() === "POST"
      && response.url().endsWith("/api/demo/sessions"),
  );
  await page.reload();
  primaryCsrf = String(
    (await (await activityRecoverySession).json() as { csrf_token: string })
      .csrf_token,
  );
  const activity = page.getByRole("heading", {
    name: copy["zh-CN"].activity,
  }).locator("..");
  await activity.locator("summary").click();
  await expect(activity.getByRole("listitem")).toHaveCount(64);
  await expect(activity.getByText("显示 64 / 67", { exact: true })).toBeVisible();
  await expect(activity.getByText(
    "当前仅显示最近 64 条；更早的保留历史不在此视图中。",
    { exact: true },
  )).toBeVisible();

  const blockedContext = await browser.newContext({ baseURL: ORIGIN });
  const blockedPage = await blockedContext.newPage();
  await blockedPage.goto("/demo/plan?scenario=blocked");
  await rotate(blockedPage, "student");
  const blockedAuthority = await blockedPage.request.get(
    "/api/demo/plan-execution-context",
  );
  expect(blockedAuthority.status()).toBe(200);
  const blockedCaseId = String(
    (await blockedAuthority.json() as { case_id: string }).case_id,
  );
  await blockedContext.close();

  let crossCasePosts = 0;
  stalePage.on("request", (request) => {
    if (request.method() === "POST") crossCasePosts += 1;
  });
  await stalePage.evaluate((caseId) => {
    const key = "night-voyager:plan-execution:v1";
    const raw = sessionStorage.getItem(key);
    if (!raw) throw new Error("missing recovery envelope");
    const envelope = JSON.parse(raw) as Record<string, unknown>;
    envelope.caseId = caseId;
    sessionStorage.setItem(key, JSON.stringify(envelope));
  }, blockedCaseId);
  // cross-Case envelope: server context rejects the stored identity with zero mutation.
  await stalePage.reload();
  await expectLiveAndVisibleCopy(
    stalePage,
    "角色或执行 authority 已变化，请重新连接。",
  );
  expect(crossCasePosts).toBe(0);

  let releaseRead!: () => void;
  const readRelease = new Promise<void>((resolve) => {
    releaseRead = resolve;
  });
  let readStarted!: () => void;
  const readInFlight = new Promise<void>((resolve) => {
    readStarted = resolve;
  });
  let holdRead = true;
  await page.route("**/timeline-execution", async (route) => {
    if (!holdRead) {
      await route.continue();
      return;
    }
    holdRead = false;
    const response = await route.fetch();
    readStarted();
    await readRelease;
    await route.fulfill({ response });
  });
  const inFlightSession = page.waitForResponse(
    (response) => response.request().method() === "POST"
      && response.url().endsWith("/api/demo/sessions"),
  );
  const reload = page.reload();
  const refreshed = await inFlightSession;
  primaryCsrf = String(
    (await refreshed.json() as { csrf_token: string }).csrf_token,
  );
  await readInFlight;

  // shared session rotation while read is in flight must close to session_changed.
  const rotation = await page.request.post("/api/demo/sessions", {
    headers: {
      Origin: ORIGIN,
      "Content-Type": "application/json",
      "X-CSRF-Token": primaryCsrf,
    },
    data: { demo_actor: "plan_execution_happy_advisor" },
  });
  expect(rotation.status()).toBe(201);
  releaseRead();
  await reload;
  await page.unroute("**/timeline-execution");
  await expectLiveAndVisibleCopy(
    page,
    "角色或执行 authority 已变化，请重新连接。",
  );

  await staleContext.close();
  await writeFile(recoveryProofFile!, `${JSON.stringify({
    schema_version: 1,
    scenario: "happy",
    case_id: context.case_id,
    timeline_plan_id: context.timeline_plan_id,
    execution_id: context.execution_id,
    stale_rejection_code: staleProblem.code,
    session_changed: true,
    cross_case_zero_mutation: crossCasePosts === 0,
    zero_mutation: true,
    activity_total: 67,
    activity_visible: 64,
  })}\n`, { encoding: "utf8", mode: 0o600 });
});
