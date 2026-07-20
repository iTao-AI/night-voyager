export type PlanningOperation = "generate_planning_run_v1" | "generate_governed_mixed_planning_run_v1";
export type PlanningSkillPinStatus = "not_created" | "matched" | "legacy_unpinned";

export interface PlanningSkillInspector {
  schema_version: 1;
  case_id: string;
  operation: PlanningOperation | null;
  active_skill_key: "study-destination-compare";
  active_version: string;
  activation_sequence: number;
  evaluator_id: "night-voyager.deterministic-skill-evaluator";
  evaluator_version: "v1";
  evaluation_dataset_id: string;
  evaluation_dataset_version: string;
  task_request_sha256_prefix: string | null;
  version_content_sha256_prefix: string;
  runtime_binding_sha256_prefix: string;
  adapter_id: "deterministic_planning" | "governed_mixed_planning" | null;
  adapter_version: "m4a-v1" | "dra-mixed-v1" | null;
  pin_status: PlanningSkillPinStatus;
}

const UUID_CANONICAL = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const SEMVER = /^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)$/;
const DIGEST_PREFIX = /^[0-9a-f]{12}$/;
const CONTRACT = /^[a-z0-9][a-z0-9.-]{0,127}$/;
const KEYS = ["schema_version", "case_id", "operation", "active_skill_key", "active_version", "activation_sequence", "evaluator_id", "evaluator_version", "evaluation_dataset_id", "evaluation_dataset_version", "task_request_sha256_prefix", "version_content_sha256_prefix", "runtime_binding_sha256_prefix", "adapter_id", "adapter_version", "pin_status"] as const;

function invalid(): never { throw new Error("invalid response"); }
function object(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function exact(value: Record<string, unknown>): boolean { const actual = Object.keys(value).sort(); const expected = [...KEYS].sort(); return actual.length === expected.length && actual.every((key, index) => key === expected[index]); }
function digest(value: unknown): value is string { return typeof value === "string" && DIGEST_PREFIX.test(value); }

export function parsePlanningSkillInspector(value: unknown): PlanningSkillInspector {
  if (!object(value) || !exact(value) || value.schema_version !== 1 || typeof value.case_id !== "string" || !UUID_CANONICAL.test(value.case_id) || !(value.operation === null || value.operation === "generate_planning_run_v1" || value.operation === "generate_governed_mixed_planning_run_v1") || value.active_skill_key !== "study-destination-compare" || typeof value.active_version !== "string" || !SEMVER.test(value.active_version) || !Number.isSafeInteger(value.activation_sequence) || Number(value.activation_sequence) <= 0 || value.evaluator_id !== "night-voyager.deterministic-skill-evaluator" || value.evaluator_version !== "v1" || typeof value.evaluation_dataset_id !== "string" || !CONTRACT.test(value.evaluation_dataset_id) || typeof value.evaluation_dataset_version !== "string" || !SEMVER.test(value.evaluation_dataset_version) || !(value.task_request_sha256_prefix === null || digest(value.task_request_sha256_prefix)) || !digest(value.version_content_sha256_prefix) || !digest(value.runtime_binding_sha256_prefix) || !(value.adapter_id === null || value.adapter_id === "deterministic_planning" || value.adapter_id === "governed_mixed_planning") || !(value.adapter_version === null || value.adapter_version === "m4a-v1" || value.adapter_version === "dra-mixed-v1") || !["not_created", "matched", "legacy_unpinned"].includes(String(value.pin_status))) invalid();
  if ((value.adapter_id === null) !== (value.adapter_version === null)) invalid();
  if (value.pin_status === "not_created" && (value.operation !== null || value.task_request_sha256_prefix !== null || value.adapter_id !== null)) invalid();
  if (value.pin_status !== "not_created" && (value.operation === null || value.task_request_sha256_prefix === null)) invalid();
  if (value.pin_status === "matched" && value.adapter_id === null) invalid();
  if (value.adapter_id !== null) {
    const expected = value.operation === "generate_planning_run_v1" ? ["deterministic_planning", "m4a-v1"] : ["governed_mixed_planning", "dra-mixed-v1"];
    if (value.adapter_id !== expected[0] || value.adapter_version !== expected[1]) invalid();
  }
  return Object.freeze(value as unknown as PlanningSkillInspector);
}
