import { writeFile } from "node:fs/promises";
import { expect, test, type Page, type Response } from "@playwright/test";

const proofFile = process.env.PLAN_EXECUTION_PROOF_FILE;
const scenario = process.env.PLAN_EXECUTION_SCENARIO;
const locale = process.env.PRESENTATION_LOCALE === "en" ? "en" : "zh-CN";

type Receipt = {
  receipt_id: string;
  result_id: string;
  execution_id: string;
  checkpoint_id: string | null;
};

type View = {
  execution: { execution_id: string; state: string };
  checkpoints: { checkpoint_id: string; milestone_key: string }[];
  current_checkpoint: { checkpoint_id: string; milestone_key: string } | null;
  reassessment: { reassessment_id: string } | null;
};

const copy = {
  "zh-CN": {
    student: "学生", parent: "家长", advisor: "顾问",
    start: "开始执行行动计划", progress: "记录进行中",
    completion: "提交完成状态给顾问", requestUpdate: "请求更新",
    verify: "验证并继续", blocked: "记录阻塞并停止当前 checkpoint",
    reassess: "请求重新评估并停止执行", recover: "重新验证执行 authority",
    completed: "行动计划已完成。", handoff: "重新评估交接",
  },
  en: {
    student: "Student", parent: "Parent", advisor: "Advisor",
    start: "Start the action plan", progress: "Record progress",
    completion: "Submit completion to advisor", requestUpdate: "Request update",
    verify: "Verify and continue", blocked: "Record blocked and stop this checkpoint",
    reassess: "Request reassessment and stop execution", recover: "Revalidate execution authority",
    completed: "The action plan is complete.", handoff: "Reassessment handoff",
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

async function rotate(page: Page, role: keyof typeof copy.en) {
  const button = page.getByRole("button", { name: copy[locale][role], exact: true });
  await button.click();
  await expect(button).toHaveAttribute("aria-pressed", "true");
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

  await page.goto(`/demo/plan?scenario=${scenario}`);
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
  await expect(page.getByText(labels.completed, { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByText(labels.completed, { exact: true })).toBeVisible();
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
