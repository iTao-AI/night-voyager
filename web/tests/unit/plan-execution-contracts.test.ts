import { expect, it } from "vitest";

import {
  parsePlanExecutionContext,
  parseTimelineExecutionView,
  type TimelineExecutionView,
} from "../../lib/plan-execution/contracts";

const id = (value: number) =>
  `10000000-0000-0000-0000-${value.toString().padStart(12, "0")}`;
const EXECUTION_ID = id(1);
const CASE_ID = id(2);
const CHECKPOINT_IDS = [id(3), id(4), id(5), id(6)] as const;
const AT = "2026-07-29T00:00:00Z";
type ExpectedTimelineExecutionView = TimelineExecutionView & {
  current_action: {
    schema_version: 1;
    code:
      | "checkpoint_attestation_required"
      | "advisor_verification_required"
      | "execution_completed"
      | "reassessment_handoff_required";
    owner_role: "advisor" | "student" | "parent" | "none";
    checkpoint_id: string | null;
    execution_version: number;
    checkpoint_version: number | null;
  };
};

export const contextFixture = {
  schema_version: 1,
  scenario: "governed-plan-execution-v1",
  case_id: CASE_ID,
  case_revision: 1,
  decision_id: id(7),
  decision_receipt_id: id(8),
  timeline_plan_id: id(9),
  execution_id: null,
  active_role: "student",
  assignment_status: "assigned",
} as const;

export function viewFixture(
  checkpointState: "in_progress" | "awaiting_advisor" | "blocked" = "in_progress",
): ExpectedTimelineExecutionView {
  const checkpoints = ([
    ["documents", "student", "2026-09-01"],
    ["application", "student", "2026-10-15"],
    ["visa", "student", "2026-12-15"],
    ["arrival", "parent", "2027-01-20"],
  ] as const).map(([milestone_key, accountable_role, due_date], index) => ({
    schema_version: 1 as const,
    checkpoint_id: CHECKPOINT_IDS[index],
    execution_id: EXECUTION_ID,
    ordinal: index + 1,
    milestone_key,
    due_date,
    accountable_role,
    state: index === 0 ? checkpointState : "pending" as const,
    risk_state: "on_track" as const,
    row_version: 1,
    created_at: AT,
    updated_at: AT,
  }));
  const current = checkpoints[0];
  return {
    schema_version: 1,
    execution: {
      schema_version: 1, execution_id: EXECUTION_ID, case_id: CASE_ID, case_revision: 1,
      decision_id: id(7), decision_receipt_id: id(8), timeline_plan_id: id(9),
      state: "active",
      row_version: 1, created_at: AT, updated_at: AT,
    },
    checkpoints,
    current_checkpoint: current,
    latest_attestation: checkpointState === "awaiting_advisor" ? {
      schema_version: 1, attestation_id: id(10), execution_id: EXECUTION_ID,
      checkpoint_id: current.checkpoint_id, reporter_actor_id: id(11),
      reporter_role: "student", attestation_kind: "completion",
      status_code: "ready_for_advisor", attestation_code: "documents_status_confirmed",
      reason_code: "not_applicable", observed_execution_version: 1,
      observed_checkpoint_version: 1, created_at: AT,
    } : null,
    latest_verification: null,
    reassessment: null,
    current_action: {
      schema_version: 1,
      code: checkpointState === "awaiting_advisor"
        ? "advisor_verification_required"
        : checkpointState === "blocked"
          ? "reassessment_handoff_required"
          : "checkpoint_attestation_required",
      owner_role: checkpointState === "in_progress" ? "student" : "advisor",
      checkpoint_id: current.checkpoint_id,
      execution_version: 1,
      checkpoint_version: 1,
    },
    observed_date: "2026-07-29",
    activity: [],
    activity_total: 0,
    activity_truncated: false,
  } as ExpectedTimelineExecutionView;
}

it("strictly parses the server-owned context and execution projection", () => {
  expect(parsePlanExecutionContext(contextFixture)).toEqual(contextFixture);
  expect(parseTimelineExecutionView(viewFixture())).toEqual(viewFixture());
  expect(() => parsePlanExecutionContext({ ...contextFixture, csrf_token: "secret" })).toThrow();
  expect(() => parseTimelineExecutionView({ ...viewFixture(), as_of: "2026-01-01" })).toThrow();
});

it("accepts independently projected latest records from different checkpoints", () => {
  const view = viewFixture();
  view.checkpoints[0] = {
    ...view.checkpoints[0],
    state: "verified",
    row_version: 3,
  };
  view.checkpoints[1] = {
    ...view.checkpoints[1],
    state: "awaiting_advisor",
    row_version: 2,
  };
  view.current_checkpoint = view.checkpoints[1];
  view.latest_attestation = {
    schema_version: 1,
    attestation_id: id(14),
    execution_id: EXECUTION_ID,
    checkpoint_id: CHECKPOINT_IDS[1],
    reporter_actor_id: id(11),
    reporter_role: "student",
    attestation_kind: "completion",
    status_code: "ready_for_advisor",
    attestation_code: "application_status_confirmed",
    reason_code: "not_applicable",
    observed_execution_version: 2,
    observed_checkpoint_version: 1,
    created_at: "2026-07-29T02:00:00Z",
  };
  view.latest_verification = {
    schema_version: 1,
    verification_id: id(12),
    execution_id: EXECUTION_ID,
    checkpoint_id: CHECKPOINT_IDS[0],
    attestation_id: id(10),
    advisor_actor_id: id(13),
    action: "verify",
    reason_code: "attestation_verified",
    observed_execution_version: 1,
    observed_checkpoint_version: 2,
    created_at: "2026-07-29T01:00:00Z",
  };
  view.current_action = {
    schema_version: 1,
    code: "advisor_verification_required",
    owner_role: "advisor",
    checkpoint_id: CHECKPOINT_IDS[1],
    execution_version: 1,
    checkpoint_version: 2,
  };

  expect(parseTimelineExecutionView(view)).toEqual(view);

  const foreignExecution = structuredClone(view);
  foreignExecution.latest_verification!.execution_id = id(99);
  expect(() => parseTimelineExecutionView(foreignExecution)).toThrow();

  const foreignCheckpoint = structuredClone(view);
  foreignCheckpoint.latest_verification!.checkpoint_id = id(99);
  expect(() => parseTimelineExecutionView(foreignCheckpoint)).toThrow();
});

