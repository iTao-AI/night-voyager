import { expect, it } from "vitest";

import {
  beginPlanExecutionMutation,
  derivePlanExecutionState,
} from "../../lib/plan-execution/reducer";
import { contextFixture, viewFixture } from "./plan-execution-contracts.test";

it("derives every PR A action from fresh server authority", () => {
  expect(derivePlanExecutionState(contextFixture, null).value).toBe("ready_to_start");
  expect(derivePlanExecutionState(contextFixture, viewFixture()).value).toBe("checkpoint_active");
  expect(derivePlanExecutionState(
    { ...contextFixture, active_role: "advisor" },
    viewFixture("awaiting_advisor"),
  ).value).toBe("awaiting_advisor");
  expect(derivePlanExecutionState(contextFixture, viewFixture("blocked")).value).toBe("reassessment_required");
  const completed = viewFixture();
  completed.execution.state = "completed";
  completed.current_checkpoint = null;
  completed.current_action = {
    schema_version: 1,
    code: "execution_completed",
    owner_role: "none",
    checkpoint_id: null,
    execution_version: completed.execution.row_version,
    checkpoint_version: null,
  };
  expect(derivePlanExecutionState(contextFixture, completed).value).toBe("execution_completed");
});

it("carries only the operation and safe prior display state while mutating", () => {
  const prior = derivePlanExecutionState(contextFixture, viewFixture());
  const pending = beginPlanExecutionMutation(prior, "attest");

  expect(pending.value).toBe("mutation_in_flight");
  expect(pending.operation).toBe("attest");
  expect(pending.safeDisplayState).toBe("checkpoint_active");
  expect(pending).not.toHaveProperty("authorityRows");
});
