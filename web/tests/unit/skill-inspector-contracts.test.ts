import { expect, it } from "vitest";

import { parsePlanningSkillInspector } from "../../lib/skill-inspector/contracts";

const ID = "40000000-0000-0000-0000-000000000031";
const base = {
  schema_version: 1,
  case_id: ID,
  operation: null,
  active_skill_key: "study-destination-compare",
  active_version: "1.0.0",
  activation_sequence: 1,
  evaluator_id: "night-voyager.deterministic-skill-evaluator",
  evaluator_version: "v1",
  evaluation_dataset_id: "night-voyager.study-destination-compare.eval",
  evaluation_dataset_version: "1.0.0",
  task_request_sha256_prefix: null,
  version_content_sha256_prefix: "111111111111",
  runtime_binding_sha256_prefix: "abcdef123456",
  adapter_id: null,
  adapter_version: null,
  pin_status: "not_created",
};

it("accepts all three exact planning inspector states", () => {
  expect(parsePlanningSkillInspector(base)).toEqual(base);
  expect(parsePlanningSkillInspector({ ...base, operation: "generate_planning_run_v1", task_request_sha256_prefix: "222222222222", adapter_id: "deterministic_planning", adapter_version: "m4a-v1", pin_status: "matched" })).toMatchObject({ pin_status: "matched" });
  expect(parsePlanningSkillInspector({ ...base, operation: "generate_planning_run_v1", task_request_sha256_prefix: "222222222222", pin_status: "legacy_unpinned" })).toMatchObject({ pin_status: "legacy_unpinned" });
});

it.each([
  ["unknown pin status", { ...base, pin_status: "active" }],
  ["raw full digest", { ...base, version_content_sha256_prefix: "a".repeat(64) }],
  ["raw contract payload", { ...base, evaluator_payload: { passed: true } }],
  ["task data on not-created state", { ...base, operation: "generate_planning_run_v1" }],
  ["missing matched adapter", { ...base, operation: "generate_planning_run_v1", task_request_sha256_prefix: "222222222222", pin_status: "matched" }],
  ["wrong leaf adapter", { ...base, operation: "generate_planning_run_v1", task_request_sha256_prefix: "222222222222", adapter_id: "governed_mixed_planning", adapter_version: "dra-mixed-v1", pin_status: "matched" }],
])("rejects %s", (_name, value) => {
  expect(() => parsePlanningSkillInspector(value)).toThrow("invalid response");
});
