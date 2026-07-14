import { describe, expect, it } from "vitest";

import { demoReducer, type DemoDisplayState } from "../../lib/connected-demo/reducer";
import { brief, ledger } from "./connected-demo-test-data";

const taskReady = ledger("task-ready");
const activeLedger = ledger("active-task");
const reviewLedger = ledger("review-required");
const familyBrief = brief("family-review");

describe("connected demo reducer", () => {
  it("allows only authoritative walkthrough transitions", () => {
    let state: DemoDisplayState = { value: "bootstrapping" };
    state = demoReducer(state, { type: "ADVISOR_SESSION_READY", ledger: taskReady });
    expect(state.value).toBe("advisor_ready");
    state = demoReducer(state, { type: "CREATE_TASK" });
    expect(state.value).toBe("task_creating");
    state = demoReducer(state, { type: "TASK_ACCEPTED", taskId: "task" });
    expect(state.value).toBe("task_streaming");
    state = demoReducer(state, { type: "TASK_REFRESHED", ledger: reviewLedger, after: 2 });
    expect(state.value).toBe("advisor_review");
    state = demoReducer(state, { type: "REVIEW_SUBMIT" });
    state = demoReducer(state, { type: "REVIEW_ACCEPTED", caseId: "case" });
    expect(state.value).toBe("role_switching");
    state = demoReducer(state, { type: "PARENT_SESSION_READY", brief: familyBrief });
    expect(state.value).toBe("family_review");
  });

  it("fails closed on illegal promotion", () => {
    const state = demoReducer({ value: "bootstrapping" }, { type: "PARENT_SESSION_READY", brief: familyBrief });
    expect(state).toEqual({ value: "recoverable_error", code: "invalid_transition" });
  });

  it("keeps review-required monotonic across duplicate SSE refreshes", () => {
    const state = demoReducer(
      { value: "advisor_review", ledger: reviewLedger },
      { type: "TASK_REFRESHED", ledger: reviewLedger, after: 3 },
    );
    expect(state).toEqual({ value: "advisor_review", ledger: reviewLedger });
  });

  it("reconstructs every authoritative reload phase", () => {
    expect(demoReducer({ value: "bootstrapping" }, { type: "AUTHORITATIVE_RELOAD", ledger: taskReady }).value).toBe("advisor_ready");
    expect(demoReducer({ value: "bootstrapping" }, { type: "AUTHORITATIVE_RELOAD", ledger: activeLedger }).value).toBe("task_streaming");
    expect(demoReducer({ value: "bootstrapping" }, { type: "AUTHORITATIVE_RELOAD", ledger: reviewLedger }).value).toBe("advisor_review");
    expect(demoReducer({ value: "bootstrapping" }, { type: "AUTHORITATIVE_RELOAD", ledger: ledger("family-review") }).value).toBe("advisor_ready");
    expect(demoReducer({ value: "bootstrapping" }, { type: "AUTHORITATIVE_RELOAD", ledger: ledger("plan-ready") }).value).toBe("advisor_ready");
  });

  it.each(["needs_evidence", "timed_out", "failed", "cancelled", "outdated"] as const)("enters terminal UI for %s", (status) => {
    const state = demoReducer(
      { value: "task_streaming", ledger: activeLedger, taskId: activeLedger.task!.task_id, after: 8 },
      { type: "TASK_REFRESHED", ledger: ledger("terminal-task-failure", status), after: 7 },
    );
    expect(state.value).toBe("terminal_task_failure");
  });

  it("keeps the durable cursor monotonic", () => {
    const state = demoReducer(
      { value: "task_streaming", ledger: activeLedger, taskId: activeLedger.task!.task_id, after: 8 },
      { type: "TASK_REFRESHED", ledger: activeLedger, after: 3 },
    );
    expect(state).toMatchObject({ value: "task_streaming", after: 8 });
  });
});
