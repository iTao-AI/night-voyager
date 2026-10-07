import { expect, test, type Page } from "@playwright/test";
import { handoffFixture, handoffId } from "../tests/fixtures/reassessment-handoff";

test.use({ permissions: ["clipboard-read", "clipboard-write"] });

// Same whole-main guard as fact-to-plan; do not filter out hidden DOM content.
const rawPublicData = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|schema_version|confirmed_fact_id|candidate_id|request_sha256|night_voyager_(?:api|worker|migrator)|\/Users\/|Traceback|csrf|cookie/i;

// HTTP reads and demo sessions are routed synthetic fixtures. No native business
// mutation, receipt, database persistence or recovery proof is claimed here.
async function routeFixture(page: Page, fixture = handoffFixture()) {
  const state = {
    fixture, sessionFailure: false, holdSession: null as Promise<void> | null,
    requests: [] as string[],
  };
  await page.route("**/api/demo/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    state.requests.push(`${request.method()} ${path}`);
    if (path === "/api/demo/session-bootstrap") {
      await route.fulfill({ json: { csrf_token: "synthetic-bootstrap" } });
    } else if (path === "/api/demo/sessions") {
      if (state.holdSession) await state.holdSession;
      if (state.sessionFailure) {
        await route.fulfill({ status: 401, json: { code: "session_changed" } });
        return;
      }
      const role = String(request.postDataJSON().demo_actor).split("_").at(-1);
      if (role !== "advisor" && role !== "student" && role !== "parent") throw new Error("unexpected fixture role");
      state.fixture.context.active_role = role;
      await route.fulfill({ json: { role, csrf_token: "synthetic-session" } });
    } else if (path.endsWith("/plan-execution-context")) {
      await route.fulfill({ json: state.fixture.context });
    } else if (path.endsWith("/timeline-execution") && request.method() === "GET") {
      await route.fulfill({ json: state.fixture.view });
    } else {
      await route.fulfill({ status: 501, json: { code: "unexpected_fixture_request" } });
    }
  });
  return state;
}

const labels = {
  "zh-CN": {
    advisor: "顾问", parent: "家长", handoff: "重新评估交接", copy: "复制交接摘要",
    copied: "交接摘要已复制。", fallback: "可选择的交接摘要", identities: "查看交接来源身份",
    missing: "当前视图未提供身份匹配的阻塞证明详情。", reason: "缺少必需输入",
    accepted: "保存时的数据库日期", observed: "当前视图所见日期", milestone: "申请提交",
  },
  en: {
    advisor: "Advisor", parent: "Parent", handoff: "Reassessment handoff", copy: "Copy handoff summary",
    copied: "Handoff summary copied.", fallback: "Selectable handoff summary", identities: "View handoff source identities",
    missing: "Matching blocked attestation details are unavailable in this view.", reason: "Required input is missing",
    accepted: "Accepted database date", observed: "View observed date", milestone: "Application",
  },
} as const;

async function open(page: Page, locale: keyof typeof labels, width: number) {
  await page.setViewportSize({ width, height: 1000 });
  await page.addInitScript((value) => {
    localStorage.setItem("night-voyager:presentation-locale:v1", value);
  }, locale);
  await page.goto("/demo/plan");
  await page.getByRole("button", { name: labels[locale].advisor, exact: true }).click();
  const handoff = page.getByRole("region", { name: labels[locale].handoff });
  await expect(handoff).toBeVisible();
  return handoff;
}

async function expectReadable(page: Page) {
  const geometry = await page.locator(".reassessment-handoff").evaluate((section) => {
    const box = section.getBoundingClientRect();
    return { left: box.left, right: box.right, width: innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      sectionWidth: section.clientWidth, contentWidth: section.scrollWidth,
      skipLinkBottom: document.querySelector(".skip-link")!.getBoundingClientRect().bottom };
  });
  expect(geometry.left).toBeGreaterThanOrEqual(0);
  expect(geometry.right).toBeLessThanOrEqual(geometry.width + 1);
  expect(geometry.documentWidth).toBeLessThanOrEqual(geometry.width + 1);
  expect(geometry.contentWidth).toBeLessThanOrEqual(geometry.sectionWidth + 1);
  expect(geometry.skipLinkBottom).toBeLessThanOrEqual(0);
}

