import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { isDeepStrictEqual } from "node:util";
import { expect, test, type Page, type Response } from "@playwright/test";
import { parseMemoryCandidateVerification } from "../lib/collaboration-demo/contracts";
import type { AdvisorLedger, CurrentDecisionBrief } from "../lib/connected-demo/contracts";
import { intakeFactControl } from "./intake-locators";
import { intakeCandidateForConfirmation, intakeProposalReplay } from "./intake-readback";

const root = process.env.CONTROLLED_INTAKE_REVIEW_ROOT;
const origin = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3000";
const caseId = "49000000-0000-0000-0000-000000000003";
const defaultCase = "40000000-0000-0000-0000-000000000002";
const pack = "50000000-0000-0000-0000-000000000017";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const confirmationReason = "确认学生提出的合成入学月份变更，费用依据独立资料包。";
type Json = Record<string, unknown>;

async function read<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(path, { timeout: 10_000 }).catch(() => {
    throw new Error(`GET ${path} failed within the 10-second request bound`);
  });
  expect(response.ok(), `GET ${path}: ${response.status()}`).toBe(true);
  return await response.json() as T;
}

function mutation(page: Page, path: string | RegExp) {
  return page.waitForResponse(response => {
    const actual = new URL(response.url()).pathname;
    return response.request().method() === "POST" && (typeof path === "string" ? actual === path : path.test(actual));
  }, { timeout: 15_000 });
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
    await panel.screenshot({ path: `${root}/${state}-${width}.png`, timeout: 10_000 });
    await writeFile(`${root}/${state}-${width}.json`, JSON.stringify(geometry));
  }
}

