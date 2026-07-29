import { act, renderHook } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import {
  loadPlanExecutionEnvelope,
  savePlanExecutionEnvelope,
  type PlanExecutionEnvelopeV1,
} from "../../lib/plan-execution/session-storage";
import { usePlanExecution } from "../../lib/plan-execution/use-plan-execution";
import { contextFixture, viewFixture } from "./plan-execution-contracts.test";

afterEach(() => {
  sessionStorage.clear();
  vi.restoreAllMocks();
});

const envelope: PlanExecutionEnvelopeV1 = {
  schema_version: 1, journey: "plan-execution", role: "student",
  caseId: contextFixture.case_id, timelinePlanId: contextFixture.timeline_plan_id,
  executionId: null, executionVersion: null, checkpointId: null,
  checkpointVersion: null, lastReceiptId: null, mutations: {},
};

it("replaces one bounded envelope and never persists session authority", () => {
  savePlanExecutionEnvelope(envelope);
  savePlanExecutionEnvelope({ ...envelope, role: "parent", lastReceiptId: contextFixture.case_id });
  expect(sessionStorage).toHaveLength(1);
  expect(loadPlanExecutionEnvelope()?.role).toBe("parent");
  const raw = JSON.stringify(loadPlanExecutionEnvelope());
  expect(raw).not.toContain("csrf");
  expect(raw).not.toContain("attestation_body");
  expect(raw).not.toContain("due_date");
});

it("persists the operation, captures its receipt, then performs a fresh GET", async () => {
  const calls: string[] = [];
  const view = viewFixture();
  const api = {
    bootstrap: vi.fn(async () => ({ csrf_token: "bootstrap" })),
    mint: vi.fn(async () => ({ role: "student" as const, csrf_token: "csrf" })),
    revoke: vi.fn(async () => undefined),
    context: vi.fn(async () => contextFixture),
    read: vi.fn(async () => { calls.push("GET"); return view; }),
    start: vi.fn(async () => {
      calls.push("POST");
      expect(loadPlanExecutionEnvelope()?.mutations.start).toBeDefined();
      return {
        schema_version: 1 as const, receipt_id: contextFixture.case_id,
        operation: "start" as const, result_kind: "timeline_execution_started" as const,
        result_id: contextFixture.case_id, execution_id: contextFixture.case_id,
        checkpoint_id: null, before_execution_version: null, after_execution_version: 1,
        before_checkpoint_version: null, after_checkpoint_version: null,
        created_at: "2026-07-29T00:00:00Z",
      };
    }),
    attest: vi.fn(), verify: vi.fn(), reassess: vi.fn(),
  };
  const { result } = renderHook(() => usePlanExecution(api));
  await act(async () => result.current.connect("student"));
  await act(async () => result.current.start());
  expect(calls).toEqual(["POST", "GET"]);
  expect(loadPlanExecutionEnvelope()?.lastReceiptId).toBe(contextFixture.case_id);
});
