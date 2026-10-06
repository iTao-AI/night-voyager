// @vitest-environment node
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { Page, Request, Response } from "@playwright/test";
import { afterEach, expect, it, vi } from "vitest";

import { createPlanningRevisionDiagnostics, safePlanningRevisionPath } from "../../e2e/support/planning-revision-diagnostics";

const HEAD = "b9e37518bcee783328edf06e403cdb87b9e21020";
const CASE = "/api/demo/cases/49000000-0000-0000-0000-000000000001";
const directories: string[] = [];

async function harness(options: { language?: string; label?: string; child?: boolean; pseudo?: boolean; visibilityFailure?: boolean } = {}) {
  const root = await mkdtemp(join(tmpdir(), "nv-safe-diagnostic-"));
  directories.push(root);
  const handlers = new Map<string, (value: unknown) => void>();
  const screenshot = vi.fn(async ({ path }: { path: string }) => { await writeFile(path, Buffer.from("static-button-unit-image")); });
  const page = {
    on: (event: string, handler: (value: unknown) => void) => handlers.set(event, handler),
    off: (event: string) => handlers.delete(event),
    evaluate: vi.fn(async () => options.language ?? "en"),
    getByRole: (_role: string, { name }: { name: string }) => ({ first: () => ({
      isVisible: async () => {
        if (options.visibilityFailure) throw new Error("unit-secret-probe-error");
        return name === options.label;
      },
      evaluate: async (callback: (element: HTMLElement, expected: string) => boolean, expected: string) => callback({ tagName: "BUTTON", textContent: name, children: options.child ? [{}] : [] } as unknown as HTMLElement, expected),
      screenshot,
    }) }),
  } as unknown as Page;
  vi.stubGlobal("getComputedStyle", () => ({ backgroundImage: "none", content: options.pseudo ? '"unit-secret-pseudo"' : "none" }));
  const diagnostic = createPlanningRevisionDiagnostics(page, root, "en", HEAD);
  return { root, handlers, screenshot, diagnostic, emit: (event: string, value: unknown) => handlers.get(event)?.(value) };
}

function request(path: string, method = "GET") {
  return {
    url: () => `http://127.0.0.1:3000${path}`,
    method: () => method,
    headers: vi.fn(() => { throw new Error("credentials must not be read"); }),
    postData: vi.fn(() => { throw new Error("request body must not be read"); }),
  } as unknown as Request;
}

afterEach(async () => {
  vi.unstubAllGlobals();
  await Promise.all(directories.splice(0).map((directory) => rm(directory, { recursive: true, force: true })));
});

it("normalizes only declared synthetic HTTP paths and drops query values", () => {
  expect(safePlanningRevisionPath(`http://127.0.0.1:3000${CASE}/advisor-reviews?csrf=unit-secret`)).toBe("/api/demo/cases/:case/advisor-reviews");
  expect(safePlanningRevisionPath("/api/demo/sessions?token=unit-secret")).toBe("/api/demo/sessions");
  expect(safePlanningRevisionPath(`https://external.example${CASE}/journey-status`)).toBeNull();
  expect(safePlanningRevisionPath("/api/demo/cases/private-case/journey-status")).toBeNull();
  expect(safePlanningRevisionPath(`${CASE}/../../private`)).toBeNull();
  expect(safePlanningRevisionPath("http://[")).toBeNull();
});

it("preserves an unfinished POST without reading credentials or inventing UI observations", async () => {
  const run = await harness();
  const post = request(`${CASE}/advisor-reviews?token=unit-secret`, "POST");
  run.diagnostic.mark("replay-action");
  run.diagnostic.observeReplay(2, true);
  run.emit("request", post);
  expect(run.diagnostic.inspect()).toMatchObject({ stage: "replay-action", document_lang: "unknown", visible: { continue_student: null }, replay: { observed_posts: 2, same_key: true }, http: [{ path: "/api/demo/cases/:case/advisor-reviews", status: null, outcome: "pending" }] });
  run.emit("requestfailed", post);
  expect(run.diagnostic.inspect().http[0].outcome).toBe("failed");
  expect(post.headers).not.toHaveBeenCalled();
  expect(post.postData).not.toHaveBeenCalled();
  await run.diagnostic.saveFailure();
  run.diagnostic.stop();
  expect(run.handlers.size).toBe(0);
});

