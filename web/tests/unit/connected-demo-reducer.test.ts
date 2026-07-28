import { describe, expect, it } from "vitest";

import { demoReducer, type DemoDisplayState } from "../../lib/connected-demo/reducer";
import { TASK_ID, brief, ledger, status } from "./connected-demo-test-data";

describe("connected demo reducer", () => {
  it.each([
    ["task_ready", "advisor_ready"],
    ["active_task", "task_streaming"],
    ["review_required", "advisor_review"],
    ["revision_requested", "revision_requested"],
    ["revision_fact_pending", "revision_fact_pending"],
    ["replan_required", "replan_required"],
    ["revision_task_active", "task_streaming"],
    ["revision_review_required", "advisor_review"],
    ["revision_blocked", "revision_blocked"],
    ["family_review", "family_review"],
    ["plan_ready", "plan_ready"],
    ["terminal_task_failure", "terminal_task_failure"],
  ] as const)("reconstructs authoritative %s as %s", (phase, expected) => {
    const event = phase === "revision_requested"
      ? { type: "STATUS_RELOADED" as const, status: status(phase) }
      : phase === "family_review" || phase === "plan_ready"
        ? { type: "STATUS_RELOADED" as const, status: status(phase), brief: brief(phase) }
        : { type: "STATUS_RELOADED" as const, status: status(phase), ledger: ledger(phase, phase === "terminal_task_failure" ? "failed" : "preparing") };
    expect(demoReducer({ value: "bootstrapping" }, event).value).toBe(expected);
  });

  it("fails closed when status role, revision, phase, or detail identity differs", () => {
    const review = ledger("review_required");
    const authoritative = status("review_required");
    for (const event of [
      { type: "STATUS_RELOADED" as const, status: { ...authoritative, active_role: "student" as const }, ledger: review },
      { type: "STATUS_RELOADED" as const, status: { ...authoritative, current_revision: 2 }, ledger: review },
      { type: "STATUS_RELOADED" as const, status: { ...authoritative, phase: "replan_required" as const }, ledger: review },
      { type: "STATUS_RELOADED" as const, status: authoritative, brief: brief("family_review") },
    ]) {
      expect(demoReducer({ value: "bootstrapping" }, event)).toEqual({
        value: "recoverable_error",
        code: "invalid_transition",
      });
    }
  });

  it("allows task creation only from task-ready or replan-required", () => {
    for (const phase of ["task_ready", "replan_required"] as const) {
      const ready = demoReducer(
        { value: "bootstrapping" },
        { type: "STATUS_RELOADED", status: status(phase), ledger: ledger(phase) },
      );
      expect(demoReducer(ready, { type: "CREATE_TASK" }).value).toBe("task_creating");
    }
    const review = demoReducer(
      { value: "bootstrapping" },
      { type: "STATUS_RELOADED", status: status("review_required"), ledger: ledger("review_required") },
    );
    expect(demoReducer(review, { type: "CREATE_TASK" })).toEqual({
      value: "recoverable_error",
      code: "invalid_transition",
    });
  });

  it("ignores stale old-task events and keeps the cursor monotonic", () => {
    const activeStatus = status("active_task");
    const activeLedger = ledger("active_task");
    const state = demoReducer(
      { value: "bootstrapping" },
      { type: "STATUS_RELOADED", status: activeStatus, ledger: activeLedger },
    );
    expect(state.value).toBe("task_streaming");
    if (state.value !== "task_streaming") throw new Error("test setup");
    const oldTask = demoReducer(state, {
      type: "TASK_REFRESHED",
      status: activeStatus,
      ledger: activeLedger,
      taskId: "61000000-0000-0000-0000-000000000099",
      after: 9,
    });
    expect(oldTask).toEqual(state);
    const staleCursor = demoReducer(
      { ...state, after: 8 } satisfies DemoDisplayState,
      { type: "TASK_REFRESHED", status: activeStatus, ledger: activeLedger, taskId: TASK_ID, after: 3 },
    );
    expect(staleCursor).toMatchObject({ value: "task_streaming", after: 8 });
  });

  it("requires a fresh current-revision status before revision approval", () => {
    const revised = ledger("revision_review_required");
    const state = demoReducer(
      { value: "bootstrapping" },
      { type: "STATUS_RELOADED", status: status("revision_review_required"), ledger: revised },
    );
    expect(state.value).toBe("advisor_review");
    expect(demoReducer(state, { type: "REVIEW_SUBMIT" }).value).toBe("review_submitting");
  });

  it("retains a bounded role-rotation target without promoting business authority", () => {
    const state = demoReducer(
      { value: "bootstrapping" },
      { type: "ROLE_SWITCH", caseId: status("revision_requested").case_id, targetRole: "student" },
    );
    expect(state).toMatchObject({
      value: "role_switching",
      targetRole: "student",
      prior: { value: "bootstrapping" },
    });
  });
});
