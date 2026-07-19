// @vitest-environment node
import { afterEach, expect, it, vi } from "vitest";

import { createConnectedDemoApi } from "../../lib/connected-demo/api";
import { parseBrief, parseLedger, parseTask } from "../../lib/connected-demo/contracts";
import { requestFingerprint } from "../../lib/connected-demo/idempotency";
import { brief, ledger, standaloneTask } from "./connected-demo-test-data";

afterEach(() => vi.unstubAllGlobals());

it.each([
  ["create", standaloneTask(false)],
  ["get", standaloneTask()],
  ["cancel", { ...standaloneTask(true), status: "cancelled", row_version: 2 }],
  ["legacy unpinned get", { ...standaloneTask(), skill_pin: null, leaf_binding: null }],
])("accepts the exact PR B standalone Task %s response", (_operation, response) => {
  expect(parseTask(response)).toEqual(response);
});

it.each([
  ["missing pin", () => { const value = structuredClone(standaloneTask()) as Record<string, unknown>; delete value.skill_pin; return value; }],
  ["extra pin key", () => ({ ...standaloneTask(), skill_pin: { ...standaloneTask().skill_pin, extra: true } })],
  ["malformed pin", () => ({ ...standaloneTask(), skill_pin: { ...standaloneTask().skill_pin, runtime_binding_sha256: "not-a-sha256" } })],
  ["pin without leaf", () => ({ ...standaloneTask(), leaf_binding: null })],
  ["missing leaf", () => { const value = structuredClone(standaloneTask()) as Record<string, unknown>; delete value.leaf_binding; return value; }],
  ["extra leaf key", () => ({ ...standaloneTask(), leaf_binding: { ...standaloneTask().leaf_binding, extra: true } })],
  ["mismatched leaf", () => ({ ...standaloneTask(), leaf_binding: { ...standaloneTask().leaf_binding, adapter_id: "governed_mixed_planning" } })],
])("rejects a standalone Task with %s", (_name, mutate) => {
  expect(() => parseTask(mutate())).toThrow("invalid response");
});

it("keeps the nested AdvisorLedger Task projection on its existing exact shape", () => {
  const value = ledger("active-task");
  value.task = { ...value.task!, skill_pin: standaloneTask().skill_pin } as typeof value.task;
  expect(() => parseLedger(value)).toThrow("invalid response");
});

it("uses only same-origin explicit routes and closed schema guards", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    expect(String(input)).toBe("/api/demo/session-bootstrap");
    return Response.json({ csrf_token: "csrf", extra: "forbidden" });
  });
  vi.stubGlobal("fetch", fetchMock);
  await expect(createConnectedDemoApi().bootstrap()).rejects.toThrow("invalid response");
});

it.each([
  ["invalid phase", () => ({ ...ledger("task-ready"), phase: "invented" })],
  ["invalid UUID", () => ({ ...ledger("task-ready"), case_id: "case" })],
  ["invalid positive integer", () => ({ ...ledger("task-ready"), case_revision: 0 })],
  ["nested extra key", () => ({ ...ledger("review-required"), routes: [{ ...ledger("review-required").routes[0], extra: true }] })],
  ["nested missing key", () => { const value = structuredClone(ledger("review-required")) as unknown as Record<string, unknown>; delete (value.review_inputs as Record<string, unknown>).planning_run_id; return value; }],
  ["phase authority mismatch", () => ({ ...ledger("task-ready"), routes: ledger("review-required").routes })],
])("rejects closed Ledger schema: %s", (_name, mutate) => {
  expect(() => parseLedger(mutate())).toThrow("invalid response");
});

it("rejects receipt/timeline phase inconsistencies", () => {
  const family = brief("family-review");
  const complete = brief("plan-ready");
  expect(() => parseBrief({ ...family, receipt: complete.receipt })).toThrow("invalid response");
  expect(() => parseBrief({ ...complete, timeline: null })).toThrow("invalid response");
  expect(() => parseBrief({ ...family, decision_requirements: { ...family.decision_requirements, required_trade_offs: [] } })).toThrow("invalid response");
});

it.each([
  ["requirements route is not eligible", (value: ReturnType<typeof brief>) => { value.decision_requirements.eligible_route_id = "71000000-0000-0000-0000-000000000009"; }],
  ["receipt route differs", (value: ReturnType<typeof brief>) => { value.receipt!.selected_route_id = "71000000-0000-0000-0000-000000000009"; }],
  ["receipt range excludes pinned cost", (value: ReturnType<typeof brief>) => { value.receipt!.accepted_budget_min_minor = 36_000_000; }],
  ["receipt exceeds hard ceiling", (value: ReturnType<typeof brief>) => { value.receipt!.accepted_budget_max_minor = 41_000_000; }],
  ["receipt trade-offs differ", (value: ReturnType<typeof brief>) => { value.receipt!.accepted_trade_offs = []; }],
  ["timeline country differs", (value: ReturnType<typeof brief>) => { value.timeline!.country = "japan"; }],
])("rejects cross-projection inconsistency: %s", (_name, mutate) => {
  const value = brief("plan-ready");
  mutate(value);
  expect(() => parseBrief(value)).toThrow("invalid response");
});

it("fingerprints canonical requests without storing their body", async () => {
  const first = await requestFingerprint({ b: 2, a: 1 });
  const second = await requestFingerprint({ a: 1, b: 2 });
  expect(first).toBe(second);
  expect(first).toMatch(/^[0-9a-f]{64}$/);
});