for (const locale of ["zh-CN", "en"] as const) {
  for (const width of [1440, 390]) {
    for (const trigger of ["blocked_attestation", "deadline_elapsed"] as const) {
      test(`fixture handoff reading and native clipboard ${locale} ${width} ${trigger}`, async ({ page }, info) => {
        const fixture = handoffFixture(trigger);
        const state = await routeFixture(page, fixture);
        const handoff = await open(page, locale, width);
        const copy = labels[locale];
        await expect(handoff.getByText(copy.milestone, { exact: true })).toBeVisible();
        await expect(handoff.getByText("2026-10-15", { exact: true })).toBeVisible();
        if (trigger === "blocked_attestation") await expect(handoff.getByText(copy.reason, { exact: true })).toBeVisible();
        await expect(handoff.locator("details")).not.toHaveAttribute("open", "");
        await expect(page.getByRole("main")).not.toContainText(rawPublicData, { timeout: 15000 });
        await expect(handoff.locator("details dl")).toHaveCount(0);
        await expectReadable(page);
        await handoff.screenshot({ path: info.outputPath("handoff.png") });
        await handoff.getByRole("button", { name: copy.copy, exact: true }).click();
        await expect(handoff.getByText(copy.copied)).toBeVisible();
        const exported = await page.evaluate(() => navigator.clipboard.readText());
        const separator = locale === "zh-CN" ? "：" : ": ";
        expect(exported).toContain(`${copy.accepted}${separator}${fixture.view.reassessment!.accepted_database_date}`);
        expect(exported).toContain(`${copy.observed}${separator}${fixture.view.observed_date}`);
        expect(exported).toContain("pending_future_authorization");
        expect(exported).not.toContain(handoffId(90));
        expect(exported).not.toContain(handoffId(91));
        expect(exported).not.toMatch(/actor_id|csrf_token|x-csrf|cookie|authorization:/i);
        const requestsBeforeDisclosure = [...state.requests];
        const disclosure = handoff.locator("details summary");
        await disclosure.focus();
        await disclosure.press("Enter");
        await expect(handoff.locator("details")).toHaveAttribute("open", "");
        for (const id of [1, 2, 3, 4, 5, 11, 30]) {
          await expect(handoff.locator("details").getByText(handoffId(id), { exact: true })).toBeVisible();
        }
        await expect(handoff.locator("details")).not.toContainText(/actor_id|csrf|cookie|authorization:/i);
        await expect(handoff.locator("details")).not.toContainText(handoffId(90));
        await expect(handoff.locator("details")).not.toContainText(handoffId(91));
        const rows = await handoff.locator("dl > div").evaluateAll((elements) => elements.map((element) => ({
          label: element.querySelector("dt")!.textContent!, value: element.querySelector("dd")!.textContent!,
        })));
        for (const { label, value } of rows) expect(exported).toContain(`${label}${separator}${value}`);
        await expectReadable(page);
        await page.screenshot({ path: info.outputPath("source-identities.png"), fullPage: true });
        await disclosure.press("Space");
        await expect(handoff.locator("details")).not.toHaveAttribute("open", "");
        await expect(handoff.locator("details dl, details p")).toHaveCount(0);
        await expect(page.getByRole("main")).not.toContainText(rawPublicData, { timeout: 15000 });
        expect(state.requests).toEqual(requestsBeforeDisclosure);
        expect(state.requests.filter((request) => request.startsWith("POST") && request.includes("timeline-"))).toEqual([]);
      });
    }

    test(`fixture selectable fallback and locale invalidation ${locale} ${width}`, async ({ page }, info) => {
      await routeFixture(page);
      const handoff = await open(page, locale, width);
      await page.evaluate(() => Object.defineProperty(navigator.clipboard, "writeText", {
        configurable: true, value: () => Promise.reject(new Error("injected clipboard denial")),
      }));
      await handoff.getByRole("button", { name: labels[locale].copy, exact: true }).click();
      const fallback = handoff.getByRole("textbox", { name: labels[locale].fallback });
      await expect(fallback).toBeFocused();
      await expect(fallback).toBeInViewport();
      expect(await fallback.inputValue()).toContain(handoffId(30));
      expect(await fallback.evaluate((element: HTMLTextAreaElement) =>
        element.selectionStart === 0 && element.selectionEnd === element.value.length)).toBe(true);
      await expectReadable(page);
      await page.screenshot({ path: info.outputPath("copy-fallback.png") });
      await page.getByRole("button", { name: locale === "en" ? "中文" : "English", exact: true }).click();
      await expect(page.getByRole("textbox")).toHaveCount(0);
      await expect(page.getByRole("button", { name: labels[locale === "en" ? "zh-CN" : "en"].copy })).toBeEnabled();
    });
  }
}

for (const mismatch of ["reference", "checkpoint", "missing"] as const) {
  test(`fixture parser/UI does not attribute a ${mismatch} blocker`, async ({ page }) => {
    const fixture = handoffFixture();
    if (mismatch === "missing") fixture.view.latest_attestation = null;
    else if (mismatch === "reference") fixture.view.latest_attestation!.attestation_id = handoffId(99);
    else fixture.view.latest_attestation!.checkpoint_id = handoffId(10);
    await routeFixture(page, fixture);
    const handoff = await open(page, "en", 390);
    await expect(handoff.getByText(labels.en.missing)).toBeVisible();
    await expect(handoff.getByText(labels.en.reason)).toHaveCount(0);
  });
}

test("fixture role rotation removes fallback while pending and closes on session loss", async ({ page }) => {
  const state = await routeFixture(page);
  const handoff = await open(page, "en", 390);
  await page.evaluate(() => Object.defineProperty(navigator.clipboard, "writeText", {
    configurable: true, value: () => Promise.reject(new Error("injected clipboard denial")),
  }));
  await handoff.getByRole("button", { name: labels.en.copy }).click();
  await expect(handoff.getByRole("textbox", { name: labels.en.fallback })).toBeVisible();
  let release!: () => void;
  state.holdSession = new Promise<void>((resolve) => { release = resolve; });
  state.sessionFailure = true;
  await page.getByRole("button", { name: labels.en.parent, exact: true }).click();
  await expect(page.getByRole("textbox")).toHaveCount(0);
  await expect(page.getByRole("button", { name: labels.en.copy })).toHaveCount(0);
  release();
  await expect(page.getByText("Role or execution authority changed. Reconnect safely.").first()).toBeVisible();
  await expect(page.getByRole("button", { name: labels.en.copy })).toHaveCount(0);
});

test("fixture changed Case context cannot keep the old handoff copyable", async ({ page }) => {
  const state = await routeFixture(page);
  await open(page, "en", 1440);
  state.fixture = handoffFixture("deadline_elapsed", 100);
  await page.getByRole("button", { name: labels.en.parent, exact: true }).click();
  await expect(page.getByText("Role or execution authority changed. Reconnect safely.").first()).toBeVisible();
  await expect(page.getByRole("button", { name: labels.en.copy })).toHaveCount(0);
  await expect(page.getByRole("region", { name: labels.en.handoff })).toHaveCount(0);
});
