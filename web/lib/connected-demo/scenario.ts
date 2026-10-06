import type { DemoJourneyEnvelope } from "./session-storage";

export type ConnectedDemoScenario = "default" | "intake-delay";
export const INTAKE_REVISION_CASE_ID = "49000000-0000-0000-0000-000000000003";
export function parseConnectedDemoScenario(value: string | string[] | undefined): ConnectedDemoScenario {
  if (value === undefined) return "default";
  if (value === "intake-delay") return value;
  throw new Error("invalid demo scenario");
}
export function initialDemoCaseId(scenario: ConnectedDemoScenario): string {
  return scenario === "intake-delay" ? INTAKE_REVISION_CASE_ID : "40000000-0000-0000-0000-000000000002";
}
export function connectedEntryConflict(scenario: ConnectedDemoScenario, existing: DemoJourneyEnvelope | null): "advisor-family" | "collaboration" | null {
  if (existing?.journey === "collaboration") return "collaboration";
  if (scenario === "intake-delay" && existing && existing.caseId !== INTAKE_REVISION_CASE_ID) return "advisor-family";
  return null;
}
