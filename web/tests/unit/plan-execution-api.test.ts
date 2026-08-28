import { afterEach, expect, it, vi } from "vitest";

import {
  createPlanExecutionApi,
  isPlanExecutionSessionLoss,
  isPlanExecutionStaleAuthority,
  PlanExecutionApiError,
} from "../../lib/plan-execution/api";
import { connectedContextFixture } from "./plan-execution-contracts.test";

afterEach(() => {
  vi.unstubAllGlobals();
});

it("preserves the exact public status and problem code for classification", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(
    { code: "authentication_failed" },
    { status: 401 },
  )));

  const error = await createPlanExecutionApi().context().catch((caught: unknown) => caught);

  expect(error).toMatchObject({
    status: 401,
    code: "authentication_failed",
    message: "authentication_failed",
  });
});

it("keeps session-loss and stale-authority problem codes mutually exclusive", () => {
  for (const error of [
    new PlanExecutionApiError(401, "request_failed"),
    new PlanExecutionApiError(409, "authentication_failed"),
    new Error("bff_session_recovery_required"),
    new Error("session_changed"),
  ]) {
    expect(isPlanExecutionSessionLoss(error)).toBe(true);
    expect(isPlanExecutionStaleAuthority(error)).toBe(false);
  }
  for (const code of [
    "stale_execution_version",
    "stale_checkpoint_version",
    "checkpoint_not_current",
    "execution_completed",
  ]) {
    const error = new PlanExecutionApiError(409, code);
    expect(isPlanExecutionSessionLoss(error)).toBe(false);
    expect(isPlanExecutionStaleAuthority(error)).toBe(true);
  }
  const transport = new PlanExecutionApiError(503, "bff_upstream_unavailable");
  expect(isPlanExecutionSessionLoss(transport)).toBe(false);
  expect(isPlanExecutionStaleAuthority(transport)).toBe(false);
});

it("uses only the connected case identity at the authority seam", async () => {
  const caseId = connectedContextFixture.case_id;
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    if (url === "/api/demo/sessions") return Response.json({ role: "student", csrf_token: "csrf" });
    return Response.json(connectedContextFixture);
  }));
  const api = createPlanExecutionApi({ kind: "connected", caseId });

  await api.mint("student", "bootstrap-csrf");
  await expect(api.context()).resolves.toEqual(connectedContextFixture);
  expect(calls[0]?.init?.body).toContain('"demo_actor":"student"');
  expect(calls.at(-1)?.url).toBe(`/api/demo/cases/${caseId}/plan-execution-context`);
  expect(calls.map(({ url }) => url)).not.toContain("/api/demo/plan-execution-context");
});
