import { afterEach, expect, it, vi } from "vitest";

import {
  createPlanExecutionApi,
  isPlanExecutionSessionLoss,
  isPlanExecutionStaleAuthority,
  PlanExecutionApiError,
} from "../../lib/plan-execution/api";

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