it("binds every reassessment predecessor identity to the enclosing execution", () => {
  const view = viewFixture("blocked");
  view.execution.state = "reassessment_required";
  view.reassessment = {
    schema_version: 1,
    reassessment_id: id(20),
    execution_id: EXECUTION_ID,
    checkpoint_id: CHECKPOINT_IDS[0],
    advisor_actor_id: id(21),
    trigger: "deadline_elapsed",
    trigger_reference_id: null,
    accepted_database_date: "2026-07-29",
    accepted_trigger_projection_sha256: "a".repeat(64),
    handoff_schema_version: 1,
    predecessor_case_id: CASE_ID,
    predecessor_case_revision: 1,
    predecessor_decision_id: id(7),
    predecessor_decision_receipt_id: id(8),
    predecessor_timeline_plan_id: id(9),
    predecessor_execution_id: EXECUTION_ID,
    predecessor_checkpoint_id: CHECKPOINT_IDS[0],
    owner_role: "advisor",
    successor_status: "pending_future_authorization",
    created_at: AT,
  };
  expect(parseTimelineExecutionView(view)).toEqual(view);

  for (const field of [
    "predecessor_case_id",
    "predecessor_decision_id",
    "predecessor_decision_receipt_id",
    "predecessor_timeline_plan_id",
  ] as const) {
    const invalid = structuredClone(view);
    invalid.reassessment![field] = id(99);
    expect(() => parseTimelineExecutionView(invalid)).toThrow();
  }
  const invalidRevision = structuredClone(view);
  invalidRevision.reassessment!.predecessor_case_revision = 2;
  expect(() => parseTimelineExecutionView(invalidRevision)).toThrow();
});

it("rejects non-canonical checkpoint graphs and contradictory current action", () => {
  const duplicate = viewFixture();
  duplicate.checkpoints[1] = {
    ...duplicate.checkpoints[1],
    ordinal: 1,
    milestone_key: "documents",
  };
  expect(() => parseTimelineExecutionView(duplicate)).toThrow();

  const wrongExecution = viewFixture();
  wrongExecution.checkpoints[2] = {
    ...wrongExecution.checkpoints[2],
    execution_id: id(99),
  };
  expect(() => parseTimelineExecutionView(wrongExecution)).toThrow();

  const wrongCurrent = viewFixture();
  wrongCurrent.current_checkpoint = wrongCurrent.checkpoints[1];
  expect(() => parseTimelineExecutionView(wrongCurrent)).toThrow();

  const wrongAction = viewFixture();
  wrongAction.current_action = {
    ...wrongAction.current_action,
    code: "advisor_verification_required",
    owner_role: "advisor",
  };
  expect(() => parseTimelineExecutionView(wrongAction)).toThrow();
});

it("rejects unbound latest records and invalid bounded activity semantics", () => {
  const unboundAttestation = viewFixture("awaiting_advisor");
  unboundAttestation.latest_attestation = {
    ...unboundAttestation.latest_attestation!,
    checkpoint_id: id(99),
  };
  expect(() => parseTimelineExecutionView(unboundAttestation)).toThrow();

  const unboundVerification = viewFixture("awaiting_advisor");
  unboundVerification.latest_verification = {
    schema_version: 1,
    verification_id: id(12),
    execution_id: EXECUTION_ID,
    checkpoint_id: id(99),
    attestation_id: unboundVerification.latest_attestation!.attestation_id,
    advisor_actor_id: id(13),
    action: "verify",
    reason_code: "attestation_verified",
    observed_execution_version: 1,
    observed_checkpoint_version: 1,
    created_at: AT,
  };
  expect(() => parseTimelineExecutionView(unboundVerification)).toThrow();

  const tooMany = viewFixture();
  tooMany.activity = Array.from({ length: 65 }, (_, index) => ({
    schema_version: 1 as const,
    kind: "mutation_receipt_recorded" as const,
    durable_id: id(100 + index),
    execution_id: EXECUTION_ID,
    checkpoint_id: null,
    created_at: `2026-07-29T00:${String(index % 60).padStart(2, "0")}:00Z`,
  })).reverse();
  tooMany.activity_total = 65;
  expect(() => parseTimelineExecutionView(tooMany)).toThrow();

  const wrongOrder = viewFixture();
  wrongOrder.activity = [
    {
      schema_version: 1,
      kind: "mutation_receipt_recorded",
      durable_id: id(200),
      execution_id: EXECUTION_ID,
      checkpoint_id: null,
      created_at: "2026-07-29T00:00:00Z",
    },
    {
      schema_version: 1,
      kind: "mutation_receipt_recorded",
      durable_id: id(201),
      execution_id: EXECUTION_ID,
      checkpoint_id: null,
      created_at: "2026-07-29T01:00:00Z",
    },
  ];
  wrongOrder.activity_total = 2;
  expect(() => parseTimelineExecutionView(wrongOrder)).toThrow();
});
