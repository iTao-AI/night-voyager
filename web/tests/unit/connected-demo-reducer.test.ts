import { describe, expect, it } from "vitest";

import { demoReducer, type DemoDisplayState } from "../../lib/connected-demo/reducer";
import type { AdvisorLedger, CurrentDecisionBrief } from "../../lib/connected-demo/contracts";

const ledger = { schema_version: 1, phase: "task-ready", case_id: "case" } as AdvisorLedger;
const reviewLedger = { ...ledger, phase: "review-required" } as AdvisorLedger;
const brief = { schema_version: 1, phase: "family-review", case_id: "case" } as CurrentDecisionBrief;

describe("connected demo reducer", () => {
  it("allows only authoritative walkthrough transitions", () => {
    let state: DemoDisplayState = { value: "bootstrapping" };
    state = demoReducer(state, { type: "ADVISOR_SESSION_READY", ledger });
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
    state = demoReducer(state, { type: "PARENT_SESSION_READY", brief });
    expect(state.value).toBe("family_review");
  });

  it("fails closed on illegal promotion", () => {
    const state = demoReducer({ value: "bootstrapping" }, { type: "PARENT_SESSION_READY", brief });
    expect(state).toEqual({ value: "recoverable_error", code: "invalid_transition" });
  });

  it("keeps review-required monotonic across duplicate SSE refreshes", () => {
    const state = demoReducer(
      { value: "advisor_review", ledger: reviewLedger },
      { type: "TASK_REFRESHED", ledger: reviewLedger, after: 3 },
    );
    expect(state).toEqual({ value: "advisor_review", ledger: reviewLedger });
  });
});
