import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { loadRecoveryMetadata, saveRecoveryMetadata } from "../../lib/connected-demo/session-storage";
import { useConnectedDemo } from "../../lib/connected-demo/use-connected-demo";

afterEach(() => {
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

it("fails closed when recovery metadata is missing or inconsistent", () => {
  expect(loadRecoveryMetadata()).toBeNull();
  sessionStorage.setItem("night-voyager:m5", JSON.stringify({ role: "parent" }));
  expect(loadRecoveryMetadata()).toBeNull();
});

it("stores only same-tab display and mutation recovery metadata", () => {
  saveRecoveryMetadata({
    role: "advisor",
    csrf: "csrf",
    caseId: "40000000-0000-0000-0000-000000000002",
    taskId: null,
    briefId: null,
    cursor: 0,
  });
  expect(loadRecoveryMetadata()?.role).toBe("advisor");
  expect(localStorage.length).toBe(0);
});

it("reloads the authoritative parent projection from valid same-tab metadata", async () => {
  saveRecoveryMetadata({
    role: "parent",
    csrf: "csrf",
    caseId: "40000000-0000-0000-0000-000000000002",
    taskId: null,
    briefId: "81000000-0000-0000-0000-000000000301",
    cursor: 0,
  });
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({
    schema_version: 1,
    proof_mode: "synthetic-demo",
    phase: "plan-ready",
    case_id: "40000000-0000-0000-0000-000000000002",
    brief_id: "81000000-0000-0000-0000-000000000301",
    brief_version: 1,
    source_snapshot_date: "2026-07-01",
    family_safe_projection: {
      intake: "2027-02",
      routes: [],
      eligible_route_ids: ["71000000-0000-0000-0000-000000000001"],
      accepted_evidence_risks: [],
      synthetic_proof: true,
    },
    decision_requirements: {
      schema_version: 1,
      eligible_route_id: "71000000-0000-0000-0000-000000000001",
      currency: "CNY",
      pinned_cost_minor: 35_000_000,
      hard_ceiling_minor: 40_000_000,
      required_trade_offs: ["budget_elasticity"],
    },
    receipt: { receipt_id: "83000000-0000-0000-0000-000000000301" },
    timeline: { country: "australia" },
  })));

  const { result } = renderHook(() => useConnectedDemo());

  await waitFor(() => expect(result.current.state.value).toBe("plan_ready"));
});
