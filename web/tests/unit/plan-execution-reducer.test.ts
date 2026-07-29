import { expect, it } from "vitest";

import { derivePlanExecutionState } from "../../lib/plan-execution/reducer";
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
  expect(derivePlanExecutionState(contextFixture, completed).value).toBe("execution_completed");
});
