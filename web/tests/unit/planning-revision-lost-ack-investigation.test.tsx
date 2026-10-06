import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { ConnectedDemo } from "../../components/connected-demo/ConnectedDemo";
import { saveRecoveryMetadata } from "../../lib/connected-demo/session-storage";
import { PresentationProvider } from "../../lib/presentation/context";
import { CASE_ID, ledger, status } from "./connected-demo-test-data";

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

function setup(locale: "en" | "zh-CN") {
  localStorage.setItem("night-voyager:presentation-locale:v1", locale);
  saveRecoveryMetadata({ schema_version: 3, journey: "advisor-family", role: "advisor", csrf: "unit-csrf", caseId: CASE_ID, currentRevision: 1, currentTaskId: null, predecessorRunId: null, currentRunId: "70000000-0000-0000-0000-000000000001", cursor: 0, phase: "review_required", mutations: {} });
  const replay = deferred<Response>();
  const authority = deferred<Response>();
  const keys: string[] = [];
  const boundaries: string[] = [];
  let authorityReads = 0;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path.endsWith("/advisor-reviews")) {
      keys.push(new Headers(init?.headers).get("Idempotency-Key") ?? "");
      if (keys.length === 1) {
        boundaries.push("committed-response-lost");
        throw new TypeError("Synthetic committed ACK loss");
      }
      boundaries.push("replay-post-started");
      const response = await replay.promise;
      boundaries.push("replay-post-response");
      return response;
    }
    if (path.endsWith("/journey-status")) {
      if (keys.length === 0) return Response.json(status("review_required"));
      authorityReads++;
      boundaries.push("authority-get-started");
      const response = await authority.promise;
      boundaries.push("authority-get-response");
      return response;
    }
    if (path.endsWith("/advisor-ledger")) return Response.json(ledger("review_required"));
    if (path.endsWith("/confirmed-facts")) return Response.json({ schema_version: 1, current: [], history: [], next_cursor: null });
    if (path.endsWith("/planning-skill-inspector")) return Response.json({ code: "unavailable" }, { status: 404 });
    throw new Error(`Unexpected unit request ${path}`);
  }));
  render(<ConnectedDemo />, { wrapper: PresentationProvider });
  const copy = locale === "en"
    ? { request: "Request revision", reconnect: "Reconnect advisor flow", student: "Continue as student" }
    : { request: "请求修订", reconnect: "重新连接顾问流程", student: "以学生身份继续" };
  return { replay, authority, keys, boundaries, copy, authorityReads: () => authorityReads };
}

async function loseAndReplay(copy: ReturnType<typeof setup>["copy"], keys: string[]) {
  fireEvent.click(await screen.findByRole("button", { name: copy.request }));
  fireEvent.click(await screen.findByRole("button", { name: copy.reconnect }));
  await waitFor(() => expect(keys).toHaveLength(2));
}

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  localStorage.clear();
  vi.unstubAllGlobals();
});

it.each(["en", "zh-CN"] as const)("delayed same-key replay and authority GET reach the actual %s handoff", async (locale) => {
  const run = setup(locale);
  await loseAndReplay(run.copy, run.keys);
  expect(run.keys[0]).toBeTruthy();
  expect(run.keys[1]).toBe(run.keys[0]);
  expect(run.authorityReads()).toBe(0);
  expect(screen.queryByRole("button", { name: run.copy.student })).toBeNull();
  await act(async () => { run.replay.resolve(Response.json({ replayed: true })); });
  expect(run.authorityReads()).toBe(1);
  expect(screen.queryByRole("button", { name: run.copy.student })).toBeNull();
  await act(async () => { run.authority.resolve(Response.json(status("revision_requested"))); });
  expect(await screen.findByRole("button", { name: run.copy.student })).toBeVisible();
  expect(document.documentElement.lang).toBe(locale);
  expect(run.boundaries).toEqual(["committed-response-lost", "replay-post-started", "replay-post-response", "authority-get-started", "authority-get-response"]);
});

it.each(["replay-503", "authority-503", "authority-401"] as const)("keeps an observable recovery surface for %s instead of a student handoff", async (failure) => {
  const run = setup("en");
  await loseAndReplay(run.copy, run.keys);
  await act(async () => {
    run.replay.resolve(failure === "replay-503"
      ? Response.json({ code: "bff_upstream_unavailable" }, { status: 503 })
      : Response.json({ replayed: true }));
  });
  if (failure !== "replay-503") {
    await act(async () => {
      run.authority.resolve(Response.json({ code: failure === "authority-401" ? "authentication_failed" : "bff_upstream_unavailable" }, { status: failure === "authority-401" ? 401 : 503 }));
    });
  }
  expect(await screen.findByRole("button", { name: run.copy.reconnect })).toBeVisible();
  expect(screen.queryByRole("button", { name: run.copy.student })).toBeNull();
  expect(document.documentElement.lang).toBe("en");
  expect(run.authorityReads()).toBe(failure === "replay-503" ? 0 : 1);
});
