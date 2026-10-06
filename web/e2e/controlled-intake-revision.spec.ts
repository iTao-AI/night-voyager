import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { expect, test, type Page, type Response } from "@playwright/test";
import type { AdvisorLedger, CurrentDecisionBrief } from "../lib/connected-demo/contracts";

const root = process.env.CONTROLLED_INTAKE_REVIEW_ROOT;
const origin = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3000";
const caseId = "49000000-0000-0000-0000-000000000003";
const defaultCase = "40000000-0000-0000-0000-000000000002";
const pack = "50000000-0000-0000-0000-000000000017";
type Json = Record<string, unknown>;

async function read<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(path);
  expect(response.ok(), `GET ${path}: ${response.status()}`).toBe(true);
  return await response.json() as T;
}

function mutation(page: Page, suffix: string) {
  return page.waitForResponse(response => response.request().method() === "POST" && new URL(response.url()).pathname.endsWith(suffix));
}

async function envelope(page: Page): Promise<Json> {
  return await page.evaluate(() => JSON.parse(sessionStorage.getItem("night-voyager:m5") ?? "{}") as Record<string, unknown>);
}

async function capture(page: Page, state: string, selector = "#demo-main") {
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${state}/${width}: overflow`).toBe(true);
    const panel = page.locator(selector).first();
    await expect(panel).toBeVisible();
    const geometry = await panel.evaluate(element => {
      const rect = element.getBoundingClientRect();
      return { left: rect.left, right: rect.right, width: rect.width, viewport: innerWidth };
    });
    expect(geometry.left).toBeGreaterThanOrEqual(-1);
    expect(geometry.right).toBeLessThanOrEqual(width + 1);
    await panel.screenshot({ path: `${root}/${state}-${width}.png` });
    await writeFile(`${root}/${state}-${width}.json`, JSON.stringify(geometry));
  }
}

async function replay(page: Page, response: Response): Promise<Json> {
  const request = response.request();
  const headers = await request.allHeaders();
  const result = await page.request.post(new URL(request.url()).pathname, {
    headers: { Origin: origin, "X-CSRF-Token": headers["x-csrf-token"], "Idempotency-Key": headers["idempotency-key"] },
    data: request.postDataJSON(),
  });
  expect(result.ok(), `replay: ${result.status()}`).toBe(true);
  return await result.json() as Json;
}

async function checkpointReview() {
  await writeFile(`${root}/db-checkpoint.json`, JSON.stringify({ stage: "review-requested" }));
  await expect.poll(async () => {
    try { return (await readFile(`${root}/review-requested.ack`, "utf8")).trim(); }
    catch { return ""; }
  }, { timeout: 45_000 }).toBe("review-requested");
}

test("controlled intake preserves the active journey and reaches a real parent receipt", async ({ page }) => {
  test.skip(!root, "requires the authorized isolated intake native lane");
  await mkdir(root!, { recursive: true });
  const events: Json[] = [];
  const stages: string[] = [];
  const observe = async (response: Response, expected: Json) => {
    expect(response.ok()).toBe(true);
    const request = response.request();
    expect(request.postDataJSON()).toMatchObject(expected);
    const headers = await request.allHeaders();
    events.push({ path: new URL(request.url()).pathname, status: response.status(), body: request.postDataJSON(), idempotency_sha256: createHash("sha256").update(headers["idempotency-key"] ?? "").digest("hex") });
    return await response.json() as Json;
  };
  const ledger = () => read<AdvisorLedger>(page, `/api/demo/cases/${caseId}/advisor-ledger`);

  try {
    await page.goto("/");
    await page.evaluate(() => localStorage.setItem("night-voyager:presentation-locale:v1", "zh-CN"));
    await page.goto("/demo");
    await expect(page.getByRole("button", { name: "开始顾问流程", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "开始顾问流程", exact: true }).click();
    await expect.poll(async () => (await envelope(page)).caseId).toBe(defaultCase);
    await expect(page.getByRole("button", { name: "创建规划任务", exact: true })).toBeVisible();
    const saved = await envelope(page);
    const prior = await read<AdvisorLedger>(page, `/api/demo/cases/${defaultCase}/advisor-ledger`);
    await page.goto("/demo?scenario=intake-delay");
    await expect(page.getByRole("heading", { name: "另一个演示流程正在进行", exact: true })).toBeVisible();
    expect(await envelope(page)).toEqual(saved);
    expect(await read<AdvisorLedger>(page, `/api/demo/cases/${defaultCase}/advisor-ledger`)).toEqual(prior);
    stages.push("existing-journey-not-overwritten");
    await page.getByRole("button", { name: "结束当前流程并继续", exact: true }).click();
    await page.getByRole("button", { name: "开始顾问流程", exact: true }).click();
    await expect.poll(async () => (await envelope(page)).caseId).toBe(caseId);
    const initial = await ledger();
    expect(initial).toMatchObject({ schema_version: 3, case_revision: 1, case_intake: "2027-02", phase: "review_required" });
    expect(initial.planning_run?.source_pack_id).not.toBe(pack);
    stages.push("explicit-controlled-start");

    const requested = mutation(page, "/advisor-reviews");
    await page.getByRole("button", { name: "请求修订", exact: true }).click();
    const oldReview = await observe(await requested, { action: "request_revision", expected_case_revision: 1 });
    await checkpointReview();
    await page.getByRole("button", { name: "以学生身份继续", exact: true }).click();
    await expect.poll(async () => (await envelope(page)).role).toBe("student");
    await page.getByLabel("要修改的事实", { exact: true }).selectOption("student.intake");
    await page.getByLabel("新入学月份", { exact: true }).fill("2028-02");
    await capture(page, "student-intake", ".revision-fact-editor");
    const proposed = mutation(page, "/memory-candidates");
    await page.getByRole("button", { name: "提交变更提案", exact: true }).click();
    const proposal = await proposed;
    const candidate = await observe(proposal, { case_revision: 1, proposal: { fact_key: "student.intake", value: "2028-02" } });
    const replayed = await replay(page, proposal);
    expect(replayed.candidate_id).toBe(candidate.candidate_id);
    await page.reload();
    expect(await envelope(page)).toMatchObject({ caseId, role: "student", revisionIntent: { factKey: "student.intake", value: "2028-02" } });
    stages.push("student-proposal-replayed-and-reloaded");
    await page.getByRole("button", { name: "以顾问身份继续", exact: true }).click();
    await expect.poll(async () => (await envelope(page)).role).toBe("advisor");
    await page.getByLabel("确认理由", { exact: true }).fill("确认学生提出的合成入学月份变更，费用依据独立资料包。");
    const confirmed = mutation(page, "/verification-decisions");
    await page.getByRole("button", { name: "确认事实变更", exact: true }).click();
    await observe(await confirmed, { expected_case_revision: 1, decision: "confirm" });
    await expect.poll(async () => (await ledger()).phase).toBe("replan_required");
    const ready = await ledger();
    expect(ready.canonical_task_inputs).toMatchObject({ expected_case_revision: 2, source_pack_id: pack, source_pack_version: 1 });
    await page.reload();
    const created = mutation(page, "/agent-tasks");
    await page.getByRole("button", { name: "创建修订规划任务", exact: true }).click();
    const task = await observe(await created, { expected_case_revision: 2, source_pack_id: pack, source_pack_version: 1 });
    await expect.poll(async () => (await ledger()).phase, { timeout: 60_000 }).toBe("revision_review_required");
    await page.reload();
    const revised = await ledger();
    expect(revised.task?.task_id).toBe(task.task_id);
    expect(revised).toMatchObject({ case_revision: 2, case_intake: "2028-02" });
    expect(revised.planning_run).toMatchObject({ source_pack_id: pack, source_pack_version: 1 });
    expect(revised.routes.find(route => route.country === "australia")?.cost).toMatchObject({ intake: "2028-02", cny_total_minor: 32_640_000, fx_date: "2026-07-01" });
    expect(revised.comparison?.changed_fact).toEqual({ fact_key: "student.intake", previous_value: "2027-02", current_value: "2028-02" });
    expect(revised.comparison?.countries.every(country => country.delta === "unchanged")).toBe(true);
    expect(revised.comparison?.previous_request_review).toMatchObject({ review_id: oldReview.review_id, case_revision: 1, action: "request_revision" });
    await expect(page.locator(".changed-fact-summary").filter({ hasText: "326,400" })).toContainText("2028-02");
    await capture(page, "actual-cost-zh", '.changed-fact-summary:has-text("326,400")');
    await capture(page, "fresh-review-zh", ".revision-comparison");
    await page.evaluate(() => localStorage.setItem("night-voyager:presentation-locale:v1", "en"));
    await page.reload();
    await expect(page.getByRole("button", { name: "Approve revised plan", exact: true })).toBeVisible();
    await expect(page.locator(".revision-comparison")).toContainText("2028-02");
    await capture(page, "fresh-review-en", ".revision-comparison");
    await page.evaluate(() => localStorage.setItem("night-voyager:presentation-locale:v1", "zh-CN"));
    await page.reload();
    stages.push("actual-worker-pack-cost-and-frozen-review");

    const approved = mutation(page, "/advisor-reviews");
    await page.getByRole("button", { name: "批准修订计划", exact: true }).click();
    await observe(await approved, { expected_case_revision: 2, action: "approve_for_consultation", planning_run_id: revised.planning_run?.planning_run_id });
    await page.getByRole("button", { name: "以家长身份继续", exact: true }).click();
    await expect.poll(async () => (await envelope(page)).role).toBe("parent");
    await page.getByLabel(/接受预算下限（元）/).fill("320000");
    await page.getByLabel(/接受预算上限（元）/).fill("360000");
    const decide = page.getByRole("button", { name: "继续家庭决定", exact: true });
    await expect(decide).toBeDisabled();
    await page.getByRole("checkbox", { name: /我接受：预算弹性/ }).check();
    await expect(decide).toBeDisabled();
    await page.getByRole("checkbox", { name: /我以家长身份确认/ }).check();
    await capture(page, "parent-consent", ".family-decision-action");
    const decided = mutation(page, "/family-decisions");
    await decide.click();
    await observe(await decided, { accepted_budget_min_minor: 32_000_000, accepted_budget_max_minor: 36_000_000, accepted_trade_offs: ["budget_elasticity"] });
    await expect(page.getByRole("heading", { name: "家庭决定回执", exact: true })).toBeVisible();
    const final = await read<CurrentDecisionBrief>(page, `/api/demo/cases/${caseId}/current-decision-brief`);
    expect(final.receipt).toMatchObject({ accepted_budget_min_minor: 32_000_000, accepted_budget_max_minor: 36_000_000, accepted_trade_offs: ["budget_elasticity"], source: "direct", decision_made_by_actor_id: "20000000-0000-0000-0000-000000000003", recorded_by_actor_id: "20000000-0000-0000-0000-000000000003" });
    expect(final.timeline?.intake).toBe("2028-02");
    expect(final.timeline?.milestones.map(milestone => milestone.due_date)).toEqual(["2027-09-01", "2027-10-15", "2027-12-15", "2028-01-20"]);
    await page.reload();
    await expect(page.getByRole("heading", { name: "家庭决定回执", exact: true })).toBeVisible();
    expect((await read<CurrentDecisionBrief>(page, `/api/demo/cases/${caseId}/current-decision-brief`)).receipt).toEqual(final.receipt);
    await capture(page, "receipt", ".decided-frame");
    stages.push("direct-parent-receipt-timeline-and-reload");
    await writeFile(`${root}/browser-readback.json`, JSON.stringify({ case_id: caseId, initial, old_request_review: oldReview, revised, receipt: final.receipt, timeline: final.timeline, candidate_replay_same_id: true }, null, 2));
  } finally {
    await writeFile(`${root}/browser-mutations.json`, JSON.stringify({ stages, events }, null, 2));
  }
});
