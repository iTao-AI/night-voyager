import { readFile, rename, writeFile } from "node:fs/promises";
import { expect, test, type Page } from "@playwright/test";

const root = process.env.CUSTOMER_RECOVERY_REVIEW_ROOT;
const locale = process.env.PRESENTATION_LOCALE === "en" ? "en" : "zh-CN";
const origin = "http://127.0.0.1:3000";
const happy = "49000000-0000-0000-0000-000000000001";
const hard = "49000000-0000-0000-0000-000000000002";
type Json = Record<string, unknown>;
const name = (zh: string, en: string) => locale === "en" ? en : zh;

async function read(page: Page, path: string): Promise<Json> {
  const response = await page.request.get(path);
  expect(response.ok()).toBe(true);
  return await response.json() as Json;
}
async function post(page: Page, path: string, csrf: string, data: unknown): Promise<Json> {
  const response = await page.request.post(path, { headers: { Origin: origin, "X-CSRF-Token": csrf, "Idempotency-Key": crypto.randomUUID() }, data });
  expect(response.ok(), `POST ${path}: ${response.status()} ${await response.text()}`).toBe(true);
  return await response.json() as Json;
}
async function mint(page: Page, role: string): Promise<string> {
  const bootstrap = await read(page, "/api/demo/session-bootstrap");
  const result = await post(page, "/api/demo/sessions", String(bootstrap.csrf_token), { demo_actor: role });
  return String(result.csrf_token);
}
async function rotate(page: Page, csrf: string, role: string) {
  expect((await page.request.delete("/api/demo/session", { headers: { Origin: origin, "X-CSRF-Token": csrf } })).ok()).toBe(true);
  return await mint(page, role);
}
async function csrf(page: Page) {
  return await page.evaluate(() => JSON.parse(sessionStorage.getItem("night-voyager:m5") ?? "{}").csrf as string);
}
async function hydrate(page: Page, caseId: string, token: string) {
  const status = await read(page, `/api/demo/cases/${caseId}/journey-status`);
  const ledger = await read(page, `/api/demo/cases/${caseId}/advisor-ledger`);
  const task = ledger.task as Json | null;
  const run = ledger.planning_run as Json | null;
  const comparison = ledger.comparison as Json | null;
  await page.evaluate((envelope) => sessionStorage.setItem("night-voyager:m5", JSON.stringify(envelope)), {
    schema_version: 3, journey: "advisor-family", role: "advisor", csrf: token, caseId,
    currentRevision: Number(status.current_revision), currentTaskId: task?.task_id ?? null,
    predecessorRunId: comparison?.previous_planning_run_id ?? null,
    currentRunId: run?.planning_run_id ?? null, cursor: 0, phase: status.phase, mutations: {},
  });
}
async function control(stage: string, extra: Json = {}) {
  await writeFile(`${root}/control.pending`, JSON.stringify({ stage, ...extra }));
  await rename(`${root}/control.pending`, `${root}/control.json`);
  await expect.poll(async () => {
    try { return (await readFile(`${root}/ack`, "utf8")).trim(); } catch { return ""; }
  }, { timeout: 90_000 }).toBe(stage);
}
async function capture(page: Page, state: string, selector: string) {
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${state}:${width} overflow`).toBe(true);
    const panel = page.locator(selector).first();
    await expect(panel).toBeVisible();
    const geometry = await panel.evaluate((element) => {
      const r = element.getBoundingClientRect();
      return { left: r.left, right: r.right, width: r.width, height: r.height, viewport: innerWidth };
    });
    expect(geometry.left).toBeGreaterThanOrEqual(-1);
    expect(geometry.right).toBeLessThanOrEqual(width + 1);
    await panel.screenshot({ path: `${root}/customer-${locale}-${width}-${state}-panel.png` });
    await page.screenshot({ path: `${root}/customer-${locale}-${width}-${state}.png`, fullPage: true });
    const controls = await panel.locator("input:not([type=checkbox]), select, textarea, button").evaluateAll((elements) => elements.map((element) => {
      const r = element.getBoundingClientRect();
      return { tag: element.tagName, id: element.id, width: r.width, height: r.height, left: r.left, right: r.right };
    }));
    for (const control of controls) {
      expect(control.left, `${state}:${control.id} left`).toBeGreaterThanOrEqual(-1);
      expect(control.right, `${state}:${control.id} right`).toBeLessThanOrEqual(width + 1);
      expect(control.height, `${state}:${control.id} target height`).toBeGreaterThanOrEqual(44);
    }
    await writeFile(`${root}/customer-${locale}-${width}-${state}-geometry.json`, JSON.stringify({ ...geometry, controls }));
  }
}

test("parent budget revision and native terminal recovery require explicit fresh authority", async ({ page }) => {
  test.skip(!root, "requires the isolated customer recovery runner");
  test.setTimeout(360_000);
  page.setDefaultTimeout(20_000);
  await page.goto("/");
  await page.evaluate((value) => localStorage.setItem("night-voyager:presentation-locale:v1", value), locale);
  let token = await mint(page, "advisor");
  await hydrate(page, happy, token);
  await page.goto("/demo");
  await page.getByRole("button", { name: name("请求修订", "Request revision"), exact: true }).click();
  await page.getByRole("button", { name: name("以学生身份继续", "Continue as student"), exact: true }).click();
  await page.getByLabel(name("要修改的事实", "Fact to change")).selectOption("family.budget");
  const studentFacts = await read(page, `/api/demo/cases/${happy}/confirmed-facts`);
  expect((studentFacts.current as Json[]).some((fact) => fact.fact_key === "family.budget")).toBe(true);
  let injectedParentFactsFailure = false;
  let parentMints = 0;
  let prematureBusinessWrites = 0;
  const recoveryRequests = (request: import("@playwright/test").Request) => {
    if (request.method() !== "POST") return;
    const path = new URL(request.url()).pathname;
    if (path === "/api/demo/sessions") parentMints += 1;
    if (/\/(messages|memory-candidates|verification-decisions|agent-tasks|family-decisions)$/.test(path)) prematureBusinessWrites += 1;
  };
  page.on("request", recoveryRequests);
  const factsPath = `/api/demo/cases/${happy}/confirmed-facts`;
  await page.route(`**${factsPath}`, async (route) => {
    if (!injectedParentFactsFailure) {
      injectedParentFactsFailure = true;
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ code: "temporarily_unavailable" }) });
    } else await route.continue();
  });
  const parentSessionResponse = page.waitForResponse((response) => response.request().method() === "POST" && response.url().endsWith("/api/demo/sessions"));
  await page.getByRole("button", { name: name("以家长编辑预算", "Edit budget as parent"), exact: true }).click();
  const parentSession = await (await parentSessionResponse).json() as Json;
  expect(parentSession.role).toBe("parent");
  await expect.poll(() => injectedParentFactsFailure).toBe(true);
  await expect(page.getByRole("button", { name: name("重新连接顾问流程", "Reconnect advisor flow"), exact: true })).toBeVisible();
  const savedParent = await page.evaluate(() => JSON.parse(sessionStorage.getItem("night-voyager:m5") ?? "{}"));
  expect(savedParent.role).toBe("parent");
  expect(savedParent.csrf).toBe(parentSession.csrf_token);
  expect(savedParent.pendingRole).toBeUndefined();
  expect(savedParent.revisionIntent).toBeUndefined();
  expect(savedParent.mutations["fact-proposal-message"]).toBeUndefined();
  expect(savedParent.mutations["fact-proposal-candidate"]).toBeUndefined();
  expect(prematureBusinessWrites).toBe(0);
  await page.screenshot({ path: `${root}/customer-${locale}-parent-facts-503.png`, fullPage: true });
  const authoritativeParentFacts = page.waitForResponse((response) => response.url().endsWith(factsPath) && response.status() === 200);
  await page.reload();
  const parentFacts = await (await authoritativeParentFacts).json() as Json;
  expect((parentFacts.current as Json[]).some((fact) => fact.fact_key === "family.budget")).toBe(true);
  const recoveredParentStatus = await read(page, `/api/demo/cases/${happy}/journey-status`);
  expect(recoveredParentStatus.active_role).toBe("parent");
  expect(recoveredParentStatus.current_revision).toBe(1);
  await page.getByLabel(name("常规预算", "Preferred budget"), { exact: true }).fill("300000");
  expect(parentMints).toBe(1);
  expect(prematureBusinessWrites).toBe(0);
  page.off("request", recoveryRequests);
  await page.unroute(`**${factsPath}`);
  await page.getByLabel(name("最高预算", "Maximum budget"), { exact: true }).fill("390000");
  await capture(page, "budget-editor", ".revision-fact-editor");
  const proposalResponse = page.waitForResponse((response) => response.request().method() === "POST" && response.url().includes("memory-candidates"));
  await page.getByRole("button", { name: name("以家长提交预算提案", "Submit budget proposal as parent"), exact: true }).click();
  const proposal = await proposalResponse;
  expect(proposal.ok()).toBe(true);
  expect(proposal.request().postDataJSON()).toMatchObject({ proposal: { fact_key: "family.budget", value: { preferred_minor: 30_000_000, hard_ceiling_minor: 39_000_000 } } });
  await page.getByRole("button", { name: name("以顾问身份继续", "Continue as advisor"), exact: true }).click();
  await page.getByLabel(name("确认理由", "Confirmation reason"), { exact: true }).fill("Confirm the parent's changed synthetic budget after checking the proposed interval.");
  await capture(page, "budget-candidate", ".revision-confirmation");
  await page.getByRole("button", { name: name("确认事实变更", "Confirm fact change"), exact: true }).click();
  const sourceResponse = page.waitForResponse((response) => response.request().method() === "POST" && response.url().endsWith(`/cases/${happy}/agent-tasks`));
  await page.getByRole("button", { name: name("创建修订规划任务", "Create revised planning task"), exact: true }).click();
  const source = await (await sourceResponse).json() as Json;
  await control("fail-happy", { task_id: source.task_id });
  await page.reload();
  const retry = page.getByRole("button", { name: name("创建新的规划任务", "Create a fresh planning task"), exact: true });
  await expect(retry).toBeDisabled();
  const consent = page.getByRole("checkbox", { name: /我作为顾问明确同意|As the advisor, I explicitly consent/ });
  await consent.check();
  await capture(page, "retry-consent", ".advisor-ledger-action");
  const retryResponse = page.waitForResponse((response) => response.request().method() === "POST" && response.url().endsWith(`/tasks/${source.task_id}/retry`));
  const stream = page.waitForRequest((request) => request.url().includes("events?after=0"));
  await retry.click();
  const successorResponse = await retryResponse;
  expect(successorResponse.status()).toBe(202);
  expect(successorResponse.request().postDataJSON()).toMatchObject({ schema_version: 1, expected_case_revision: 2 });
  const successor = await successorResponse.json() as Json;
  expect(successor.task_id).not.toBe(source.task_id);
  await stream;
  await control("start-worker", { source_task_id: source.task_id, successor_task_id: successor.task_id });
  await expect.poll(async () => (await read(page, `/api/demo/cases/${happy}/journey-status`)).phase, { timeout: 90_000 }).toBe("revision_review_required");
  await page.reload();
  const ledger = await read(page, `/api/demo/cases/${happy}/advisor-ledger`);
  expect(ledger.current_brief_id).toBeNull();
  expect((ledger.task as Json).task_id).toBe(successor.task_id);
  expect((ledger.comparison as Json).changed_fact).toMatchObject({ fact_key: "family.budget", current_value: { preferred_minor: 30_000_000, hard_ceiling_minor: 39_000_000 } });
  await capture(page, "fresh-review", ".revision-comparison");
  await capture(page, "fresh-review-action", ".advisor-ledger-action");
  await page.getByRole("button", { name: name("批准修订计划", "Approve revised plan"), exact: true }).click();
  await page.getByRole("button", { name: name("以家长身份继续", "Continue as parent"), exact: true }).click();
  await page.getByLabel(/接受预算下限（元）|Accepted budget minimum \(yuan\)/).fill("300000");
  await page.getByLabel(/接受预算上限（元）|Accepted budget maximum \(yuan\)/).fill("360000");
  const familyAction = page.getByRole("button", { name: name("继续家庭决定", "Continue family decision"), exact: true });
  await expect(familyAction).toBeDisabled();
  await page.getByRole("checkbox", { name: /我接受：预算弹性|I accept: Budget flexibility/ }).check();
  await expect(familyAction).toBeDisabled();
  await page.getByRole("checkbox", { name: /我以家长身份确认|As parent, I confirm/ }).check();
  await capture(page, "family-consent", ".family-decision-action");
  const decisionResponse = page.waitForResponse((response) => response.request().method() === "POST" && response.url().includes("/family-decisions"));
  await familyAction.click();
  const decision = await decisionResponse;
  expect(decision.ok()).toBe(true);
  expect(decision.request().postDataJSON()).toMatchObject({ accepted_budget_min_minor: 30_000_000, accepted_budget_max_minor: 36_000_000, accepted_trade_offs: ["budget_elasticity"] });
  await expect(page.getByRole("heading", { name: name("家庭决定回执", "Family Decision Receipt"), exact: true })).toBeVisible();
  const brief = await read(page, `/api/demo/cases/${happy}/current-decision-brief`);
  expect(brief.receipt).toMatchObject({ accepted_budget_min_minor: 30_000_000, accepted_budget_max_minor: 36_000_000, accepted_trade_offs: ["budget_elasticity"], decision_made_by_actor_id: "20000000-0000-0000-0000-000000000003" });
  await capture(page, "receipt", ".decided-frame");
  await control("stop-worker");
  token = await rotate(page, await csrf(page), "advisor");
  const hardLedger = await read(page, `/api/demo/cases/${hard}/advisor-ledger`);
  const inputs = hardLedger.review_inputs as Json;
  await post(page, `/api/demo/cases/${hard}/advisor-reviews`, token, { schema_version: 1, planning_run_id: inputs.planning_run_id, expected_case_revision: 1, action: "request_revision", eligible_route_ids: [], risk_acceptances: [], reviewer_notes: "Synthetic hard-failure negative." });
  const parent = await rotate(page, token, "parent");
  const thread = await read(page, `/api/demo/cases/${hard}/collaboration-thread`);
  const message = await post(page, `/api/demo/collaboration-threads/${thread.thread_id}/messages`, parent, { schema_version: 1, body: "Synthetic parent budget revision for a hard-failure negative." });
  await post(page, `/api/demo/messages/${message.message_event_id}/memory-candidates`, parent, { schema_version: 1, case_revision: 1, proposal: { schema_version: 1, fact_key: "family.budget", value: { schema_version: 1, currency: "CNY", period: "program_total", preferred_minor: 30_000_000, hard_ceiling_minor: 39_000_000, elasticity_bps: 0, refused: false } } });
  token = await rotate(page, parent, "advisor");
  const candidates = await (await page.request.get(`/api/demo/cases/${hard}/memory-candidates`)).json() as Json[];
  const candidate = candidates.find((item) => item.fact_key === "family.budget" && item.state === "pending")!;
  await post(page, `/api/demo/memory-candidates/${candidate.candidate_id}/verification-decisions`, token, { schema_version: 1, expected_case_revision: 1, decision: "confirm", reason: "Confirm synthetic hard-failure negative budget." });
  const hardReplan = await read(page, `/api/demo/cases/${hard}/advisor-ledger`);
  const hardInputs = hardReplan.canonical_task_inputs as Json;
  const hardSource = await post(page, `/api/demo/cases/${hard}/agent-tasks`, token, { schema_version: 1, operation: hardInputs.operation, expected_case_revision: hardInputs.expected_case_revision, source_pack_id: hardInputs.source_pack_id, source_pack_version: hardInputs.source_pack_version, policy_version: hardInputs.policy_version });
  await control("fail-hard", { task_id: hardSource.task_id });
  await hydrate(page, hard, token);
  await page.goto("/demo");
  for (const state of ["hard-failure", "unknown-failure"]) {
    if (state === "unknown-failure") { await control("unknown-negative", { task_id: hardSource.task_id }); await page.reload(); }
    const denied = await read(page, `/api/demo/cases/${hard}/advisor-ledger`);
    expect((denied.task as Json).task_id).toBe(hardSource.task_id);
    expect((denied.task as Json).public_code).toBe(state === "hard-failure" ? "invalid_schema" : "provider_unknown");
    expect((denied.recovery as Json).retry_allowed).toBe(false);
    expect(denied.canonical_task_inputs).toBeNull();
    await expect(page.getByRole("button", { name: name("创建新的规划任务", "Create a fresh planning task"), exact: true })).toHaveCount(0);
    await expect(page.getByRole("checkbox", { name: /我作为顾问明确同意|As the advisor, I explicitly consent/ })).toHaveCount(0);
    const rejected = await page.request.post(`/api/demo/tasks/${hardSource.task_id}/retry`, { headers: { Origin: origin, "X-CSRF-Token": token, "Idempotency-Key": crypto.randomUUID() }, data: { schema_version: 1, expected_row_version: (denied.task as Json).row_version, expected_case_revision: 2 } });
    expect(rejected.status()).toBe(409);
    await capture(page, state, ".advisor-ledger-action");
  }
  await writeFile(`${root}/proof.json`, JSON.stringify({ schema_version: 1, locale, parent_facts_recovery: { injected_503: injectedParentFactsFailure, parent_mints: parentMints, business_writes_before_authority: prematureBusinessWrites, same_tab_reload: true, active_role: recoveredParentStatus.active_role }, happy_case_id: happy, source_task_id: source.task_id, successor_task_id: successor.task_id, hard_task_id: hardSource.task_id, receipt: brief.receipt }));
  await control("verify-source", { source_task_id: source.task_id });
});
