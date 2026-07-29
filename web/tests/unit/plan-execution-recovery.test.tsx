import { act, renderHook, waitFor } from "@testing-library/react";
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
  scenario: "happy",
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

it("fails closed and clears a cross-scenario recovery envelope", async () => {
  savePlanExecutionEnvelope({ ...envelope, scenario: "blocked" });
  const api = {
    bootstrap: vi.fn(), mint: vi.fn(), revoke: vi.fn(), context: vi.fn(),
    read: vi.fn(), start: vi.fn(), attest: vi.fn(), verify: vi.fn(), reassess: vi.fn(),
  };
  const { result } = renderHook(() => usePlanExecution(api, "happy"));

  await act(async () => result.current.recover());

  expect(result.current.state.value).toBe("recoverable_error");
  expect(loadPlanExecutionEnvelope()).toBeNull();
  expect(api.bootstrap).not.toHaveBeenCalled();
  expect(api.start).not.toHaveBeenCalled();
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

it("recovers a lost acknowledgement with the exact body, key, and live session", async () => {
  const calls: Array<{ body: unknown; csrf: string; key: string }> = [];
  let attempt = 0;
  const view = viewFixture();
  const receipt = {
    schema_version: 1 as const, receipt_id: contextFixture.case_id,
    operation: "start" as const, result_kind: "timeline_execution_started" as const,
    result_id: contextFixture.case_id, execution_id: contextFixture.case_id,
    checkpoint_id: null, before_execution_version: null, after_execution_version: 1,
    before_checkpoint_version: null, after_checkpoint_version: null,
    created_at: "2026-07-29T00:00:00Z",
  };
  const api = {
    bootstrap: vi.fn(async () => ({ csrf_token: "bootstrap" })),
    mint: vi.fn(async () => ({ role: "student" as const, csrf_token: "csrf" })),
    revoke: vi.fn(async () => undefined),
    context: vi.fn(async () => contextFixture),
    read: vi.fn(async () => view),
    start: vi.fn(async (_id: string, body: unknown, csrf: string, key: string) => {
      calls.push({ body, csrf, key });
      attempt += 1;
      if (attempt === 1) throw new Error("request_failed");
      return receipt;
    }),
    attest: vi.fn(), verify: vi.fn(), reassess: vi.fn(),
  };
  const { result } = renderHook(() => usePlanExecution(api));
  await act(async () => result.current.connect("student"));
  await act(async () => result.current.start());
  expect(result.current.state.value).toBe("recoverable_error");
  await act(async () => result.current.recover());

  expect(calls).toHaveLength(2);
  expect(calls[1]).toEqual(calls[0]);
  expect(api.bootstrap).toHaveBeenCalledTimes(1);
  expect(api.mint).toHaveBeenCalledTimes(1);
  expect(result.current.state.receipt).toEqual(receipt);
});

it("revalidates a stored Case before closing a residual session and minting fresh CSRF", async () => {
  const completed = viewFixture();
  completed.execution.state = "completed";
  completed.checkpoints = completed.checkpoints.map((checkpoint) => ({
    ...checkpoint,
    state: "verified",
  }));
  completed.current_checkpoint = null;
  completed.current_action = {
    schema_version: 1,
    code: "execution_completed",
    owner_role: "none",
    checkpoint_id: null,
    execution_version: completed.execution.row_version,
    checkpoint_version: null,
  };
  const restoredContext = {
    ...contextFixture,
    execution_id: completed.execution.execution_id,
  };
  savePlanExecutionEnvelope({
    ...envelope,
    executionId: completed.execution.execution_id,
  });
  const order: string[] = [];
  let bootstrapAttempt = 0;
  const api = {
    bootstrap: vi.fn(async () => {
      order.push("bootstrap");
      bootstrapAttempt += 1;
      if (bootstrapAttempt === 1) throw new Error("bff_session_recovery_required");
      return { csrf_token: "fresh-bootstrap" };
    }),
    mint: vi.fn(async () => {
      order.push("mint");
      return { role: "student" as const, csrf_token: "fresh-csrf" };
    }),
    revoke: vi.fn(async () => undefined),
    context: vi.fn(async () => {
      order.push("context");
      return restoredContext;
    }),
    read: vi.fn(async () => completed),
    start: vi.fn(), attest: vi.fn(), verify: vi.fn(), reassess: vi.fn(),
  };

  const { result } = renderHook(() => usePlanExecution(api));

  await waitFor(() => expect(result.current.state.value).toBe("execution_completed"));
  expect(order).toEqual(["context", "bootstrap", "bootstrap", "mint", "context"]);
  expect(api.mint).toHaveBeenCalledWith("student", "fresh-bootstrap", "happy");
  expect(loadPlanExecutionEnvelope()?.executionId).toBe(completed.execution.execution_id);
});

it("ignores a delayed response from an aborted controller generation", async () => {
  let resolveRead!: (value: ReturnType<typeof viewFixture>) => void;
  const delayedRead = new Promise<ReturnType<typeof viewFixture>>((resolve) => {
    resolveRead = resolve;
  });
  let reads = 0;
  let activeRole: "student" | "advisor" = "student";
  const api = {
    bootstrap: vi.fn(async () => ({ csrf_token: "bootstrap" })),
    mint: vi.fn(async (role: "student" | "advisor") => {
      activeRole = role;
      return { role, csrf_token: `csrf-${role}` };
    }),
    revoke: vi.fn(async () => undefined),
    context: vi.fn(async () => ({ ...contextFixture, active_role: activeRole })),
    read: vi.fn(async () => {
      reads += 1;
      return reads === 1 ? delayedRead : viewFixture();
    }),
    start: vi.fn(), attest: vi.fn(), verify: vi.fn(), reassess: vi.fn(),
  };
  const { result } = renderHook(() => usePlanExecution(api));
  await act(async () => {
    const first = result.current.connect("student");
    await Promise.resolve();
    const second = result.current.switchRole("advisor");
    resolveRead(viewFixture());
    await Promise.all([first, second]);
  });

  expect(result.current.state.context?.active_role).toBe("advisor");
});
