import { expect, it } from "vitest";

import {
  connectedPlanExecutionAuthority,
  parsePlanExecutionRoute,
  parsePlanExecutionScenario,
  planExecutionPrincipal,
} from "../../lib/plan-execution/scenario";

it("maps only the closed demo scenario and role pairs to server principals", () => {
  expect(planExecutionPrincipal("happy", "advisor")).toBe("plan_execution_happy_advisor");
  expect(planExecutionPrincipal("happy", "student")).toBe("plan_execution_happy_student");
  expect(planExecutionPrincipal("happy", "parent")).toBe("plan_execution_happy_parent");
  expect(planExecutionPrincipal("blocked", "advisor")).toBe("plan_execution_blocked_advisor");
  expect(planExecutionPrincipal("blocked", "student")).toBe("plan_execution_blocked_student");
  expect(planExecutionPrincipal("blocked", "parent")).toBe("plan_execution_blocked_parent");
});

it("defaults absence to happy and rejects unknown, duplicate, and case selectors", () => {
  expect(parsePlanExecutionScenario({})).toBe("happy");
  expect(parsePlanExecutionScenario({ scenario: "blocked" })).toBe("blocked");
  expect(() => parsePlanExecutionScenario({ scenario: "unknown" })).toThrow("invalid demo scenario");
  expect(() => parsePlanExecutionScenario({ scenario: ["happy", "blocked"] })).toThrow(
    "invalid demo scenario",
  );
  expect(() => parsePlanExecutionScenario({ case_id: "4a000000-0000-0000-0000-000000000001" }))
    .toThrow("invalid demo scenario");
});

it("accepts an exclusive canonical connected case route", () => {
  const caseId = "4a000000-0000-0000-0000-000000000001";
  expect(parsePlanExecutionRoute({ case_id: caseId })).toEqual({
    kind: "connected",
    caseId,
  });
  expect(connectedPlanExecutionAuthority(caseId)).toEqual({
    kind: "connected",
    caseId,
  });
  expect(() => parsePlanExecutionRoute({ case_id: caseId, scenario: "happy" }))
    .toThrow("invalid plan execution route");
  expect(() => parsePlanExecutionRoute({ case_id: caseId.toUpperCase() }))
    .toThrow("invalid plan execution route");
  expect(() => parsePlanExecutionRoute({ case_id: [caseId, caseId] }))
    .toThrow("invalid plan execution route");
  expect(() => parsePlanExecutionRoute({ unknown: "value" }))
    .toThrow("invalid plan execution route");
});
