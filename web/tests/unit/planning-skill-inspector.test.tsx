import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";

import { PlanningSkillInspector } from "../../components/skill-inspector/PlanningSkillInspector";

const base = {
  schema_version: 1 as const,
  case_id: "41000000-0000-0000-0000-000000000001",
  operation: null,
  active_skill_key: "study-destination-compare" as const,
  active_version: "1.0.0",
  activation_sequence: 1,
  evaluator_id: "night-voyager.deterministic-skill-evaluator" as const,
  evaluator_version: "v1" as const,
  evaluation_dataset_id: "night-voyager.study-destination-compare.eval",
  evaluation_dataset_version: "1.0.0",
  task_request_sha256_prefix: null,
  version_content_sha256_prefix: "111111111111",
  runtime_binding_sha256_prefix: "abcdef123456",
  adapter_id: null,
  adapter_version: null,
  pin_status: "not_created" as const,
};

afterEach(cleanup);

it("renders the no-task collaboration projection in a collapsed disclosure", () => {
  const { container } = render(<PlanningSkillInspector inspector={base} />);
  const disclosure = screen.getByText("Planning Skill inspector").closest("details");
  expect(disclosure).not.toHaveAttribute("open");
  expect(screen.getByText("No planning task created")).toBeVisible();
  expect(container).not.toHaveTextContent(/41000000|schema_version|skill_definition_id|runtime_binding_sha256/i);
  expect(screen.queryByRole("button")).toBeNull();
});

it("renders matched task-time execution identity with bounded prefixes", () => {
  render(<PlanningSkillInspector inspector={{ ...base, operation: "generate_planning_run_v1", task_request_sha256_prefix: "222222222222", adapter_id: "deterministic_planning", adapter_version: "m4a-v1", pin_status: "matched" }} />);
  expect(screen.getByText("Pinned execution matched")).toBeVisible();
  fireEvent.click(screen.getByText("Planning Skill inspector"));
  expect(screen.getByText("deterministic_planning@m4a-v1")).toBeVisible();
  expect(screen.getByText("222222222222")).toBeVisible();
  expect(screen.queryByText(/2222222222222222/)).toBeNull();
});

it("labels legacy history without claiming a current runtime match", () => {
  render(<PlanningSkillInspector inspector={{ ...base, operation: "generate_planning_run_v1", task_request_sha256_prefix: "222222222222", pin_status: "legacy_unpinned" }} />);
  expect(screen.getByText("Legacy task without runtime pin")).toBeVisible();
  fireEvent.click(screen.getByText("Planning Skill inspector"));
  expect(screen.getByText("No recorded leaf adapter")).toBeVisible();
});
