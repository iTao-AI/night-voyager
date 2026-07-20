import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

const hook = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));
vi.mock("../../lib/connected-demo/use-connected-demo", () => ({ useConnectedDemo: () => hook.value }));

import { ConnectedDemo } from "../../components/connected-demo/ConnectedDemo";

const inspector = {
  schema_version: 1 as const,
  case_id: "40000000-0000-0000-0000-000000000002",
  operation: "generate_planning_run_v1" as const,
  active_skill_key: "study-destination-compare",
  active_version: "1.0.0",
  activation_sequence: 1,
  evaluator_id: "night-voyager.deterministic-skill-evaluator",
  evaluator_version: "v1",
  evaluation_dataset_id: "night-voyager.study-destination-compare.eval",
  evaluation_dataset_version: "1.0.0",
  task_request_sha256_prefix: "222222222222",
  version_content_sha256_prefix: "111111111111",
  runtime_binding_sha256_prefix: "abcdef123456",
  adapter_id: "deterministic_planning",
  adapter_version: "m4a-v1",
  pin_status: "matched" as const,
};

function demo(state: Record<string, unknown>) {
  return { state, inspector, journeyConflict: null, confirmed: false, setConfirmed: vi.fn(), endConflictingJourney: vi.fn(), connectAdvisor: vi.fn(), recover: vi.fn(), retry: vi.fn(), createTask: vi.fn(), approve: vi.fn(), rotateToParent: vi.fn(), decide: vi.fn() };
}

afterEach(cleanup);

it("hides stale advisor inspector data in recoverable error", () => {
  hook.value = demo({ value: "recoverable_error", code: "transport_failure" });
  render(<ConnectedDemo />);
  expect(screen.queryByText("Planning Skill inspector")).toBeNull();
});