async function replay(page: Page, response: Response): Promise<Json> {
  const request = response.request();
  const headers = await request.allHeaders();
  expect(Boolean(headers["x-csrf-token"] && headers["idempotency-key"])).toBe(true);
  const path = new URL(request.url()).pathname;
  const result = await page.request.post(path, {
    headers: { Origin: origin, "X-CSRF-Token": headers["x-csrf-token"], "Idempotency-Key": headers["idempotency-key"] },
    data: request.postDataJSON(),
    timeout: 10_000,
  }).catch(() => {
    // APIRequestContext errors can include headers; persist only this bounded summary.
    throw new Error(`POST replay ${path} failed within the 10-second request bound`);
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
  let currentStage = "initialization";
  const enterStage = async (stage: string) => {
    currentStage = stage;
    await writeFile(`${root}/current-stage.json`, JSON.stringify({ stage, state: "entered" }));
  };
  const observe = async (response: Response, expected: Json) => {
    expect(response.ok()).toBe(true);
    const request = response.request();
    expect(request.postDataJSON()).toMatchObject(expected);
    const headers = await request.allHeaders();
    expect(Boolean(headers["idempotency-key"])).toBe(true);
    events.push({ path: new URL(request.url()).pathname, status: response.status(), body: request.postDataJSON(), idempotency_sha256: createHash("sha256").update(headers["idempotency-key"] ?? "").digest("hex") });
    return await response.json() as Json;
  };
  const ledger = () => read<AdvisorLedger>(page, `/api/demo/cases/${caseId}/advisor-ledger`);

  try {
    await enterStage("ordinary-journey-start");
    await page.goto("/");
    await page.evaluate(() => localStorage.setItem("night-voyager:presentation-locale:v1", "zh-CN"));
    await page.goto("/demo");
    await expect(page.getByRole("button", { name: "开始顾问流程", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "开始顾问流程", exact: true }).click();
    await expect.poll(async () => (await envelope(page)).caseId).toBe(defaultCase);
    await expect(page.getByRole("button", { name: "创建规划任务", exact: true })).toBeVisible();
    const saved = await envelope(page);
    const prior = await read<AdvisorLedger>(page, `/api/demo/cases/${defaultCase}/advisor-ledger`);
    await enterStage("active-journey-protection");
    await page.goto("/demo?scenario=intake-delay");
    await expect(page.getByRole("heading", { name: "另一个演示流程正在进行", exact: true })).toBeVisible();
    expect(isDeepStrictEqual(await envelope(page), saved), "saved journey envelope changed").toBe(true);
    expect(await read<AdvisorLedger>(page, `/api/demo/cases/${defaultCase}/advisor-ledger`)).toEqual(prior);
    stages.push("existing-journey-not-overwritten");
    await enterStage("controlled-case-start");
    await page.getByRole("button", { name: "结束当前流程并继续", exact: true }).click();
    await page.getByRole("button", { name: "开始顾问流程", exact: true }).click();
    await expect.poll(async () => (await envelope(page)).caseId).toBe(caseId);
    const initial = await ledger();
    expect(initial).toMatchObject({ schema_version: 3, case_revision: 1, case_intake: "2027-02", phase: "review_required" });
    expect(initial.planning_run?.source_pack_id).not.toBe(pack);
    stages.push("explicit-controlled-start");

    await enterStage("request-revision-and-db-checkpoint");
    const requested = mutation(page, `/api/demo/cases/${caseId}/advisor-reviews`);
    await page.getByRole("button", { name: "请求修订", exact: true }).click();
    const oldReview = await observe(await requested, { action: "request_revision", expected_case_revision: 1 });
    expect(oldReview.review_id).toMatch(uuid);
    await checkpointReview();
    await enterStage("student-intake-editor");
    await page.getByRole("button", { name: "以学生身份继续", exact: true }).click();
    await expect.poll(async () => (await envelope(page)).role).toBe("student");
    await intakeFactControl(page).selectOption("student.intake");
    await page.getByLabel("新入学月份", { exact: true }).fill("2028-02");
    await capture(page, "student-intake", ".revision-fact-editor");
    await enterStage("student-proposal-replay");
    const proposed = mutation(page, /^\/api\/demo\/messages\/[0-9a-f-]{36}\/memory-candidates$/);
    await page.getByRole("button", { name: "提交变更提案", exact: true }).click();
    const proposal = await proposed;
    const participant = await observe(proposal, { schema_version: 1, case_revision: 1, proposal: { schema_version: 1, fact_key: "student.intake", value: "2028-02" } });
    const replayed = await replay(page, proposal);
    const candidate = intakeProposalReplay(participant, replayed);
    await enterStage("pending-proposal-reload");
    await page.reload();
    const restored = await envelope(page);
    expect({ caseId: restored.caseId, role: restored.role, revisionIntent: restored.revisionIntent })
      .toEqual({ caseId, role: "student", revisionIntent: { expectedCaseRevision: 1, factKey: "student.intake", value: "2028-02" } });
    stages.push("student-proposal-replayed-and-reloaded");
    await enterStage("advisor-handoff-and-confirmation");
    await page.getByRole("button", { name: "以顾问身份继续", exact: true }).click();
    await expect.poll(async () => (await envelope(page)).role).toBe("advisor");
    const persistedCandidate = intakeCandidateForConfirmation(await read<unknown>(page, `/api/demo/cases/${caseId}/memory-candidates`), candidate);
    await page.getByLabel("确认理由", { exact: true }).fill(confirmationReason);
    const confirmed = mutation(page, `/api/demo/memory-candidates/${persistedCandidate.candidate_id}/verification-decisions`);
    await page.getByRole("button", { name: "确认事实变更", exact: true }).click();
    const verification = parseMemoryCandidateVerification(await observe(await confirmed, { schema_version: 1, expected_case_revision: 1, decision: "confirm", reason: confirmationReason }));
    expect(verification).toMatchObject({ candidate_id: persistedCandidate.candidate_id, decision: "confirm", result_revision: 2 });
    await expect.poll(async () => (await ledger()).phase).toBe("replan_required");
    const ready = await ledger();
    expect(ready.canonical_task_inputs).toEqual({ schema_version: 1, case_id: caseId, operation: "generate_planning_run_v1", expected_case_revision: 2, source_pack_id: pack, source_pack_version: 1, policy_version: "m3a-policy-v1" });
    await enterStage("canonical-replanning-task");
    await page.reload();
    const created = mutation(page, `/api/demo/cases/${caseId}/agent-tasks`);
    await page.getByRole("button", { name: "创建修订规划任务", exact: true }).click();
    const task = await observe(await created, { schema_version: 1, operation: "generate_planning_run_v1", expected_case_revision: 2, source_pack_id: pack, source_pack_version: 1, policy_version: "m3a-policy-v1" });
    expect(task.task_id).toMatch(uuid);
    await enterStage("successor-worker-wait");
    await expect.poll(async () => (await ledger()).phase, { timeout: 60_000 }).toBe("revision_review_required");
    await page.reload();
    await enterStage("fresh-review-comparison");
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
    await enterStage("english-comparison");
    await page.evaluate(() => localStorage.setItem("night-voyager:presentation-locale:v1", "en"));
    await page.reload();
    await expect(page.getByRole("button", { name: "Approve revised plan", exact: true })).toBeVisible();
    await expect(page.locator(".revision-comparison")).toContainText("2028-02");
    await capture(page, "fresh-review-en", ".revision-comparison");
    await page.evaluate(() => localStorage.setItem("night-voyager:presentation-locale:v1", "zh-CN"));
    await page.reload();
    stages.push("actual-worker-pack-cost-and-frozen-review");

    await enterStage("fresh-advisor-approval");
    expect(revised.review_inputs?.eligible_route_ids).toEqual([revised.routes.find(route => route.country === "australia")?.route_id]);
    const approved = mutation(page, `/api/demo/cases/${caseId}/advisor-reviews`);
    await page.getByRole("button", { name: "批准修订计划", exact: true }).click();
    await observe(await approved, { schema_version: 1, expected_case_revision: 2, action: "approve_for_consultation", planning_run_id: revised.planning_run?.planning_run_id, eligible_route_ids: revised.review_inputs?.eligible_route_ids });
    await page.getByRole("button", { name: "以家长身份继续", exact: true }).click();
    await expect.poll(async () => (await envelope(page)).role).toBe("parent");
    await enterStage("parent-explicit-consent");
    const brief = await read<CurrentDecisionBrief>(page, `/api/demo/cases/${caseId}/current-decision-brief`);
    expect(brief).toMatchObject({ phase: "family_review", family_safe_projection: { intake: "2028-02" }, decision_requirements: { eligible_route_id: revised.routes.find(route => route.country === "australia")?.route_id, pinned_cost_minor: 32_640_000, currency: "CNY", required_trade_offs: ["budget_elasticity"] } });
    await page.getByLabel(/接受预算下限（元）/).fill("320000");
    await page.getByLabel(/接受预算上限（元）/).fill("360000");
    const decide = page.getByRole("button", { name: "继续家庭决定", exact: true });
    await expect(decide).toBeDisabled();
    await page.getByRole("checkbox", { name: /我接受：预算弹性/ }).check();
    await expect(decide).toBeDisabled();
    await page.getByRole("checkbox", { name: /我以家长身份确认/ }).check();
    await capture(page, "parent-consent", ".family-decision-action");
    const decided = mutation(page, `/api/demo/decision-briefs/${brief.brief_id}/family-decisions`);
    await decide.click();
    await observe(await decided, { schema_version: 1, expected_brief_version: brief.brief_version, selected_route_id: brief.decision_requirements.eligible_route_id, currency: "CNY", accepted_budget_min_minor: 32_000_000, accepted_budget_max_minor: 36_000_000, accepted_trade_offs: ["budget_elasticity"] });
    await enterStage("family-receipt-timeline");
    await expect(page.getByRole("heading", { name: "家庭决定回执", exact: true })).toBeVisible();
    const final = await read<CurrentDecisionBrief>(page, `/api/demo/cases/${caseId}/current-decision-brief`);
    expect(final.receipt).toMatchObject({ accepted_budget_min_minor: 32_000_000, accepted_budget_max_minor: 36_000_000, accepted_trade_offs: ["budget_elasticity"], source: "direct", decision_made_by_actor_id: "20000000-0000-0000-0000-000000000003", recorded_by_actor_id: "20000000-0000-0000-0000-000000000003" });
    expect(final.timeline).toMatchObject({ country: "australia", intake: "2028-02" });
    expect(final.timeline?.milestones.map(milestone => milestone.due_date)).toEqual(["2027-09-01", "2027-10-15", "2027-12-15", "2028-01-20"]);
    await enterStage("receipt-reload");
    await page.reload();
    await expect(page.getByRole("heading", { name: "家庭决定回执", exact: true })).toBeVisible();
    const reloaded = await read<CurrentDecisionBrief>(page, `/api/demo/cases/${caseId}/current-decision-brief`);
    expect(reloaded.receipt).toEqual(final.receipt);
    expect(reloaded.timeline).toEqual(final.timeline);
    await capture(page, "receipt", ".decided-frame");
    stages.push("direct-parent-receipt-timeline-and-reload");
    await writeFile(`${root}/browser-readback.json`, JSON.stringify({ case_id: caseId, initial, old_request_review: oldReview, revised, receipt: final.receipt, timeline: final.timeline, candidate_replay_same_participant_projection: true, confirmed_candidate_id: persistedCandidate.candidate_id }, null, 2));
    await enterStage("complete");
  } finally {
    await writeFile(`${root}/current-stage.json`, JSON.stringify({ stage: currentStage, state: currentStage === "complete" ? "completed" : "stopped" }));
    await writeFile(`${root}/browser-mutations.json`, JSON.stringify({ current_stage: currentStage, stages, events }, null, 2));
  }
});
