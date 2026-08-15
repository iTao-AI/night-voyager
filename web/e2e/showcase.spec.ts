import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import { expect, test, type Browser, type Page } from "@playwright/test";

import {
  SHOWCASE_ASSET_CONTRACT,
  SHOWCASE_ASSET_NAMES,
  type ShowcaseAssetName,
} from "../lib/presentation/showcase";

const captureEnabled = process.env.PRESENTATION_SHOWCASE_CAPTURE === "1";
const publicRoot = process.env.PRESENTATION_SHOWCASE_PUBLIC_ROOT
  ?? process.env.PRESENTATION_PUBLIC_EVIDENCE_ROOT;
const metadataPath = process.env.PRESENTATION_SHOWCASE_METADATA_PATH;
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3000";

type CaptureRecord = {
  filename: ShowcaseAssetName;
  route: string;
  state: string;
  proof_segment: string;
  locale: string;
  viewport: { width: number; height: number };
};

test.describe("native advisor showcase capture", () => {
  test("captures exactly four canonical frames from real deterministic states", async ({ browser }) => {
    test.skip(!captureEnabled || !publicRoot, "requires the explicit showcase capture lane");

    const records: CaptureRecord[] = [];
    await captureRootFrame(browser, "advisor-workspace-overview.png", false, records);
    await captureConnectedReceipt(browser, records);
    await captureBlockedRecovery(browser, records);
    await captureRootFrame(browser, "advisor-workspace-mobile.png", true, records);

    expect(records.map((record) => record.filename)).toEqual([...SHOWCASE_ASSET_NAMES]);
    if (metadataPath) {
      await mkdir(path.dirname(metadataPath), { recursive: true, mode: 0o700 });
      await writeFile(metadataPath, `${JSON.stringify({ records }, null, 2)}\n`, {
        encoding: "utf8",
        mode: 0o600,
      });
    }
  });
});

async function newPage(
  browser: Browser,
  viewport: { width: number; height: number },
  initialRoute = "/",
) {
  const context = await browser.newContext({
    baseURL: BASE_URL,
    deviceScaleFactor: 1,
    locale: "zh-CN",
    viewport,
  });
  await context.addInitScript(() => {
    localStorage.removeItem("night-voyager:presentation-locale:v1");
    sessionStorage.clear();
  });
  const page = await context.newPage();
  const browserErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") browserErrors.push(`console: ${message.text()}`);
  });
  page.on("pageerror", (error) => {
    browserErrors.push(`pageerror: ${error.message}`);
  });
  await page.goto(initialRoute, { waitUntil: "domcontentloaded" });
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
  return { browserErrors, context, page };
}

async function captureRootFrame(
  browser: Browser,
  filename: "advisor-workspace-overview.png" | "advisor-workspace-mobile.png",
  mobile: boolean,
  records: CaptureRecord[],
) {
  const contract = SHOWCASE_ASSET_CONTRACT[filename];
  const { browserErrors, context, page } = await newPage(browser, contract.viewport);
  try {
    if (mobile) {
      const subject = page.locator(
        ".portfolio-story-chapter[data-story-scene='route'] .portfolio-story-static-subject:visible",
      );
      await expect(subject.locator(".advisor-workspace-preview")).toHaveAttribute(
        "data-preview-scene",
        "route",
      );
      await page.evaluate(() => {
        document.documentElement.style.scrollBehavior = "auto";
        document.body.style.scrollBehavior = "auto";
      });
      await subject.evaluate((element) => element.scrollIntoView({ block: "start", behavior: "auto" }));
      await expect.poll(async () => Math.abs(await subject.evaluate((element) => element.getBoundingClientRect().top))).toBeLessThan(2);
    } else {
      await page.evaluate(() => window.scrollTo({ left: 0, top: 0 }));
      const subject = page.locator(".portfolio-hero-product");
      await expect(subject.locator(".advisor-workspace-preview")).toHaveAttribute(
        "data-preview-scene",
        "route",
      );
      await composeDesktopOverviewCapture(page);
    }
    await expect(page.locator(".advisor-workspace-preview").filter({ visible: true }).first()).toBeVisible();
    await captureViewport(page, filename);
    expect(browserErrors).toEqual([]);
    records.push({
      filename,
      route: contract.route,
      state: contract.state,
      proof_segment: contract.proofSegment,
      locale: contract.locale,
      viewport: contract.viewport,
    });
  } finally {
    await page.evaluate(() => window.stop());
    await page.goto("about:blank", { waitUntil: "commit" });
    await context.close();
  }
}

async function composeDesktopOverviewCapture(page: Page) {
  await page.evaluate(() => {
    const hero = document.querySelector<HTMLElement>(".portfolio-hero");
    const copy = document.querySelector<HTMLElement>(".portfolio-hero-copy");
    const product = document.querySelector<HTMLElement>(".portfolio-hero-product");
    if (!hero || !copy || !product) throw new Error("root overview capture landmarks are missing");

    // Capture-only composition: keep the real route preview, but remove the
    // portfolio hero's tall presentation layout so the frame is readable at
    // the canonical README viewport. This does not change product behavior.
    hero.style.display = "block";
    hero.style.minHeight = "0";
    hero.style.padding = "0";
    copy.style.display = "none";
    product.style.width = "min(100%, 68rem)";
    product.style.maxWidth = "68rem";
    product.style.margin = "0 auto";
    document.documentElement.style.scrollBehavior = "auto";
  });
}