it("records only closed authority fields after the response body finishes", async () => {
  const run = await harness();
  const get = request(`${CASE}/journey-status`);
  run.emit("request", get);
  let finish!: () => void;
  const finished = new Promise<void>((resolve) => { finish = resolve; });
  const response = {
    request: () => get, status: () => 200, finished: () => finished,
    json: vi.fn(async () => ({ phase: "revision_requested", active_role: "student", code: "unit-secret-unknown", csrf: "unit-secret-csrf", cookie: "unit-secret-cookie", idempotency_key: "unit-secret-key" })),
  } as unknown as Response;
  run.emit("response", response);
  expect(run.diagnostic.inspect().http[0].outcome).toBe("pending");
  expect(response.json).not.toHaveBeenCalled();
  finish();
  await vi.waitFor(() => expect(run.diagnostic.inspect().http[0].outcome).toBe("response"));
  expect(run.diagnostic.inspect().http[0]).toMatchObject({ status: 200, phase: "revision_requested", role: "student", code: null });
  await run.diagnostic.saveFailure();
  run.diagnostic.stop();
  const report = await readFile(`${run.root}/diagnostics-en/diagnostics.json`, "utf8");
  expect(report).not.toContain("unit-secret");
});

it("does not read successful session bodies and preserves an allowed recovery error", async () => {
  const run = await harness();
  for (const [path, status, code] of [["/api/demo/sessions", 200, "unit-secret-token"], [`${CASE}/advisor-reviews`, 503, "bff_upstream_unavailable"]] as const) {
    const req = request(path, "POST");
    run.emit("request", req);
    const response = { request: () => req, status: () => status, finished: async () => null, json: vi.fn(async () => ({ code })) } as unknown as Response;
    run.emit("response", response);
    await vi.waitFor(() => expect(run.diagnostic.inspect().http.at(-1)?.status).toBe(status));
    expect(response.json).toHaveBeenCalledTimes(status >= 400 ? 1 : 0);
  }
  expect(run.diagnostic.inspect().http.at(-1)?.code).toBe("bff_upstream_unavailable");
  await run.diagnostic.saveFailure();
  run.diagnostic.stop();
});

it("saves an observed language mismatch with only a verified static button crop", async () => {
  const run = await harness({ language: "zh-CN", label: "重新连接顾问流程" });
  await run.diagnostic.saveFailure();
  run.diagnostic.stop();
  const value = JSON.parse(await readFile(`${run.root}/diagnostics-en/diagnostics.json`, "utf8"));
  expect(value).toMatchObject({ locale: "en", document_lang: "zh-CN", visible: { reconnect: true }, screenshot: { file: "visible-action.png", action: "reconnect-zh-CN", text_matches: true } });
  expect(run.screenshot).toHaveBeenCalledTimes(1);
});

it.each([{ child: true }, { pseudo: true }])("excludes a button containing extra visual content: %j", async (options) => {
  const run = await harness({ ...options, label: "Reconnect advisor flow" });
  await run.diagnostic.saveFailure();
  run.diagnostic.stop();
  const value = JSON.parse(await readFile(`${run.root}/diagnostics-en/diagnostics.json`, "utf8"));
  expect(value.visible.reconnect).toBe(true);
  expect(value.screenshot).toBeNull();
  expect(run.screenshot).not.toHaveBeenCalled();
});

it("keeps failed visibility probes unknown and exports no probe exception", async () => {
  const run = await harness({ visibilityFailure: true });
  await run.diagnostic.saveFailure();
  run.diagnostic.stop();
  const report = await readFile(`${run.root}/diagnostics-en/diagnostics.json`, "utf8");
  expect(Object.values(JSON.parse(report).visible).every((value) => value === null)).toBe(true);
  expect(report).not.toContain("unit-secret");
});

it("writes an atomic progress snapshot with a pending request and unknown UI", async () => {
  const run = await harness();
  run.emit("request", request(`${CASE}/advisor-reviews?token=unit-secret`, "POST"));
  run.diagnostic.mark("student-handoff-assertion");
  await run.diagnostic.saveFailure();
  run.diagnostic.stop();
  // Simulate losing the final snapshot; keep the observer's atomic progress file.
  await rm(`${run.root}/diagnostics-en/diagnostics.json`);
  const report = await readFile(`${run.root}/diagnostics-en/progress.json`, "utf8");
  expect(JSON.parse(report)).toMatchObject({ stage: "student-handoff-assertion", document_lang: "unknown", visible: { continue_student: null }, http: [{ status: null, outcome: "pending" }] });
  expect(report).not.toContain("unit-secret");
});
