import { expect, test, type Page } from "@playwright/test";

const terminalProof = process.env.M5_TERMINAL_PROOF === "1";
const ORIGIN = "http://127.0.0.1:3000";
const PRIMARY_CASE = "41000000-0000-0000-0000-000000000001";
const ACTIVE_CASE = "41000000-0000-0000-0000-000000000002";
const STALE_CASE = "41000000-0000-0000-0000-000000000003";
const EXPIRED_CASE = "41000000-0000-0000-0000-000000000004";

async function journey(page: Page) {
  return await page.evaluate(() => JSON.parse(sessionStorage.getItem("night-voyager:m5") ?? "null"));
}

async function mutation(page: Page, path: string, key: string, body: unknown) {
  const metadata = await journey(page);
  return await page.request.post(path, {
    headers: { Origin: ORIGIN, "Content-Type": "application/json", "X-CSRF-Token": metadata.csrf, "Idempotency-Key": key },
    data: body,
  });
}

async function createActiveTaskBlockedCandidate(page: Page): Promise<void> {
  const thread = await page.request.get(`/api/demo/cases/${ACTIVE_CASE}/collaboration-thread`);
  expect(thread.status()).toBe(200);
  const threadId = (await thread.json()).thread_id;
  const appended = await mutation(page, `/api/demo/collaboration-threads/${threadId}/messages`, "00000000-0000-4000-8000-000000000601", { schema_version: 1, body: "Our family accepts the bounded high-risk option." });
  expect(appended.status()).toBe(201);
  const messageId = (await appended.json()).message_event_id;
  const proposed = await mutation(page, `/api/demo/messages/${messageId}/memory-candidates`, "00000000-0000-4000-8000-000000000602", { schema_version: 1, case_revision: 1, proposal: { schema_version: 1, fact_key: "family.risk_tolerance", value: "high" } });
  expect(proposed.status()).toBe(201);
}

async function verifyNegative(page: Page, caseId: string, key: string, expectedCode: string) {
  const candidates = await page.request.get(`/api/demo/cases/${caseId}/memory-candidates`);
  expect(candidates.status()).toBe(200);
  const [candidate] = await candidates.json();
  expect(candidate.candidate_id).toBeTruthy();
  const response = await mutation(page, `/api/demo/memory-candidates/${candidate.candidate_id}/verification-decisions`, key, { schema_version: 1, expected_case_revision: candidate.case_revision, decision: "confirm", reason: "Confirm the bounded synthetic proposal." });
  expect(response.status()).toBe(409);
  expect((await response.json()).code).toBe(expectedCode);
}

async function expectCollapsedNoTaskInspector(page: Page) {
  const details = page.locator(".skill-inspector details");
  await expect(details.locator("summary")).toBeVisible();
  await expect(details).not.toHaveAttribute("open", "");
  await expect(details).toContainText(/尚未创建规划任务|Planning task not created/);
}

