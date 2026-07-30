import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import {
  PlanExecutionApiError,
} from "../../lib/plan-execution/api";
import type { TimelineMutationReceipt } from "../../lib/plan-execution/contracts";
import {
  loadPlanExecutionEnvelope,
  savePlanExecutionEnvelope,
  type PlanExecutionEnvelopeV1,
} from "../../lib/plan-execution/session-storage";
import { usePlanExecution } from "../../lib/plan-execution/use-plan-execution";
import { contextFixture, viewFixture } from "./plan-execution-contracts.test";

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((accept) => {
    resolve = accept;
  });
  return { promise, resolve };
}

function startReceipt(
  overrides: Partial<TimelineMutationReceipt> = {},
): TimelineMutationReceipt {
  const view = viewFixture();
  return {
    schema_version: 1,
    receipt_id: contextFixture.case_id,
    operation: "start",
    result_kind: "timeline_execution_started",
    result_id: view.execution.execution_id,
    execution_id: view.execution.execution_id,
    checkpoint_id: null,
    before_execution_version: null,
    after_execution_version: 1,
    before_checkpoint_version: null,
    after_checkpoint_version: null,
    created_at: "2026-07-29T00:00:00Z",
    ...overrides,
  };
}

function attestationReceipt(
  overrides: Partial<TimelineMutationReceipt> = {},
): TimelineMutationReceipt {
  const view = viewFixture();
  return {
    schema_version: 1,
    receipt_id: contextFixture.case_id,
    operation: "attest",
    result_kind: "timeline_checkpoint_attested",
    result_id: contextFixture.decision_receipt_id,
    execution_id: view.execution.execution_id,
    checkpoint_id: view.checkpoints[0].checkpoint_id,
    before_execution_version: 1,
    after_execution_version: 2,
    before_checkpoint_version: 1,
    after_checkpoint_version: 2,
    created_at: "2026-07-29T00:00:00Z",
    ...overrides,
  };
}

