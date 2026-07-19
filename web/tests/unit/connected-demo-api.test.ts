// @vitest-environment node
import { afterEach, expect, it, vi } from "vitest";

import { createConnectedDemoApi } from "../../lib/connected-demo/api";
import { parseBrief, parseLedger, parseTask } from "../../lib/connected-demo/contracts";
import type { SkillLeafBindingV1, StandaloneTaskProjection } from "../../lib/connected-demo/contracts";
import { requestFingerprint } from "../../lib/connected-demo/idempotency";
import { CASE_ID, TASK_ID, brief, ledger, standaloneTask } from "./connected-demo-test-data";

afterEach(() => vi.unstubAllGlobals());

it("keeps the static standalone runtime binding contract as narrow as its parser", () => {
  // @ts-expect-error operation leaves do not permit adapter cross-products
  const invalidLeaf: SkillLeafBindingV1 = {
    operation: "generate_planning_run_v1",
    adapter_id: "governed_mixed_planning",
    adapter_version: "dra-mixed-v1",
  };
  // @ts-expect-error standalone runtime pins and leaves are both null or both present
  const partialBinding: StandaloneTaskProjection = {
    ...parseTask(standaloneTask()),
    skill_pin: null,
  };
  expect([invalidLeaf, partialBinding]).toHaveLength(2);
});

it("wires exact standalone Task create, get, and cancel requests through validation", async () => {
  const createBody = {
    schema_version: 1 as const,
    operation: "generate_planning_run_v1" as const,
    expected_case_revision: 1,
    source_pack_id: "50000000-0000-0000-0000-000000000001",
    source_pack_version: 1,
    policy_version: "m3a-policy-v1" as const,
  };
  const cancelBody = { schema_version: 1 as const, expected_row_version: 1 };
  const responses = [
    standaloneTask(false),
    standaloneTask(),
    { ...standaloneTask(false), row_version: 2, status: "cancelled", public_code: "cancelled" },
  ];
  const requests: Array<[RequestInfo | URL, RequestInit | undefined]> = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    requests.push([input, init]);
    return Response.json(responses[fetchMock.mock.calls.length - 1]);
  });
  vi.stubGlobal("fetch", fetchMock);
  const api = createConnectedDemoApi();

  await expect(api.createTask(CASE_ID, createBody, "csrf", "create-key")).resolves.toEqual(responses[0]);
  await expect(api.task(TASK_ID)).resolves.toEqual(responses[1]);
  await expect(api.cancelTask(TASK_ID, cancelBody, "csrf", "cancel-key")).resolves.toEqual(responses[2]);

  expect(fetchMock).toHaveBeenCalledTimes(3);
  expect(requests[0][0]).toBe(`/api/demo/cases/${CASE_ID}/agent-tasks`);
  expect(requests[0][1]).toMatchObject({ method: "POST", body: JSON.stringify(createBody), cache: "no-store" });
  expect(new Headers(requests[0][1]?.headers)).toEqual(new Headers({ "Content-Type": "application/json", "X-CSRF-Token": "csrf", "Idempotency-Key": "create-key" }));
  expect(requests[1][0]).toBe(`/api/demo/tasks/${TASK_ID}`);
  expect(requests[1][1]).toEqual({ cache: "no-store" });
  expect(requests[2][0]).toBe(`/api/demo/tasks/${TASK_ID}/cancel`);
  expect(requests[2][1]).toMatchObject({ method: "POST", body: JSON.stringify(cancelBody), cache: "no-store" });
  expect(new Headers(requests[2][1]?.headers)).toEqual(new Headers({ "Content-Type": "application/json", "X-CSRF-Token": "csrf", "Idempotency-Key": "cancel-key" }));
});

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
  ["leaf without pin", () => ({ ...standaloneTask(), skill_pin: null })],
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