test("collaboration-demo.spec.ts proves governed memory authority without creating a task", async ({ page }) => {
  test.skip(terminalProof, "runs only in the normal worker-backed Compose lane");
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/demo/collaboration");
  await expect(page.getByRole("banner")).toBeVisible();
  await expect(page.getByRole("main")).toBeVisible();
  await expect(page.getByRole("contentinfo")).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: /跳到主要内容|Skip to main content/ })).toBeFocused();

  await page.getByRole("button", { name: /开始家长流程|Start parent flow/ }).click();
  await expect(page.getByRole("heading", { name: /共享 Case 沟通记录|Shared Case communication record/ })).toBeVisible();
  await expect(page.getByText(/当前角色：家长|Current role：Parent/)).toBeVisible();
  const parentInspector = await page.request.get(`/api/demo/cases/${PRIMARY_CASE}/planning-skill-inspector`);
  expect(parentInspector.status()).toBe(404);

  await createActiveTaskBlockedCandidate(page);
  await page.getByRole("button", { name: /添加已确认预算消息|Add confirmed budget message/ }).click();
  await expect(page.getByText("Our confirmed program budget is 300,000 to 400,000 CNY.")).toBeVisible();
  await page.getByRole("button", { name: /提交预算供顾问审核|Submit the budget for advisor review/ }).click();
  await expect(page.getByText(/等待顾问确认|Awaiting advisor confirmation/)).toBeVisible();
  const participantCandidates = await page.request.get(`/api/demo/cases/${PRIMARY_CASE}/memory-candidates`);
  const [participantCandidate] = await participantCandidates.json();
  expect(participantCandidate.candidate_id).toBeUndefined();

  await page.reload();
  await expect(page.getByText(/等待顾问确认|Awaiting advisor confirmation/)).toBeVisible();
  await page.getByRole("button", { name: /以指定顾问身份继续|Continue as assigned advisor/ }).click();
  await expect(page.getByRole("heading", { name: /顾问确认|Advisor confirmation/ })).toBeFocused();
  await expect(page.getByText(/当前角色：顾问|Current role：Advisor/)).toBeVisible();
  await expectCollapsedNoTaskInspector(page);

  await verifyNegative(page, STALE_CASE, "00000000-0000-4000-8000-000000000603", "memory_candidate_stale");
  await verifyNegative(page, EXPIRED_CASE, "00000000-0000-4000-8000-000000000604", "memory_candidate_expired");
  await verifyNegative(page, ACTIVE_CASE, "00000000-0000-4000-8000-000000000605", "active_task_blocks_revision");

  const confirmationKeys: string[] = [];
  let confirmationAttempt = 0;
  await page.route("**/api/demo/memory-candidates/*/verification-decisions", async (route) => {
    confirmationAttempt += 1;
    confirmationKeys.push(route.request().headers()["idempotency-key"] ?? "");
    if (confirmationAttempt === 1) {
      const committed = await route.fetch();
      expect(committed.status()).toBe(201);
      await route.abort("failed");
      return;
    }
    await route.continue();
  });
  await page.getByRole("button", { name: /确认家庭预算|Confirm family budget/ }).click();
  await expect(page.getByRole("heading", { name: /协作流程已安全暂停|Collaboration paused safely/ })).toBeVisible();
  await page.getByRole("button", { name: /重新载入协作 authority|Reload collaboration authority/ }).click();
  await expect(page.getByRole("heading", { name: /需要重新规划|Re-plan required/ })).toBeFocused();
  expect(confirmationKeys).toHaveLength(2);
  expect(confirmationKeys[0]).toBe(confirmationKeys[1]);
  await page.unroute("**/api/demo/memory-candidates/*/verification-decisions");

  await expect(page.getByText("Fact version 1")).toBeVisible();
  await expect(page.getByText("Case revision 2")).toBeVisible();
  await expectCollapsedNoTaskInspector(page);
  await expect(page.getByRole("button", { name: /create.*task/i })).toHaveCount(0);
  const raw = /schema_version|confirmed_fact_id|candidate_id|night_voyager_api|\/Users\/|41000000-/;
  await expect(page.getByRole("main")).not.toContainText(raw);

  for (const viewport of [{ width: 1440, height: 900 }, { width: 768, height: 900 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    await expect(page.getByText("Our confirmed program budget is 300,000 to 400,000 CNY.")).toBeVisible();
    await expect(page.getByText("Fact version 1")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    const shortTargets = await page.locator("button:visible, a.primary-action:visible").evaluateAll((nodes) => nodes.filter((node) => node.getBoundingClientRect().height < 44).length);
    expect(shortTargets).toBe(0);
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  if (process.env.UPDATE_COLLABORATION_SCREENSHOT === "1") {
    const skipLink = page.getByRole("link", { name: /跳到主要内容|Skip to main content/ });
    await skipLink.evaluate((node) => node.setAttribute("hidden", ""));
    await expect(skipLink).toBeHidden();
    await page.screenshot({ path: "/workspace/docs/assets/collaboration-confirmed-fact.png", fullPage: true });
  }
});
