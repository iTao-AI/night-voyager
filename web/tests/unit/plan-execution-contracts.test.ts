import { expect, it } from "vitest";

import {
  parsePlanExecutionContext,
  parseTimelineExecutionView,
  type TimelineExecutionView,
} from "../../lib/plan-execution/contracts";

const ID = "10000000-0000-0000-0000-000000000001";
const AT = "2026-07-29T00:00:00Z";

export const contextFixture = {
  schema_version: 1,
  scenario: "governed-plan-execution-v1",
  case_id: ID,
  case_revision: 1,
  decision_id: ID,
  decision_receipt_id: ID,
  timeline_plan_id: ID,
  execution_id: null,
  active_role: "student",
  assignment_status: "assigned",
} as const;

export function viewFixture(
  checkpointState: "in_progress" | "awaiting_advisor" | "blocked" = "in_progress",
): TimelineExecutionView {
  return {
    schema_version: 1,
    execution: {
      schema_version: 1, execution_id: ID, case_id: ID, case_revision: 1,
      decision_id: ID, decision_receipt_id: ID, timeline_plan_id: ID,
      state: checkpointState === "blocked" ? "reassessment_required" : "active",
      row_version: 1, created_at: AT, updated_at: AT,
    },
    checkpoints: [{
      schema_version: 1, checkpoint_id: ID, execution_id: ID, ordinal: 1,
      milestone_key: "documents", due_date: "2026-09-01",
      accountable_role: "student", state: checkpointState,
      risk_state: "on_track", row_version: 1, created_at: AT, updated_at: AT,
    }],
    current_checkpoint: {
      schema_version: 1, checkpoint_id: ID, execution_id: ID, ordinal: 1,
      milestone_key: "documents", due_date: "2026-09-01",
      accountable_role: "student", state: checkpointState,
      risk_state: "on_track", row_version: 1, created_at: AT, updated_at: AT,
    },
    latest_attestation: checkpointState === "awaiting_advisor" ? {
      schema_version: 1, attestation_id: ID, execution_id: ID, checkpoint_id: ID,
      reporter_actor_id: ID, reporter_role: "student", attestation_kind: "completion",
      status_code: "ready_for_advisor", attestation_code: "documents_status_confirmed",
      reason_code: "not_applicable", observed_execution_version: 1,
      observed_checkpoint_version: 1, created_at: AT,
    } : null,
    latest_verification: null,
    reassessment: null,
    observed_date: "2026-07-29",
    activity: [],
    activity_total: 0,
    activity_truncated: false,
  };
}

it("strictly parses the server-owned context and execution projection", () => {
  expect(parsePlanExecutionContext(contextFixture)).toEqual(contextFixture);
  expect(parseTimelineExecutionView(viewFixture())).toEqual(viewFixture());
  expect(() => parsePlanExecutionContext({ ...contextFixture, csrf_token: "secret" })).toThrow();
  expect(() => parseTimelineExecutionView({ ...viewFixture(), as_of: "2026-01-01" })).toThrow();
});