function laterAttestationView() {
  const view = viewFixture("awaiting_advisor");
  view.execution = { ...view.execution, row_version: 3 };
  view.checkpoints[0] = { ...view.checkpoints[0], row_version: 3 };
  view.current_checkpoint = view.checkpoints[0];
  view.current_action = {
    ...view.current_action,
    execution_version: 3,
    checkpoint_version: 3,
  };
  return view;
}

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
  let started = false;
  const api = {
    bootstrap: vi.fn(async () => ({ csrf_token: "bootstrap" })),
    mint: vi.fn(async () => ({ role: "student" as const, csrf_token: "csrf" })),
    revoke: vi.fn(async () => undefined),
    context: vi.fn(async () => ({
      ...contextFixture,
      execution_id: started ? view.execution.execution_id : null,
    })),
    read: vi.fn(async () => { calls.push("GET"); return view; }),
    start: vi.fn(async () => {
      calls.push("POST");
      started = true;
      expect(loadPlanExecutionEnvelope()?.mutations.start).toBeDefined();
      return startReceipt();
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
  const receipt = startReceipt();
  const api = {
    bootstrap: vi.fn(async () => ({ csrf_token: "bootstrap" })),
    mint: vi.fn(async () => ({ role: "student" as const, csrf_token: "csrf" })),
    revoke: vi.fn(async () => undefined),
    context: vi.fn(async () => ({
      ...contextFixture,
      execution_id: attempt === 0 ? null : view.execution.execution_id,
    })),
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

it("retains the exact pending replay across a post-receipt GET transport failure", async () => {
  const calls: Array<{ body: unknown; csrf: string; key: string }> = [];
  const view = viewFixture();
  const receipt = startReceipt();
  let startAttempts = 0;
  let readAttempts = 0;
  const api = {
    bootstrap: vi.fn(async () => ({ csrf_token: "bootstrap" })),
    mint: vi.fn(async () => ({ role: "student" as const, csrf_token: "csrf" })),
    revoke: vi.fn(async () => undefined),
    context: vi.fn(async () => ({
      ...contextFixture,
      execution_id: startAttempts === 0 ? null : view.execution.execution_id,
    })),
    read: vi.fn(async () => {
      readAttempts += 1;
      if (readAttempts === 1) {
        throw new PlanExecutionApiError(503, "bff_upstream_unavailable");
      }
      return view;
    }),
    start: vi.fn(async (_id: string, body: unknown, csrf: string, key: string) => {
      calls.push({ body, csrf, key });
      startAttempts += 1;
      if (startAttempts === 1) throw new Error("request_failed");
      return receipt;
    }),
    attest: vi.fn(), verify: vi.fn(), reassess: vi.fn(),
  };
  const { result } = renderHook(() => usePlanExecution(api));
  await act(async () => result.current.connect("student"));
  await act(async () => result.current.start());
  const exactSlot = loadPlanExecutionEnvelope()?.mutations.start;

  await act(async () => result.current.recover());

  expect(result.current.state.value).toBe("recoverable_error");
  expect(calls).toHaveLength(2);
  expect(calls[1]).toEqual(calls[0]);
  expect(loadPlanExecutionEnvelope()?.mutations.start).toEqual(exactSlot);

  await act(async () => result.current.recover());

  expect(calls).toHaveLength(3);
  expect(calls[2]).toEqual(calls[0]);
  expect(result.current.state.receipt).toEqual(receipt);
  expect(loadPlanExecutionEnvelope()?.mutations.start).toBeUndefined();
});

it("reconciles an exact pending receipt with a newer same-execution GET", async () => {
  const initial = viewFixture();
  const authoritative = laterAttestationView();
  const receipt = attestationReceipt();
  const calls: Array<{ body: unknown; key: string }> = [];
  let readAttempts = 0;
  const api = {
    bootstrap: vi.fn(async () => ({ csrf_token: "bootstrap" })),
    mint: vi.fn(async () => ({ role: "student" as const, csrf_token: "csrf" })),
    revoke: vi.fn(async () => undefined),
    context: vi.fn(async () => ({
      ...contextFixture,
      execution_id: initial.execution.execution_id,
    })),
    read: vi.fn(async () => {
      readAttempts += 1;
      return readAttempts === 1 ? initial : authoritative;
    }),
    start: vi.fn(),
    attest: vi.fn(async (
      _id: string,
      body: unknown,
      _csrf: string,
      key: string,
    ) => {
      calls.push({ body, key });
      if (calls.length === 1) throw new Error("request_failed");
      return receipt;
    }),
    verify: vi.fn(), reassess: vi.fn(),
  };
  const { result } = renderHook(() => usePlanExecution(api));
  await act(async () => result.current.connect("student"));
  await act(async () => result.current.attest());
  const exactSlot = loadPlanExecutionEnvelope()?.mutations.attest;

  await act(async () => result.current.recover());

  expect(calls).toHaveLength(2);
  expect(calls[1]).toEqual(calls[0]);
  expect(result.current.state.value).toBe("awaiting_advisor");
  expect(result.current.state.receipt).toEqual(receipt);
  expect(result.current.state.view).toEqual(authoritative);
  expect(loadPlanExecutionEnvelope()?.lastReceiptId).toBe(receipt.receipt_id);
  expect(loadPlanExecutionEnvelope()?.mutations.attest).toBeUndefined();
  expect(exactSlot).toBeDefined();
});

it("reconciles a normal mutation receipt with a newer same-execution GET", async () => {
  const initial = viewFixture();
  const authoritative = laterAttestationView();
  const receipt = attestationReceipt();
  const keys: string[] = [];
  let readAttempts = 0;
  const api = {
    bootstrap: vi.fn(async () => ({ csrf_token: "bootstrap" })),
    mint: vi.fn(async () => ({ role: "student" as const, csrf_token: "csrf" })),
    revoke: vi.fn(async () => undefined),
    context: vi.fn(async () => ({
      ...contextFixture,
      execution_id: initial.execution.execution_id,
    })),
    read: vi.fn(async () => {
      readAttempts += 1;
      return readAttempts === 1 ? initial : authoritative;
    }),
    start: vi.fn(),
    attest: vi.fn(async (
      _id: string,
      _body: unknown,
      _csrf: string,
      key: string,
    ) => {
      keys.push(key);
      return receipt;
    }),
    verify: vi.fn(), reassess: vi.fn(),
  };
  const { result } = renderHook(() => usePlanExecution(api));
  await act(async () => result.current.connect("student"));

  await act(async () => result.current.attest());

  expect(keys).toHaveLength(1);
  expect(result.current.state.value).toBe("awaiting_advisor");
  expect(result.current.state.receipt).toEqual(receipt);
  expect(result.current.state.view).toEqual(authoritative);
  expect(loadPlanExecutionEnvelope()?.mutations.attest).toBeUndefined();
});

it.each([
  {
    name: "operation and result kind",
    overrides: {
      operation: "attest" as const,
      result_kind: "timeline_checkpoint_attested" as const,
    },
  },
  {
    name: "execution",
    overrides: { execution_id: contextFixture.case_id },
  },
  {
    name: "start checkpoint",
    overrides: { checkpoint_id: viewFixture().checkpoints[0].checkpoint_id },
  },
])("fails closed on a pending replay receipt with mismatched $name identity", async ({
  overrides,
}) => {
  const view = viewFixture();
  const receipt = startReceipt(overrides);
  let startAttempts = 0;
  const keys: string[] = [];
  const api = {
    bootstrap: vi.fn(async () => ({ csrf_token: "bootstrap" })),
    mint: vi.fn(async () => ({ role: "student" as const, csrf_token: "csrf" })),
    revoke: vi.fn(async () => undefined),
    context: vi.fn(async () => ({
      ...contextFixture,
      execution_id: startAttempts === 0 ? null : view.execution.execution_id,
    })),
    read: vi.fn(async () => view),
    start: vi.fn(async (_id: string, _body: unknown, _csrf: string, key: string) => {
      keys.push(key);
      startAttempts += 1;
      if (startAttempts === 1) throw new Error("request_failed");
      return receipt;
    }),
    attest: vi.fn(), verify: vi.fn(), reassess: vi.fn(),
  };
  const { result } = renderHook(() => usePlanExecution(api));
  await act(async () => result.current.connect("student"));
  await act(async () => result.current.start());
  await act(async () => result.current.recover());

  expect(result.current.state.value).toBe("session_changed");
  expect(result.current.state.receipt).toBeNull();
  expect(result.current.state.view).toBeNull();
  expect(loadPlanExecutionEnvelope()?.mutations.start).toBeUndefined();
  expect(keys).toEqual([keys[0], keys[0]]);

  await act(async () => result.current.recover());
  expect(api.start).toHaveBeenCalledTimes(2);
});

it.each([
  {
    name: "non-increasing execution version",
    overrides: { after_execution_version: 1 },
  },
  {
    name: "future execution version",
    overrides: { after_execution_version: 4 },
  },
  {
    name: "non-increasing checkpoint version",
    overrides: { after_checkpoint_version: 1 },
  },
  {
    name: "future checkpoint version",
    overrides: { after_checkpoint_version: 4 },
  },
])("fails closed on a pending replay receipt with $name", async ({
  overrides,
}) => {
  const initial = viewFixture();
  const authoritative = laterAttestationView();
  const receipt = attestationReceipt({
    result_id: authoritative.latest_attestation!.attestation_id,
    ...overrides,
  });
  let readAttempts = 0;
  let attestAttempts = 0;
  const api = {
    bootstrap: vi.fn(async () => ({ csrf_token: "bootstrap" })),
    mint: vi.fn(async () => ({ role: "student" as const, csrf_token: "csrf" })),
    revoke: vi.fn(async () => undefined),
    context: vi.fn(async () => ({
      ...contextFixture,
      execution_id: initial.execution.execution_id,
    })),
    read: vi.fn(async () => {
      readAttempts += 1;
      return readAttempts === 1 ? initial : authoritative;
    }),
    start: vi.fn(),
    attest: vi.fn(async () => {
      attestAttempts += 1;
      if (attestAttempts === 1) throw new Error("request_failed");
      return receipt;
    }),
    verify: vi.fn(), reassess: vi.fn(),
  };
  const { result } = renderHook(() => usePlanExecution(api));
  await act(async () => result.current.connect("student"));
  await act(async () => result.current.attest());

  await act(async () => result.current.recover());

  expect(result.current.state.value).toBe("session_changed");
  expect(result.current.state.receipt).toBeNull();
  expect(result.current.state.view).toEqual(initial);
  expect(loadPlanExecutionEnvelope()?.mutations.attest).toBeUndefined();
});

it("fails closed when a checkpoint replay receipt does not bind its body and fresh result", async () => {
  const initial = viewFixture();
  const authoritative = viewFixture("awaiting_advisor");
  const receipt: TimelineMutationReceipt = {
    schema_version: 1,
    receipt_id: contextFixture.case_id,
    operation: "attest",
    result_kind: "timeline_checkpoint_attested",
    result_id: authoritative.latest_attestation!.attestation_id,
    execution_id: authoritative.execution.execution_id,
    checkpoint_id: authoritative.checkpoints[1].checkpoint_id,
    before_execution_version: 1,
    after_execution_version: 2,
    before_checkpoint_version: 1,
    after_checkpoint_version: 2,
    created_at: "2026-07-29T00:00:00Z",
  };
  let readAttempts = 0;
  let attestAttempts = 0;
  const keys: string[] = [];
  const liveContext = {
    ...contextFixture,
    execution_id: initial.execution.execution_id,
  };
  const api = {
    bootstrap: vi.fn(async () => ({ csrf_token: "bootstrap" })),
    mint: vi.fn(async () => ({ role: "student" as const, csrf_token: "csrf" })),
    revoke: vi.fn(async () => undefined),
    context: vi.fn(async () => liveContext),
    read: vi.fn(async () => {
      readAttempts += 1;
      return readAttempts === 1 ? initial : authoritative;
    }),
    start: vi.fn(),
    attest: vi.fn(async (
      _id: string,
      _body: unknown,
      _csrf: string,
      key: string,
    ) => {
      keys.push(key);
      attestAttempts += 1;
      if (attestAttempts === 1) throw new Error("request_failed");
      return receipt;
    }),
    verify: vi.fn(), reassess: vi.fn(),
  };
  const { result } = renderHook(() => usePlanExecution(api));
  await act(async () => result.current.connect("student"));
  await act(async () => result.current.attest());
  await act(async () => result.current.recover());

  expect(result.current.state.value).toBe("session_changed");
  expect(result.current.state.receipt).toBeNull();
  expect(result.current.state.view).toEqual(initial);
  expect(loadPlanExecutionEnvelope()?.mutations.attest).toBeUndefined();
  expect(keys).toEqual([keys[0], keys[0]]);
});

it("closes a pending replay when the shared session rotates during its read", async () => {
  const delayedRead = deferred<ReturnType<typeof viewFixture>>();
  const view = viewFixture();
  const receipt = {
    schema_version: 1 as const, receipt_id: contextFixture.case_id,
    operation: "start" as const, result_kind: "timeline_execution_started" as const,
    result_id: contextFixture.case_id, execution_id: view.execution.execution_id,
    checkpoint_id: null, before_execution_version: null, after_execution_version: 1,
    before_checkpoint_version: null, after_checkpoint_version: null,
    created_at: "2026-07-29T00:00:00Z",
  };
  let startAttempts = 0;
  let contextReads = 0;
  let activeRole: "student" | "advisor" = "student";
  const api = {
    bootstrap: vi.fn(async () => ({ csrf_token: "bootstrap" })),
    mint: vi.fn(async () => ({ role: "student" as const, csrf_token: "csrf" })),
    revoke: vi.fn(async () => undefined),
    context: vi.fn(async () => {
      contextReads += 1;
      return {
        ...contextFixture,
        execution_id: contextReads === 1 ? null : view.execution.execution_id,
        active_role: activeRole,
      };
    }),
    read: vi.fn(async () => delayedRead.promise),
    start: vi.fn(async () => {
      startAttempts += 1;
      if (startAttempts === 1) throw new Error("request_failed");
      return receipt;
    }),
    attest: vi.fn(), verify: vi.fn(), reassess: vi.fn(),
  };
  const { result } = renderHook(() => usePlanExecution(api));
  await act(async () => result.current.connect("student"));
  await act(async () => result.current.start());

  let recovery!: Promise<void>;
  await act(async () => {
    recovery = result.current.recover();
    await Promise.resolve();
  });
  await waitFor(() => expect(api.read).toHaveBeenCalledTimes(1));
  activeRole = "advisor";
  delayedRead.resolve(view);
  await act(async () => recovery);

  expect(result.current.state.value).toBe("session_changed");
  expect(result.current.state.view).toBeNull();
  expect(loadPlanExecutionEnvelope()?.mutations.start).toBeUndefined();
  expect(loadPlanExecutionEnvelope()?.lastReceiptId).toBeNull();
  await act(async () => result.current.start());
  expect(api.start).toHaveBeenCalledTimes(2);
});

it("closes a pending replay 401 and never continues to its read", async () => {
  let startAttempts = 0;
  const api = {
    bootstrap: vi.fn(async () => ({ csrf_token: "bootstrap" })),
    mint: vi.fn(async () => ({ role: "student" as const, csrf_token: "csrf" })),
    revoke: vi.fn(async () => undefined),
    context: vi.fn(async () => contextFixture),
    read: vi.fn(async () => viewFixture()),
    start: vi.fn(async () => {
      startAttempts += 1;
      if (startAttempts === 1) throw new Error("request_failed");
      throw new PlanExecutionApiError(401, "request_failed");
    }),
    attest: vi.fn(), verify: vi.fn(), reassess: vi.fn(),
  };
  const { result } = renderHook(() => usePlanExecution(api));
  await act(async () => result.current.connect("student"));
  await act(async () => result.current.start());
  await act(async () => result.current.recover());

  expect(result.current.state.value).toBe("session_changed");
  expect(api.read).not.toHaveBeenCalled();
  expect(loadPlanExecutionEnvelope()?.mutations.start).toBeUndefined();
  await act(async () => result.current.recover());
  expect(api.start).toHaveBeenCalledTimes(2);
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
  expect(order).toEqual([
    "context", "bootstrap", "bootstrap", "mint", "context", "context",
  ]);
  expect(api.mint).toHaveBeenCalledWith("student", "fresh-bootstrap", "happy");
  expect(loadPlanExecutionEnvelope()?.executionId).toBe(completed.execution.execution_id);
});

it("closes a stored-envelope post-mint read 401 as session_changed", async () => {
  const view = viewFixture();
  const restoredContext = {
    ...contextFixture,
    execution_id: view.execution.execution_id,
  };
  savePlanExecutionEnvelope({
    ...envelope,
    executionId: view.execution.execution_id,
  });
  const api = {
    bootstrap: vi.fn(async () => ({ csrf_token: "bootstrap" })),
    mint: vi.fn(async () => ({ role: "student" as const, csrf_token: "csrf" })),
    revoke: vi.fn(async () => undefined),
    context: vi.fn(async () => restoredContext),
    read: vi.fn(async () => {
      throw new PlanExecutionApiError(401, "request_failed");
    }),
    start: vi.fn(), attest: vi.fn(), verify: vi.fn(), reassess: vi.fn(),
  };
  const { result } = renderHook(() => usePlanExecution(api));

  await waitFor(() => expect(result.current.state.value).toBe("session_changed"));
  expect(api.bootstrap).toHaveBeenCalledTimes(1);
  expect(api.mint).toHaveBeenCalledTimes(1);
  expect(api.start).not.toHaveBeenCalled();
});

it("does not rotate while the initial authority read holds the generation lock", async () => {
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

  expect(result.current.state.context?.active_role).toBe("student");
  expect(api.mint).toHaveBeenCalledTimes(1);
});

it("holds one atomic role rotation lock and emits no stale mutation", async () => {
  const rotation = deferred<{ role: "advisor"; csrf_token: string }>();
  let activeRole: "student" | "advisor" = "student";
  const api = {
    bootstrap: vi.fn(async () => ({ csrf_token: "bootstrap" })),
    mint: vi.fn(async (role: "student" | "advisor" | "parent") => {
      if (role === "student") return { role, csrf_token: "csrf-student" };
      return rotation.promise;
    }),
    revoke: vi.fn(async () => undefined),
    context: vi.fn(async () => ({ ...contextFixture, active_role: activeRole })),
    read: vi.fn(async () => viewFixture()),
    start: vi.fn(), attest: vi.fn(), verify: vi.fn(), reassess: vi.fn(),
  };
  const { result } = renderHook(() => usePlanExecution(api));
  await act(async () => result.current.connect("student"));

  let first!: Promise<void>;
  await act(async () => {
    first = result.current.switchRole("advisor");
    await Promise.resolve();
  });
  expect(result.current.busy).toBe(true);
  await act(async () => {
    await Promise.all([
      result.current.switchRole("parent"),
      result.current.start(),
    ]);
  });
  expect(api.mint).toHaveBeenCalledTimes(2);
  expect(api.revoke).not.toHaveBeenCalled();
  expect(api.start).not.toHaveBeenCalled();
  expect(result.current.busy).toBe(true);

  activeRole = "advisor";
  rotation.resolve({ role: "advisor", csrf_token: "csrf-advisor" });
  await act(async () => first);
  expect(result.current.busy).toBe(false);
  expect(result.current.state.context?.active_role).toBe("advisor");
  expect(api.mint).toHaveBeenLastCalledWith("advisor", "csrf-student", "happy");
});

it("closes a revoked mutation as session_changed without a later read", async () => {
  const api = {
    bootstrap: vi.fn(async () => ({ csrf_token: "bootstrap" })),
    mint: vi.fn(async () => ({ role: "student" as const, csrf_token: "csrf" })),
    revoke: vi.fn(async () => undefined),
    context: vi.fn(async () => contextFixture),
    read: vi.fn(async () => viewFixture()),
    start: vi.fn(async () => { throw new Error("authentication_failed"); }),
    attest: vi.fn(), verify: vi.fn(), reassess: vi.fn(),
  };
  const { result } = renderHook(() => usePlanExecution(api));
  await act(async () => result.current.connect("student"));
  await act(async () => result.current.start());

  expect(result.current.state.value).toBe("session_changed");
  expect(api.read).not.toHaveBeenCalled();
  expect(loadPlanExecutionEnvelope()?.mutations.start).toBeUndefined();
});

it("closes an in-flight revoked rotation without destroying prior authority", async () => {
  const api = {
    bootstrap: vi.fn(async () => ({ csrf_token: "bootstrap" })),
    mint: vi.fn()
      .mockResolvedValueOnce({ role: "student" as const, csrf_token: "csrf" })
      .mockRejectedValueOnce(new Error("authentication_failed")),
    revoke: vi.fn(async () => undefined),
    context: vi.fn(async () => contextFixture),
    read: vi.fn(async () => viewFixture()),
    start: vi.fn(), attest: vi.fn(), verify: vi.fn(), reassess: vi.fn(),
  };
  const { result } = renderHook(() => usePlanExecution(api));
  await act(async () => result.current.connect("student"));
  await act(async () => result.current.switchRole("advisor"));

  expect(result.current.state.value).toBe("session_changed");
  expect(api.revoke).not.toHaveBeenCalled();
  expect(api.bootstrap).toHaveBeenCalledTimes(1);
  expect(result.current.busy).toBe(false);
});

it("refreshes rejected stale versions instead of replaying a known rejection", async () => {
  const fresh = viewFixture();
  fresh.execution.row_version = 2;
  fresh.current_checkpoint!.row_version = 2;
  fresh.checkpoints[0].row_version = 2;
  const api = {
    bootstrap: vi.fn(async () => ({ csrf_token: "bootstrap" })),
    mint: vi.fn(async () => ({ role: "student" as const, csrf_token: "csrf" })),
    revoke: vi.fn(async () => undefined),
    context: vi.fn(async () => ({ ...contextFixture, execution_id: fresh.execution.execution_id })),
    read: vi.fn(async () => fresh),
    start: vi.fn(async () => { throw new Error("stale_execution_version"); }),
    attest: vi.fn(), verify: vi.fn(), reassess: vi.fn(),
  };
  const { result } = renderHook(() => usePlanExecution(api));
  await act(async () => result.current.connect("student"));
  await act(async () => result.current.start());

  expect(api.start).toHaveBeenCalledTimes(1);
  expect(api.read).toHaveBeenCalledTimes(2);
  expect(result.current.state.value).toBe("checkpoint_active");
  expect(result.current.state.view?.execution.row_version).toBe(2);
  expect(loadPlanExecutionEnvelope()?.mutations.start).toBeUndefined();
});

it("closes a stale-authority refresh 401 without replaying the rejected mutation", async () => {
  const api = {
    bootstrap: vi.fn(async () => ({ csrf_token: "bootstrap" })),
    mint: vi.fn(async () => ({ role: "student" as const, csrf_token: "csrf" })),
    revoke: vi.fn(async () => undefined),
    context: vi.fn()
      .mockResolvedValueOnce(contextFixture)
      .mockRejectedValueOnce(new PlanExecutionApiError(401, "request_failed")),
    read: vi.fn(async () => viewFixture()),
    start: vi.fn(async () => {
      throw new PlanExecutionApiError(409, "stale_execution_version");
    }),
    attest: vi.fn(), verify: vi.fn(), reassess: vi.fn(),
  };
  const { result } = renderHook(() => usePlanExecution(api));
  await act(async () => result.current.connect("student"));

  const escaped = await act(async () =>
    result.current.start().then(() => null, (error: unknown) => error));

  expect(escaped).toBeNull();
  expect(result.current.state.value).toBe("session_changed");
  expect(loadPlanExecutionEnvelope()?.mutations.start).toBeUndefined();
  expect(api.start).toHaveBeenCalledTimes(1);
  expect(api.read).not.toHaveBeenCalled();
});

it("keeps a stale-authority refresh transport failure recoverable", async () => {
  const api = {
    bootstrap: vi.fn(async () => ({ csrf_token: "bootstrap" })),
    mint: vi.fn(async () => ({ role: "student" as const, csrf_token: "csrf" })),
    revoke: vi.fn(async () => undefined),
    context: vi.fn()
      .mockResolvedValueOnce(contextFixture)
      .mockRejectedValueOnce(new PlanExecutionApiError(
        503,
        "bff_upstream_unavailable",
      )),
    read: vi.fn(async () => viewFixture()),
    start: vi.fn(async () => {
      throw new PlanExecutionApiError(409, "stale_execution_version");
    }),
    attest: vi.fn(), verify: vi.fn(), reassess: vi.fn(),
  };
  const { result } = renderHook(() => usePlanExecution(api));
  await act(async () => result.current.connect("student"));

  const escaped = await act(async () =>
    result.current.start().then(() => null, (error: unknown) => error));

  expect(escaped).toBeNull();
  expect(result.current.state.value).toBe("recoverable_error");
  expect(result.current.state.error).toBe("bff_upstream_unavailable");
  expect(result.current.state.operation).toBeNull();
  expect(loadPlanExecutionEnvelope()?.mutations.start).toBeUndefined();
  expect(api.start).toHaveBeenCalledTimes(1);
});

it("closes recovery when the shared session rotates while its read is in flight", async () => {
  const delayed = deferred<ReturnType<typeof viewFixture>>();
  const view = viewFixture();
  const restoredContext = {
    ...contextFixture,
    execution_id: view.execution.execution_id,
  };
  savePlanExecutionEnvelope({
    ...envelope,
    executionId: view.execution.execution_id,
  });
  let contextReads = 0;
  const api = {
    bootstrap: vi.fn(async () => ({ csrf_token: "bootstrap" })),
    mint: vi.fn(async () => ({ role: "student" as const, csrf_token: "csrf" })),
    revoke: vi.fn(async () => undefined),
    context: vi.fn(async () => {
      contextReads += 1;
      return {
        ...restoredContext,
        active_role: contextReads >= 3 ? "advisor" as const : "student" as const,
      };
    }),
    read: vi.fn(async () => delayed.promise),
    start: vi.fn(), attest: vi.fn(), verify: vi.fn(), reassess: vi.fn(),
  };
  const { result } = renderHook(() => usePlanExecution(api));
  await waitFor(() => expect(api.read).toHaveBeenCalledTimes(1));
  delayed.resolve(view);

  await waitFor(() => expect(result.current.state.value).toBe("session_changed"));
  expect(contextReads).toBe(3);
  expect(result.current.state.view).toBeNull();
  expect(api.start).not.toHaveBeenCalled();
});
