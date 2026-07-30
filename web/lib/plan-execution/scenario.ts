import type { PlanExecutionRole } from "./contracts";

export type PlanExecutionDemoScenario = "happy" | "blocked";
export type PlanExecutionDemoPrincipal =
  | `plan_execution_happy_${PlanExecutionRole}`
  | `plan_execution_blocked_${PlanExecutionRole}`;

export function planExecutionPrincipal(
  scenario: PlanExecutionDemoScenario,
  role: PlanExecutionRole,
): PlanExecutionDemoPrincipal {
  return `plan_execution_${scenario}_${role}`;
}

export function parsePlanExecutionScenario(
  searchParams: Record<string, string | string[] | undefined>,
): PlanExecutionDemoScenario {
  const keys = Object.keys(searchParams);
  if (keys.some((key) => key !== "scenario")) throw new Error("invalid demo scenario");
  const value = searchParams.scenario;
  if (value === undefined) return "happy";
  if (value === "happy" || value === "blocked") return value;
  throw new Error("invalid demo scenario");
}