async function captureConnectedReceipt(browser: Browser, records: CaptureRecord[]) {
  const filename = "advisor-normal-path.png" as const;
  const contract = SHOWCASE_ASSET_CONTRACT[filename];
  const { browserErrors, context, page } = await newPage(browser, contract.viewport, contract.route);
  try {
    await expect(page.locator(".advisor-workspace-shell")).toHaveAttribute(
      "data-proof-segment",
      contract.proofSegment,
    );
    await page.getByRole("button", { name: "开始顾问流程", exact: true }).click();
    const createTask = page.getByRole("button", { name: "创建规划任务", exact: true });
    await expect(createTask).toBeEnabled();
    await createTask.click({ timeout: 15_000 });
    await expect(
      page.getByRole("button", { name: "批准当前计划", exact: true }),
    ).toBeEnabled({ timeout: 90_000 });
    await page.getByRole("button", { name: "批准当前计划", exact: true }).click();
    const parentSwitch = page.getByRole("button", { name: "以家长身份继续", exact: true });
    await expect(parentSwitch).toBeVisible({ timeout: 30_000 });
    await parentSwitch.click();
    await expect(page.getByRole("heading", { name: "家庭决定简报", exact: true })).toBeVisible({ timeout: 30_000 });
    await page.getByRole("checkbox").check();
    await page.getByRole("button", { name: "继续家庭决定", exact: true }).click();
    await expect(page.getByRole("heading", { name: "家庭决定回执", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "行动时间线", exact: true })).toBeVisible();
    await expect(page.locator("[data-persisted-result='true']")).toBeVisible();
    await page.locator("[data-persisted-result='true']").evaluate((element) => {
      element.scrollIntoView({ block: "start" });
    });
    await captureViewport(page, filename);
    expect(browserErrors).toEqual([]);
    records.push({
      filename,
      route: contract.route,
      state: contract.state,
      proof_segment: contract.proofSegment,
      locale: contract.locale,
      viewport: contract.viewport,
    });
  } finally {
    await page.evaluate(() => window.stop());
    await page.goto("about:blank", { waitUntil: "commit" });
    await context.close();
  }
}

async function captureBlockedRecovery(browser: Browser, records: CaptureRecord[]) {
  const filename = "advisor-blocked-recovery.png" as const;
  const contract = SHOWCASE_ASSET_CONTRACT[filename];
  const { browserErrors, context, page } = await newPage(browser, contract.viewport, contract.route);
  try {
    await expect(page.locator(".advisor-workspace-shell")).toHaveAttribute(
      "data-proof-segment",
      contract.proofSegment,
    );
    await page.getByRole("button", { name: "学生", exact: true }).click();
    await page.getByRole("button", { name: "开始执行行动计划", exact: true }).click();
    await page.getByRole("button", { name: "记录阻塞并停止当前 checkpoint", exact: true }).click();
    await page.getByRole("button", { name: "顾问", exact: true }).click();
    await expect(page.getByText("当前 checkpoint 已阻塞。家庭不能继续提交状态；由已分配顾问决定是否请求重新评估。", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "请求重新评估并停止执行", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "请求重新评估并停止执行", exact: true }).click();
    await expect(page.getByRole("heading", { name: "重新评估交接", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "验证并继续", exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "提交完成状态给顾问", exact: true })).toHaveCount(0);
    await page.evaluate(() => window.scrollTo({ left: 0, top: 0 }));
    await captureViewport(page, filename);
    expect(browserErrors).toEqual([]);
    records.push({
      filename,
      route: contract.route,
      state: contract.state,
      proof_segment: contract.proofSegment,
      locale: contract.locale,
      viewport: contract.viewport,
    });
  } finally {
    await page.evaluate(() => window.stop());
    await page.goto("about:blank", { waitUntil: "commit" });
    await context.close();
  }
}

async function captureViewport(page: Page, filename: ShowcaseAssetName) {
  const destination = path.join(publicRoot!, filename);
  await mkdir(path.dirname(destination), { recursive: true, mode: 0o755 });
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
  });
  await page.screenshot({
    animations: "disabled",
    fullPage: false,
    path: destination,
  });
  const png = await readFile(destination);
  expect(png.subarray(0, 8)).toEqual(Buffer.from("89504e470d0a1a0a", "hex"));
  expect(png.subarray(12, 16).toString("ascii")).toBe("IHDR");
  const width = png.readUInt32BE(16);
  const height = png.readUInt32BE(20);
  expect({ width, height }).toEqual(SHOWCASE_ASSET_CONTRACT[filename].viewport);
}
