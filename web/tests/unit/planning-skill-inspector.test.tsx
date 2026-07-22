import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";

import { PlanningSkillInspector } from "../../components/skill-inspector/PlanningSkillInspector";
import { PresentationProvider } from "../../lib/presentation/context";

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

afterEach(() => { cleanup(); localStorage.clear(); });

it("renders no-task Skill proof in a collapsed localized disclosure", () => {
  const { container } = render(<PlanningSkillInspector inspector={base} />, { wrapper: PresentationProvider });
  expect(screen.getByText("尚未创建 Skill pin")).toBeVisible();
  expect(screen.getByText("规划 Skill 检查器").closest("details")).not.toHaveAttribute("open");
  expect(container).not.toHaveTextContent(/41000000|schema_version|skill_definition_id|runtime_binding_sha256/i);
  expect(screen.queryByRole("button")).toBeNull();
});

it("preserves canonical operation, Skill, version, adapter, and digest identities", () => {
  render(<PlanningSkillInspector inspector={{ ...base, operation: "generate_planning_run_v1", task_request_sha256_prefix: "222222222222", adapter_id: "deterministic_planning", adapter_version: "m4a-v1", pin_status: "matched" }} />, { wrapper: PresentationProvider });
  expect(screen.getByText("运行时 Skill pin 已匹配")).toBeVisible();
  fireEvent.click(screen.getByText("规划 Skill 检查器"));
  for (const identity of ["generate_planning_run_v1", "study-destination-compare@1.0.0", "deterministic_planning@m4a-v1", "222222222222", "111111111111", "abcdef123456"]) {
    expect(screen.getByText(identity)).toBeVisible();
  }
  expect(screen.queryByText(/2222222222222222/)).toBeNull();
});

it("labels legacy proof without claiming a current runtime match", () => {
  render(<PlanningSkillInspector inspector={{ ...base, operation: "generate_planning_run_v1", task_request_sha256_prefix: "222222222222", pin_status: "legacy_unpinned" }} />, { wrapper: PresentationProvider });
  expect(screen.getByText("旧任务没有 Skill pin")).toBeVisible();
  fireEvent.click(screen.getByText("规划 Skill 检查器"));
  expect(screen.getByText("未记录 leaf adapter")).toBeVisible();
});

it("localizes labels in English without changing proof identities", async () => {
  localStorage.setItem("night-voyager:presentation-locale:v1", "en");
  render(<PlanningSkillInspector inspector={{ ...base, operation: "generate_planning_run_v1", task_request_sha256_prefix: "222222222222", adapter_id: "deterministic_planning", adapter_version: "m4a-v1", pin_status: "matched" }} />, { wrapper: PresentationProvider });
  await waitFor(() => expect(screen.getByText("Runtime Skill pin matched")).toBeVisible());
  fireEvent.click(screen.getByText("Planning Skill inspector"));
  expect(screen.getByText("generate_planning_run_v1")).toBeVisible();
  expect(screen.getByText("deterministic_planning@m4a-v1")).toBeVisible();
});
