import type { PlanExecutionRole } from "./contracts";

export type PlanExecutionDemoScenario = "happy" | "blocked";
export type PlanExecutionDemoPrincipal =
  | `plan_execution_happy_${PlanExecutionRole}`
  | `plan_execution_blocked_${PlanExecutionRole}`;
export type PlanExecutionAuthority =
  | { kind: "seeded"; scenario: PlanExecutionDemoScenario }
  | { kind: "connected"; caseId: string };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export function planExecutionPrincipal(
  scenario: PlanExecutionDemoScenario,
  role: PlanExecutionRole,
): PlanExecutionDemoPrincipal {
  return `plan_execution_${scenario}_${role}`;
}

export function seededPlanExecutionAuthority(
  scenario: PlanExecutionDemoScenario,
): PlanExecutionAuthority {
  return { kind: "seeded", scenario };
}

export function connectedPlanExecutionAuthority(caseId: string): PlanExecutionAuthority {
  if (!UUID.test(caseId)) throw new Error("invalid plan execution authority");
  return { kind: "connected", caseId };
}

export function normalizePlanExecutionAuthority(
  value: PlanExecutionAuthority | PlanExecutionDemoScenario = "happy",
): PlanExecutionAuthority {
  if (value === "happy" || value === "blocked") return seededPlanExecutionAuthority(value);
  if (value.kind === "seeded") return seededPlanExecutionAuthority(value.scenario);
  return connectedPlanExecutionAuthority(value.caseId);
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

export function parsePlanExecutionRoute(
  searchParams: Record<string, string | string[] | undefined>,
): PlanExecutionAuthority {
  const keys = Object.keys(searchParams);
  if (keys.some((key) => key !== "scenario" && key !== "case_id")) {
    throw new Error("invalid plan execution route");
  }
  const caseId = searchParams.case_id;
  const scenario = searchParams.scenario;
  if (caseId !== undefined) {
    if (scenario !== undefined || typeof caseId !== "string") {
      throw new Error("invalid plan execution route");
    }
    try {
      return connectedPlanExecutionAuthority(caseId);
    } catch {
      throw new Error("invalid plan execution route");
    }
  }
  if (scenario !== undefined) {
    if (typeof scenario !== "string" || (scenario !== "happy" && scenario !== "blocked")) {
      throw new Error("invalid plan execution route");
    }
    return seededPlanExecutionAuthority(scenario);
  }
  return seededPlanExecutionAuthority("happy");
}
